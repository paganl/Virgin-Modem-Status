from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, EVENT_MSG_OIDS, TROUBLE_KEYWORDS
from .coordinator import VirginCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coord: VirginCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([VirginDocsisHealthy(coord, entry)])

class VirginDocsisHealthy(BinarySensorEntity):
    _attr_name = "DOCSIS Healthy"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: VirginCoordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_docsis_healthy"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        msgs = [data.get(oid, "") for oid in EVENT_MSG_OIDS if data.get(oid)]
        if not msgs:
            return None  # unknown
        last = msgs[-1].lower()
        return not any(k in last for k in TROUBLE_KEYWORDS)
