# custom_components/virgin_modem_status/sensor.py
from __future__ import annotations

from typing import Any, Dict

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_MSG_OIDS, EVENT_TIME_OIDS
from .coordinator import VirginModemCoordinator  # <- make sure this matches your actual class name

def _get_coordinator(container: Any) -> VirginModemCoordinator:
    """Support both hass.data[DOMAIN][entry_id] and hass.data[DOMAIN][entry_id]['coordinator']."""
    return container.get("coordinator", container)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    container = hass.data[DOMAIN][entry.entry_id]
    coordinator: VirginModemCoordinator = _get_coordinator(container)

    async_add_entities(
        [
            VirginLastEventSensor(coordinator, entry),
        ],
        update_before_add=True,
    )

class VirginBaseEntity(CoordinatorEntity[Dict[str, Any]]):
    """Common bits for all entities."""

    def __init__(self, coordinator: VirginModemCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Virgin Media (unofficial)",
            name="Virgin Modem",
        )

class VirginLastEventSensor(VirginBaseEntity, SensorEntity):
    """Single sensor that surfaces the latest DOCSIS event message."""

    _attr_name = "Last DOCSIS Event"
    _attr_unique_id: str

    def __init__(self, coordinator: VirginModemCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_event"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data or {}
        # Keep only non-empty messages, preserving API order; take the newest (last)
        msgs = [data.get(oid) for oid in EVENT_MSG_OIDS if data.get(oid)]
        return msgs[-1] if msgs else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "times": {oid: data.get(oid) for oid in EVENT_TIME_OIDS if data.get(oid)},
            "messages": {oid: data.get(oid) for oid in EVENT_MSG_OIDS if data.get(oid)},
        }
