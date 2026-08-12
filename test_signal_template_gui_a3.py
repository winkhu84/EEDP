"""EOS-014-A3: SignalTemplateLibrary GUI recommendation-path tests."""

from __future__ import annotations

from app.engine.recommendation_engine import RecommendationEngine
from app.engine.signal_engine import SignalEngine
from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.device import Device
from app.model.signal import Signal


_PUMP_ORDER = (
    "Start Command",
    "Stop Command",
    "Local/Remote Mode",
    "Run Feedback",
    "Fault Feedback",
)


def _pump_device(device_id: str = "1", tag: str = "P-101") -> Device:
    return Device(
        id=device_id,
        tag=tag,
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )


def _engine() -> RecommendationEngine:
    return RecommendationEngine()


def test_1_pump_order_matches_library() -> None:
    library = SignalTemplateLibrary()
    engine = RecommendationEngine(template_library=library)
    device = _pump_device()

    result = engine.recommend(device)
    library_names = [item.name for item in library.get_signals("Pump")]
    rec_names = [item.name for item in result.recommendations]
    signal_names = [signal.name for signal in device.signals]

    assert library_names == list(_PUMP_ORDER)
    assert rec_names == list(_PUMP_ORDER)
    assert signal_names == list(_PUMP_ORDER)


def test_2_required_optional_state() -> None:
    result = _engine().recommendation_result(_pump_device())
    by_name = {item.name: item for item in result.recommendations}
    assert by_name["Start Command"].required is True
    assert by_name["Start Command"].category == "Required"
    assert by_name["Stop Command"].required is False
    assert by_name["Stop Command"].category == "Optional"
    assert by_name["Local/Remote Mode"].required is False
    assert by_name["Run Feedback"].required is True
    assert by_name["Fault Feedback"].required is True


def test_3_default_enabled_state() -> None:
    device = _pump_device()
    _engine().recommend(device)
    by_name = {signal.name: signal for signal in device.signals}
    assert by_name["Start Command"].enabled is True
    assert by_name["Stop Command"].enabled is False
    assert by_name["Local/Remote Mode"].enabled is False
    assert by_name["Run Feedback"].enabled is True
    assert by_name["Fault Feedback"].enabled is True


def test_4_new_empty_device_gets_independent_copies() -> None:
    library = SignalTemplateLibrary()
    engine = RecommendationEngine(template_library=library)
    template = library.get_template("Pump")
    assert template is not None

    device = _pump_device()
    engine.recommend(device)

    assert len(device.signals) == len(template.signals)
    for copied, source in zip(device.signals, template.signals_in_order()):
        assert copied is not source
        assert not isinstance(copied, type(source))
        assert copied.name == source.name
        assert copied.io_type == source.signal_type
        assert copied.required is source.required
        assert copied.enabled is source.default_enabled
        assert copied.description == source.description
        assert copied.remark == source.remark


def test_5_mutating_device_signal_does_not_mutate_template() -> None:
    library = SignalTemplateLibrary()
    engine = RecommendationEngine(template_library=library)
    template = library.get_template("Pump")
    assert template is not None

    device = _pump_device(device_id="2", tag="P-102")
    engine.recommend(device)

    original_name = template.signals[0].name
    original_description = template.signals[0].description
    original_enabled = template.signals[0].default_enabled

    device.signals[0].name = "MUTATED DEVICE NAME"
    device.signals[0].description = "changed by device"
    device.signals[0].enabled = not device.signals[0].enabled
    device.signals[0].address = "Q0.0"

    assert template.signals[0].name == original_name
    assert template.signals[0].description == original_description
    assert template.signals[0].default_enabled is original_enabled

    template.signals[0].name = "MUTATED TEMPLATE NAME"
    template.signals[0].description = "changed by template"
    assert device.signals[0].name == "MUTATED DEVICE NAME"
    assert device.signals[0].description == "changed by device"
    assert device.signals[0].address == "Q0.0"

    refreshed = library.get_signals("Pump")
    assert refreshed[0].name == "Start Command"


def test_6_existing_device_selection_does_not_replace_signals() -> None:
    engine = _engine()
    device = _pump_device(device_id="3", tag="P-103")
    engine.recommend(device)
    original_ids = [id(signal) for signal in device.signals]
    original_names = [signal.name for signal in device.signals]

    result = engine.ensure_signals(device)

    assert [id(signal) for signal in device.signals] == original_ids
    assert [signal.name for signal in device.signals] == original_names
    assert [item.name for item in result.recommendations] == list(_PUMP_ORDER)


def test_7_existing_addresses_survive_ensure_signals() -> None:
    engine = _engine()
    device = _pump_device(device_id="4", tag="P-104")
    engine.recommend(device)
    device.signals[0].address = "Q0.0"
    device.signals[3].address = "I0.0"
    device.di_start_address = "I2.0"
    device.do_start_address = "Q2.0"

    engine.ensure_signals(device)

    assert device.signals[0].address == "Q0.0"
    assert device.signals[3].address == "I0.0"
    assert device.di_start_address == "I2.0"
    assert device.do_start_address == "Q2.0"


def test_8_custom_signals_survive_selection() -> None:
    engine = _engine()
    device = _pump_device(device_id="5", tag="P-105")
    engine.recommend(device)
    custom = SignalEngine().create_signal(
        name="Custom Interlock",
        io_type="DI",
        required=False,
        enabled=True,
        address="I1.7",
        description="User-added signal",
    )
    device.add_signal(custom)
    count_before = len(device.signals)

    engine.ensure_signals(device)

    assert len(device.signals) == count_before
    assert device.signals[-1] is custom
    assert device.signals[-1].name == "Custom Interlock"
    assert device.signals[-1].address == "I1.7"


def test_9_unknown_type_is_safe() -> None:
    engine = _engine()
    empty = Device(
        id="6",
        tag="X-001",
        area="PRE",
        category="Equipment",
        type="NotAType",
        description="",
        quantity=1,
    )
    result = engine.recommend(empty)
    assert result.recommendations == ()
    assert empty.signals == []

    owned = Signal(
        name="Keep Me",
        io_type="DI",
        required=False,
        enabled=True,
        address="I9.0",
        description="imported",
    )
    existing = Device(
        id="7",
        tag="X-002",
        area="PRE",
        category="Equipment",
        type="NotAType",
        description="",
        quantity=1,
        signals=[owned],
    )
    engine.recommend(existing)
    engine.ensure_signals(existing)
    assert len(existing.signals) == 1
    assert existing.signals[0] is owned
    assert existing.signals[0].name == "Keep Me"
    assert existing.signals[0].address == "I9.0"


def test_import_empty_device_selection_does_not_apply_template() -> None:
    """Import IO List creates empty devices; first selection must not fill them."""
    engine = _engine()
    imported = _pump_device(device_id="8", tag="P-IMPORT")
    assert imported.signals == []

    result = engine.ensure_signals(imported)

    assert imported.signals == []
    assert [item.name for item in result.recommendations] == list(_PUMP_ORDER)


def test_add_device_path_still_applies_template() -> None:
    device = _pump_device(device_id="9", tag="P-106")
    _engine().recommend(device)
    assert [signal.name for signal in device.signals] == list(_PUMP_ORDER)


if __name__ == "__main__":
    test_1_pump_order_matches_library()
    test_2_required_optional_state()
    test_3_default_enabled_state()
    test_4_new_empty_device_gets_independent_copies()
    test_5_mutating_device_signal_does_not_mutate_template()
    test_6_existing_device_selection_does_not_replace_signals()
    test_7_existing_addresses_survive_ensure_signals()
    test_8_custom_signals_survive_selection()
    test_9_unknown_type_is_safe()
    test_import_empty_device_selection_does_not_apply_template()
    test_add_device_path_still_applies_template()
    print("OK")
