from __future__ import annotations
from typing import Any, Dict, Tuple

import logging
from pysnmp.hlapi import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, nextCmd
)

from .const import (
    DEFAULT_HOST, DEFAULT_PORT, DEFAULT_COMMUNITY,
)

# Base OIDs (columns) — we’ll walk these
# eventDateTime: 1.3.6.1.2.1.69.1.5.8.1.2
# eventText:     1.3.6.1.2.1.69.1.5.8.1.7
_TIME_BASE = "1.3.6.1.2.1.69.1.5.8.1.2"
_MSG_BASE  = "1.3.6.1.2.1.69.1.5.8.1.7"
# Optional priority column varies by FW; skip for now

_LOGGER = logging.getLogger(__name__)

class VirginApiError(Exception):
    pass

class VirginApi:
    """SNMP-backed API for Virgin modem docsDevEvTable."""
    def __init__(self, host: str, session=None, timeout: int = 1, retries: int = 1) -> None:
        # session not used (kept for constructor compatibility)
        self.host = host or DEFAULT_HOST
        self.port = DEFAULT_PORT
        self.community = DEFAULT_COMMUNITY
        self.timeout = timeout
        self.retries = retries

    def _walk_column(self, base_oid: str) -> Dict[int, str]:
        """Walk a single column and return {index: value}."""
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
                raise VirginApiError(f"{errStat.prettyPrint()} at {errIdx and varBinds[int(errIdx)-1][0] or '?'}")
            for name, val in varBinds:
                oid_str = str(name)
                if not oid_str.startswith(base_oid + "."):
                    # walked past the column
                    return result
                # last integer in OID is the row index
                try:
                    idx = int(oid_str.split(".")[-1])
                except Exception:
                    continue
                result[idx] = str(val)
        return result

    async def fetch_snapshot(self) -> Dict[str, Any]:
        """
        Return a flat dict:
          1.3.6.1.2.1.69.1.5.8.1.2.i -> time
          1.3.6.1.2.1.69.1.5.8.1.7.i -> message
        """
        try:
            # run SNMP in threadpool via HA if needed; it’s fast enough to run sync in practice,
            # but coordinator calls us in executor anyway.
            times = self._walk_column(_TIME_BASE)
            msgs  = self._walk_column(_MSG_BASE)
        except Exception as exc:
            raise VirginApiError(f"SNMP fetch failed: {exc}") from exc

        flat: Dict[str, Any] = {}
        # Only include rows present in both
        indices = sorted(set(times) & set(msgs))
        for i in indices:
            flat[f"{_TIME_BASE}.{i}"] = times[i]
            flat[f"{_MSG_BASE}.{i}"]  = msgs[i]

        _LOGGER.debug("VirginApi(SNMP): parsed %d rows from %s", len(indices), self.host)
        return flat
