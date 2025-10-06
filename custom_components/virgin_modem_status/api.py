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

# OID column prefixes used by many DOCSIS firmwares
OID_TIME = "1.3.6.1.2.1.69.1.5.8.1.2."   # docsDevEvTime
OID_PRI  = "1.3.6.1.2.1.69.1.5.8.1.5."   # docsDevEvLevel / priority
OID_MSG  = "1.3.6.1.2.1.69.1.5.8.1.7."   # docsDevEvText

class VirginApiError(Exception):
    """Raised when the Virgin modem status fetch or parse fails."""


class VirginApi:
    """
    HTTP-backed API for Virgin modem status.
    Tries JSON (including flat OID maps) first; falls back to HTML parsing (no extra deps).
    """

    def __init__(self, host: str, session: ClientSession, timeout: int = _DEFAULT_TIMEOUT) -> None:
        self.host = host or DEFAULT_HOST
        self._base = f"http://{self.host}"
        self._session = session
        self._timeout = ClientTimeout(total=timeout)

    async def fetch_snapshot(self) -> Dict[str, Any]:
        """Fetch modem status and return a flat OID-like dict of the last ~20 events."""
        url = f"{self._base}{ROUTER_STATUS_PATH}"
        try:
            async with self._session.get(url, timeout=self._timeout) as resp:
                resp.raise_for_status()
                raw = await resp.text()
        except (ClientError, Exception) as exc:
            raise VirginApiError(f"Router status fetch failed: {exc}") from exc

        # Prefer JSON path; cover both array/list layouts and flat OID->value dicts
        events: List[Dict[str, Any]] = []
        txt = (raw or "").lstrip()
        if txt.startswith("{") or txt.startswith("["):
            try:
                data = json.loads(txt)
                events = self._extract_events_from_json(data)
                if events:
                    _LOGGER.debug("VirginApi: parsed %d JSON events from %s", len(events), url)
                    return self._events_to_flat_map(events)
            except Exception as exc:
                _LOGGER.debug("VirginApi: JSON parse failed (%s), will try HTML.", exc)

        # HTML fallback (only warn about login on the HTML path)
        events = self._extract_events_from_html(raw)
        _LOGGER.debug(
            "VirginApi: parsed %d HTML events from %s (first bytes: %r)",
            len(events), url, raw[:120] if raw else ""
        )
        if not events:
            _LOGGER.warning("VirginApi: no events parsed from %s", url)
            return {}

        return self._events_to_flat_map(events)

    # ---------- helpers ----------

    def _events_to_flat_map(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert normalised event rows to the flat OID-like structure the coordinator expects."""
        flat: Dict[str, Any] = {}
        # keep the last 20 (or fewer) rows
        tail = events[-20:]
        for i, ev in enumerate(tail, start=1):
            t = (ev.get("time") or "").strip()
            m = (ev.get("message") or "").strip()
            p = (ev.get("priority") or "").strip()
            flat[f"{OID_TIME}{i}"] = t
            flat[f"{OID_MSG}{i}"]  = m
            if p:
                flat[f"{OID_PRI}{i}"] = p
        return flat

    def _extract_events_from_json(self, data: Any) -> List[Dict[str, Any]]:
        """
        Handle common JSON layouts:
        - flat dict of OIDs (your modem does this)
        - array/list of event dicts
        - nested under keys like 'events', 'docsisLog', etc.
        """
        # 1) Flat OID map?
        if isinstance(data, dict):
            evs = self._extract_events_from_oid_dict(data)
            if evs:
                return evs

        # 2) Direct list of dicts
        if isinstance(data, list):
            return [self._norm_ev(x) for x in data if isinstance(x, dict)]

        # 3) Nested objects
        if isinstance(data, dict):
            for key in ("events", "EventLog", "docsis_events", "docsisLog", "log"):
                val = data.get(key)
                if isinstance(val, list):
                    return [self._norm_ev(x) for x in val if isinstance(x, dict)]
            for parent in ("data", "status", "result"):
                sub = data.get(parent)
                if isinstance(sub, (dict, list)):
                    evs = self._extract_events_from_json(sub)
                    if evs:
                        return evs
        return []

    def _extract_events_from_oid_dict(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build event rows from a flat OID map, e.g.:
          1.3.6.1.2.1.69.1.5.8.1.2.<i> -> time
          1.3.6.1.2.1.69.1.5.8.1.7.<i> -> message
          1.3.6.1.2.1.69.1.5.8.1.5.<i> -> priority (optional)
        """
        idxs: set[int] = set()
        for k in data.keys():
            if k.startswith(OID_TIME) or k.startswith(OID_MSG) or k.startswith(OID_PRI):
                try:
                    idxs.add(int(k.split(".")[-1]))
                except Exception:
                    pass

        events: List[Dict[str, Any]] = []
        for i in sorted(idxs):
            t = str(data.get(f"{OID_TIME}{i}", "")).strip()
            m = str(data.get(f"{OID_MSG}{i}", "")).strip()
            p = str(data.get(f"{OID_PRI}{i}", "")).strip()
            if not (t or m):
                continue
            events.append({"time": t, "message": m, "priority": p})
        return events

    def _extract_events_from_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Heuristic HTML parser:
        - Look for <tr> with 2–5 <td> cells.
        - Assume first cell = time, last cell = message, middle = priority where present.
        """
        if not html:
            return []

        # Normalise whitespace to make regex saner
        text = re.sub(r"\s+", " ", html)

        # Bail-out if it looks like a login page
        if re.search(r"(login|sign in)", text, re.I) and "password" in text.lower():
            _LOGGER.warning("VirginApi: page looks like a login form; cannot parse logs.")
            return []

        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.I)
        events: List[Dict[str, Any]] = []

        # Time detector (several common formats)
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

            # Some firmwares put time in 2nd cell
            if not time_pat.search(raw_first) and time_pat.search(raw_mid):
                raw_first, raw_mid = raw_mid, raw_first

            # Must have a time-ish first cell
            if not time_pat.search(raw_first):
                continue

            ev = {
                "time": raw_first,
                "priority": raw_mid.lower(),
                "message": raw_last,
            }

            # Ignore headers / empties
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
