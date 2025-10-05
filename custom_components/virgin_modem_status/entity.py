# custom_components/virgin_modem_status/entity.py
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VirginCoordinator


class VirginEntity(CoordinatorEntity):
    """Base entity that links sensors to a single Virgin Modem device."""

    def __init__(self, coordinator: VirginCoordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        host = getattr(coordinator.api, "host", "192.168.100.1")

        # Single, stable device per host so entities appear under the integration card.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},              # <- stable device key
            manufacturer="Virgin Media (unofficial)",
            name=f"Virgin Modem ({host})",
            configuration_url=f"http://{host}/",       # clickable link on device page
        )
        self._attr_has_entity_name = True
