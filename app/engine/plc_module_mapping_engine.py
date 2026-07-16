"""PLC module and channel mapping engine."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from app.common.constants import PROJECT_AREAS
from app.engine.address_manager import (
    increment_analog_address,
    increment_digital_address,
    parse_analog_address,
    parse_digital_address,
)
from app.engine.address_usage_engine import (
    group_analog_addresses_by_card,
    group_digital_addresses_by_card,
)
from app.engine.fc_io_generator import natural_tag_key
from app.model.device import Device
from app.model.plc_card_config import PlcCardConfig, default_plc_card_configurations
from app.model.plc_module_mapping import (
    STATUS_CONFLICT,
    STATUS_SPARE,
    STATUS_USED,
    PLCChannelAssignment,
    PLCChannelMapping,
    PLCModuleMapping,
    PLCModuleMappingIssue,
    PLCModuleMappingResult,
    PLCModuleTypeSummary,
)

_IO_ORDER = ("DI", "DO", "AI", "AO")
_AREA_ORDER = {name: index for index, name in enumerate(PROJECT_AREAS)}
_VALID_IO = frozenset(_IO_ORDER)


def collect_signal_assignments(
    devices: Sequence[Device],
) -> tuple[list[PLCChannelAssignment], list[PLCModuleMappingIssue]]:
    """Collect enabled addressed signals and related warnings."""
    assignments: list[PLCChannelAssignment] = []
    warnings: list[PLCModuleMappingIssue] = []

    for device in devices:
        for index, signal in enumerate(device.signals):
            if not signal.enabled:
                continue
            io_type = (signal.io_type or "").strip().upper()
            address = (signal.address or "").strip()

            if not address:
                warnings.append(
                    PLCModuleMappingIssue(
                        severity="warning",
                        code="MISSING_PLC_ADDRESS",
                        message="Enabled Signal without address",
                        device_tag=device.tag,
                        signal_name=signal.name,
                        io_type=io_type,
                    )
                )
                continue

            if io_type not in _VALID_IO:
                warnings.append(
                    PLCModuleMappingIssue(
                        severity="warning",
                        code="UNSUPPORTED_IO_TYPE",
                        message=f"Unsupported I/O Type: {signal.io_type or '(blank)'}",
                        device_tag=device.tag,
                        signal_name=signal.name,
                        plc_address=address,
                        io_type=io_type,
                    )
                )
                continue

            if io_type in {"DI", "DO"}:
                try:
                    parsed = parse_digital_address(address)
                except ValueError:
                    warnings.append(
                        PLCModuleMappingIssue(
                            severity="warning",
                            code="INVALID_ADDRESS_FORMAT",
                            message=f"Address outside recognized format: {address}",
                            device_tag=device.tag,
                            signal_name=signal.name,
                            plc_address=address,
                            io_type=io_type,
                        )
                    )
                    continue
                expected_prefix = "I" if io_type == "DI" else "Q"
                if parsed.prefix != expected_prefix:
                    # Still map by address format; flag type mismatch as error later.
                    pass
            else:
                try:
                    parsed_a = parse_analog_address(address)
                except ValueError:
                    warnings.append(
                        PLCModuleMappingIssue(
                            severity="warning",
                            code="INVALID_ADDRESS_FORMAT",
                            message=f"Address outside recognized format: {address}",
                            device_tag=device.tag,
                            signal_name=signal.name,
                            plc_address=address,
                            io_type=io_type,
                        )
                    )
                    continue
                if parsed_a.word % 2 != 0:
                    warnings.append(
                        PLCModuleMappingIssue(
                            severity="warning",
                            code="ANALOG_ALIGNMENT",
                            message=(
                                f"Analog address not aligned to 2 bytes: {address}"
                            ),
                            device_tag=device.tag,
                            signal_name=signal.name,
                            plc_address=address,
                            io_type=io_type,
                        )
                    )

            assignments.append(
                PLCChannelAssignment(
                    device_tag=device.tag,
                    device_type=device.type,
                    area=device.area,
                    signal_name=signal.name,
                    io_type=io_type,
                    plc_address=address,
                    signal_order=index,
                )
            )

    return assignments, warnings


def get_digital_card_index(byte_address: int, channels_per_card: int) -> int:
    """Return 1-based digital card index from byte address."""
    if channels_per_card <= 0:
        raise ValueError("channels_per_card must be greater than zero.")
    bytes_per_card = channels_per_card // 8
    if bytes_per_card <= 0:
        bytes_per_card = 4
    return (byte_address // bytes_per_card) + 1


def get_analog_card_index(
    word_address: int,
    base_address: int,
    channels_per_card: int,
) -> int:
    """Return 1-based analog card index relative to a base word address."""
    if channels_per_card <= 0:
        raise ValueError("channels_per_card must be greater than zero.")
    relative = max(0, word_address - base_address)
    channel_index = relative // 2
    return (channel_index // channels_per_card) + 1


def _sort_assignments(
    assignments: Sequence[PLCChannelAssignment],
) -> list[PLCChannelAssignment]:
    def key(item: PLCChannelAssignment) -> tuple:
        area_rank = _AREA_ORDER.get(item.area.strip().upper(), len(_AREA_ORDER) + 1)
        return (
            area_rank,
            natural_tag_key(item.device_tag),
            item.signal_order,
            item.signal_name.casefold(),
        )

    return sorted(assignments, key=key)


def _config_map(
    configs: Sequence[PlcCardConfig],
) -> dict[str, PlcCardConfig]:
    mapping = {
        config.io_type.strip().upper(): config
        for config in configs
    }
    defaults = default_plc_card_configurations()
    for config in defaults:
        mapping.setdefault(config.io_type, config)
    return mapping


def _index_by_address(
    assignments: Sequence[PLCChannelAssignment],
) -> dict[str, list[PLCChannelAssignment]]:
    by_address: dict[str, list[PLCChannelAssignment]] = defaultdict(list)
    for item in assignments:
        by_address[item.plc_address.strip().upper()].append(item)
    return by_address


def _channel_status(count: int) -> str:
    if count <= 0:
        return STATUS_SPARE
    if count == 1:
        return STATUS_USED
    return STATUS_CONFLICT


def build_digital_card_mapping(
    assignments: Sequence[PLCChannelAssignment],
    io_type: str,
    channels_per_card: int,
    *,
    module_name: str,
    rack_slot: dict[tuple[str, int], tuple[str, str]] | None = None,
) -> list[PLCModuleMapping]:
    """Build DI/DO card mappings from assignments of one I/O type."""
    io_type = io_type.strip().upper()
    prefix = "I" if io_type == "DI" else "Q"
    typed = [item for item in assignments if item.io_type == io_type]
    addresses = [item.plc_address for item in typed]
    # Also include addresses that parse as this prefix even if io_type mismatched.
    by_address = _index_by_address(assignments)
    for address in list(by_address.keys()):
        try:
            parsed = parse_digital_address(address)
        except ValueError:
            continue
        if parsed.prefix == prefix:
            addresses.append(address)

    blocks = group_digital_addresses_by_card(addresses, prefix, channels_per_card)
    modules: list[PLCModuleMapping] = []
    rack_slot = rack_slot or {}

    for card_number, start_address, end_address in blocks:
        channels: list[PLCChannelMapping] = []
        used = 0
        conflicts = 0
        for offset in range(channels_per_card):
            address = increment_digital_address(start_address, offset)
            occupants = _sort_assignments(by_address.get(address.upper(), ()))
            status = _channel_status(len(occupants))
            if status == STATUS_USED:
                used += 1
            elif status == STATUS_CONFLICT:
                used += 1
                conflicts += 1
            channels.append(
                PLCChannelMapping(
                    channel_index=offset,
                    channel_address=address,
                    status=status,
                    assignments=list(occupants),
                )
            )
        rack, slot = rack_slot.get((io_type, card_number), ("", ""))
        modules.append(
            PLCModuleMapping(
                io_type=io_type,
                module_name=module_name,
                channels_per_card=channels_per_card,
                card_number=card_number,
                start_address=start_address,
                end_address=end_address,
                used_channels=used,
                spare_channels=channels_per_card - used,
                conflict_channels=conflicts,
                rack=rack,
                slot=slot,
                channels=channels,
            )
        )
    return modules


def build_analog_card_mapping(
    assignments: Sequence[PLCChannelAssignment],
    io_type: str,
    channels_per_card: int,
    *,
    module_name: str,
    rack_slot: dict[tuple[str, int], tuple[str, str]] | None = None,
) -> list[PLCModuleMapping]:
    """Build AI/AO card mappings from assignments of one I/O type."""
    io_type = io_type.strip().upper()
    prefix = "IW" if io_type == "AI" else "QW"
    typed = [item for item in assignments if item.io_type == io_type]
    addresses = [item.plc_address for item in typed]
    by_address = _index_by_address(assignments)
    for address in list(by_address.keys()):
        try:
            parsed = parse_analog_address(address)
        except ValueError:
            continue
        if parsed.prefix == prefix:
            addresses.append(address)

    blocks = group_analog_addresses_by_card(addresses, prefix, channels_per_card)
    modules: list[PLCModuleMapping] = []
    rack_slot = rack_slot or {}

    for card_number, start_address, end_address in blocks:
        channels: list[PLCChannelMapping] = []
        used = 0
        conflicts = 0
        for offset in range(channels_per_card):
            address = increment_analog_address(start_address, offset)
            occupants = _sort_assignments(by_address.get(address.upper(), ()))
            status = _channel_status(len(occupants))
            if status == STATUS_USED:
                used += 1
            elif status == STATUS_CONFLICT:
                used += 1
                conflicts += 1
            channels.append(
                PLCChannelMapping(
                    channel_index=offset,
                    channel_address=address,
                    status=status,
                    assignments=list(occupants),
                )
            )
        rack, slot = rack_slot.get((io_type, card_number), ("", ""))
        modules.append(
            PLCModuleMapping(
                io_type=io_type,
                module_name=module_name,
                channels_per_card=channels_per_card,
                card_number=card_number,
                start_address=start_address,
                end_address=end_address,
                used_channels=used,
                spare_channels=channels_per_card - used,
                conflict_channels=conflicts,
                rack=rack,
                slot=slot,
                channels=channels,
            )
        )
    return modules


def validate_mapping(
    modules: Sequence[PLCModuleMapping],
    assignments: Sequence[PLCChannelAssignment],
) -> tuple[list[PLCModuleMappingIssue], list[PLCModuleMappingIssue]]:
    """Validate mapping occupancy and address/type consistency."""
    warnings: list[PLCModuleMappingIssue] = []
    errors: list[PLCModuleMappingIssue] = []

    by_address = _index_by_address(assignments)
    for address, occupants in by_address.items():
        if len(occupants) > 1:
            detail = "; ".join(
                f"{item.device_tag} / {item.signal_name}" for item in occupants
            )
            for item in occupants:
                errors.append(
                    PLCModuleMappingIssue(
                        severity="error",
                        code="DUPLICATE_PLC_ADDRESS",
                        message=f"Duplicate PLC Address {address}: {detail}",
                        device_tag=item.device_tag,
                        signal_name=item.signal_name,
                        plc_address=item.plc_address,
                        io_type=item.io_type,
                    )
                )

        for item in occupants:
            expected_digital = "I" if item.io_type == "DI" else "Q"
            expected_analog = "IW" if item.io_type == "AI" else "QW"
            try:
                if item.io_type in {"DI", "DO"}:
                    parsed = parse_digital_address(item.plc_address)
                    if parsed.prefix != expected_digital:
                        errors.append(
                            PLCModuleMappingIssue(
                                severity="error",
                                code="ADDRESS_IO_TYPE_MISMATCH",
                                message=(
                                    f"Channel address does not match Signal I/O Type: "
                                    f"{item.plc_address} vs {item.io_type}"
                                ),
                                device_tag=item.device_tag,
                                signal_name=item.signal_name,
                                plc_address=item.plc_address,
                                io_type=item.io_type,
                            )
                        )
                else:
                    parsed_a = parse_analog_address(item.plc_address)
                    if parsed_a.prefix != expected_analog:
                        errors.append(
                            PLCModuleMappingIssue(
                                severity="error",
                                code="ADDRESS_IO_TYPE_MISMATCH",
                                message=(
                                    f"Channel address does not match Signal I/O Type: "
                                    f"{item.plc_address} vs {item.io_type}"
                                ),
                                device_tag=item.device_tag,
                                signal_name=item.signal_name,
                                plc_address=item.plc_address,
                                io_type=item.io_type,
                            )
                        )
            except ValueError:
                continue

    # Duplicate rack/slot when both entered.
    rack_slot_map: dict[tuple[str, str], list[PLCModuleMapping]] = defaultdict(list)
    for module in modules:
        rack = module.rack.strip()
        slot = module.slot.strip()
        if rack and slot:
            rack_slot_map[(rack, slot)].append(module)
    for (rack, slot), cards in rack_slot_map.items():
        if len(cards) < 2:
            continue
        for module in cards:
            errors.append(
                PLCModuleMappingIssue(
                    severity="error",
                    code="DUPLICATE_RACK_SLOT",
                    message=(
                        f"Duplicate Rack/Slot {rack}/{slot} on "
                        f"{module.io_type} Card {module.card_number}"
                    ),
                    io_type=module.io_type,
                )
            )

    return warnings, errors


def _build_summaries(
    modules: Sequence[PLCModuleMapping],
    configs: dict[str, PlcCardConfig],
) -> list[PLCModuleTypeSummary]:
    summaries: list[PLCModuleTypeSummary] = []
    by_type: dict[str, list[PLCModuleMapping]] = defaultdict(list)
    for module in modules:
        by_type[module.io_type].append(module)

    for io_type in _IO_ORDER:
        config = configs[io_type]
        cards = by_type.get(io_type, [])
        used = sum(card.used_channels for card in cards)
        conflicts = sum(card.conflict_channels for card in cards)
        total = sum(card.channels_per_card for card in cards)
        spare = sum(card.spare_channels for card in cards)
        summaries.append(
            PLCModuleTypeSummary(
                io_type=io_type,
                module_name=config.module_name,
                cards=len(cards),
                used=used,
                total_channels=total,
                spare=spare,
                conflicts=conflicts,
            )
        )
    return summaries


def build_project_module_mapping(
    devices: Sequence[Device],
    card_configurations: Sequence[PlcCardConfig] | None = None,
    *,
    rack_slot: dict[tuple[str, int], tuple[str, str]] | None = None,
) -> PLCModuleMappingResult:
    """Build complete PLC module/channel mapping for the project."""
    configs = _config_map(
        tuple(card_configurations)
        if card_configurations is not None
        else default_plc_card_configurations()
    )
    assignments, collect_warnings = collect_signal_assignments(devices)

    modules: list[PLCModuleMapping] = []
    for io_type in _IO_ORDER:
        config = configs[io_type]
        if io_type in {"DI", "DO"}:
            modules.extend(
                build_digital_card_mapping(
                    assignments,
                    io_type,
                    config.channels_per_card,
                    module_name=config.module_name,
                    rack_slot=rack_slot,
                )
            )
        else:
            modules.extend(
                build_analog_card_mapping(
                    assignments,
                    io_type,
                    config.channels_per_card,
                    module_name=config.module_name,
                    rack_slot=rack_slot,
                )
            )

    modules.sort(
        key=lambda module: (
            _IO_ORDER.index(module.io_type),
            module.card_number,
            module.start_address,
        )
    )

    extra_warnings, errors = validate_mapping(modules, assignments)
    warnings = list(collect_warnings) + list(extra_warnings)
    summaries = _build_summaries(modules, configs)

    return PLCModuleMappingResult(
        modules=modules,
        summaries=summaries,
        warnings=warnings,
        errors=errors,
    )
