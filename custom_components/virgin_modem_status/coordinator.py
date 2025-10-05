# custom_components/virgin_modem_status/coordinator.py
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VirginApi


class VirginCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinates fetching status from the Virgin modem."""

    def __init__(self, hass: HomeAssistant, api: VirginApi, scan_interval: int) -> None:
        self.api = api
        super().__init__(
            hass=hass,
            logger=logging.getLogger(__name__),  # use stdlib logger
            name="Virgin Modem Status",
            update_interval=timedelta(seconds=max(5, int(scan_interval))),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the modem API."""
        try:
            data = await self.api.async_get_status()
            # ensure we always return a dict for sensors to consume
            return data if isinstance(data, dict) else {}
        except Exception as err:  # pylint: disable=broad-except
            raise UpdateFailed(f"Error fetching Virgin modem status: {err}") from err
