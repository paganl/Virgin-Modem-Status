# logbook.py
from __future__ import annotations
from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME

from .const import DOMAIN

EVENT_GENERAL = f"{DOMAIN}_event"
EVENT_ERROR   = f"{DOMAIN}_error"

async def async_describe_events(hass, async_describe_event):
    """Describe our custom events for the logbook."""
    def _fmt(payload):
        pri = (payload.get("priority") or "notice").upper()
        msg = payload.get("message") or ""
        t   = payload.get("time") or ""
        return {
            LOGBOOK_ENTRY_NAME: "Virgin Modem",
            LOGBOOK_ENTRY_MESSAGE: f"{pri}: {msg} ({t})",
        }

    async_describe_event(
        DOMAIN,
        EVENT_GENERAL,
        "Virgin Modem event",
        _fmt,
    )
    async_describe_event(
        DOMAIN,
        EVENT_ERROR,
        "Virgin Modem error",
        _fmt,
    )
