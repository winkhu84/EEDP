"""I/O Summary Engine — device and project I/O counts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Mapping

from app.model.device import Device

_VALID_IO_TYPES = frozenset({"DI", "DO", "AI", "AO"})


def _empty_summary() -> dict[str, int]:
    return {"DI": 0, "DO": 0, "AI": 0, "AO": 0, "TOTAL": 0}


def _count_enabled_signals(device: Device) -> dict[str, int]:
    """Count enabled signals on one device (quantity not applied)."""
    counts = {"DI": 0, "DO": 0, "AI": 0, "AO": 0}
    for signal in device.signals:
        if not signal.enabled:
            continue
        io_type = (signal.io_type or "").strip().upper()
        if io_type not in _VALID_IO_TYPES:
            continue
        counts[io_type] += 1
    return counts


def summarize_device(
    device: Device | None,
    *,
    apply_quantity: bool = False,
) -> dict[str, int]:
    """Summarize enabled I/O for one device.

    Device panel usage: apply_quantity=False (raw enabled signals).
    Project contribution usage: apply_quantity=True.
    """
    if device is None:
        return _empty_summary()

    counts = _count_enabled_signals(device)
    if apply_quantity:
        factor = max(int(device.quantity), 0)
        for key in ("DI", "DO", "AI", "AO"):
            counts[key] *= factor

    return {
        "DI": counts["DI"],
        "DO": counts["DO"],
        "AI": counts["AI"],
        "AO": counts["AO"],
        "TOTAL": counts["DI"] + counts["DO"] + counts["AI"] + counts["AO"],
    }


def summarize_project(project_or_devices: Iterable[Device] | None) -> dict[str, int]:
    """Summarize enabled I/O across all devices, multiplying each by quantity."""
    if project_or_devices is None:
        return _empty_summary()

    totals = {"DI": 0, "DO": 0, "AI": 0, "AO": 0}
    for device in project_or_devices:
        part = summarize_device(device, apply_quantity=True)
        for key in ("DI", "DO", "AI", "AO"):
            totals[key] += part[key]

    return {
        "DI": totals["DI"],
        "DO": totals["DO"],
        "AI": totals["AI"],
        "AO": totals["AO"],
        "TOTAL": totals["DI"] + totals["DO"] + totals["AI"] + totals["AO"],
    }


def summary_to_mapping(summary: Mapping[str, int]) -> dict[str, int]:
    """Normalize any summary mapping to the standard keys."""
    return {
        "DI": int(summary.get("DI", 0)),
        "DO": int(summary.get("DO", 0)),
        "AI": int(summary.get("AI", 0)),
        "AO": int(summary.get("AO", 0)),
        "TOTAL": int(summary.get("TOTAL", 0)),
    }
