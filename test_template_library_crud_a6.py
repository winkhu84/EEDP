"""EOS-014-A6: SignalTemplateLibrary CRUD engine tests."""

from __future__ import annotations

from pathlib import Path
from shutil import copytree

import yaml

from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.device import Device
from app.model.signal_template import (
    TemplateIdentityError,
    TemplateSignal,
    next_display_name,
    next_template_id,
)


_PUMP_ORDER = (
    "Start Command",
    "Stop Command",
    "Local/Remote Mode",
    "Run Feedback",
    "Fault Feedback",
)
_SHIPPED_LIBRARY = Path(__file__).resolve().parent / "library"


def _copy_shipped(tmp_path: Path) -> SignalTemplateLibrary:
    dest = tmp_path / "library"
    copytree(_SHIPPED_LIBRARY, dest)
    return SignalTemplateLibrary(library_root=dest)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_create_template(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    created = library.create_template(
        display_name="Skid",
        category="Equipment",
        description="Custom skid",
        signals=[
            TemplateSignal(
                id="run_fb",
                name="Run Feedback",
                signal_type="DI",
                required=True,
            )
        ],
    )
    assert created.id == "skid"
    assert created.source_path == ""
    fetched = library.get_template("Skid")
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched is not created
    assert not (tmp_path / "library" / "Equipment" / "skid.yaml").exists()


def test_create_empty_template(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    created = library.create_template(display_name="Empty Type")
    assert created.id == "empty_type"
    assert created.signals == ()
    assert "Empty Type" in library.device_types()


def test_duplicate_template(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    original = library.get_template("Pump")
    assert original is not None
    original_ids = [item.id for item in original.signals_in_order()]
    dup = library.duplicate_template("pump")
    assert dup.id != original.id
    assert dup.device_type == "Pump Copy"
    assert dup.id == "pump_copy"
    assert [item.name for item in dup.signals_in_order()] == list(_PUMP_ORDER)
    assert [item.id for item in dup.signals_in_order()] != original_ids
    assert len({item.id for item in dup.signals_in_order()}) == len(dup.signals)
    dup.signals[0].name = "CHANGED"
    assert original.signals[0].name == "Start Command"
    assert original.device_type == "Pump"


def test_duplicate_regenerates_signal_ids_and_is_independent(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    original = library.get_template_by_id("pump")
    assert original is not None
    first_id = original.signals_in_order()[0].id
    dup = library.duplicate_template("Pump")
    assert dup.signals_in_order()[0].id != first_id
    assert dup.signals_in_order()[0].signal_type == "DO"
    assert dup.signals_in_order()[0].required is True
    dup.signals[0].required = False
    assert original.signals[0].required is True


def test_unique_display_name_and_id_generation() -> None:
    names = ("Pump", "Pump Copy", "Pump Copy 2")
    assert next_display_name("Pump", names) == "Pump Copy 3"
    ids = ("pump", "pump_copy")
    assert next_template_id("pump", ids) == "pump_copy_2"
    assert next_template_id("skid", ids) == "skid"


def test_update_template(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    pump = library.get_template("Pump")
    assert pump is not None
    pump.description = "Updated pump"
    pump.signals[0].remark = "note"
    updated = library.update_template(pump)
    assert updated.description == "Updated pump"
    assert updated.id == "pump"
    assert updated.source_path
    assert library.get_template("Pump").description == "Updated pump"


def test_duplicate_template_id_rejected(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    try:
        library.create_template(display_name="Other", template_id="pump")
        raise AssertionError("expected TemplateIdentityError")
    except TemplateIdentityError as exc:
        assert "Duplicate template id" in str(exc)


def test_duplicate_signal_id_rejected(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    try:
        library.create_template(
            display_name="Bad Signals",
            signals=(
                TemplateSignal(id="same", name="A", signal_type="DI", required=True),
                TemplateSignal(id="same", name="B", signal_type="DO", required=False),
            ),
        )
        raise AssertionError("expected TemplateIdentityError")
    except TemplateIdentityError as exc:
        assert "Duplicate signal id" in str(exc)


def test_delete_template_memory_only(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    pump_file = Path(library.get_template("Pump").source_path)
    assert pump_file.is_file()
    library.delete_template("pump")
    assert library.get_template("Pump") is None
    assert pump_file.is_file()


def test_delete_unknown_template_rejected(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    try:
        library.delete_template("not_a_template")
        raise AssertionError("expected TemplateIdentityError")
    except TemplateIdentityError as exc:
        assert "unknown template id" in str(exc).casefold()


def test_delete_persist_removes_only_source_file(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    pump_file = Path(library.get_template("Pump").source_path)
    library.delete_template("pump", persist=True)
    assert library.get_template("Pump") is None
    assert not pump_file.exists()
    assert library.get_template("Valve") is not None


def test_save_and_reload(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    created = library.create_template(
        display_name="Heater",
        description="가열기",
        signals=[
            TemplateSignal(
                id="temp_ai",
                name="Measurement",
                signal_type="AI",
                required=True,
                description="온도",
                remark="비고",
            )
        ],
    )
    saved = library.save_template(created)
    assert saved.source_path
    assert Path(saved.source_path).is_file()
    reloaded = SignalTemplateLibrary(library_root=tmp_path / "library")
    heater = reloaded.get_template("Heater")
    assert heater is not None
    assert heater.id == "heater"
    assert heater.description == "가열기"
    assert heater.signals[0].remark == "비고"
    assert heater.signals[0].id == "temp_ai"


def test_utf8_korean_round_trip(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    created = library.create_template(
        display_name="순환펌프",
        description="한글 템플릿",
        signals=[
            TemplateSignal(
                id="start_command",
                name="기동",
                signal_type="DO",
                required=True,
                description="기동 지령",
            )
        ],
    )
    library.save_template(created)
    again = SignalTemplateLibrary(library_root=tmp_path / "library").get_template(
        "순환펌프"
    )
    assert again is not None
    assert again.description == "한글 템플릿"
    assert again.signals[0].name == "기동"


def test_malformed_persistence_error(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    pump = library.get_template("Pump")
    assert pump is not None
    pump.signals[0].signal_type = "XX"
    try:
        library.save_template(pump)
        raise AssertionError("expected TemplateIdentityError")
    except TemplateIdentityError as exc:
        assert "Invalid IO type" in str(exc)
    assert yaml.safe_load(Path(pump.source_path).read_text(encoding="utf-8"))["name"] == "Pump"


def test_update_unknown_id_rejected(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    pump = library.get_template("Pump")
    assert pump is not None
    pump.id = "missing_id"
    try:
        library.update_template(pump)
        raise AssertionError("expected TemplateIdentityError")
    except TemplateIdentityError as extra:
        assert "unknown template id" in str(extra).casefold()


def test_save_preserves_other_unsaved_working_set_edits(tmp_path: Path) -> None:
    """Saving one template must not discard unsaved edits to another."""
    library = _copy_shipped(tmp_path)
    pump = library.get_template("Pump")
    valve = library.get_template("Valve")
    assert pump is not None and valve is not None
    pump.description = "UNSAVED_A"
    library.update_template(pump)
    valve.description = "SAVED_B"
    library.update_template(valve)
    library.save_template(library.get_template("Valve"))
    assert library.get_template("Pump").description == "UNSAVED_A"
    assert library.get_template("Valve").description == "SAVED_B"
    unsaved_new = library.create_template(display_name="Temp Skid")
    valve2 = library.get_template("Valve")
    valve2.description = "SAVED_B2"
    library.update_template(valve2)
    library.save_template(library.get_template("Valve"))
    assert library.get_template("Temp Skid") is not None
    assert library.get_template("Temp Skid").id == unsaved_new.id


def test_device_independence(tmp_path: Path) -> None:
    library = _copy_shipped(tmp_path)
    device = Device(
        id="a6-1",
        tag="P-601",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    library.apply_copy_to_device(device)
    device.signals[0].address = "Q0.0"
    device.signals[3].address = "I0.1"
    names_before = [signal.name for signal in device.signals]
    ids_before = [id(signal) for signal in device.signals]

    pump = library.get_template("Pump")
    assert pump is not None
    pump.description = "Library changed"
    pump.signals[0].name = "Start Command Edited"
    library.update_template(pump)
    library.save_template(pump)

    dup = library.duplicate_template("pump")
    dup.description = "Duplicate only"
    library.save_template(dup)

    library.delete_template("pump_copy", persist=True)

    assert [id(signal) for signal in device.signals] == ids_before
    assert [signal.name for signal in device.signals] == names_before
    assert device.signals[0].address == "Q0.0"
    assert device.signals[3].address == "I0.1"
    assert device.type == "Pump"


if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as raw:
        root = Path(raw)
        test_create_template(root / "c1")
        test_create_empty_template(root / "c2")
        test_duplicate_template(root / "d1")
        test_duplicate_regenerates_signal_ids_and_is_independent(root / "d2")
        test_update_template(root / "u1")
        test_duplicate_template_id_rejected(root / "r1")
        test_duplicate_signal_id_rejected(root / "r2")
        test_delete_template_memory_only(root / "del1")
        test_delete_unknown_template_rejected(root / "del2")
        test_delete_persist_removes_only_source_file(root / "del3")
        test_save_and_reload(root / "s1")
        test_utf8_korean_round_trip(root / "k1")
        test_malformed_persistence_error(root / "m1")
        test_update_unknown_id_rejected(root / "u2")
        test_save_preserves_other_unsaved_working_set_edits(root / "ws")
        test_device_independence(root / "dev")
    test_unique_display_name_and_id_generation()
    print("OK")
