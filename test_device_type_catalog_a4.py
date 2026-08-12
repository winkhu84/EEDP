"""EOS-014-A4: Device Type combo source-of-truth tests."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.common.constants import DEVICE_TYPES
from app.engine.device_manager import DeviceDraft, DeviceManager
from app.engine.device_type_catalog import (
    order_device_types,
    resolve_gui_device_types,
    sanitize_device_type_names,
)
from app.engine.recommendation_engine import RecommendationEngine
from app.engine.signal_engine import SignalEngine
from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.device import Device
from app.model.signal import Signal
from app.ui.main_controller import MainController
from app.ui.main_window import MainWindow
from app.ui.widgets.device_manager_widget import DeviceManagerWidget


_CURRENT_EIGHT = (
    "Pump",
    "Valve",
    "Fan",
    "Pressure Transmitter",
    "Flow Meter",
    "Level Sensor",
    "Thermocouple",
    "RTD",
)


def _qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_1_gui_types_come_from_library() -> None:
    library = SignalTemplateLibrary()
    resolved = resolve_gui_device_types(library.device_types())
    assert set(resolved) == set(library.device_types())
    assert set(_CURRENT_EIGHT).issubset(set(resolved))


def test_2_current_eight_types_remain_available() -> None:
    types = resolve_gui_device_types(SignalTemplateLibrary().device_types())
    for name in _CURRENT_EIGHT:
        assert name in types


def test_3_current_ordering_remains_stable() -> None:
    types = resolve_gui_device_types(SignalTemplateLibrary().device_types())
    assert types[: len(_CURRENT_EIGHT)] == _CURRENT_EIGHT
    assert types == DEVICE_TYPES


def test_4_no_duplicate_or_blank_types() -> None:
    messy = ("Pump", "", "  ", "Pump", "Valve", " Custom ", "Valve")
    cleaned = sanitize_device_type_names(messy)
    assert cleaned == ("Pump", "Valve", "Custom")
    ordered = order_device_types(("Fan", "Pump", "Fan", ""))
    assert ordered == ("Pump", "Fan")
    assert "" not in ordered
    assert len(ordered) == len(set(ordered))


def test_5_empty_library_falls_back_to_device_types() -> None:
    empty_root = Path(__file__).resolve().parent / "_missing_library_a4"
    library = SignalTemplateLibrary(library_root=empty_root)
    assert library.device_types() == ()
    resolved = resolve_gui_device_types(library.device_types())
    assert resolved == DEVICE_TYPES
    assert resolve_gui_device_types(()) == DEVICE_TYPES
    assert resolve_gui_device_types(None) == DEVICE_TYPES


def test_6_custom_type_is_appended_and_selectable() -> None:
    _qt_app()
    types = resolve_gui_device_types(
        SignalTemplateLibrary().device_types(),
        extra_types=("Unknown", "Custom Skid"),
    )
    assert types[:8] == _CURRENT_EIGHT
    assert "Unknown" in types
    assert "Custom Skid" in types
    assert len(types) == len(set(types))

    widget = DeviceManagerWidget()
    widget.set_device_types(types, selected="Unknown")
    assert "Unknown" in widget.device_types()
    assert widget.type_combo.currentText() == "Unknown"
    widget.set_device_types(types, selected="Pump")
    assert widget.type_combo.currentText() == "Pump"


def test_7_selecting_existing_device_does_not_wipe_signals() -> None:
    engine = RecommendationEngine()
    device = Device(
        id="a4-1",
        tag="P-301",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    engine.recommend(device)
    device.signals[0].address = "Q0.0"
    custom = SignalEngine().create_signal(
        name="Custom Interlock",
        io_type="DI",
        required=False,
        enabled=True,
        address="I1.7",
    )
    device.add_signal(custom)
    ids_before = [id(signal) for signal in device.signals]

    engine.ensure_signals(device)
    assert [id(signal) for signal in device.signals] == ids_before
    assert device.signals[0].address == "Q0.0"
    assert device.signals[-1] is custom


def test_8_add_device_pump_still_gets_template() -> None:
    device = Device(
        id="a4-2",
        tag="P-302",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    RecommendationEngine().recommend(device)
    assert [signal.name for signal in device.signals] == [
        "Start Command",
        "Stop Command",
        "Local/Remote Mode",
        "Run Feedback",
        "Fault Feedback",
    ]


def test_9_unknown_imported_type_does_not_get_a_template() -> None:
    engine = RecommendationEngine()
    imported = Device(
        id="a4-3",
        tag="ZZ-001",
        area="PRE",
        category="Unknown",
        type="Unknown",
        description="from excel",
        quantity=1,
        signals=[
            Signal(
                name="Imported DI",
                io_type="DI",
                required=False,
                enabled=True,
                address="I3.0",
            )
        ],
    )
    engine.ensure_signals(imported)
    engine.recommend(imported)
    assert len(imported.signals) == 1
    assert imported.signals[0].name == "Imported DI"
    assert imported.signals[0].address == "I3.0"

    empty_unknown = Device(
        id="a4-4",
        tag="ZZ-002",
        area="PRE",
        category="Unknown",
        type="Unknown",
        description="",
        quantity=1,
    )
    engine.ensure_signals(empty_unknown)
    assert empty_unknown.signals == []


def test_controller_refresh_uses_library_and_preserves_custom() -> None:
    _qt_app()
    window = MainWindow()
    devices = DeviceManager()
    devices.add_device(
        DeviceDraft(
            area="PRE",
            category="Unknown",
            type="Unknown",
            tag="ZZ-100",
            description="imported",
            quantity=1,
        )
    )
    controller = MainController(window, device_manager=devices)
    controller.bind()

    combo_types = window.device_manager.device_types()
    assert combo_types[:8] == _CURRENT_EIGHT
    assert set(SignalTemplateLibrary().device_types()).issubset(set(combo_types))
    assert "Unknown" in combo_types
    assert combo_types.count("Pump") == 1

    owned = devices.get_by_tag("ZZ-100")
    assert owned is not None
    assert owned.signals == []
    RecommendationEngine().ensure_signals(owned)
    assert owned.signals == []


if __name__ == "__main__":
    test_1_gui_types_come_from_library()
    test_2_current_eight_types_remain_available()
    test_3_current_ordering_remains_stable()
    test_4_no_duplicate_or_blank_types()
    test_5_empty_library_falls_back_to_device_types()
    test_6_custom_type_is_appended_and_selectable()
    test_7_selecting_existing_device_does_not_wipe_signals()
    test_8_add_device_pump_still_gets_template()
    test_9_unknown_imported_type_does_not_get_a_template()
    test_controller_refresh_uses_library_and_preserves_custom()
    print("OK")
