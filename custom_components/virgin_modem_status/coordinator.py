# coordinator.py
from __future__ import annotations
import logging
from datetime import timedelta, datetime, timezone
from typing import Dict, Any, Optional

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components import logbook as ha_logbook

from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_HOST, DEFAULT_COMMUNITY, DEFAULT_PORT,
    EVENT_TIME_OIDS, EVENT_MSG_OIDS, EVENT_PRI_OIDS,
    TROUBLE_KEYWORDS, PRIORITY_RULES, DEFAULT_PRIORITY
)

_LOGGER = logging.getLogger(__name__)

class VirginCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, host: str, community: str = DEFAULT_COMMUNITY, port: int = DEFAULT_PORT):
        super().__init__(
            hass, _LOGGER,
            name="Virgin Modem Status",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.host = host or DEFAULT_HOST
        self.community = community or DEFAULT_COMMUNITY
        self.port = port or DEFAULT_PORT

        # Track last announced event/error to avoid spamming logbook
        self._last_event_idx: Optional[int] = None
        self._last_error_idx: Optional[int] = None
        self._last_event_sig: Optional[str] = None   # (idx,msg,time) signature
        self._last_error_sig: Optional[str] = None

    async def _async_update_data(self) -> dict:
        data = await self.hass.async_add_executor_job(self._fetch_snmp_snapshot)

        # Derive latest event (idx/msg/time/priority + trouble)
        derived_event = self._derive_latest_event(data)
        data.update(derived_event)

        # Derive latest *error* (warning/critical), with timestamp/priority
        derived_error = self._derive_latest_error(data)
        data.update(derived_error)

        # Announce to Logbook if changed
        self._maybe_log_event(data)
        self._maybe_log_error(data)

        return data

    # ---------- internals ----------

    def _fetch_snmp_snapshot(self) -> Dict[str, Any]:
        from pysnmp.hlapi import (
            SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity, getCmd
        )

        engine = SnmpEngine()
        auth = CommunityData(self.community, mpModel=1)  # v2c
        target = UdpTransportTarget((self.host, self.port), timeout=1, retries=1)
        ctx = ContextData()

        result: Dict[str, Any] = {}
        oids = EVENT_TIME_OIDS + EVENT_MSG_OIDS + EVENT_PRI_OIDS  # PRI may or may not exist

        for oid in oids:
            try:
                errorIndication, errorStatus, errorIndex, varBinds = next(
                    getCmd(engine, auth, target, ctx, ObjectType(ObjectIdentity(oid)))
                )
                if errorIndication or errorStatus:
                    continue
                for name, val in varBinds:
                    result[str(name)] = str(val)
            except Exception as exc:
                _LOGGER.debug("SNMP get exception for %s: %s", oid, exc)

        return result

    def _derive_latest_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        time_map = {int(oid.rsplit(".", 1)[-1]): data.get(oid) for oid in EVENT_TIME_OIDS if data.get(oid)}
        msg_map  = {int(oid.rsplit(".", 1)[-1]): data.get(oid) for oid in EVENT_MSG_OIDS  if data.get(oid)}
        pri_map  = {int(oid.rsplit(".", 1)[-1]): data.get(oid) for oid in EVENT_PRI_OIDS  if data.get(oid)}

        best_idx: Optional[int] = None
        for idx in sorted(set(time_map) & set(msg_map)):
            if best_idx is None or idx > best_idx:
                best_idx = idx

        last_msg = msg_map.get(best_idx) if best_idx is not None else None
        raw_time = time_map.get(best_idx) if best_idx is not None else None
        pri_raw  = (pri_map.get(best_idx) or "").strip().lower() if best_idx is not None else ""

        # Priority: use modem value if present, else infer from message
        priority = self._normalise_priority(pri_raw) or self._infer_priority(last_msg)

        trouble = False
        if last_msg:
            m = last_msg.lower()
            trouble = any(k in m for k in TROUBLE_KEYWORDS) or priority in ("warning", "critical")

        return {
            "last_event_index": best_idx,
            "last_event_msg": last_msg,
            "last_event_time_raw": raw_time,
            "last_event_time_iso": self._coerce_iso(raw_time),
            "last_event_priority": priority,
            "docsis_trouble": trouble,
        }

    def _derive_latest_error(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Latest entry whose priority is warning/critical (or matches trouble keywords)."""
        time_map = {int(oid.rsplit(".", 1)[-1]): data.get(oid) for oid in EVENT_TIME_OIDS if data.get(oid)}
        msg_map  = {int(oid.rsplit(".", 1)[-1]): data.get(oid) for oid in EVENT_MSG_OIDS  if data.get(oid)}
        pri_map  = {int(oid.rsplit(".", 1)[-1]): data.get(oid) for oid in EVENT_PRI_OIDS  if data.get(oid)}

        latest_err_idx: Optional[int] = None
        latest_err_msg: Optional[str] = None
        latest_err_time: Optional[str] = None
        latest_err_pri: str = DEFAULT_PRIORITY

        for idx in sorted(set(msg_map) & set(time_map)):
            msg = (msg_map.get(idx) or "").strip()
            pri_raw = (pri_map.get(idx) or "").strip().lower()
            pri = self._normalise_priority(pri_raw) or self._infer_priority(msg)
            is_err = pri in ("warning", "critical") or any(k in msg.lower() for k in TROUBLE_KEYWORDS)
            if is_err:
                if latest_err_idx is None or idx > latest_err_idx:
                    latest_err_idx = idx
                    latest_err_msg = msg
                    latest_err_time = time_map.get(idx)
                    latest_err_pri = pri

        return {
            "last_error_index": latest_err_idx,
            "last_error_msg": latest_err_msg,
            "last_error_time_raw": latest_err_time,
            "last_error_time_iso": self._coerce_iso(latest_err_time),
            "last_error_priority": latest_err_pri if latest_err_idx is not None else None,
        }

    def _maybe_log_event(self, data: Dict[str, Any]) -> None:
        idx = data.get("last_event_index")
        msg = (data.get("last_event_msg") or "").strip()
        iso = data.get("last_event_time_iso")
        pri = (data.get("last_event_priority") or DEFAULT_PRIORITY).lower()

        sig = f"{idx}|{msg}|{iso}|{pri}"
        if not msg or sig == self._last_event_sig:
            return
        self._last_event_sig = sig
        self._last_event_idx = idx

        # Fire a domain event (described by logbook.py) and also inject a logbook entry right away
        payload = {"index": idx, "message": msg, "time": iso, "priority": pri}
        self.hass.bus.async_fire(f"{DOMAIN}_event", payload)

        # Also write a logbook entry (so it shows even if logbook.py is missing)
        ha_logbook.async_log_entry(
            self.hass,
            name="Virgin Modem",
            message=f"{pri.upper()}: {msg}",
            domain=DOMAIN,
            when=self._parse_iso(iso) or datetime.now(timezone.utc),
        )

    def _maybe_log_error(self, data: Dict[str, Any]) -> None:
        idx = data.get("last_error_index")
        if idx is None:
            return
        msg = (data.get("last_error_msg") or "").strip()
        iso = data.get("last_error_time_iso")
        pri = (data.get("last_error_priority") or "warning").lower()

        sig = f"{idx}|{msg}|{iso}|{pri}"
        if not msg or sig == self._last_error_sig:
            return
        self._last_error_sig = sig
        self._last_error_idx = idx

        payload = {"index": idx, "message": msg, "time": iso, "priority": pri, "type": "error"}
        self.hass.bus.async_fire(f"{DOMAIN}_error", payload)

        # Emphasise errors in logbook
        ha_logbook.async_log_entry(
            self.hass,
            name="Virgin Modem",
            message=f"{pri.upper()}: {msg}",
            domain=DOMAIN,
            when=self._parse_iso(iso) or datetime.now(timezone.utc),
        )

    @staticmethod
    def _normalise_priority(val: str) -> str:
        v = (val or "").strip().lower()
        if not v:
            return ""
        # Map common modem labels
        if v.startswith("crit"): return "critical"
        if v.startswith("warn"): return "warning"
        if v.startswith("err"):  return "critical"
        if v.startswith("not"):  return "notice"
        return v

    @staticmethod
    def _infer_priority(msg: Optional[str]) -> str:
        if not msg:
            return DEFAULT_PRIORITY
        m = msg.lower()
        for key, pri in PRIORITY_RULES:
            if key in m:
                return pri
        return DEFAULT_PRIORITY

    @staticmethod
    def _coerce_iso(val: Optional[str]) -> Optional[str]:
        if not val:
            return None
        s = str(val).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return None

    @staticmethod
    def _parse_iso(iso: Optional[str]) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(iso) if iso else None
        except Exception:
            return None
