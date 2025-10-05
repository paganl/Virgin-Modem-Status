from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_MSG_OIDS, EVENT_TIME_OIDS
from .coordinator import VirginCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: VirginCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VirginLastEventSensor(coord, entry)])


class VirginBaseEntity:
    def __init__(self, coordinator: VirginCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Virgin Media (unofficial)",
            name="Virgin Modem",
        )


class VirginLastEventSensor(VirginBaseEntity, SensorEntity):
    _attr_name = "Last DOCSIS Event"

    @property
    def native_value(self) -> str | None:
        data: dict[str, Any] = self.coordinator.data or {}
        # Get newest non-empty message using the event OIDs list order
        msgs = [data.get(oid, "") for oid in EVENT_MSG_OIDS if data.get(oid)]
        return msgs[-1] if msgs else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        data: dict[str, Any] = self.coordinator.data or {}
        return {
            "times": {oid: data.get(oid) for oid in EVENT_TIME_OIDS if data.get(oid)},
            "messages": {oid: data.get(oid) for oid in EVENT_MSG_OIDS if data.get(oid)},
        }
