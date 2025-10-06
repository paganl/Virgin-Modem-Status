# custom_components/virgin_modem_status/api.py
from __future__ import annotations
from typing import Any, Dict, Optional
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
          EVENT_TIME_OIDS[i] -> "YYYY-MM-DD HH:MM:SS"
          EVENT_MSG_OIDS[i]  -> "message text"
        If your modem doesn’t return JSON, you’ll need to adapt this.
        """
        url = f"{self._base}/getRouterStatus"
        try:
            async with self._session.get(url, timeout=self._timeout) as resp:
                resp.raise_for_status()
                # many firmwares return JSON; if it’s JS, you may need to eval/strip
                data = await resp.json(content_type=None)
        except (ClientError, Exception) as exc:
            raise VirginApiError(f"Router status fetch failed: {exc}") from exc

        # ---- Map to the flat dict the coordinator expects ----
        flat: Dict[str, Any] = {}

        # Example: if data["events"] is a list of dicts like
        # [{"time":"2025-10-06 16:18:40","text":"SYNC Timing ..." , "pri":"warning"}, ...]
        events = (data.get("events") or []) if isinstance(data, dict) else []
        # Take last 20 (1..20)
        events = events[-20:]
        # Build OID-style keys 1..N (coordinator scans 1..20)
        for i, ev in enumerate(events, start=1):
            t = ev.get("time") or ev.get("timestamp") or ""
            m = ev.get("text") or ev.get("message") or ""
            p = (ev.get("priority") or ev.get("pri") or "").lower()
            flat[f"1.3.6.1.2.1.69.1.5.8.1.2.{i}"] = t
            flat[f"1.3.6.1.2.1.69.1.5.8.1.7.{i}"] = m
            if p:
                flat[f"1.3.6.1.2.1.69.1.5.8.1.3.{i}"] = p  # optional priority column

        return flat
