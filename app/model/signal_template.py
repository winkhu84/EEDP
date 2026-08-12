"""Signal Template domain entities.

Templates describe recommended signals for one Device Type.
They are copied onto Device.signals; devices never hold live template refs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.model.signal import Signal

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify_identifier(text: str) -> str:
    """Return a stable lowercase identifier fragment from display text."""
    slug = _NON_ALNUM.sub("_", text.strip().casefold()).strip("_")
    return slug or "signal"


def make_template_signal_id(device_type: str, signal_name: str) -> str:
    """Build a stable template-signal id: '{device_type}.{signal_name}' slugs."""
    return f"{slugify_identifier(device_type)}.{slugify_identifier(signal_name)}"


@dataclass
class TemplateSignal:
    """One signal definition inside a Device Type template."""

    id: str
    name: str
    signal_type: str
    required: bool
    description: str = ""
    remark: str = ""
    default_enabled: bool = True
    order: int = 0

    def copy_to_signal(self) -> Signal:
        """Return a new Device Signal owned independently of this template."""
        return Signal(
            name=self.name,
            io_type=self.signal_type,
            required=self.required,
            enabled=self.default_enabled,
            address="",
            terminal="",
            cable="",
            description=self.description,
            remark=self.remark,
        )


@dataclass
class SignalTemplate:
    """Recommended-signal template for one Device Type."""

    device_type: str
    category: str = ""
    description: str = ""
    signals: tuple[TemplateSignal, ...] = field(default_factory=tuple)

    def signals_in_order(self) -> tuple[TemplateSignal, ...]:
        """Return template signals sorted by display/order position."""
        return tuple(sorted(self.signals, key=lambda item: item.order))

    def copy_signals(self) -> list[Signal]:
        """Create independent Device Signal copies in template order."""
        return [item.copy_to_signal() for item in self.signals_in_order()]
