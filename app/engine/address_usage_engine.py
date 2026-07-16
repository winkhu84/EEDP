"""PLC address usage analysis for the Address Usage Monitor."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.engine.address_manager import (
    increment_analog_address,
    increment_digital_address,
    parse_analog_address,
    parse_digital_address,
)
from app.model.device import Device
from app.model.plc_card_config import PlcCardConfig, default_plc_card_configurations

STATUS_SPARE = "spare"
STATUS_USED = "used"
STATUS_CONFLICT = "conflict"


@dataclass(frozen=True)
class AddressAssignment:
    """One device signal occupying a PLC address."""

    device_tag: str
    signal_name: str
    io_type: str
    device_id: str = ""


@dataclass(frozen=True)
class ChannelUsage:
    """Usage status for one PLC channel address."""

    address: str
    status: str
    assignments: tuple[AddressAssignment, ...] = ()

    def tooltip(self) -> str:
        if self.status == STATUS_SPARE:
            return f"Address: {self.address}\nStatus: Spare"
        if self.status == STATUS_CONFLICT:
            lines = [
                f"Address: {self.address}",
                "Conflict detected",
                "",
            ]
            for item in self.assignments:
                lines.append(f"{item.device_tag} / {item.signal_name}")
            return "\n".join(lines)
        # used
        if not self.assignments:
            return f"Address: {self.address}\nStatus: Used"
        first = self.assignments[0]
        return (
            f"Address: {self.address}\n"
            f"Device: {first.device_tag}\n"
            f"Signal: {first.signal_name}\n"
            f"I/O Type: {first.io_type}"
        )


@dataclass(frozen=True)
class CardUsage:
    """One physical card block with channel occupancy."""

    io_type: str
    module_name: str
    card_index: int
    start_address: str
    end_address: str
    used: int
    spare: int
    conflicts: int
    channels: tuple[ChannelUsage, ...] = ()

    def combo_label(self) -> str:
        return (
            f"{self.io_type} Card {self.card_index}: "
            f"{self.start_address} - {self.end_address}"
        )

    def as_dict(self) -> dict:
        return {
            "io_type": self.io_type,
            "module_name": self.module_name,
            "card_index": self.card_index,
            "start_address": self.start_address,
            "end_address": self.end_address,
            "used": self.used,
            "spare": self.spare,
            "conflicts": self.conflicts,
            "channels": [
                {
                    "address": channel.address,
                    "status": channel.status,
                    "assignments": [
                        {
                            "device_tag": item.device_tag,
                            "signal_name": item.signal_name,
                        }
                        for item in channel.assignments
                    ],
                }
                for channel in self.channels
            ],
        }


@dataclass
class ProjectAddressIndex:
    """Normalized address → assignments map for the project."""

    by_address: dict[str, list[AddressAssignment]] = field(default_factory=dict)

    def get(self, address: str) -> list[AddressAssignment]:
        return list(self.by_address.get(_normalize_address(address), ()))


def _normalize_address(address: str) -> str:
    return address.strip().upper()


def collect_project_addresses(
    devices: Sequence[Device],
) -> ProjectAddressIndex:
    """Collect enabled signals that have a non-empty PLC address."""
    index = ProjectAddressIndex()
    for device in devices:
        for signal in device.signals:
            if not signal.enabled:
                continue
            address = signal.address.strip()
            if not address:
                continue
            key = _normalize_address(address)
            index.by_address.setdefault(key, []).append(
                AddressAssignment(
                    device_tag=device.tag,
                    signal_name=signal.name,
                    io_type=signal.io_type.strip().upper(),
                    device_id=device.id,
                )
            )
    return index


def find_address_assignments(
    devices: Sequence[Device],
    address: str,
) -> list[AddressAssignment]:
    """Return all assignments for one address (case-insensitive)."""
    return collect_project_addresses(devices).get(address)


def _config_for_io_type(
    io_type: str,
    configs: Sequence[PlcCardConfig],
) -> PlcCardConfig:
    key = io_type.strip().upper()
    for config in configs:
        if config.io_type.strip().upper() == key:
            return config
    defaults = {
        "DI": PlcCardConfig("DI", "DI 32CH", 32),
        "DO": PlcCardConfig("DO", "DO 32CH", 32),
        "AI": PlcCardConfig("AI", "AI 8CH", 8),
        "AO": PlcCardConfig("AO", "AO 8CH", 8),
    }
    return defaults[key]


def _digital_prefix(io_type: str) -> str:
    return "I" if io_type.upper() == "DI" else "Q"


def _analog_prefix(io_type: str) -> str:
    return "IW" if io_type.upper() == "AI" else "QW"


def _channel_status(assignments: list[AddressAssignment]) -> str:
    if not assignments:
        return STATUS_SPARE
    if len(assignments) > 1:
        return STATUS_CONFLICT
    return STATUS_USED


def group_digital_addresses_by_card(
    addresses: Sequence[str],
    prefix: str,
    channels_per_card: int,
) -> list[tuple[int, str, str]]:
    """Return sorted (card_index, start_address, end_address) blocks in use.

    Card blocks are contiguous four-byte (32-bit) groups for a 32CH card.
    Card index is 1-based relative to absolute byte 0.
    """
    if channels_per_card <= 0:
        raise ValueError("channels_per_card must be greater than zero.")

    prefix = prefix.upper()
    card_indices: set[int] = set()
    for address in addresses:
        try:
            parsed = parse_digital_address(address)
        except ValueError:
            continue
        if parsed.prefix != prefix:
            continue
        bit_index = parsed.byte * 8 + parsed.bit
        card_indices.add(bit_index // channels_per_card)

    blocks: list[tuple[int, str, str]] = []
    for card_zero in sorted(card_indices):
        start_bit = card_zero * channels_per_card
        end_bit = start_bit + channels_per_card - 1
        start = f"{prefix}{start_bit // 8}.{start_bit % 8}"
        end = f"{prefix}{end_bit // 8}.{end_bit % 8}"
        blocks.append((card_zero + 1, start, end))
    return blocks


def group_analog_addresses_by_card(
    addresses: Sequence[str],
    prefix: str,
    channels_per_card: int,
) -> list[tuple[int, str, str]]:
    """Group analog word addresses into channel-capacity card blocks."""
    if channels_per_card <= 0:
        raise ValueError("channels_per_card must be greater than zero.")

    prefix = prefix.upper()
    card_indices: set[int] = set()
    for address in addresses:
        try:
            parsed = parse_analog_address(address)
        except ValueError:
            continue
        if parsed.prefix != prefix:
            continue
        channel_index = parsed.word // 2
        card_indices.add(channel_index // channels_per_card)

    blocks: list[tuple[int, str, str]] = []
    for card_zero in sorted(card_indices):
        start_channel = card_zero * channels_per_card
        end_channel = start_channel + channels_per_card - 1
        start = f"{prefix}{start_channel * 2}"
        end = f"{prefix}{end_channel * 2}"
        blocks.append((card_zero + 1, start, end))
    return blocks


def _group_analog_addresses_by_card(
    addresses: Sequence[str],
    prefix: str,
    channels_per_card: int,
) -> list[tuple[int, str, str]]:
    """Backward-compatible alias for group_analog_addresses_by_card."""
    return group_analog_addresses_by_card(addresses, prefix, channels_per_card)


def _build_digital_card(
    *,
    io_type: str,
    module_name: str,
    card_index: int,
    start_address: str,
    channels_per_card: int,
    index: ProjectAddressIndex,
) -> CardUsage:
    channels: list[ChannelUsage] = []
    used = 0
    conflicts = 0
    for offset in range(channels_per_card):
        address = increment_digital_address(start_address, offset)
        assignments = tuple(index.get(address))
        status = _channel_status(list(assignments))
        if status == STATUS_USED:
            used += 1
        elif status == STATUS_CONFLICT:
            conflicts += 1
            used += 1
        channels.append(
            ChannelUsage(
                address=address,
                status=status,
                assignments=assignments,
            )
        )

    spare = channels_per_card - used
    end_address = increment_digital_address(start_address, channels_per_card - 1)
    return CardUsage(
        io_type=io_type,
        module_name=module_name,
        card_index=card_index,
        start_address=start_address,
        end_address=end_address,
        used=used,
        spare=spare,
        conflicts=conflicts,
        channels=tuple(channels),
    )


def _build_analog_card(
    *,
    io_type: str,
    module_name: str,
    card_index: int,
    start_address: str,
    channels_per_card: int,
    index: ProjectAddressIndex,
) -> CardUsage:
    channels: list[ChannelUsage] = []
    used = 0
    conflicts = 0
    for offset in range(channels_per_card):
        address = increment_analog_address(start_address, offset)
        assignments = tuple(index.get(address))
        status = _channel_status(list(assignments))
        if status == STATUS_USED:
            used += 1
        elif status == STATUS_CONFLICT:
            conflicts += 1
            used += 1
        channels.append(
            ChannelUsage(
                address=address,
                status=status,
                assignments=assignments,
            )
        )

    spare = channels_per_card - used
    end_address = increment_analog_address(start_address, channels_per_card - 1)
    return CardUsage(
        io_type=io_type,
        module_name=module_name,
        card_index=card_index,
        start_address=start_address,
        end_address=end_address,
        used=used,
        spare=spare,
        conflicts=conflicts,
        channels=tuple(channels),
    )


def build_card_usage(
    devices: Sequence[Device],
    io_type: str,
    channels_per_card: int | None = None,
    *,
    card_configurations: Sequence[PlcCardConfig] | None = None,
    selected_device_id: str | None = None,
) -> tuple[CardUsage, ...]:
    """Build card-block usage views for one I/O type from real Signal.address values.

    When no addresses of this type exist, returns an empty tuple.
    """
    del selected_device_id  # reserved for optional selected-device highlighting
    io_type = io_type.strip().upper()
    configs = (
        tuple(card_configurations)
        if card_configurations is not None
        else default_plc_card_configurations()
    )
    config = _config_for_io_type(io_type, configs)
    capacity = (
        int(channels_per_card)
        if channels_per_card is not None
        else config.channels_per_card
    )

    index = collect_project_addresses(devices)

    if io_type in {"DI", "DO"}:
        prefix = _digital_prefix(io_type)
        relevant: list[str] = []
        for address in index.by_address:
            try:
                parsed = parse_digital_address(address)
            except ValueError:
                continue
            if parsed.prefix == prefix:
                relevant.append(address)
        blocks = group_digital_addresses_by_card(relevant, prefix, capacity)
        return tuple(
            _build_digital_card(
                io_type=io_type,
                module_name=config.module_name,
                card_index=card_index,
                start_address=start,
                channels_per_card=capacity,
                index=index,
            )
            for card_index, start, _end in blocks
        )

    prefix = _analog_prefix(io_type)
    relevant = []
    for address in index.by_address:
        try:
            parsed = parse_analog_address(address)
        except ValueError:
            continue
        if parsed.prefix == prefix:
            relevant.append(address)
    blocks = _group_analog_addresses_by_card(relevant, prefix, capacity)
    return tuple(
        _build_analog_card(
            io_type=io_type,
            module_name=config.module_name,
            card_index=card_index,
            start_address=start,
            channels_per_card=capacity,
            index=index,
        )
        for card_index, start, _end in blocks
    )


def build_all_card_usage(
    devices: Sequence[Device],
    *,
    card_configurations: Sequence[PlcCardConfig] | None = None,
    selected_device_id: str | None = None,
) -> dict[str, tuple[CardUsage, ...]]:
    """Build usage cards for DI, DO, AI, and AO."""
    return {
        io_type: build_card_usage(
            devices,
            io_type,
            card_configurations=card_configurations,
            selected_device_id=selected_device_id,
        )
        for io_type in ("DI", "DO", "AI", "AO")
    }
