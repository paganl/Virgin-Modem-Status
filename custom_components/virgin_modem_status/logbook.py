# custom_components/virgin_modem_status/logbook.py
from __future__ import annotations
import inspect
from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from .const import DOMAIN, EVENT_GENERAL, EVENT_ERROR

def async_describe_events(hass, async_describe_event):
    """Register Virgin Modem events for the Logbook (HA-version compatible)."""

    def _fmt(payload):
        # HA may pass the event dict or just the payload; support both.
        data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
        pri = (data.get("priority") or "notice").upper() if isinstance(data, dict) else "NOTICE"
        msg = (data.get("message") or "") if isinstance(data, dict) else ""
        t   = (data.get("time") or "") if isinstance(data, dict) else ""
        return {
            LOGBOOK_ENTRY_NAME: "Virgin Modem",
            LOGBOOK_ENTRY_MESSAGE: f"{pri}: {msg} ({t})",
        }

    # Detect whether HA expects (domain, event, formatter) or (domain, event, description, formatter)
    try:
        arity = len(inspect.signature(async_describe_event).parameters)
    except Exception:
        arity = 3  # safe default

    if arity >= 4:
        # Older API: include description string
        async_describe_event(DOMAIN, EVENT_GENERAL, "Virgin Modem event", _fmt)
        async_describe_event(DOMAIN, EVENT_ERROR,   "Virgin Modem error", _fmt)
    else:
        # Newer API: no description parameter
        async_describe_event(DOMAIN, EVENT_GENERAL, _fmt)
        async_describe_event(DOMAIN, EVENT_ERROR,   _fmt)
