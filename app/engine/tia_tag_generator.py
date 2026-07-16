"""TIA Portal tag name helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence

from app.common.constants import PROJECT_AREAS
from app.engine.fc_io_generator import natural_tag_key
from app.model.device import Device
from app.model.signal import Signal
from app.model.tia_tag import STATUS_ERROR, STATUS_OK, STATUS_WARNING, TIATag

SIGNAL_ABBREVIATIONS: dict[str, str] = {
    "Start Command": "START_CMD",
    "Stop Command": "STOP_CMD",
    "Local/Remote Mode": "LOCAL_REMOTE",
    "Run Feedback": "RUN_FB",
    "Fault Feedback": "FAULT_FB",
}

IO_TYPE_TO_DATA_TYPE: dict[str, str] = {
    "DI": "Bool",
    "DO": "Bool",
    "AI": "Int",
    "AO": "Int",
}

_UNSUPPORTED_CHARS = re.compile(r"[^A-Z0-9_]")
_REPEATED_UNDERSCORES = re.compile(r"_+")
_TIA_AREA_ORDER = {name: index for index, name in enumerate(PROJECT_AREAS)}
_TIA_IO_ORDER = {name: index for index, name in enumerate(("DI", "DO", "AI", "AO"))}
_TIA_IO_ADDRESS_PATTERNS = {
    "DI": re.compile(r"^%I\d+\.\d+$", re.IGNORECASE),
    "DO": re.compile(r"^%Q\d+\.\d+$", re.IGNORECASE),
    "AI": re.compile(r"^%IW\d+$", re.IGNORECASE),
    "AO": re.compile(r"^%QW\d+$", re.IGNORECASE),
}
_SYMBOL_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SYMBOL_NAME_MAX_LENGTH = 128
_BLANK_ADDRESS_MESSAGE = "Enabled Signal has no PLC Address."
_ADDRESS_MISMATCH_MESSAGE = "I/O Type and logical address do not match."
_ERROR_MESSAGE_MARKERS = (
    "Duplicate TIA symbol name:",
    "Duplicate PLC logical address:",
    _ADDRESS_MISMATCH_MESSAGE,
    "Unsupported I/O Type:",
    "Failed to create TIA tag:",
    "TIA symbol name must not be blank.",
    "TIA symbol name exceeds maximum length",
    "TIA symbol name contains invalid characters",
)


def _collapse_underscores(text: str) -> str:
    """Collapse repeated underscores and trim leading/trailing ones."""
    collapsed = _REPEATED_UNDERSCORES.sub("_", text)
    return collapsed.strip("_")


def _sanitize_identifier(text: str, *, hyphen_mode: str) -> str:
    """Uppercase and keep only letters, digits, and underscores."""
    normalized = text.strip().upper().replace(" ", "_")
    if hyphen_mode == "remove":
        normalized = normalized.replace("-", "")
    elif hyphen_mode == "underscore":
        normalized = normalized.replace("-", "_").replace("/", "_")
    else:
        raise ValueError(f"Unsupported hyphen_mode: {hyphen_mode}")

    normalized = _UNSUPPORTED_CHARS.sub("", normalized)
    return _collapse_underscores(normalized)


def normalize_device_tag(device_tag: str) -> str:
    """Normalize a device tag for TIA symbol names."""
    result = _sanitize_identifier(device_tag, hyphen_mode="remove")
    if not result:
        return "TAG_UNKNOWN"
    if result[0].isdigit():
        return f"TAG_{result}"
    return result


def abbreviate_signal_name(signal_name: str) -> str:
    """Return a stable abbreviation for a signal name."""
    trimmed = signal_name.strip()
    for canonical_name, abbreviation in SIGNAL_ABBREVIATIONS.items():
        if trimmed.lower() == canonical_name.lower():
            return abbreviation

    result = _sanitize_identifier(trimmed, hyphen_mode="underscore")
    return result or "SIGNAL_UNKNOWN"


def build_symbol_name(device_tag: str, signal_name: str) -> str:
    """Build a TIA symbol name from device tag and signal name."""
    return f"{normalize_device_tag(device_tag)}_{abbreviate_signal_name(signal_name)}"


def map_io_type_to_data_type(io_type: str) -> str:
    """Map a device I/O type to the TIA Portal data type."""
    key = io_type.strip().upper()
    if not key:
        return ""
    return IO_TYPE_TO_DATA_TYPE.get(key, "")


def convert_to_tia_logical_address(address: str) -> str:
    """Convert a PLC address to a TIA Portal logical address."""
    trimmed = address.strip()
    if not trimmed:
        return ""
    if trimmed.startswith("%"):
        return f"%{trimmed[1:].upper()}"
    return f"%{trimmed.upper()}"


def build_tag_comment(device: Device, signal: Signal) -> str:
    """Build a TIA tag comment from device and signal metadata."""
    signal_text = signal.description.strip() or signal.name.strip()
    parts = [
        device.area.strip(),
        device.description.strip(),
        signal_text,
    ]
    return " | ".join(part for part in parts if part)


def _resolve_device_type(device: Device) -> str:
    """Return device type from whichever field the model provides."""
    device_type = getattr(device, "device_type", "")
    if isinstance(device_type, str) and device_type.strip():
        return device_type
    return device.type


def create_tia_tag(
    device: Device,
    signal: Signal,
    signal_order: int = 0,
) -> TIATag:
    """Convert one device signal into a TIATag."""
    data_type = map_io_type_to_data_type(signal.io_type)
    logical_address = convert_to_tia_logical_address(signal.address)
    validation_messages: list[str] = []
    status = STATUS_OK

    if not signal.address.strip():
        validation_messages.append(_BLANK_ADDRESS_MESSAGE)
        status = STATUS_WARNING

    if not data_type:
        io_value = signal.io_type.strip()
        validation_messages.append(f"Unsupported I/O Type: {io_value}")
        status = STATUS_ERROR

    return TIATag(
        symbol_name=build_symbol_name(device.tag, signal.name),
        data_type=data_type,
        logical_address=logical_address,
        comment=build_tag_comment(device, signal),
        area=device.area,
        device_type=_resolve_device_type(device),
        device_tag=device.tag,
        signal_name=signal.name,
        io_type=signal.io_type.strip().upper(),
        status=status,
        validation_messages=validation_messages,
        signal_order=signal_order,
    )


def _create_error_tia_tag(
    device: Device,
    signal: Signal,
    signal_order: int,
    error_message: str,
) -> TIATag:
    """Build an ERROR TIATag when tag creation fails unexpectedly."""
    return TIATag(
        symbol_name=build_symbol_name(device.tag, signal.name),
        data_type=map_io_type_to_data_type(signal.io_type),
        logical_address=convert_to_tia_logical_address(signal.address),
        comment=build_tag_comment(device, signal),
        area=device.area,
        device_type=_resolve_device_type(device),
        device_tag=device.tag,
        signal_name=signal.name,
        io_type=signal.io_type.strip().upper(),
        status=STATUS_ERROR,
        validation_messages=[error_message],
        signal_order=signal_order,
    )


def generate_device_tags(device: Device) -> list[TIATag]:
    """Generate TIA tags for all enabled signals on one device."""
    signals = getattr(device, "signals", None) or []
    tags: list[TIATag] = []

    for index, signal in enumerate(signals):
        if not signal.enabled:
            continue
        try:
            tags.append(create_tia_tag(device, signal, signal_order=index))
        except Exception as exc:
            tags.append(
                _create_error_tia_tag(
                    device,
                    signal,
                    signal_order=index,
                    error_message=f"Failed to create TIA tag: {exc}",
                )
            )

    return tags


def _create_device_error_tia_tag(
    device: Device,
    device_order: int,
    error_message: str,
) -> TIATag:
    """Build an ERROR TIATag when device-wide tag generation fails."""
    return TIATag(
        symbol_name=f"ERROR_{normalize_device_tag(device.tag)}",
        data_type="",
        logical_address="",
        comment="Failed to generate TIA Tags for Device.",
        area=device.area,
        device_type=_resolve_device_type(device),
        device_tag=device.tag,
        status=STATUS_ERROR,
        validation_messages=[error_message],
        device_order=device_order,
    )


def _assign_device_order(tags: list[TIATag], device_order: int) -> list[TIATag]:
    """Stamp all tags from one device with the same project order."""
    for tag in tags:
        tag.device_order = device_order
    return tags


def generate_project_tags(devices: Iterable[Device] | None) -> list[TIATag]:
    """Generate TIA tags for all enabled signals across a project."""
    if not devices:
        return []

    tags: list[TIATag] = []
    for device_order, device in enumerate(devices):
        if device is None:
            continue
        try:
            device_tags = generate_device_tags(device)
            tags.extend(_assign_device_order(device_tags, device_order))
        except Exception as exc:
            tags.append(
                _create_device_error_tia_tag(
                    device,
                    device_order=device_order,
                    error_message=str(exc),
                )
            )

    return tags


def _device_type_sort_key(device_type: str) -> tuple[int, str]:
    """Sort key that places blank device types after non-blank values."""
    text = device_type.strip()
    if not text:
        return (1, "")
    return (0, text.casefold())


def _tia_tag_sort_key(tag: TIATag) -> tuple:
    """Sort key for project TIA tags."""
    area_rank = _TIA_AREA_ORDER.get(tag.area.strip().upper(), len(_TIA_AREA_ORDER))
    io_rank = _TIA_IO_ORDER.get(tag.io_type.strip().upper(), len(_TIA_IO_ORDER))
    return (
        area_rank,
        _device_type_sort_key(tag.device_type),
        natural_tag_key(tag.device_tag),
        tag.device_order,
        io_rank,
        tag.signal_order,
    )


def sort_tia_tags(tags: Sequence[TIATag]) -> list[TIATag]:
    """Return a new list of TIA tags sorted by project display order."""
    return sorted(tags, key=_tia_tag_sort_key)


def _append_unique_message(messages: list[str], message: str) -> bool:
    """Append a validation message when it is not already present."""
    if message in messages:
        return False
    messages.append(message)
    return True


def _message_is_error(message: str) -> bool:
    """Return True when a validation message represents an error."""
    return any(marker in message for marker in _ERROR_MESSAGE_MARKERS)


def _resolve_tag_status(tag: TIATag) -> str:
    """Resolve tag status from accumulated validation messages."""
    if any(_message_is_error(message) for message in tag.validation_messages):
        return STATUS_ERROR
    if tag.validation_messages:
        return STATUS_WARNING
    return STATUS_OK


def _validate_symbol_name(tag: TIATag, errors: list[str]) -> None:
    """Validate one TIA symbol name."""
    name = tag.symbol_name
    if not name.strip():
        message = "TIA symbol name must not be blank."
    elif len(name) > _SYMBOL_NAME_MAX_LENGTH:
        message = (
            f"TIA symbol name exceeds maximum length of "
            f"{_SYMBOL_NAME_MAX_LENGTH} characters."
        )
    elif not _SYMBOL_NAME_PATTERN.fullmatch(name):
        message = (
            "TIA symbol name contains invalid characters or begins with a digit."
        )
    else:
        return

    _append_unique_message(tag.validation_messages, message)
    tag.status = STATUS_ERROR
    errors.append(
        f"{message} | Device Tag: {tag.device_tag} | Signal Name: {tag.signal_name}"
    )


def validate_tia_tags(tags: Sequence[TIATag]) -> tuple[list[str], list[str]]:
    """Validate project TIA tags and update tag status and messages."""
    warnings: list[str] = []
    errors: list[str] = []

    symbol_groups: dict[str, list[TIATag]] = defaultdict(list)
    for tag in tags:
        symbol_key = tag.symbol_name.casefold()
        if symbol_key:
            symbol_groups[symbol_key].append(tag)

    for group in symbol_groups.values():
        if len(group) < 2:
            continue
        symbol_name = group[0].symbol_name
        message = f"Duplicate TIA symbol name: {symbol_name}"
        for tag in group:
            _append_unique_message(tag.validation_messages, message)
            tag.status = STATUS_ERROR
            errors.append(
                "Duplicate TIA symbol name: "
                f"{symbol_name} | Device Tag: {tag.device_tag} | "
                f"Signal Name: {tag.signal_name}"
            )

    address_groups: dict[str, list[TIATag]] = defaultdict(list)
    for tag in tags:
        address = tag.logical_address.strip()
        if address:
            address_groups[address.casefold()].append(tag)

    for group in address_groups.values():
        if len(group) < 2:
            continue
        address = group[0].logical_address
        message = f"Duplicate PLC logical address: {address}"
        for tag in group:
            _append_unique_message(tag.validation_messages, message)
            tag.status = STATUS_ERROR
            errors.append(
                "Duplicate PLC logical address: "
                f"{address} | Device Tag: {tag.device_tag} | "
                f"Signal Name: {tag.signal_name}"
            )

    for tag in tags:
        if not tag.logical_address.strip():
            if _append_unique_message(tag.validation_messages, _BLANK_ADDRESS_MESSAGE):
                warnings.append(
                    f"{_BLANK_ADDRESS_MESSAGE} | Device Tag: {tag.device_tag} | "
                    f"Signal Name: {tag.signal_name}"
                )
            if tag.status != STATUS_ERROR:
                tag.status = STATUS_WARNING

        address = tag.logical_address.strip()
        if address:
            io_type = tag.io_type.strip().upper()
            pattern = _TIA_IO_ADDRESS_PATTERNS.get(io_type)
            if pattern is None or not pattern.fullmatch(address):
                if _append_unique_message(
                    tag.validation_messages,
                    _ADDRESS_MISMATCH_MESSAGE,
                ):
                    errors.append(
                        f"{_ADDRESS_MISMATCH_MESSAGE} | Device Tag: {tag.device_tag} | "
                        f"Signal Name: {tag.signal_name} | I/O Type: {tag.io_type} | "
                        f"Address: {tag.logical_address}"
                    )
                tag.status = STATUS_ERROR

        _validate_symbol_name(tag, errors)
        tag.status = _resolve_tag_status(tag)

    return warnings, errors


def generate_sorted_validated_project_tags(
    devices: Iterable[Device] | None,
) -> tuple[list[TIATag], list[str], list[str]]:
    """Generate, sort, and validate project TIA tags."""
    tags = generate_project_tags(devices)
    sorted_tags = sort_tia_tags(tags)
    warnings, errors = validate_tia_tags(sorted_tags)
    return sorted_tags, warnings, errors
