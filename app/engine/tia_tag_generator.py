"""TIA Portal tag name helpers."""

from __future__ import annotations

import re

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
        validation_messages.append("Enabled Signal has no PLC Address.")
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
