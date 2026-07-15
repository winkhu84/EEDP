"""Resolve device type from a tag name prefix."""

from __future__ import annotations

import re

# Longer prefixes first so PT is not matched as P.
_TAG_PREFIX_RULES: tuple[tuple[str, str], ...] = (
    ("RTD", "RTD"),
    ("XV", "Valve"),
    ("PT", "Pressure Transmitter"),
    ("LS", "Level Sensor"),
    ("FM", "Flow Meter"),
    ("TT", "Thermocouple"),
    ("FAN", "Fan"),
    ("P", "Pump"),
)

_EQUIPMENT_TYPES = frozenset({"Pump", "Valve", "Fan"})
_INSTRUMENT_TYPES = frozenset(
    {
        "Pressure Transmitter",
        "Level Sensor",
        "Flow Meter",
        "Thermocouple",
        "RTD",
    }
)


def resolve_device_type(tag: str) -> str:
    """Return device type from tag prefix, or Unknown."""
    normalized = tag.strip().upper()
    if not normalized:
        return "Unknown"

    for prefix, device_type in _TAG_PREFIX_RULES:
        pattern = rf"^{re.escape(prefix)}(?:[-_]?\d|$)"
        if re.match(pattern, normalized):
            return device_type

    return "Unknown"


def resolve_device_category(device_type: str, io_category: str = "") -> str:
    """Return Equipment / Instrument / Unknown for a device type."""
    text = io_category.strip()
    if text.lower() in {"equipment", "instrument"}:
        return text.capitalize() if text.lower() == "equipment" else "Instrument"

    if device_type in _EQUIPMENT_TYPES:
        return "Equipment"
    if device_type in _INSTRUMENT_TYPES:
        return "Instrument"
    return "Unknown"
