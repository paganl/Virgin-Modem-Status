# custom_components/virgin_modem_status/api.py
from __future__ import annotations
from typing import Any, Dict
import asyncio
import logging

from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_COMMUNITY

_LOGGER = logging.getLogger(__name__)

_TIME_BASE = "1.3.6.1.2.1.69.1.5.8.1.2"  # eventDateTime
_MSG_BASE  = "1.3.6.1.2.1.69.1.5.8.1.7"  # eventText

class VirginApiError(Exception):
    pass

class VirginApi:
    """SNMP-backed API for DOCSIS docsDevEvTable."""

    def __init__(self, host: str, session=None, timeout: int = 1, retries: int = 1) -> None:
        self.host = host or DEFAULT_HOST
        self.port = DEFAULT_PORT
        self.community = DEFAULT_COMMUNITY
        self.timeout = timeout
        self.retries = retries

    async def fetch_snapshot(self) -> Dict[str, Any]:
        """Run the SNMP walks off the event loop."""
        try:
            return await asyncio.to_thread(self._fetch_snapshot_sync)
        except ImportError as exc:
            _LOGGER.error("pysnmp/pyasn1 not available: %s", exc)
            raise VirginApiError("pysnmp not installed") from exc
        except Exception as exc:
            raise VirginApiError(f"SNMP fetch failed: {exc}") from exc

    # -------- sync work happens here (thread) --------
    def _fetch_snapshot_sync(self) -> Dict[str, Any]:
        # Lazy import so HA can load even if deps install a bit later
        from pysnmp.hlapi import (
            SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity, nextCmd
        )

        def walk_column(base_oid: str) -> Dict[int, str]:
            result: Dict[int, str] = {}
            engine = SnmpEngine()
            auth = CommunityData(self.community, mpModel=1)  # v2c
            target = UdpTransportTarget((self.host, self.port), timeout=self.timeout, retries=self.retries)
            ctx = ContextData()

            for (errInd, errStat, errIdx, varBinds) in nextCmd(
                engine, auth, target, ctx,
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False
            ):
                if errInd:
                    raise VirginApiError(str(errInd))
                if errStat:
                    at = varBinds[int(errIdx) - 1][0] if errIdx else "?"
                    raise VirginApiError(f"{errStat.prettyPrint()} at {at}")
                for name, val in varBinds:
                    oid_str = str(name)
                    if not oid_str.startswith(base_oid + "."):
                        return result  # walked past column
                    try:
                        idx = int(oid_str.split(".")[-1])
                    except Exception:
                        continue
                    result[idx] = str(val)
            return result

        times = walk_column(_TIME_BASE)
        msgs  = walk_column(_MSG_BASE)

        flat: Dict[str, Any] = {}
        indices = sorted(set(times) & set(msgs))
        for i in indices:
            flat[f"{_TIME_BASE}.{i}"] = times[i]
            flat[f"{_MSG_BASE}.{i}"]  = msgs[i]

        _LOGGER.debug("VirginApi(SNMP): parsed %d rows from %s", len(indices), self.host)
        return flat
