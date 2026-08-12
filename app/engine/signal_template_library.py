"""Signal Template library — loads Device Type templates from YAML rules."""

from __future__ import annotations

from pathlib import Path

from app.engine.rule_engine import DeviceRule, RuleEngine, SignalRule, UNKNOWN_DEVICE
from app.model.device import Device
from app.model.signal import Signal
from app.model.signal_template import (
    SignalTemplate,
    TemplateSignal,
    make_template_signal_id,
)


def template_signal_from_rule(
    rule: SignalRule,
    *,
    device_type: str,
    order: int,
) -> TemplateSignal:
    """Map a library SignalRule to an independent TemplateSignal."""
    signal_id = rule.signal_id.strip() or make_template_signal_id(
        device_type,
        rule.name,
    )
    return TemplateSignal(
        id=signal_id,
        name=rule.name,
        signal_type=rule.signal_type,
        required=rule.required,
        description=rule.description,
        remark=rule.remark,
        default_enabled=rule.resolved_default_enabled,
        order=rule.order if rule.order != 0 else order,
    )


def template_from_device_rule(rule: DeviceRule) -> SignalTemplate:
    """Build a SignalTemplate from a loaded DeviceRule."""
    signals = tuple(
        template_signal_from_rule(
            item,
            device_type=rule.name,
            order=index,
        )
        for index, item in enumerate(rule.signals)
    )
    return SignalTemplate(
        device_type=rule.name,
        category=rule.category,
        description=rule.description,
        signals=signals,
    )


class SignalTemplateLibrary:
    """Load and query Signal Templates from the existing YAML library."""

    def __init__(
        self,
        *,
        rule_engine: RuleEngine | None = None,
        library_root: Path | str | None = None,
    ) -> None:
        if rule_engine is not None:
            self._rule_engine = rule_engine
        else:
            self._rule_engine = RuleEngine(library_root)

    def reload(self) -> None:
        """Reload templates from YAML."""
        self._rule_engine.reload()

    def device_types(self) -> tuple[str, ...]:
        """Return Device Types that have a loaded template."""
        return self._rule_engine.available_types()

    def get_template(self, device_type: str) -> SignalTemplate | None:
        """Return the template for a Device Type, or None when unknown."""
        rule = self._rule_engine.load_rule(device_type)
        if rule is UNKNOWN_DEVICE or rule.name == "Unknown":
            return None
        return template_from_device_rule(rule)

    def get_signals(self, device_type: str) -> tuple[TemplateSignal, ...]:
        """Return ordered template signals for a Device Type."""
        template = self.get_template(device_type)
        if template is None:
            return ()
        return template.signals_in_order()

    def load_all(self) -> tuple[SignalTemplate, ...]:
        """Return every loaded template, sorted by Device Type."""
        templates = [
            template_from_device_rule(self._rule_engine.load_rule(name))
            for name in self.device_types()
        ]
        return tuple(templates)

    def copy_signals_for_type(self, device_type: str) -> list[Signal]:
        """Create independent Device Signal copies for a Device Type."""
        template = self.get_template(device_type)
        if template is None:
            return []
        return template.copy_signals()

    def apply_copy_to_device(self, device: Device) -> list[Signal]:
        """Copy the Device Type template onto the device as owned signals.

        Replaces device.signals with new copies. Does not keep template refs.
        """
        copies = self.copy_signals_for_type(device.type)
        device.clear_signals()
        for signal in copies:
            device.add_signal(signal)
        return copies
