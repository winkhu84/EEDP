"""PLC module and channel mapping domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field


STATUS_USED = "USED"
STATUS_SPARE = "SPARE"
STATUS_CONFLICT = "CONFLICT"


@dataclass
class PLCChannelAssignment:
    """One Device Signal occupying a PLC channel."""

    device_tag: str
    device_type: str
    area: str
    signal_name: str
    io_type: str
    plc_address: str
    signal_order: int = 0


@dataclass
class PLCChannelMapping:
    """One channel on a PLC card block."""

    channel_index: int
    channel_address: str
    status: str
    assignments: list[PLCChannelAssignment] = field(default_factory=list)


@dataclass
class PLCModuleMapping:
    """One PLC card block with channel occupancy."""

    io_type: str
    module_name: str
    channels_per_card: int
    card_number: int
    start_address: str
    end_address: str
    used_channels: int
    spare_channels: int
    conflict_channels: int
    rack: str = ""
    slot: str = ""
    channels: list[PLCChannelMapping] = field(default_factory=list)

    @property
    def utilization_percent(self) -> float:
        if self.channels_per_card <= 0:
            return 0.0
        return (self.used_channels / self.channels_per_card) * 100.0

    def list_label(self) -> str:
        return (
            f"{self.io_type} Card {self.card_number}\n"
            f"{self.start_address} - {self.end_address}\n"
            f"Used {self.used_channels} / {self.channels_per_card}    "
            f"Spare {self.spare_channels}    Conflict {self.conflict_channels}"
        )

    def combo_label(self) -> str:
        return (
            f"{self.io_type} Card {self.card_number}: "
            f"{self.start_address} - {self.end_address}"
        )


@dataclass(frozen=True)
class PLCModuleMappingIssue:
    """Validation warning or error for module mapping."""

    severity: str
    code: str
    message: str
    device_tag: str = ""
    signal_name: str = ""
    plc_address: str = ""
    io_type: str = ""


@dataclass
class PLCModuleTypeSummary:
    """Aggregated summary for one I/O type."""

    io_type: str
    module_name: str
    cards: int
    used: int
    total_channels: int
    spare: int
    conflicts: int

    @property
    def utilization_percent(self) -> float:
        if self.total_channels <= 0:
            return 0.0
        return (self.used / self.total_channels) * 100.0


@dataclass
class PLCModuleMappingResult:
    """Full project PLC module mapping outcome."""

    modules: list[PLCModuleMapping]
    summaries: list[PLCModuleTypeSummary]
    warnings: list[PLCModuleMappingIssue]
    errors: list[PLCModuleMappingIssue]

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def error_count(self) -> int:
        return len(self.errors)
