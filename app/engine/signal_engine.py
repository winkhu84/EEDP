"""Signal Engine — creates Signal objects from rules."""

from __future__ import annotations

from app.engine.rule_engine import DeviceRule, SignalRule, UNKNOWN_DEVICE
from app.model.device import Device
from app.model.signal import Signal

# Legacy names replaced by a single merged DI signal.
LEGACY_MODE_SIGNAL_NAMES = frozenset({"Local Mode", "Remote Mode"})
MERGED_MODE_SIGNAL_NAME = "Local/Remote Mode"


class SignalEngine:
    """Builds Signal domain objects for a Device."""

    def create_signal(
        self,
        name: str,
        io_type: str,
        required: bool,
        *,
        enabled: bool | None = None,
        address: str = "",
        terminal: str = "",
        cable: str = "",
        description: str = "",
        remark: str = "",
    ) -> Signal:
        """Create a single Signal object."""
        return Signal(
            name=name,
            io_type=io_type,
            required=required,
            enabled=required if enabled is None else enabled,
            address=address,
            terminal=terminal,
            cable=cable,
            description=description,
            remark=remark,
        )

    def create_signals_from_rule(
        self,
        device: Device,
        rule: DeviceRule,
    ) -> list[Signal]:
        """Create Signal objects from a device rule and assign them to the device.

        Required signals are enabled by default.
        Optional signals are created but disabled.
        Future fields (address, terminal, cable) stay empty.
        """
        device.clear_signals()

        if rule is UNKNOWN_DEVICE or rule.name == "Unknown":
            return []

        signals: list[Signal] = []
        for item in rule.signals:
            signal = self._from_rule_item(
                item,
                required=item.required,
                enabled=item.required,
            )
            device.add_signal(signal)
            signals.append(signal)

        return signals

    def needs_legacy_mode_migration(self, device: Device) -> bool:
        """Return True when device still has obsolete Local/Remote Mode signals."""
        return any(signal.name in LEGACY_MODE_SIGNAL_NAMES for signal in device.signals)

    def _from_rule_item(
        self,
        item: SignalRule,
        *,
        required: bool,
        enabled: bool,
    ) -> Signal:
        return self.create_signal(
            name=item.name,
            io_type=item.signal_type,
            required=required,
            enabled=enabled,
            description=item.description,
        )
