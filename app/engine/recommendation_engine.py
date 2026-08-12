"""Recommendation Engine.

Produces UI recommendation data and copies SignalTemplate signals onto Devices.
SignalTemplateLibrary is the single authoritative template source.
"""

from __future__ import annotations

from app.engine.address_manager import apply_default_use_start_flags
from app.engine.rule_engine import RuleEngine
from app.engine.signal_engine import SignalEngine
from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.device import Device
from app.model.recommendation import IoSummary, Recommendation, RecommendationResult


def build_io_summary(
    enabled_signal_types: list[str] | tuple[str, ...],
) -> IoSummary:
    """Count DI/DO/AI/AO from enabled signal types (legacy helper)."""
    counts = {"DI": 0, "DO": 0, "AI": 0, "AO": 0}
    for signal_type in enabled_signal_types:
        key = (signal_type or "").strip().upper()
        if key in counts:
            counts[key] += 1
    total = counts["DI"] + counts["DO"] + counts["AI"] + counts["AO"]
    return IoSummary(
        di=counts["DI"],
        do=counts["DO"],
        ai=counts["AI"],
        ao=counts["AO"],
        total=total,
    )


class RecommendationEngine:
    """GUI adapter: templates from SignalTemplateLibrary, owned copies on Device."""

    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
        signal_engine: SignalEngine | None = None,
        *,
        template_library: SignalTemplateLibrary | None = None,
    ) -> None:
        if template_library is not None:
            self._library = template_library
        else:
            self._library = SignalTemplateLibrary(rule_engine=rule_engine)
        self._signal_engine = signal_engine or SignalEngine()

    def recommendations_for_type(
        self,
        device_type: str,
    ) -> tuple[Recommendation, ...]:
        """Return ordered Recommended Signals for a Device Type (display only)."""
        return tuple(
            Recommendation(
                name=item.name,
                signal_type=item.signal_type,
                required=item.required,
            )
            for item in self._library.get_signals(device_type)
        )

    def recommend(self, device: Device) -> RecommendationResult:
        """Copy the Device Type template onto the device as owned signals.

        Unknown types are not mutated. Known types replace device.signals
        with independent copies (no live template references).
        """
        template = self._library.get_template(device.type)
        if template is None:
            apply_default_use_start_flags(device)
            return self.recommendation_result(device)

        self._library.apply_copy_to_device(device)
        apply_default_use_start_flags(device)
        return self.recommendation_result(device)

    def ensure_signals(self, device: Device) -> RecommendationResult:
        """Apply a template only on the safe legacy Local/Remote Mode path.

        Empty devices are not initialized here. New devices are copied via
        recommend() at Add Device time so Import IO List selection cannot
        fill or replace project data.
        """
        if self._signal_engine.needs_legacy_mode_migration(device):
            return self.recommend(device)
        return self.recommendation_result(device)

    def recommendation_result(self, device: Device) -> RecommendationResult:
        """Build UI recommendation data without mutating Device.signals."""
        return RecommendationResult(
            device_id=device.id,
            device_tag=device.tag,
            device_type=device.type,
            recommendations=self.recommendations_for_type(device.type),
        )

    def supported_types(self) -> tuple[str, ...]:
        """Return device types available from the Signal Template library."""
        return self._library.device_types()
