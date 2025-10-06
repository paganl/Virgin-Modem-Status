# custom_components/virgin_modem_status/api.py
from __future__ import annotations
import json, re
from typing import Any, Dict, List
from aiohttp import ClientSession, ClientTimeout, ClientError

DEFAULT_TIMEOUT = 10  # seconds

class VirginApiError(Exception):
    pass

class VirginApi:
    def __init__(self, host: str, session: ClientSession, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.host = host
        self._base = f"http://{host}"
        self._session = session
        self._timeout = ClientTimeout(total=timeout)

    async def fetch_snapshot(self) -> Dict[str, Any]:
        url = f"{self._base}/getRouterStatus"
        try:
            async with self._session.get(url, timeout=self._timeout) as resp:
                resp.raise_for_status()
                raw = await resp.text()  # tolerate wrong content-type
        except (ClientError, Exception) as exc:
            raise VirginApiError(f"Router status fetch failed: {exc}") from exc

        # Try JSON first
        events = []
        try:
            data = json.loads(raw)
            events = self._extract_events_from_json(data)
        except Exception:
            pass

        # Fallback: HTML table
        if not events:
            events = self._extract_events_from_html(raw)

        # Map to flat OID-like keys the coordinator expects
        flat: Dict[str, Any] = {}
        # keep last 20
        events = events[-20:]
        for i, ev in enumerate(events, start=1):
            t = (ev.get("time") or ev.get("timestamp") or "").strip()
            m = (ev.get("text") or ev.get("message") or "").strip()
            p = (ev.get("priority") or ev.get("pri") or "").strip().lower()
            flat[f"1.3.6.1.2.1.69.1.5.8.1.2.{i}"] = t
            flat[f"1.3.6.1.2.1.69.1.5.8.1.7.{i}"] = m
            if p:
                flat[f"1.3.6.1.2.1.69.1.5.8.1.3.{i}"] = p

        # Helpful debug breadcrumb
        # (Coordinator logging will show derived fields, but this shows raw count)
        import logging
        logging.getLogger(__name__).debug(
            "VirginApi: parsed %d events from %s (first bytes: %r)",
            len(events), url, raw[:120]
        )

        return flat

    # ---------- helpers ----------
    def _extract_events_from_json(self, data: Any) -> List[Dict[str, Any]]:
        if not isinstance(data, dict):
            return []
        # common keys seen across firmwares
        for key in ("events", "EventLog", "docsis_events", "docsisLog", "log"):
            if key in data and isinstance(data[key], list):
                return [self._norm_event_obj(x) for x in data[key] if isinstance(x, dict)]
        # nested shapes
        for parent in ("data", "status", "result"):
            obj = data.get(parent)
            if isinstance(obj, dict):
                ev = self._extract_events_from_json(obj)
                if ev:
                    return ev
        return []

    def _extract_events_from_html(self, html: str) -> List[Dict[str, Any]]:
        # Naive parse: rows containing three columns (time, priority?, message)
        # Time patterns commonly: 2025-10-06 16:18:40 or 06/10/2025 16:18:40
        rows = []
        # Strip newlines for easier regex
        text = re.sub(r"\s+", " ", html)
        # Try table rows
        for m in re.finditer(r"<tr[^>]*>\s*(<td[^>]*>.*?</td>){2,5}\s*</tr>", text, re.I):
            row = m.group(0)
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.I)
            if not cells:
                continue
            # Heuristics: last cell is message, first cell is time, second may be priority
            msg = self._strip_tags(cells[-1]).strip()
            time = self._strip_tags(cells[0]).strip()
            pri = self._strip_tags(cells[1]).strip().lower() if len(cells) > 2 else ""
            if msg and time:
                rows.append({"time": time, "message": msg, "priority": pri})
        return rows

    @staticmethod
    def _strip_tags(s: str) -> str:
        return re.sub(r"<[^>]+>", "", s)

    @staticmethod
    def _norm_event_obj(x: Dict[str, Any]) -> Dict[str, Any]:
        # normalise common fields
        return {
            "time": x.get("time") or x.get("timestamp") or x.get("date") or x.get("datetime") or "",
            "message": x.get("text") or x.get("message") or x.get("event") or "",
            "priority": x.get("priority") or x.get("pri") or x.get("severity") or "",
        }
