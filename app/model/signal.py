"""Signal domain entity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Signal:
    """I/O or control signal attached to a device."""

    name: str
    signal_type: str
    required: bool
    address: str
    remark: str
