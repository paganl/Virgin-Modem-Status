# custom_components/virgin_modem_status/sensor.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_MSG_OIDS, EVENT_TIME_OIDS
from .coordinator import VirginCoordinator
from .entity import VirginEntity


def _latest_present(raw: Dict[str, Any], oids: List[str]) -> Optional[str]:
    """Return the last non-empty value among the given OIDs from a raw dict."""
    vals = [raw.get(oid) for oid in oids if raw.get(oid)]
    return vals[-1] if vals else None


def _get_raw_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
    """Coordinator now nests OIDs under 'raw'. Fall back to top-level if needed."""
    if not isinstance(data, dict):
        return {}
    raw = data.get("raw")
    return raw if isinstance(raw, dict) else data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    coord: VirginCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            VirginLastEventSensor(coord, entry),
            VirginLastEventTimeSensor(coord, entry),
        ],
        True,
    )


class VirginLastEventSensor(VirginEntity, SensorEntity):
    """Shows the latest DOCSIS event message."""
    _attr_name = "Last DOCSIS Event"
    _attr_icon = "mdi:information"

    def __init__(self, coordinator: VirginCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_event"

    @property
    def native_value(self) -> Optional[str]:
        d = self.coordinator.data or {}
        # Preferred value computed by coordinator (if present)
        msg = d.get("last_event_message")
        if msg:
            return str(msg)
        # Fallback: read from raw OID map
        raw = _get_raw_snapshot(d)
        return _latest_present(raw, EVENT_MSG_OIDS)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        d = self.coordinator.data or {}
        raw = _get_raw_snapshot(d)
        return {
            "status": d.get("status"),
            "priority": d.get("last_event_priority"),
            "index": d.get("last_event_index"),
            "messages": {oid: raw.get(oid) for oid in EVENT_MSG_OIDS if raw.get(oid)},
            "times": {oid: raw.get(oid) for oid in EVENT_TIME_OIDS if raw.get(oid)},
        }


class VirginLastEventTimeSensor(VirginEntity, SensorEntity):
    """Shows the timestamp of the latest DOCSIS event."""
    _attr_name = "Last DOCSIS Event Time"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: VirginCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_event_time"

    @property
    def native_value(self) -> Optional[str]:
        d = self.coordinator.data or {}
        # Preferred value computed by coordinator (if present)
        t = d.get("last_event_time")
        if t:
            return str(t)
        # Fallback: read from raw OID map
        raw = _get_raw_snapshot(d)
        return _latest_present(raw, EVENT_TIME_OIDS)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        d = self.coordinator.data or {}
        raw = _get_raw_snapshot(d)
        return {
            "status": d.get("status"),
            "priority": d.get("last_event_priority"),
            "index": d.get("last_event_index"),
            "messages": {oid: raw.get(oid) for oid in EVENT_MSG_OIDS if raw.get(oid)},
            "times": {oid: raw.get(oid) for oid in EVENT_TIME_OIDS if raw.get(oid)},
        }
