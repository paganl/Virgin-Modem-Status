# custom_components/virgin_modem_status/api.py
from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional

from aiohttp import ClientSession, ClientTimeout, ClientError

DEFAULT_TIMEOUT = 10  # seconds


class VirginApiError(Exception):
    """Raised when the Virgin modem API call fails."""


class VirginApi:
    """Thin async client for the Virgin modem status endpoint."""

    def __init__(self, host: str, session: ClientSession, timeout: int = DEFAULT_TIMEOUT) -> None:
        # Accept either "192.168.100.1" or "http://192.168.100.1"
        host = host.strip().rstrip("/")
        self._base = host if host.startswith("http") else f"http://{host}"
        self._session = session
        self._timeout = ClientTimeout(total=timeout)

    async def async_get_status(self) -> Dict[str, Any]:
        """
        Fetch /getRouterStatus as JSON.

        The modem’s UI seems to add `_n` and `_` (cache-buster) params.
        We include them to mimic the browser call and avoid cached/blocked responses.
        """
        url = f"{self._base}/getRouterStatus"
        params = {
            "_n": f"{random.randint(10000, 99999)}",
            "_": str(int(time.time() * 1000)),
        }
        # Headers similar to the web UI’s XHR requests
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self._base}/",  # some firmwares check this
            "Connection": "keep-alive",
        }

        try:
            async with self._session.get(url, params=params, headers=headers, timeout=self._timeout) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise VirginApiError(f"HTTP {resp.status}: {text[:200]}")
                # Some firmwares return application/json, others text/javascript.
                # Let aiohttp parse regardless of content_type.
                data: Dict[str, Any] = await resp.json(content_type=None)
                if not isinstance(data, dict):
                    raise VirginApiError("Unexpected payload (not a JSON object)")
                return data
        except (ClientError, TimeoutError) as e:
            raise VirginApiError(f"Request failed: {e}") from e
