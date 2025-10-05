from __future__ import annotations
import asyncio
import json
from typing import Any, Dict, Optional
import aiohttp

class VirginApi:
    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._base = f"http://{host}"
        self._session = session

    async def get_status(self) -> Dict[str, Any]:
        # Cache-busters in UI aren’t required; base path works.
        url = f"{self._base}/getRouterStatus"
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=7)) as resp:
                resp.raise_for_status()
                text = await resp.text()
                return json.loads(text)
        except asyncio.TimeoutError as e:
            raise ConnectionError("Virgin modem timed out") from e
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Virgin modem HTTP error: {e}") from e
        except json.JSONDecodeError as e:
            raise ValueError("Virgin modem returned non-JSON") from e
