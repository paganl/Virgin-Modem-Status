# custom_components/virgin_modem_status/coordinator.py
from __future__ import annotations
import logging
from datetime import timedelta, datetime, timezone
from typing import Dict, Any, Optional

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components import logbook as ha_logbook

from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL,
    EVENT_TIME_OIDS, EVENT_MSG_OIDS, EVENT_PRI_OIDS,
    TROUBLE_KEYWORDS, PRIORITY_RULES, DEFAULT_PRIORITY,
    EVENT_GENERAL, EVENT_ERROR
)
from .api import VirginApi

_LOGGER = logging.getLogger(__name__)

class VirginCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, api: VirginApi, scan_interval_s: int = DEFAULT_SCAN_INTERVAL):
        super().__init__(
            hass,
            _LOGGER,
            name="Virgin Modem Status",
            update_interval=timedelta(seconds=int(scan_interval_s)),
        )
        self.api = api
        self._last_event_sig: Optional[str] = None
        self._last_error_sig: Optional[str] = None

    async def _async_update_data(self) -> dict:
        # 1) Fetch a snapshot from the modem (HTTP or SNMP via api)
        data: Dict[str, Any] = await self.api.fetch_snapshot()

        # 2) Derive latest event (idx/msg/time/priority/trouble)
        data.update(self._derive_latest_event(data))

        # 3) Derive latest *error* (warning/critical)
        data.update(self._derive_latest_error(data))

        # 4) Logbook entries (only on change)
        self._maybe_log(EVENT_GENERAL, data, is_error=False)
        self._maybe_log(EVENT_ERROR,   data, is_error=True)

        return data

    # ---------- derivation helpers ----------

    def _derive_latest_event(self, d: Dict[str, Any]) -> Dict[str, Any]:
        time_map = {int(oid.rsplit(".", 1)[-1]): d.get(oid) for oid in EVENT_TIME_OIDS if d.get(oid)}
        msg_map  = {int(oid.rsplit(".", 1)[-1]): d.get(oid) for oid in EVENT_MSG_OIDS  if d.get(oid)}
        pri_map  = {int(oid.rsplit(".", 1)[-1]): d.get(oid) for oid in EVENT_PRI_OIDS  if d.get(oid)}

        best_idx = max(set(time_map) & set(msg_map)) if (time_map and msg_map) else None
        last_msg = msg_map.get(best_idx) if best_idx is not None else None
        raw_time = time_map.get(best_idx) if best_idx is not None else None
        pri_raw  = (pri_map.get(best_idx) or "").strip().lower() if best_idx is not None else ""
        pri = self._normalise_priority(pri_raw) or self._infer_priority(last_msg)

        trouble = False
        if last_msg:
            m = last_msg.lower()
            trouble = any(k in m for k in TROUBLE_KEYWORDS) or pri in ("warning", "critical")

        return {
            "last_event_index": best_idx,
            "last_event_msg": last_msg,
            "last_event_time_raw": raw_time,
            "last_event_time_iso": self._coerce_iso(raw_time),
            "last_event_priority": pri,
            "docsis_trouble": trouble,
        }

    def _derive_latest_error(self, d: Dict[str, Any]) -> Dict[str, Any]:
        time_map = {int(oid.rsplit(".", 1)[-1]): d.get(oid) for oid in EVENT_TIME_OIDS if d.get(oid)}
        msg_map  = {int(oid.rsplit(".", 1)[-1]): d.get(oid) for oid in EVENT_MSG_OIDS  if d.get(oid)}
        pri_map  = {int(oid.rsplit(".", 1)[-1]): d.get(oid) for oid in EVENT_PRI_OIDS  if d.get(oid)}

        latest_idx: Optional[int] = None
        latest_msg: Optional[str] = None
        latest_time: Optional[str] = None
        latest_pri: str = DEFAULT_PRIORITY

        for idx in sorted(set(time_map) & set(msg_map)):
            msg = (msg_map.get(idx) or "").strip()
            pri = self._normalise_priority((pri_map.get(idx) or "").strip().lower()) or self._infer_priority(msg)
            is_err = pri in ("warning", "critical") or any(k in msg.lower() for k in TROUBLE_KEYWORDS)
            if is_err and (latest_idx is None or idx > latest_idx):
                latest_idx, latest_msg, latest_time, latest_pri = idx, msg, time_map.get(idx), pri

        return {
            "last_error_index": latest_idx,
            "last_error_msg": latest_msg,
            "last_error_time_raw": latest_time,
            "last_error_time_iso": self._coerce_iso(latest_time),
            "last_error_priority": latest_pri if latest_idx is not None else None,
        }

    def _maybe_log(self, event_type: str, d: Dict[str, Any], *, is_error: bool) -> None:
        if is_error:
            idx = d.get("last_error_index"); msg = d.get("last_error_msg")
            iso = d.get("last_error_time_iso"); pri = (d.get("last_error_priority") or "warning").lower()
            sig = f"e|{idx}|{msg}|{iso}|{pri}"
            if not idx or sig == self._last_error_sig: return
            self._last_error_sig = sig
        else:
            idx = d.get("last_event_index"); msg = d.get("last_event_msg")
            iso = d.get("last_event_time_iso"); pri = (d.get("last_event_priority") or DEFAULT_PRIORITY).lower()
            sig = f"v|{idx}|{msg}|{iso}|{pri}"
            if not idx or sig == self._last_event_sig: return
            self._last_event_sig = sig

        payload = {"index": idx, "message": msg, "time": iso, "priority": pri}
        self.hass.bus.async_fire(event_type, payload)
        # also write to Logbook immediately
        when = self._parse_iso(iso) or datetime.now(timezone.utc)
        ha_logbook.async_log_entry(
            self.hass,
            name="Virgin Modem",
            message=f"{pri.upper()}: {msg}",
            domain=DOMAIN,
            when=when,
        )

    @staticmethod
    def _normalise_priority(v: str) -> str:
        if not v: return ""
        v = v.lower()
        if v.startswith("crit") or v.startswith("err"): return "critical"
        if v.startswith("warn"): return "warning"
        if v.startswith("not"):  return "notice"
        return v

    @staticmethod
    def _infer_priority(msg: Optional[str]) -> str:
        if not msg: return DEFAULT_PRIORITY
        m = msg.lower()
        for key, pri in PRIORITY_RULES:
            if key in m:
                return pri
        return DEFAULT_PRIORITY

    @staticmethod
    def _coerce_iso(val: Optional[str]) -> Optional[str]:
        if not val: return None
        s = str(val).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return None

    @staticmethod
    def _parse_iso(iso: Optional[str]) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(iso) if iso else None
        except Exception:
            return None
