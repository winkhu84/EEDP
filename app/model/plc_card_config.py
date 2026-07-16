"""PLC card configuration domain entity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlcCardConfig:
    """Configurable PLC I/O card definition."""

    io_type: str
    module_name: str
    channels_per_card: int


def default_plc_card_configurations() -> tuple[PlcCardConfig, ...]:
    """Return default editable PLC card configurations."""
    return (
        PlcCardConfig(io_type="DI", module_name="DI 32CH", channels_per_card=32),
        PlcCardConfig(io_type="DO", module_name="DO 32CH", channels_per_card=32),
        PlcCardConfig(io_type="AI", module_name="AI 8CH", channels_per_card=8),
        PlcCardConfig(io_type="AO", module_name="AO 8CH", channels_per_card=8),
    )
