"""Device domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.model.signal import Signal


@dataclass
class Device:
    """Equipment unit within a project area."""

    id: str
    tag: str
    area: str
    category: str
    type: str
    description: str
    quantity: int
    signals: list[Signal] = field(default_factory=list)
