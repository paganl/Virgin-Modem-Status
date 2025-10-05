from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VirginCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord: VirginCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VirginReachableBinarySensor(coord, entry)])


class VirginBaseEntity:
    def __init__(self, coordinator: VirginCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Virgin Media (unofficial)",
            name="Virgin Modem",
        )


class VirginReachableBinarySensor(VirginBaseEntity, BinarySensorEntity):
    _attr_name = "Reachable"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool | None:
        # Consider the modem "reachable" if the coordinator returned any data dict
        return bool(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {"keys": list(self.coordinator.data.keys()) if self.coordinator.data else []}
