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
            "index": d.get("last_event_index"),
            "time_raw": d.get("last_event_time_raw"),
            "time_iso": d.get("last_event_time_iso"),
            "priority": d.get("last_event_priority"),
            "trouble": d.get("docsis_trouble"),
            "last_error_index": d.get("last_error_index"),
            "last_error_msg": d.get("last_error_msg"),
            "last_error_time_iso": d.get("last_error_time_iso"),
            "last_error_priority": d.get("last_error_priority"),
            "times": {oid: d.get(oid) for oid in EVENT_TIME_OIDS if d.get(oid)},
            "messages": {oid: d.get(oid) for oid in EVENT_MSG_OIDS if d.get(oid)},
        }
