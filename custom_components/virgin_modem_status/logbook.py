# custom_components/virgin_modem_status/logbook.py
from __future__ import annotations

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from .const import DOMAIN, EVENT_GENERAL, EVENT_ERROR


def async_describe_events(hass, async_describe_event):
    """Register Virgin Modem events for the Logbook (HA-version compatible)."""

    def _fmt(event):
        # HA passes the whole event; payload lives under event["data"]
        data = {}
        if isinstance(event, dict):
            data = event.get("data") or {}
            # Some call sites may already pass the payload; handle that too
            if not data and ("message" in event or "time" in event or "priority" in event):
                data = event

        pri = str(data.get("priority", "")).strip().upper() or "NOTICE"
        msg = str(data.get("message", "")).strip()
        t   = str(data.get("time", "")).strip()

        parts = []
        if pri:
            parts.append(pri + ":")
        if msg:
            parts.append(msg)
        if t:
            parts.append(f"({t})")

        return {
            LOGBOOK_ENTRY_NAME: "Virgin Modem",
            LOGBOOK_ENTRY_MESSAGE: " ".join(parts) if parts else "Event",
        }

    # Prefer the modern 3-argument form. If HA is older, fall back to the 4-argument form.
    try:
        async_describe_event(DOMAIN, EVENT_GENERAL, _fmt)
        async_describe_event(DOMAIN, EVENT_ERROR, _fmt)
    except TypeError:
        async_describe_event(DOMAIN, EVENT_GENERAL, "Virgin Modem event", _fmt)
        async_describe_event(DOMAIN, EVENT_ERROR, "Virgin Modem error", _fmt)
