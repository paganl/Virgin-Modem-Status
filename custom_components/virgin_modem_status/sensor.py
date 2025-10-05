from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_MSG_OIDS, EVENT_TIME_OIDS
from .coordinator import VirginCoordinator
from .entity import VirginEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coord: VirginCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VirginLastEventSensor(coord, entry)], True)

class VirginLastEventSensor(VirginEntity, SensorEntity):
    _attr_name = "Last DOCSIS Event"

    def __init__(self, coordinator: VirginCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_event"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        msgs = [data.get(oid) for oid in EVENT_MSG_OIDS if data.get(oid)]
        return msgs[-1] if msgs else None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "times": {oid: data.get(oid) for oid in EVENT_TIME_OIDS if data.get(oid)},
            "messages": {oid: data.get(oid) for oid in EVENT_MSG_OIDS if data.get(oid)},
        }
