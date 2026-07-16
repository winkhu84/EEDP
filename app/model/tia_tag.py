"""TIA Portal tag domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field

STATUS_OK = "OK"
STATUS_WARNING = "WARNING"
STATUS_ERROR = "ERROR"


@dataclass
class TIATag:
    """One TIA Portal tag derived from a device signal."""

    symbol_name: str
    data_type: str
    logical_address: str
    comment: str
    area: str = ""
    device_type: str = ""
    device_tag: str = ""
    signal_name: str = ""
    io_type: str = ""
    status: str = STATUS_OK
    validation_messages: list[str] = field(default_factory=list)
    signal_order: int = 0
