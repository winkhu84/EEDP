"""Area domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.model.device import Device


@dataclass
class Area:
    """Logical grouping of devices in a project."""

    name: str
    devices: list[Device] = field(default_factory=list)
