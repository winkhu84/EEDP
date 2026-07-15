"""Rules domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Rules:
    """Signal requirements for a customer and device type."""

    customer: str
    device_type: str
    required_signals: list[str] = field(default_factory=list)
    optional_signals: list[str] = field(default_factory=list)
