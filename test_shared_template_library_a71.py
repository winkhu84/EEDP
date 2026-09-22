"""EOS-014-A7.1: shared SignalTemplateLibrary wiring tests."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.engine.recommendation_engine import RecommendationEngine
from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.device import Device
from app.ui.main_controller import MainController
from app.ui.main_window import MainWindow


_PUMP_ORDER = (
    "Start Command",
    "Stop Command",
    "Local/Remote Mode",
    "Run Feedback",
    "Fault Feedback",
)


def _qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_controller_and_recommendation_engine_share_library() -> None:
    _qt_app()
    window = MainWindow()
    controller = MainController(window)
    assert controller.template_library is controller._recommendation_engine.template_library
    assert isinstance(controller.template_library, SignalTemplateLibrary)


def test_injected_library_is_shared() -> None:
    _qt_app()
    window = MainWindow()
    library = SignalTemplateLibrary()
    engine = RecommendationEngine(template_library=library)
    controller = MainController(
        window,
        recommendation_engine=engine,
        template_library=library,
    )
    assert controller.template_library is library
    assert controller._recommendation_engine.template_library is library


def test_device_type_refresh_reads_shared_library() -> None:
    _qt_app()
    window = MainWindow()
    library = SignalTemplateLibrary()
    controller = MainController(window, template_library=library)
    controller.bind()
    combo_types = window.device_manager.device_types()
    assert set(library.device_types()).issubset(set(combo_types))
    assert combo_types[:8] == (
        "Pump",
        "Valve",
        "Fan",
        "Pressure Transmitter",
        "Flow Meter",
        "Level Sensor",
        "Thermocouple",
        "RTD",
    )


def test_recommended_signals_still_work_via_shared_library() -> None:
    library = SignalTemplateLibrary()
    engine = RecommendationEngine(template_library=library)
    device = Device(
        id="a71-1",
        tag="P-701",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    result = engine.recommend(device)
    assert [item.name for item in result.recommendations] == list(_PUMP_ORDER)
    assert [signal.name for signal in device.signals] == list(_PUMP_ORDER)
    assert engine.template_library is library


def test_pump_recommendations_unchanged() -> None:
    _qt_app()
    window = MainWindow()
    controller = MainController(window)
    device = Device(
        id="a71-2",
        tag="P-702",
        area="PRE",
        category="Equipment",
        type="Pump",
        description="Pump",
        quantity=1,
    )
    result = controller._recommendation_engine.recommend(device)
    assert [item.name for item in result.recommendations] == list(_PUMP_ORDER)
    assert [signal.name for signal in device.signals] == list(_PUMP_ORDER)
    assert controller.template_library.get_signals("Pump")[0].name == "Start Command"


if __name__ == "__main__":
    test_main_controller_and_recommendation_engine_share_library()
    test_injected_library_is_shared()
    test_device_type_refresh_reads_shared_library()
    test_recommended_signals_still_work_via_shared_library()
    test_pump_recommendations_unchanged()
    print("OK")
