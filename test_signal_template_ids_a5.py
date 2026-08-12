"""EOS-014-A5: persistent template and signal identity tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.engine.recommendation_engine import RecommendationEngine
from app.engine.rule_engine import RuleEngine
from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.device import Device
from app.model.signal_template import (
    TemplateIdentityError,
    make_template_id,
    template_to_yaml_data,
)


_PUMP_ORDER = (
    "Start Command",
    "Stop Command",
    "Local/Remote Mode",
    "Run Feedback",
    "Fault Feedback",
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _library_from(root: Path) -> SignalTemplateLibrary:
    return SignalTemplateLibrary(library_root=root)


def test_1_legacy_yaml_without_template_id_loads(tmp_path: Path) -> None:
    _write(
        tmp_path / "Equipment" / "Pump.yaml",
        "name: Pump\ncategory: Equipment\nsignals:\n"
        "  - name: Start Command\n    signal_type: DO\n    required: true\n",
    )
    library = _library_from(tmp_path)
    template = library.get_template("Pump")
    assert template is not None
    assert template.id == "pump"
    assert template.device_type == "Pump"
    assert library.load_errors == ()


def test_2_legacy_signal_without_id_loads() -> None:
    signals = SignalTemplateLibrary().get_signals("Pump")
    by_name = {item.name: item for item in signals}
    assert by_name["Start Command"].id == "pump.start_command"
    assert by_name["Local/Remote Mode"].id == "pump.local_remote_mode"


def test_3_explicit_template_id_loads(tmp_path: Path) -> None:
    _write(
        tmp_path / "Equipment" / "custom.yaml",
        "id: custom_pump\nname: Custom Pump\ncategory: Equipment\nsignals:\n"
        "  - name: Start Command\n    signal_type: DO\n    required: true\n",
    )
    library = _library_from(tmp_path)
    template = library.get_template("Custom Pump")
    assert template is not None
    assert template.id == "custom_pump"
    assert library.get_template_by_id("custom_pump") is not None
    assert library.get_template_by_id("custom_pump").device_type == "Custom Pump"


def test_4_explicit_signal_id_loads(tmp_path: Path) -> None:
    _write(
        tmp_path / "Equipment" / "Pump.yaml",
        "id: pump\nname: Pump\ncategory: Equipment\nsignals:\n"
        "  - id: start_command\n    name: Start Command\n"
        "    signal_type: DO\n    required: true\n",
    )
    template = _library_from(tmp_path).get_template("Pump")
    assert template is not None
    assert template.signals[0].id == "start_command"
    assert template.signals[0].name == "Start Command"


def test_5_template_id_stable_if_display_name_changes() -> None:
    template = SignalTemplateLibrary().get_template("Pump")
    assert template is not None
    original_id = template.id
    template.device_type = "Process Pump"
    assert template.id == original_id == "pump"


def test_6_signal_id_stable_if_signal_name_changes() -> None:
    template = SignalTemplateLibrary().get_template("Pump")
    assert template is not None
    signal = template.signals[0]
    original_id = signal.id
    signal.name = "Start Cmd"
    assert signal.id == original_id == "pump.start_command"


def test_7_duplicate_template_id_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "Equipment" / "a.yaml",
        "id: pump\nname: Pump\ncategory: Equipment\nsignals:\n"
        "  - name: Start Command\n    signal_type: DO\n",
    )
    _write(
        tmp_path / "Equipment" / "b.yaml",
        "id: pump\nname: Other Pump\ncategory: Equipment\nsignals:\n"
        "  - name: Start Command\n    signal_type: DO\n",
    )
    library = _library_from(tmp_path)
    assert library.get_template("Pump") is not None
    assert library.get_template("Other Pump") is None
    assert any("Duplicate template id 'pump'" in item for item in library.load_errors)


def test_8_duplicate_signal_id_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "Equipment" / "Pump.yaml",
        "id: pump\nname: Pump\ncategory: Equipment\nsignals:\n"
        "  - id: start_command\n    name: Start Command\n    signal_type: DO\n"
        "  - id: start_command\n    name: Stop Command\n    signal_type: DO\n",
    )
    library = _library_from(tmp_path)
    assert library.get_template("Pump") is None
    assert any("Duplicate signal id 'start_command'" in item for item in library.load_errors)


def test_9_and_10_ordering_preserved() -> None:
    library = SignalTemplateLibrary()
    names = [item.name for item in library.get_signals("Pump")]
    assert names == list(_PUMP_ORDER)
    types = library.device_types()
    assert "Pump" in types
    assert types == tuple(sorted(types))


def test_11_serialize_reload_round_trip_preserves_ids(tmp_path: Path) -> None:
    source = SignalTemplateLibrary().get_template("Pump")
    assert source is not None
    data = template_to_yaml_data(source)
    out = tmp_path / "Equipment" / "pump.yaml"
    SignalTemplateLibrary().save_template(source, out)

    reloaded = _library_from(tmp_path).get_template("Pump")
    assert reloaded is not None
    assert reloaded.id == source.id == "pump"
    assert [item.id for item in reloaded.signals_in_order()] == [
        item.id for item in source.signals_in_order()
    ]
    assert [item.name for item in reloaded.signals_in_order()] == list(_PUMP_ORDER)
    assert data["id"] == "pump"
    assert data["name"] == "Pump"
    assert data["signals"][0]["id"] == "pump.start_command"


def test_12_utf8_korean_survives_round_trip(tmp_path: Path) -> None:
    _write(
        tmp_path / "Equipment" / "Pump.yaml",
        "id: pump\nname: Pump\ncategory: Equipment\n"
        "description: 순환 펌프\nsignals:\n"
        "  - id: start_command\n    name: 기동 지령\n"
        "    signal_type: DO\n    required: true\n"
        "    description: 한글 설명\n    remark: 비고\n",
    )
    library = _library_from(tmp_path)
    template = library.get_template("Pump")
    assert template is not None
    assert template.description == "순환 펌프"
    assert template.signals[0].name == "기동 지령"
    assert template.signals[0].description == "한글 설명"
    assert template.signals[0].remark == "비고"

    out_root = tmp_path / "out"
    out = out_root / "Equipment" / "pump.yaml"
    library.save_template(template, out)
    round_trip = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert round_trip["description"] == "순환 펌프"
    assert round_trip["signals"][0]["name"] == "기동 지령"
    assert round_trip["signals"][0]["remark"] == "비고"

    again = _library_from(out_root).get_template("Pump")
    assert again is not None
    assert again.description == "순환 펌프"
    assert again.signals[0].name == "기동 지령"


def test_13_pump_recommendation_order_unchanged() -> None:
    device = Device(
        id="a5-1",
        tag="P-501",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    result = RecommendationEngine().recommend(device)
    assert [item.name for item in result.recommendations] == list(_PUMP_ORDER)
    assert [signal.name for signal in device.signals] == list(_PUMP_ORDER)


def test_14_add_device_type_string_unchanged() -> None:
    device = Device(
        id="a5-2",
        tag="P-502",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    RecommendationEngine().recommend(device)
    assert device.type == "Pump"
    assert make_template_id("Pump") == "pump"


def test_15_device_signals_are_independent_copies() -> None:
    library = SignalTemplateLibrary()
    template = library.get_template("Pump")
    assert template is not None
    device = Device(
        id="a5-3",
        tag="P-503",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    library.apply_copy_to_device(device)
    device.signals[0].name = "MUTATED"
    device.signals[0].address = "Q0.0"
    assert template.signals[0].name == "Start Command"
    template.signals[0].description = "changed template"
    assert device.signals[0].name == "MUTATED"
    assert device.signals[0].address == "Q0.0"


def test_duplicate_foundation_copies_signal_ids() -> None:
    source = SignalTemplateLibrary().get_template("Pump")
    assert source is not None
    copy = source.copy_with_identity(new_id="pump_copy", new_device_type="Pump Copy")
    assert copy.id == "pump_copy"
    assert copy.device_type == "Pump Copy"
    assert [item.id for item in copy.signals_in_order()] == [
        item.id for item in source.signals_in_order()
    ]
    copy.signals[0].name = "Changed"
    assert source.signals[0].name == "Start Command"
    try:
        source.copy_with_identity(new_id="BAD ID", new_device_type="X")
        raise AssertionError("expected TemplateIdentityError")
    except TemplateIdentityError:
        pass


def test_invalid_explicit_ids_are_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "Equipment" / "bad.yaml",
        "id: 'Pump Copy'\nname: Bad\ncategory: Equipment\nsignals:\n"
        "  - name: Start Command\n    signal_type: DO\n",
    )
    library = _library_from(tmp_path)
    assert library.get_template("Bad") is None
    assert any("Invalid template id" in item for item in library.load_errors)


def test_malformed_yaml_fails_safely(tmp_path: Path) -> None:
    _write(tmp_path / "Equipment" / "broken.yaml", ": : not yaml\n[")
    _write(
        tmp_path / "Equipment" / "Pump.yaml",
        "name: Pump\ncategory: Equipment\nsignals:\n"
        "  - name: Start Command\n    signal_type: DO\n",
    )
    library = _library_from(tmp_path)
    assert library.get_template("Pump") is not None
    assert library.load_errors


if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as raw:
        root = Path(raw)
        test_1_legacy_yaml_without_template_id_loads(root / "t1")
        test_3_explicit_template_id_loads(root / "t3")
        test_4_explicit_signal_id_loads(root / "t4")
        test_7_duplicate_template_id_is_rejected(root / "t7")
        test_8_duplicate_signal_id_is_rejected(root / "t8")
        test_11_serialize_reload_round_trip_preserves_ids(root / "t11")
        test_12_utf8_korean_survives_round_trip(root / "t12")
        test_invalid_explicit_ids_are_rejected(root / "tinv")
        test_malformed_yaml_fails_safely(root / "tmal")
    test_2_legacy_signal_without_id_loads()
    test_5_template_id_stable_if_display_name_changes()
    test_6_signal_id_stable_if_signal_name_changes()
    test_9_and_10_ordering_preserved()
    test_13_pump_recommendation_order_unchanged()
    test_14_add_device_type_string_unchanged()
    test_15_device_signals_are_independent_copies()
    test_duplicate_foundation_copies_signal_ids()
    print("OK")
