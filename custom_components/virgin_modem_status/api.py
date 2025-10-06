# custom_components/virgin_modem_status/api.py
from __future__ import annotations
from typing import Any, Dict, List
import logging
import json
import re
from aiohttp import ClientSession, ClientTimeout, ClientError

from .const import DEFAULT_HOST, ROUTER_STATUS_PATH

_LOGGER = logging.getLogger(__name__)
_DEFAULT_TIMEOUT = 10  # seconds

class VirginApiError(Exception):
    """Raised when the Virgin modem status fetch or parse fails."""

class VirginApi:
    """
    HTTP-backed API for Virgin modem status.
    Tries JSON first; falls back to HTML parsing (no external deps).
    """

    def __init__(self, host: str, session: ClientSession, timeout: int = _DEFAULT_TIMEOUT) -> None:
        self.host = host or DEFAULT_HOST
        self._base = f"http://{self.host}"
        self._session = session
        self._timeout = ClientTimeout(total=timeout)

    async def fetch_snapshot(self) -> Dict[str, Any]:
        url = f"{self._base}{ROUTER_STATUS_PATH}"
        raw = None
        try:
            async with self._session.get(url, timeout=self._timeout) as resp:
                resp.raise_for_status()
                # Don’t assume JSON; always read text first.
                raw = await resp.text()
        except (ClientError, Exception) as exc:
            raise VirginApiError(f"Router status fetch failed: {exc}") from exc

        events: List[Dict[str, Any]] = []

        # 1) JSON (various shapes we’ve seen)
        try:
            data = json.loads(raw)
            events = self._extract_events_from_json(data)
            if events:
                _LOGGER.debug("VirginApi: parsed %d JSON events from %s", len(events), url)
        except Exception:
            pass

        # 2) HTML fallback
        if not events:
            events = self._extract_events_from_html(raw)
            _LOGGER.debug(
                "VirginApi: parsed %d HTML events from %s (first bytes: %r)",
                len(events), url, raw[:120]
            )

        if not events:
            # Not fatal to the integration; coordinator will try again next interval.
            _LOGGER.warning("VirginApi: no events parsed from %s", url)

        # Map to flat OID-like dict that the coordinator expects (last 20 only)
        flat: Dict[str, Any] = {}
        events = events[-20:]
        for i, ev in enumerate(events, start=1):
            t = (ev.get("time") or ev.get("timestamp") or "").strip()
            m = (ev.get("message") or ev.get("text") or "").strip()
            p = (ev.get("priority") or ev.get("pri") or "").strip().lower()
            flat[f"1.3.6.1.2.1.69.1.5.8.1.2.{i}"] = t
            flat[f"1.3.6.1.2.1.69.1.5.8.1.7.{i}"] = m
            if p:
                flat[f"1.3.6.1.2.1.69.1.5.8.1.3.{i}"] = p

        return flat

    # ---------- helpers ----------

    def _extract_events_from_json(self, data: Any) -> List[Dict[str, Any]]:
        """Handle common JSON layouts across firmware variants."""
        if isinstance(data, list):
            return [self._norm_ev(x) for x in data if isinstance(x, dict)]

        if not isinstance(data, dict):
            return []

        # Common keys across vendors
        for key in ("events", "EventLog", "docsis_events", "docsisLog", "log"):
            val = data.get(key)
            if isinstance(val, list):
                return [self._norm_ev(x) for x in val if isinstance(x, dict)]

        # Nested objects
        for parent in ("data", "status", "result"):
            sub = data.get(parent)
            if isinstance(sub, (dict, list)):
                evs = self._extract_events_from_json(sub)
                if evs:
                    return evs

        return []

    def _extract_events_from_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Heuristic HTML parser:
        - Look for <tr> with 2–5 <td> cells.
        - Assume first cell = time, last cell = message, middle maybe priority.
        - Works on most Virgin “status/log” pages that render a simple table.
        """
        # Normalise whitespace to make regex saner
        text = re.sub(r"\s+", " ", html)

        # Quick bail-outs: login page or zero logs
        if re.search(r"(login|sign in)", text, re.I) and "password" in text.lower():
            _LOGGER.warning("VirginApi: page looks like a login form; cannot parse logs.")
            return []

        # Pull rows
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.I)
        events: List[Dict[str, Any]] = []

        # Define a time detector (several common formats)
        time_pat = re.compile(
            r"(?:(\d{4}-\d{2}-\d{2})|(\d{1,2}/\d{1,2}/\d{2,4}))\s+(\d{1,2}:\d{2}:\d{2})"
        )

        def strip_tags(s: str) -> str:
            return re.sub(r"<[^>]+>", "", s).strip()

        for row in rows:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.I)
            if len(cells) < 2:
                continue

            raw_first = strip_tags(cells[0])
            raw_last  = strip_tags(cells[-1])
            raw_mid   = strip_tags(cells[1]) if len(cells) >= 3 else ""

            # Heuristic: first cell should look like a time (else skip)
            if not time_pat.search(raw_first):
                # Some firmwares put time in 2nd cell; swap if that matches
                if time_pat.search(raw_mid):
                    raw_first, raw_mid = raw_mid, raw_first
                else:
                    continue

            ev = {
                "time": raw_first,
                "priority": raw_mid.lower(),
                "message": raw_last,
            }

            # Ignore header rows and empties
            if not ev["message"] or ev["message"].lower() in ("message", "event", "description"):
                continue

            events.append(ev)

        return events

    @staticmethod
    def _norm_ev(x: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "time": x.get("time") or x.get("timestamp") or x.get("date") or x.get("datetime") or "",
            "message": x.get("message") or x.get("text") or x.get("event") or "",
            "priority": x.get("priority") or x.get("pri") or x.get("severity") or "",
        }
