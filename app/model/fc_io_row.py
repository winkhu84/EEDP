"""FC_IO row domain entity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FCIORow:
    """One row in the project FC_IO table."""

    area: str
    device_type: str
    device_tag: str
    device_description: str
    signal_name: str
    io_type: str
    plc_address: str
    required: bool
    signal_description: str
    remark: str
    rack: str = ""
    slot: str = ""
    channel: str = ""
    terminal: str = ""
    cable: str = ""
    # Internal sort key: position in Device.signals (not shown in UI).
    signal_order: int = 0
