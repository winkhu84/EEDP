"""Tests for Signal Template model and library (EOS-014-A2)."""

from __future__ import annotations

from app.engine.recommendation_engine import RecommendationEngine
from app.engine.rule_engine import RuleEngine
from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.device import Device
from app.model.signal_template import make_template_signal_id


_PUMP_ORDER = (
    "Start Command",
    "Stop Command",
    "Local/Remote Mode",
    "Run Feedback",
    "Fault Feedback",
)


def _library() -> SignalTemplateLibrary:
    return SignalTemplateLibrary()


def test_library_loads_successfully() -> None:
    library = _library()
    types = library.device_types()
    assert "Pump" in types
    assert "Valve" in types
    assert len(types) >= 8


def test_pump_template_can_be_retrieved() -> None:
    template = _library().get_template("Pump")
    assert template is not None
    assert template.device_type == "Pump"
    assert template.category == "Equipment"


def test_pump_signal_order_matches_recommended() -> None:
    names = [item.name for item in _library().get_signals("Pump")]
    assert names == list(_PUMP_ORDER)

    device = Device(
        id="1",
        tag="P-101",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    RecommendationEngine().recommend(device)
    assert [signal.name for signal in device.signals] == list(_PUMP_ORDER)


def test_required_optional_and_io_type_preserved() -> None:
    by_name = {item.name: item for item in _library().get_signals("Pump")}
    assert by_name["Start Command"].required is True
    assert by_name["Start Command"].signal_type == "DO"
    assert by_name["Stop Command"].required is False
    assert by_name["Stop Command"].signal_type == "DO"
    assert by_name["Local/Remote Mode"].required is False
    assert by_name["Local/Remote Mode"].signal_type == "DI"
    assert by_name["Run Feedback"].required is True
    assert by_name["Run Feedback"].signal_type == "DI"
    assert by_name["Fault Feedback"].required is True
    assert by_name["Fault Feedback"].signal_type == "DI"


def test_stable_ids_are_available() -> None:
    signals = _library().get_signals("Pump")
    ids = [item.id for item in signals]
    assert ids == [
        "pump.start_command",
        "pump.stop_command",
        "pump.local_remote_mode",
        "pump.run_feedback",
        "pump.fault_feedback",
    ]
    assert make_template_signal_id("Pump", "Start Command") == "pump.start_command"
    assert len(set(ids)) == len(ids)


def test_default_enabled_matches_required_when_unspecified() -> None:
    by_name = {item.name: item for item in _library().get_signals("Pump")}
    assert by_name["Start Command"].default_enabled is True
    assert by_name["Stop Command"].default_enabled is False
    assert by_name["Local/Remote Mode"].default_enabled is False
    assert by_name["Run Feedback"].default_enabled is True


def test_template_copy_creates_independent_device_signals() -> None:
    template = _library().get_template("Pump")
    assert template is not None
    copies = template.copy_signals()
    assert [signal.name for signal in copies] == list(_PUMP_ORDER)
    assert copies[0].enabled is True
    assert copies[1].enabled is False

    template.signals[0].name = "CHANGED TEMPLATE NAME"
    template.signals[0].default_enabled = False
    assert copies[0].name == "Start Command"
    assert copies[0].enabled is True


def test_modifying_template_does_not_change_applied_device_signals() -> None:
    library = _library()
    template = library.get_template("Pump")
    assert template is not None
    device = Device(
        id="2",
        tag="P-102",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    for signal in template.copy_signals():
        device.add_signal(signal)

    template.signals[0].name = "MUTATED"
    template.signals[0].remark = "changed"
    device.signals[0].address = "Q0.0"

    assert device.signals[0].name == "Start Command"
    assert device.signals[0].remark == ""
    assert template.signals[0].name == "MUTATED"
    assert device.signals[0].address == "Q0.0"


def test_existing_recommendation_behavior_still_works() -> None:
    device = Device(
        id="3",
        tag="P-103",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    result = RecommendationEngine().recommend(device)
    assert [item.name for item in result.recommendations] == list(_PUMP_ORDER)
    assert device.signals[0].enabled is True
    assert device.signals[1].enabled is False
    assert RuleEngine().load_rule("Pump").name == "Pump"


def test_unknown_type_returns_none() -> None:
    assert _library().get_template("NotAType") is None
    assert _library().copy_signals_for_type("") == []


if __name__ == "__main__":
    test_library_loads_successfully()
    test_pump_template_can_be_retrieved()
    test_pump_signal_order_matches_recommended()
    test_required_optional_and_io_type_preserved()
    test_stable_ids_are_available()
    test_default_enabled_matches_required_when_unspecified()
    test_template_copy_creates_independent_device_signals()
    test_modifying_template_does_not_change_applied_device_signals()
    test_existing_recommendation_behavior_still_works()
    test_unknown_type_returns_none()
    print("OK")
