"""In-memory device manager (business logic)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from app.model.device import Device
from app.model.signal import Signal


@dataclass(frozen=True)
class DeviceDraft:
    """Form values used to create a Device."""

    area: str
    category: str
    type: str
    tag: str
    description: str
    quantity: int


@dataclass(frozen=True)
class AddDevicesResult:
    """Outcome of creating one or more devices from a draft."""

    devices: tuple[Device, ...]
    error: str | None = None
    conflicts: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.error is None and len(self.devices) > 0


def parse_tag_number(tag: str) -> tuple[str, int, int] | None:
    """Split a tag into (prefix, number, digit_width) if it ends with digits."""
    match = re.match(r"^(.*?)(\d+)$", tag.strip())
    if not match:
        return None
    digits = match.group(2)
    return match.group(1), int(digits), len(digits)


def expand_sequential_tags(base_tag: str, quantity: int) -> list[str] | None:
    """Expand a base tag into sequential tags. None when no numeric suffix."""
    parsed = parse_tag_number(base_tag)
    if parsed is None:
        return None

    prefix, start, width = parsed
    count = max(1, int(quantity))
    return [f"{prefix}{(start + offset):0{width}d}" for offset in range(count)]


def suggest_next_tag(tag: str, existing_tags: set[str]) -> str:
    """Suggest the next available tag (e.g. P-101 → P-102)."""
    parsed = parse_tag_number(tag)
    if parsed is not None:
        prefix, number, width = parsed
        while True:
            number += 1
            candidate = f"{prefix}{number:0{width}d}"
            if candidate not in existing_tags:
                return candidate

    suffix = 2
    while True:
        candidate = f"{tag}-{suffix}"
        if candidate not in existing_tags:
            return candidate
        suffix += 1


def _copy_signals(signals: list[Signal]) -> list[Signal]:
    return [
        Signal(
            name=signal.name,
            io_type=signal.io_type,
            required=signal.required,
            enabled=signal.enabled,
            address=signal.address,
            terminal=signal.terminal,
            cable=signal.cable,
            description=signal.description,
            remark=signal.remark,
        )
        for signal in signals
    ]


class DeviceManager:
    """Holds devices in memory. No persistence."""

    def __init__(self) -> None:
        self._devices: list[Device] = []

    @property
    def devices(self) -> tuple[Device, ...]:
        return tuple(self._devices)

    def tags(self) -> set[str]:
        return {device.tag for device in self._devices}

    def get_by_id(self, device_id: str) -> Device | None:
        for device in self._devices:
            if device.id == device_id:
                return device
        return None

    def get_by_tag(self, tag: str) -> Device | None:
        for device in self._devices:
            if device.tag == tag:
                return device
        return None

    def add_device(self, draft: DeviceDraft) -> Device | None:
        """Create and store a single Device with quantity=1.

        Returns None when the tag is empty or already exists.
        """
        result = self.add_devices_from_draft(
            DeviceDraft(
                area=draft.area,
                category=draft.category,
                type=draft.type,
                tag=draft.tag,
                description=draft.description,
                quantity=1,
            )
        )
        if not result.ok:
            return None
        return result.devices[0]

    def add_devices_from_draft(self, draft: DeviceDraft) -> AddDevicesResult:
        """Create one or more individual devices from a draft.

        Quantity > 1 expands tags sequentially (P-201 → P-201, P-202, ...).
        All-or-nothing: conflicts cancel the entire operation.
        """
        tag = draft.tag.strip()
        if not tag:
            return AddDevicesResult((), error="Tag is required.")

        quantity = max(1, int(draft.quantity))
        if quantity == 1:
            tags = [tag]
        else:
            expanded = expand_sequential_tags(tag, quantity)
            if expanded is None:
                return AddDevicesResult(
                    (),
                    error=(
                        "Automatic quantity expansion requires a Tag "
                        "ending with a number."
                    ),
                )
            tags = expanded

        conflicts = tuple(
            candidate for candidate in tags if self.get_by_tag(candidate) is not None
        )
        if conflicts:
            conflict_list = ", ".join(conflicts)
            return AddDevicesResult(
                (),
                error=f"Conflicting Tags already exist: {conflict_list}",
                conflicts=conflicts,
            )

        created: list[Device] = []
        for device_tag in tags:
            device = Device(
                id=str(uuid.uuid4()),
                tag=device_tag,
                area=draft.area,
                category=draft.category,
                type=draft.type,
                description=draft.description,
                quantity=1,
                signals=[],
            )
            self._devices.append(device)
            created.append(device)

        return AddDevicesResult(tuple(created))

    def remove_device(self, device_id: str) -> Device | None:
        """Remove a device from memory. Returns the removed device, or None."""
        for index, device in enumerate(self._devices):
            if device.id == device_id:
                return self._devices.pop(index)
        return None

    def duplicate_device(self, device_id: str) -> Device | None:
        """Copy one device with the next available tag and a new internal UUID."""
        source = self.get_by_id(device_id)
        if source is None:
            return None

        new_tag = suggest_next_tag(source.tag, self.tags())
        device = Device(
            id=str(uuid.uuid4()),
            tag=new_tag,
            area=source.area,
            category=source.category,
            type=source.type,
            description=source.description,
            quantity=1,
            signals=_copy_signals(source.signals),
            di_start_address=source.di_start_address,
            do_start_address=source.do_start_address,
            ai_start_address=source.ai_start_address,
            ao_start_address=source.ao_start_address,
        )
        self._devices.append(device)
        return device
