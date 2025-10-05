# custom_components/virgin_modem_status/binary_sensor.py
from __future__ import annotations
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VirginModemCoordinator  # <- match your actual class name

def _get_coordinator(container: Any) -> VirginModemCoordinator:
    """Support both hass.data[DOMAIN][entry_id] and ...['coordinator'] shapes."""
    return container.get("coordinator", container)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    container = hass.data[DOMAIN][entry.entry_id]
    coordinator: VirginModemCoordinator = _get_coordinator(container)

    async_add_entities(
        [
            VirginStatusAvailableBinarySensor(coordinator, entry),
        ],
        update_before_add=True,
    )

class VirginBaseBinary(CoordinatorEntity[Dict[str, Any]], BinarySensorEntity):
    def __init__(self, coordinator: VirginModemCoordinator, entry: ConfigEntry) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Virgin Media (unofficial)",
            name="Virgin Modem",
        )

class VirginStatusAvailableBinary(VirginBaseBinary):
    """Simple connectivity flag: ON when API returns usable data."""

    _attr_name = "Status Available"
    _attr_unique_id: str
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: VirginModemCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status_available"

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        # Treat any non-empty payload as 'available'
        return bool(data)
