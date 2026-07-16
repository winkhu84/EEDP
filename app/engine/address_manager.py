"""Device-based PLC address assignment (business logic)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from app.model.device import Device
from app.model.signal import Signal

_DIGITAL_RE = re.compile(r"^([IQ])(\d+)\.(\d+)$", re.IGNORECASE)
_ANALOG_RE = re.compile(r"^(IW|QW)(\d+)$", re.IGNORECASE)

_IO_TYPES = ("DI", "DO", "AI", "AO")


@dataclass(frozen=True)
class DigitalAddress:
    """Parsed Siemens-style digital address (I/Q byte.bit)."""

    prefix: str
    byte: int
    bit: int

    def format(self) -> str:
        return f"{self.prefix}{self.byte}.{self.bit}"


@dataclass(frozen=True)
class AnalogAddress:
    """Parsed Siemens-style analog word address (IW/QW)."""

    prefix: str
    word: int

    def format(self) -> str:
        return f"{self.prefix}{self.word}"


@dataclass(frozen=True)
class AddressConflict:
    """One signal participating in a duplicate address."""

    device_tag: str
    signal_name: str
    address: str


@dataclass(frozen=True)
class AssignResult:
    """Outcome of assigning addresses to a device or project."""

    ok: bool
    errors: tuple[str, ...] = ()
    infos: tuple[str, ...] = ()
    conflicts: tuple[AddressConflict, ...] = ()


def parse_digital_address(address: str) -> DigitalAddress:
    """Parse I0.0 / Q1.7 style addresses. Raises ValueError on invalid input."""
    text = address.strip()
    if not text:
        raise ValueError("Digital address is empty.")

    match = _DIGITAL_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"Invalid digital address: {address}")

    prefix = match.group(1).upper()
    byte = int(match.group(2))
    bit = int(match.group(3))
    if byte < 0:
        raise ValueError(f"Invalid digital address byte: {address}")
    if bit < 0 or bit > 7:
        raise ValueError(f"Invalid digital address bit (must be 0-7): {address}")
    return DigitalAddress(prefix=prefix, byte=byte, bit=bit)


def increment_digital_address(address: str, offset: int) -> str:
    """Return digital address advanced by offset bits (wraps bit 7 → next byte)."""
    parsed = parse_digital_address(address)
    if offset < 0:
        raise ValueError("Digital address offset must be non-negative.")
    total_bits = parsed.byte * 8 + parsed.bit + offset
    return DigitalAddress(
        prefix=parsed.prefix,
        byte=total_bits // 8,
        bit=total_bits % 8,
    ).format()


def parse_analog_address(address: str) -> AnalogAddress:
    """Parse IW64 / QW66 style addresses. Raises ValueError on invalid input."""
    text = address.strip()
    if not text:
        raise ValueError("Analog address is empty.")

    match = _ANALOG_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"Invalid analog address: {address}")

    prefix = match.group(1).upper()
    word = int(match.group(2))
    if word < 0:
        raise ValueError(f"Invalid analog address word: {address}")
    return AnalogAddress(prefix=prefix, word=word)


def increment_analog_address(address: str, channel_offset: int) -> str:
    """Return analog address advanced by channel_offset × 2 bytes."""
    parsed = parse_analog_address(address)
    if channel_offset < 0:
        raise ValueError("Analog address offset must be non-negative.")
    return AnalogAddress(
        prefix=parsed.prefix,
        word=parsed.word + (channel_offset * 2),
    ).format()


def _start_for_io_type(device: Device, io_type: str) -> str:
    mapping = {
        "DI": device.di_start_address,
        "DO": device.do_start_address,
        "AI": device.ai_start_address,
        "AO": device.ao_start_address,
    }
    return mapping[io_type].strip()


def _use_for_io_type(device: Device, io_type: str) -> bool:
    mapping = {
        "DI": device.use_di_start_address,
        "DO": device.use_do_start_address,
        "AI": device.use_ai_start_address,
        "AO": device.use_ao_start_address,
    }
    return bool(mapping[io_type])


def _enabled_of_type(signals: list[Signal], io_type: str) -> list[Signal]:
    return [
        signal
        for signal in signals
        if signal.enabled and signal.io_type.upper() == io_type
    ]


def apply_default_use_start_flags(device: Device) -> None:
    """Default Use-Start checkboxes from currently enabled signals.

    Does not set start address text values.
    """
    device.use_di_start_address = bool(_enabled_of_type(device.signals, "DI"))
    device.use_do_start_address = bool(_enabled_of_type(device.signals, "DO"))
    device.use_ai_start_address = bool(_enabled_of_type(device.signals, "AI"))
    device.use_ao_start_address = bool(_enabled_of_type(device.signals, "AO"))


def _validate_start_address(io_type: str, start: str) -> str | None:
    """Return an error message, or None when valid."""
    try:
        if io_type == "DI":
            parsed = parse_digital_address(start)
            if parsed.prefix != "I":
                return f"DI Start Address must use prefix I (got {start})."
        elif io_type == "DO":
            parsed = parse_digital_address(start)
            if parsed.prefix != "Q":
                return f"DO Start Address must use prefix Q (got {start})."
        elif io_type == "AI":
            parsed = parse_analog_address(start)
            if parsed.prefix != "IW":
                return f"AI Start Address must use prefix IW (got {start})."
        elif io_type == "AO":
            parsed = parse_analog_address(start)
            if parsed.prefix != "QW":
                return f"AO Start Address must use prefix QW (got {start})."
        else:
            return f"Unknown I/O type: {io_type}"
    except ValueError as exc:
        return str(exc)
    return None


def validate_device_start_addresses(
    device: Device,
) -> tuple[list[str], list[str]]:
    """Validate start addresses for checked I/O types.

    Returns (errors, infos).
    """
    errors: list[str] = []
    infos: list[str] = []
    for io_type in _IO_TYPES:
        if not _use_for_io_type(device, io_type):
            continue

        enabled = _enabled_of_type(device.signals, io_type)
        if not enabled:
            infos.append(
                f"No enabled {io_type} signals exist for this Device."
            )
            continue

        start = _start_for_io_type(device, io_type)
        if not start:
            errors.append(
                f"{io_type} Start Address is required when Use {io_type} Start "
                f"is checked and enabled {io_type} signals exist."
            )
            continue
        message = _validate_start_address(io_type, start)
        if message is not None:
            errors.append(message)
    return errors, infos


def assign_device_addresses(device: Device) -> AssignResult:
    """Assign addresses for checked I/O types; clear unchecked / disabled.

    Preserves Device Signals list order within each I/O type.
    """
    errors, infos = validate_device_start_addresses(device)
    if errors:
        return AssignResult(ok=False, errors=tuple(errors), infos=tuple(infos))

    counters = {"DI": 0, "DO": 0, "AI": 0, "AO": 0}
    for signal in device.signals:
        io_type = signal.io_type.upper()
        if not signal.enabled:
            signal.address = ""
            continue
        if io_type not in counters:
            continue
        if not _use_for_io_type(device, io_type):
            signal.address = ""
            continue

        start = _start_for_io_type(device, io_type)
        offset = counters[io_type]
        if io_type in {"DI", "DO"}:
            signal.address = increment_digital_address(start, offset)
        else:
            signal.address = increment_analog_address(start, offset)
        counters[io_type] += 1

    return AssignResult(ok=True, infos=tuple(infos))


def assign_project_addresses(devices: list[Device] | tuple[Device, ...]) -> AssignResult:
    """Assign addresses for every device. Stops collecting when any device fails."""
    all_errors: list[str] = []
    all_infos: list[str] = []
    for device in devices:
        result = assign_device_addresses(device)
        for info in result.infos:
            all_infos.append(f"{device.tag}: {info}")
        if not result.ok:
            for error in result.errors:
                all_errors.append(f"{device.tag}: {error}")
    if all_errors:
        return AssignResult(
            ok=False,
            errors=tuple(all_errors),
            infos=tuple(all_infos),
        )

    conflicts = find_address_conflicts(devices)
    return AssignResult(
        ok=True,
        infos=tuple(all_infos),
        conflicts=tuple(conflicts),
    )


def clear_device_addresses(device: Device) -> None:
    """Clear start addresses, Use flags, and all signal.address values."""
    device.di_start_address = ""
    device.do_start_address = ""
    device.ai_start_address = ""
    device.ao_start_address = ""
    device.use_di_start_address = False
    device.use_do_start_address = False
    device.use_ai_start_address = False
    device.use_ao_start_address = False
    for signal in device.signals:
        signal.address = ""


def find_address_conflicts(
    devices: list[Device] | tuple[Device, ...],
) -> list[AddressConflict]:
    """Return all signals that share a duplicate non-empty PLC address."""
    by_address: dict[str, list[AddressConflict]] = defaultdict(list)
    for device in devices:
        for signal in device.signals:
            address = signal.address.strip()
            if not address:
                continue
            by_address[address].append(
                AddressConflict(
                    device_tag=device.tag,
                    signal_name=signal.name,
                    address=address,
                )
            )

    conflicts: list[AddressConflict] = []
    for address in sorted(by_address.keys()):
        entries = by_address[address]
        if len(entries) < 2:
            continue
        conflicts.extend(entries)
    return conflicts


def format_conflict_message(conflicts: list[AddressConflict] | tuple[AddressConflict, ...]) -> str:
    """Human-readable conflict warning for UI dialogs."""
    if not conflicts:
        return ""

    unique_addresses = sorted({item.address for item in conflicts})
    header = "PLC address conflict detected: " + ", ".join(unique_addresses)
    lines = [header, "", "Conflicting assignments:"]
    for item in conflicts:
        lines.append(f"- {item.device_tag} / {item.signal_name} / {item.address}")
    return "\n".join(lines)


def apply_start_addresses(
    device: Device,
    *,
    di_start: str,
    do_start: str,
    ai_start: str,
    ao_start: str,
    use_di: bool,
    use_do: bool,
    use_ai: bool,
    use_ao: bool,
) -> None:
    """Store UI start-address values and Use flags onto the device."""
    device.di_start_address = di_start.strip()
    device.do_start_address = do_start.strip()
    device.ai_start_address = ai_start.strip()
    device.ao_start_address = ao_start.strip()
    device.use_di_start_address = use_di
    device.use_do_start_address = use_do
    device.use_ai_start_address = use_ai
    device.use_ao_start_address = use_ao
