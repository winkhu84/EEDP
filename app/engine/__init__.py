"""Processing engine layer."""

from app.engine.address_manager import (
    AddressConflict,
    AssignResult,
    apply_default_use_start_flags,
    apply_start_addresses,
    assign_device_addresses,
    assign_project_addresses,
    clear_device_addresses,
    find_address_conflicts,
    format_conflict_message,
    increment_analog_address,
    increment_digital_address,
    parse_analog_address,
    parse_digital_address,
    validate_device_start_addresses,
)
from app.engine.address_usage_engine import (
    CardUsage,
    ChannelUsage,
    build_all_card_usage,
    build_card_usage,
    collect_project_addresses,
    find_address_assignments,
    group_digital_addresses_by_card,
)
from app.engine.device_manager import (
    AddDevicesResult,
    DeviceDraft,
    DeviceManager,
    expand_sequential_tags,
    suggest_next_tag,
)
from app.engine.fc_io_generator import (
    FCIOGenerationResult,
    FCIOIssue,
    generate_device_rows,
    generate_project_rows,
    sort_devices,
    sort_fc_io_rows,
    validate_fc_io_rows,
)
from app.engine.io_list_parser import IoListParseResult, IoListParser
from app.engine.io_summary_engine import summarize_device, summarize_project
from app.engine.plc_card_calculator import (
    PlcCardRequirement,
    calculate_card_requirement,
    calculate_project_cards,
)
from app.engine.recommendation_engine import RecommendationEngine, build_io_summary
from app.engine.rule_engine import (
    DeviceRule,
    RuleEngine,
    SignalRule,
    UNKNOWN_DEVICE,
)
from app.engine.signal_engine import SignalEngine
from app.engine.tag_type_resolver import resolve_device_category, resolve_device_type

__all__ = [
    "AddDevicesResult",
    "AddressConflict",
    "AssignResult",
    "CardUsage",
    "ChannelUsage",
    "DeviceDraft",
    "DeviceManager",
    "DeviceRule",
    "FCIOGenerationResult",
    "FCIOIssue",
    "IoListParseResult",
    "IoListParser",
    "PlcCardRequirement",
    "RecommendationEngine",
    "RuleEngine",
    "SignalEngine",
    "SignalRule",
    "UNKNOWN_DEVICE",
    "apply_default_use_start_flags",
    "apply_start_addresses",
    "assign_device_addresses",
    "assign_project_addresses",
    "build_all_card_usage",
    "build_card_usage",
    "build_io_summary",
    "calculate_card_requirement",
    "calculate_project_cards",
    "clear_device_addresses",
    "collect_project_addresses",
    "expand_sequential_tags",
    "find_address_assignments",
    "find_address_conflicts",
    "format_conflict_message",
    "generate_device_rows",
    "generate_project_rows",
    "group_digital_addresses_by_card",
    "increment_analog_address",
    "increment_digital_address",
    "parse_analog_address",
    "parse_digital_address",
    "resolve_device_category",
    "resolve_device_type",
    "sort_devices",
    "sort_fc_io_rows",
    "suggest_next_tag",
    "summarize_device",
    "summarize_project",
    "validate_device_start_addresses",
    "validate_fc_io_rows",
]
