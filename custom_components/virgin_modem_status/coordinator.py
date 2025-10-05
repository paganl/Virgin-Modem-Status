from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryError

from .api import VirginApi


class VirginCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls the Virgin modem JSON endpoint."""

    def __init__(self, hass: HomeAssistant, api: VirginApi, scan_interval: int) -> None:
        super().__init__(
            hass,
            logger=hass.logger,  # HA injects a logger on Core now
            name="Virgin Modem Status",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.fetch_status()
            # Ensure a dict even if the API returns None
            return data or {}
        except Exception as err:
            # Surface as a recoverable polling error for the coordinator
            raise ConfigEntryError(f"Virgin modem fetch failed: {err}") from err
