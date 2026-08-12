"""Signal Template domain entities.

Templates describe recommended signals for one Device Type.
They are copied onto Device.signals; devices never hold live template refs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from app.model.signal import Signal

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_TEMPLATE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_SIGNAL_ID = re.compile(r"^[a-z][a-z0-9_.]*$")


class TemplateIdentityError(ValueError):
    """Invalid or duplicate template / signal identity."""


def slugify_identifier(text: str) -> str:
    """Return a stable lowercase identifier fragment from display text."""
    slug = _NON_ALNUM.sub("_", text.strip().casefold()).strip("_")
    return slug or "signal"


def make_template_id(display_name: str) -> str:
    """Derive a legacy-compatible template id from the display name."""
    slug = slugify_identifier(display_name)
    if slug[0].isdigit():
        return f"t_{slug}"
    return slug


def make_template_signal_id(device_type: str, signal_name: str) -> str:
    """Build a stable template-signal id: '{device_type}.{signal_name}' slugs."""
    return f"{slugify_identifier(device_type)}.{slugify_identifier(signal_name)}"


def is_valid_template_id(value: str) -> bool:
    """Return True when value is a non-empty canonical template id."""
    return bool(value) and _TEMPLATE_ID.fullmatch(value) is not None


def is_valid_signal_id(value: str) -> bool:
    """Return True when value is a non-empty canonical signal id.

    Allows a dot so legacy compound ids (pump.start_command) remain valid.
    """
    return bool(value) and _SIGNAL_ID.fullmatch(value) is not None


def resolve_template_id(explicit_id: str, display_name: str) -> str:
    """Use an explicit YAML id, or derive a legacy-compatible id."""
    explicit = explicit_id.strip()
    if explicit:
        if not is_valid_template_id(explicit):
            raise TemplateIdentityError(f"Invalid template id '{explicit}'.")
        return explicit
    derived = make_template_id(display_name)
    if not is_valid_template_id(derived):
        raise TemplateIdentityError(
            f"Cannot derive template id from name '{display_name}'."
        )
    return derived


def resolve_signal_id(
    explicit_id: str,
    *,
    device_type: str,
    signal_name: str,
) -> str:
    """Use an explicit YAML signal id, or derive the current compound id."""
    explicit = explicit_id.strip()
    if explicit:
        if not is_valid_signal_id(explicit):
            raise TemplateIdentityError(f"Invalid signal id '{explicit}'.")
        return explicit
    derived = make_template_signal_id(device_type, signal_name)
    if not is_valid_signal_id(derived):
        raise TemplateIdentityError(
            f"Cannot derive signal id from '{device_type}' / '{signal_name}'."
        )
    return derived


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

    id: str
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

    def copy_with_identity(
        self,
        *,
        new_id: str,
        new_device_type: str,
    ) -> SignalTemplate:
        """Return a duplicate template with a new id/name and copied signal ids."""
        if not is_valid_template_id(new_id):
            raise TemplateIdentityError(f"Invalid template id '{new_id}'.")
        display = new_device_type.strip()
        if not display:
            raise TemplateIdentityError("Duplicate template display name is required.")
        return SignalTemplate(
            id=new_id,
            device_type=display,
            category=self.category,
            description=self.description,
            signals=tuple(replace(item) for item in self.signals),
        )


def template_to_yaml_data(template: SignalTemplate) -> dict:
    """Serialize a template to the canonical YAML-compatible mapping."""
    signals: list[dict] = []
    for item in template.signals_in_order():
        signals.append(
            {
                "id": item.id,
                "name": item.name,
                "signal_type": item.signal_type,
                "required": item.required,
                "default_enabled": item.default_enabled,
                "description": item.description,
                "remark": item.remark,
            }
        )
    return {
        "id": template.id,
        "name": template.device_type,
        "category": template.category,
        "description": template.description,
        "signals": signals,
    }
