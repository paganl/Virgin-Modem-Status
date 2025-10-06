# custom_components/virgin_modem_status/coordinator.py
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components import logbook as ha_logbook

from .api import VirginApi, VirginApiError
from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    EVENT_TIME_OIDS,
    EVENT_MSG_OIDS,
    TROUBLE_KEYWORDS,
    EVENT_ERROR,
    EVENT_GENERAL,
)

_LOGGER = logging.getLogger(__name__)


class VirginCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinates polling the modem and exposes a normalised snapshot."""

    def __init__(self, hass: HomeAssistant, api: VirginApi, scan_interval: int = DEFAULT_SCAN_INTERVAL) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(seconds=int(scan_interval)),
        )
        self.api = api
        self._last_logged_signature: Optional[str] = None  # to avoid spamming logbook

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch and shape data. Called by HA on every poll."""
        # Expose a transient “scanning” state so sensors can reflect progress
        scanning_payload: Dict[str, Any] = {
            "status": "scanning",
            "last_event_message": None,
            "last_event_time": None,
            "last_event_priority": None,
            "last_event_index": None,
        }

        try:
            raw = await self.api.fetch_snapshot()  # flat OID→value dict (or {})
        except VirginApiError as exc:
            # Let HA mark entities unavailable but keep last good data if present
            raise UpdateFailed(str(exc)) from exc

        # Nothing returned? Keep a minimal payload so sensors don’t crash.
        if not isinstance(raw, dict) or not raw:
            data = scanning_payload | {"status": "empty"}
            return data

        # Work out the latest event index that has BOTH time and message
        latest_idx: Optional[int] = None
        for i in range(1, 999):  # modest upper bound; we only expect up to ~20
            t = raw.get(f"1.3.6.1.2.1.69.1.5.8.1.2.{i}")
            m = raw.get(f"1.3.6.1.2.1.69.1.5.8.1.7.{i}")
            if t or m:
                latest_idx = i
        # If modem numbers “oldest→newest”, latest will be the highest present.
        # If none found, bail gracefully.
        if latest_idx is None:
            data = scanning_payload | {"status": "no_events", "raw": raw}
            return data

        # Pull the latest row’s fields
        last_time = str(raw.get(f"1.3.6.1.2.1.69.1.5.8.1.2.{latest_idx}", "")).strip()
        last_msg  = str(raw.get(f"1.3.6.1.2.1.69.1.5.8.1.7.{latest_idx}", "")).strip()
        # Some firmwares expose priority/level at .5.<i>
        last_pri  = str(raw.get(f"1.3.6.1.2.1.69.1.5.8.1.5.{latest_idx}", "")).strip()

        # Assess severity from priority and known trouble keywords
        is_error = self._looks_bad(last_msg, last_pri)

        # Build your shaped snapshot
        data: Dict[str, Any] = {
            "status": "ok",
            "raw": raw,  # keep for power users / templates
            "last_event_index": latest_idx,
            "last_event_time": last_time or None,
            "last_event_message": last_msg or None,
            "last_event_priority": last_pri or None,
            # Also echo lists (useful for tables)
            "times": {oid: raw.get(oid) for oid in EVENT_TIME_OIDS if oid in raw},
            "messages": {oid: raw.get(oid) for oid in EVENT_MSG_OIDS if oid in raw},
        }

        # Opportunistic Logbook entry for NEW interesting messages
        try:
            self._maybe_log(EVENT_ERROR if is_error else EVENT_GENERAL, data, is_error=is_error)
        except Exception:  # logging must never break polling
            _LOGGER.debug("Logbook emit suppressed due to exception", exc_info=True)

        return data

    # ----------------- helpers -----------------

    def _looks_bad(self, message: str, priority: str) -> bool:
        """Heuristic to flag errors/warnings worth logging distinctly."""
        msg_l = (message or "").lower()
        pri_l = (priority or "").lower()

        # Numeric priorities (higher means worse on some firmwares)
        try:
            pnum = int(pri_l)
            if pnum >= 4:
                return True
        except Exception:
            pass

        # Textual priorities
        if pri_l in {"warning", "warn", "error", "critical", "crit", "alert"}:
            return True

        # Known DOCSIS “bad things”
        return any(k in msg_l for k in TROUBLE_KEYWORDS)

    def _maybe_log(self, event_type: str, data: Dict[str, Any], is_error: bool) -> None:
        """
        Emit a single concise Logbook entry without backdating. HA’s logbook
        API (current cores) does NOT accept `when=` any more.
        We deduplicate by (time + message).
        """
        msg = data.get("last_event_message") or ""
        when_txt = data.get("last_event_time") or ""
        pri = data.get("last_event_priority") or ""

        # Dedup signature
        sig = f"{when_txt}::{msg}"
        if sig and sig == self._last_logged_signature:
            return  # already logged this exact event

        icon = "mdi:alert-circle" if is_error else "mdi:information"
        pretty = msg
        if pri:
            pretty = f"[{str(pri).upper()}] {pretty}"
        if when_txt:
            pretty = f"{pretty} (at {when_txt})"

        ha_logbook.async_log_entry(
            self.hass,
            name="Virgin Modem",
            message=pretty or "Modem event",
            domain=DOMAIN,
            entity_id=None,
            icon=icon,
        )
        self._last_logged_signature = sig
