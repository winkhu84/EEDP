"""Recommendation Engine.

Produces signal recommendations and Signal objects for a Device.
"""

from __future__ import annotations

from app.engine.rule_engine import DeviceRule, RuleEngine, UNKNOWN_DEVICE
from app.engine.signal_engine import SignalEngine
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
    """Applies library rules: UI recommendations + Device Signal objects."""

    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
        signal_engine: SignalEngine | None = None,
    ) -> None:
        self._rule_engine = rule_engine or RuleEngine()
        self._signal_engine = signal_engine or SignalEngine()

    def recommend(self, device: Device) -> RecommendationResult:
        """Create Signal objects on the device and return UI recommendation data."""
        rule = self._rule_engine.load_rule(device.type)
        self._signal_engine.create_signals_from_rule(device, rule)
        return self._to_result(device, rule)

    def ensure_signals(self, device: Device) -> RecommendationResult:
        """Apply rules when signals are missing or contain legacy Local/Remote Mode."""
        if (
            not device.signals
            or self._signal_engine.needs_legacy_mode_migration(device)
        ):
            return self.recommend(device)
        return self.recommendation_result(device)

    def recommendation_result(self, device: Device) -> RecommendationResult:
        """Build UI recommendation data without recreating Signal objects."""
        rule = self._rule_engine.load_rule(device.type)
        return self._to_result(device, rule)

    def supported_types(self) -> tuple[str, ...]:
        """Return device types available from the Rule Engine library."""
        return self._rule_engine.available_types()

    @staticmethod
    def _to_result(device: Device, rule: DeviceRule) -> RecommendationResult:
        return RecommendationResult(
            device_id=device.id,
            device_tag=device.tag,
            device_type=device.type,
            recommendations=RecommendationEngine._build_recommendations(rule),
        )

    @staticmethod
    def _build_recommendations(rule: DeviceRule) -> tuple[Recommendation, ...]:
        if rule is UNKNOWN_DEVICE or rule.name == "Unknown":
            return ()

        items: list[Recommendation] = [
            Recommendation(
                name=item.name,
                signal_type=item.signal_type,
                required=True,
            )
            for item in rule.required_signals
        ]
        items.extend(
            Recommendation(
                name=item.name,
                signal_type=item.signal_type,
                required=False,
            )
            for item in rule.optional_signals
        )
        return tuple(items)
