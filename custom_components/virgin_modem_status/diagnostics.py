"""Virgin Modem Status – Home Assistant custom integration."""
from __future__ import annotations
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coord = hass.data[DOMAIN][entry.entry_id]
    # Redact nothing here; add redaction if needed.
    return {"raw": coord.data}
