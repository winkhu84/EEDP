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


def suggest_next_tag(tag: str, existing_tags: set[str]) -> str:
    """Suggest the next available tag (e.g. P-101 → P-102)."""
    match = re.match(r"^(.*?)(\d+)$", tag)
    if match:
        prefix, digits = match.group(1), match.group(2)
        number = int(digits)
        width = len(digits)
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
        """Create and store a Device.

        Returns None when the tag is empty or already exists.
        Device.id is an internal UUID and must not be shown in the UI.
        """
        tag = draft.tag.strip()
        if not tag or self.get_by_tag(tag) is not None:
            return None

        device = Device(
            id=str(uuid.uuid4()),
            tag=tag,
            area=draft.area,
            category=draft.category,
            type=draft.type,
            description=draft.description,
            quantity=draft.quantity,
            signals=[],
        )
        self._devices.append(device)
        return device

    def remove_device(self, device_id: str) -> Device | None:
        """Remove a device from memory. Returns the removed device, or None."""
        for index, device in enumerate(self._devices):
            if device.id == device_id:
                return self._devices.pop(index)
        return None

    def duplicate_device(self, device_id: str) -> Device | None:
        """Copy a device with the next available tag and a new internal UUID."""
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
            quantity=source.quantity,
            signals=[
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
                for signal in source.signals
            ],
        )
        self._devices.append(device)
        return device
