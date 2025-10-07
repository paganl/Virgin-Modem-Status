"""Virgin Modem Status – Home Assistant custom integration."""
from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import VirginCoordinator
from .entity import VirginEntity

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coord: VirginCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VirginReachableBinary(coord, entry)], True)

class VirginReachableBinary(VirginEntity, BinarySensorEntity):
    _attr_name = "Modem Reachable"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: VirginCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reachable"

    @property
    def is_on(self) -> bool:
        # If last update succeeded, modem was reachable.
        return bool(self.coordinator.last_update_success)

    @property
    def available(self) -> bool:
        # Entity itself is always present; connectivity is expressed via is_on
        return True
