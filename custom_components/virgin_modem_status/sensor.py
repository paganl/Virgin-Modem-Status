from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, EVENT_MSG_OIDS, EVENT_TIME_OIDS
from .coordinator import VirginCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coord: VirginCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        VirginLastEventSensor(coord, entry),
    ])

class VirginBaseEntity:
    def __init__(self, coordinator: VirginCoordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Virgin Media (unofficial)",
            name="Virgin Modem",
        )
        self._attr_unique_id = f"{entry.entry_id}_last_event"

class VirginLastEventSensor(VirginBaseEntity, SensorEntity):
    _attr_name = "Last DOCSIS Event"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        # pick the newest non-empty message by matching indices
        msgs = [data.get(oid, "") for oid in EVENT_MSG_OIDS if data.get(oid)]
        return msgs[-1] if msgs else None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "times": {oid: data.get(oid) for oid in EVENT_TIME_OIDS if data.get(oid)},
            "messages": {oid: data.get(oid) for oid in EVENT_MSG_OIDS if data.get(oid)},
        }

    async def async_update(self):
        await self.coordinator.async_request_refresh()
