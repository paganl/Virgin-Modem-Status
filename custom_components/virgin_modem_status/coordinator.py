# custom_components/virgin_modem_status/coordinator.py
from __future__ import annotations

import logging
from datetime import timedelta
from random import randint

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import VirginApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class VirginCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that polls the Virgin modem JSON endpoint."""

    def __init__(self, hass: HomeAssistant, api: VirginApi, scan_interval: int):
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch latest data from the modem."""
        try:
            # Small jitter so we don't hammer the endpoint at the exact same second
            jitter = randint(0, 2)
            if jitter:
                await self.hass.async_add_executor_job(lambda: None)  # yield once

            async with async_timeout.timeout(10):
                data = await self.api.async_get_status()
        except Exception as err:
            raise UpdateFailed(f"Virgin modem fetch failed: {err}") from err

        if not isinstance(data, dict) or not data:
            raise UpdateFailed("Virgin modem returned empty/invalid payload")

        return data
