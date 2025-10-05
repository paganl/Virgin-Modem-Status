from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VirginApi
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

class VirginCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, api: VirginApi, scan_interval: int = DEFAULT_SCAN_INTERVAL) -> None:
        super().__init__(
            hass,
            logger=hass.helpers.logger.logging.getLogger(__package__),
            name=f"{DOMAIN}_coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api

    async def _async_update_data(self) -> Dict[str, Any]:
        try:
            return await self.api.get_status()
        except Exception as e:
            raise UpdateFailed(str(e)) from e
