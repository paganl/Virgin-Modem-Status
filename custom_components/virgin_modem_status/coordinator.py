# custom_components/virgin_modem_status/coordinator.py
from __future__ import annotations

import logging
from datetime import timedelta
from random import randint

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class VirginModemCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to poll Virgin modem status JSON."""

    def __init__(self, hass: HomeAssistant, host: str, scan_seconds: int = 30) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Virgin Modem Status",
            update_interval=timedelta(seconds=scan_seconds),
        )
        self._hass = hass
        self._host = host
        # The page appears to accept cache-buster params like _n / _
        self._base_url = f"http://{host}/getRouterStatus"
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict:
        """Fetch and return the modem JSON."""
        # add simple cache busters so the modem doesn’t return a cached page
        params = {"_n": f"{randint(10000, 99999)}", "_": f"{randint(10**12, 10**13-1)}"}
        try:
            async with async_timeout.timeout(10):
                resp = await self._session.get(self._base_url, params=params)
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status}")
                # Some modems send text/html; ignore content-type
                data = await resp.json(content_type=None)
                if not isinstance(data, dict):
                    raise UpdateFailed("Unexpected payload (not a JSON object)")
                return data
        except Exception as err:
            raise UpdateFailed(err) from err
