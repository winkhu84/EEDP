"""Signal domain entity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Signal:
    """I/O or control signal owned by a device."""

    name: str
    io_type: str
    required: bool
    enabled: bool = True
    address: str = ""
    terminal: str = ""
    cable: str = ""
    description: str = ""
    remark: str = ""
