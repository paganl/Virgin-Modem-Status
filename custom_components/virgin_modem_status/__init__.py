# custom_components/virgin_modem_status/__init__.py
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_SCAN_INTERVAL
from .coordinator import VirginModemCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data.get("host", DEFAULT_HOST)
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    coordinator = VirginModemCoordinator(hass, host=host, scan_seconds=scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entities if options (e.g., scan interval) change
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True

async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
