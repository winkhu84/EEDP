"""Recommendation result entities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Recommendation:
    """A single recommended signal for a device."""

    name: str
    signal_type: str
    required: bool

    @property
    def category(self) -> str:
        return "Required" if self.required else "Optional"


@dataclass(frozen=True)
class RecommendationResult:
    """Recommendation output for one device."""

    device_id: str
    device_tag: str
    device_type: str
    recommendations: tuple[Recommendation, ...]


@dataclass(frozen=True)
class IoSummary:
    """Counted I/O points from enabled signals."""

    di: int = 0
    do: int = 0
    ai: int = 0
    ao: int = 0
    total: int = 0
