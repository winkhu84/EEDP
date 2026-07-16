"""PLC Card Calculator — card quantity, capacity and spare channels."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.model.plc_card_config import PlcCardConfig, default_plc_card_configurations


@dataclass(frozen=True)
class PlcCardRequirement:
    """Calculated PLC card requirement for one I/O type."""

    io_type: str
    module_name: str
    channels_per_card: int
    used_channels: int
    required_cards: int
    total_channels: int
    spare_channels: int


def calculate_card_requirement(
    used_channels: int,
    channels_per_card: int,
) -> tuple[int, int, int]:
    """Return (required_cards, total_channels, spare_channels)."""
    if channels_per_card <= 0:
        raise ValueError("channels_per_card must be greater than zero.")

    used = max(0, int(used_channels))
    if used == 0:
        return 0, 0, 0

    required_cards = math.ceil(used / channels_per_card)
    total_channels = required_cards * channels_per_card
    spare_channels = total_channels - used
    return required_cards, total_channels, spare_channels


def calculate_project_cards(
    project_io_summary: Mapping[str, int],
    card_configurations: Sequence[PlcCardConfig] | None = None,
) -> tuple[PlcCardRequirement, ...]:
    """Calculate PLC card requirements from a project I/O summary."""
    configs = (
        tuple(card_configurations)
        if card_configurations is not None
        else default_plc_card_configurations()
    )

    results: list[PlcCardRequirement] = []
    for config in configs:
        io_key = config.io_type.strip().upper()
        used_channels = int(project_io_summary.get(io_key, 0))
        required_cards, total_channels, spare_channels = calculate_card_requirement(
            used_channels,
            config.channels_per_card,
        )
        results.append(
            PlcCardRequirement(
                io_type=io_key,
                module_name=config.module_name,
                channels_per_card=config.channels_per_card,
                used_channels=used_channels,
                required_cards=required_cards,
                total_channels=total_channels,
                spare_channels=spare_channels,
            )
        )
    return tuple(results)
