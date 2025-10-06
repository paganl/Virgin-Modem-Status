from __future__ import annotations
from typing import Any, Dict
from aiohttp import ClientSession, ClientTimeout, ClientError

DEFAULT_TIMEOUT = 10  # seconds

class VirginApiError(Exception):
    """Raised when the Virgin modem API call fails."""

class VirginApi:
    def __init__(self, host: str, session: ClientSession, timeout: int = DEFAULT_TIMEOUT) -> None:
        self._base = f"http://{host}"
        self._session = session
        self._timeout = ClientTimeout(total=timeout)

    async def fetch_snapshot(self) -> Dict[str, Any]:
        """
        Fetch /getRouterStatus and map the last 20 events into OID-like keys:
          1.3.6.1.2.1.69.1.5.8.1.2.i -> time
          1.3.6.1.2.1.69.1.5.8.1.7.i -> message
          1.3.6.1.2.1.69.1.5.8.1.3.i -> priority (if available)
        Adjust the parsing to your modem’s JSON.
        """
        url = f"{self._base}/getRouterStatus"
        try:
            async with self._session.get(url, timeout=self._timeout) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (ClientError, Exception) as exc:
            raise VirginApiError(f"Router status fetch failed: {exc}") from exc

        flat: Dict[str, Any] = {}

        # EXPECTED SHAPE (example):
        # {"events": [{"time":"2025-10-06 16:18:40","text":"SYNC ...","priority":"warning"}, ...]}
        events = (data.get("events") or []) if isinstance(data, dict) else []
        events = events[-20:]  # last 20

        for i, ev in enumerate(events, start=1):
            t = (ev.get("time") or ev.get("timestamp") or "").strip()
            m = (ev.get("text") or ev.get("message") or "").strip()
            p = (ev.get("priority") or ev.get("pri") or "").strip().lower()
            flat[f"1.3.6.1.2.1.69.1.5.8.1.2.{i}"] = t
            flat[f"1.3.6.1.2.1.69.1.5.8.1.7.{i}"] = m
            if p:
                flat[f"1.3.6.1.2.1.69.1.5.8.1.3.{i}"] = p

        return flat
