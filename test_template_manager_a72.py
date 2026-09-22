"""EOS-014-A7.2: Template Manager dialog shell and list tests."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.engine.signal_template_library import SignalTemplateLibrary
from app.ui.dialogs.template_manager_dialog import TemplateManagerDialog
from app.ui.main_controller import MainController
from app.ui.main_window import MainWindow


def _qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dialog_can_be_created() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    assert dialog.windowTitle() == "Template Manager"
    assert dialog.template_list.count() >= 8


def test_dialog_uses_shared_library_instance() -> None:
    _qt_app()
    window = MainWindow()
    controller = MainController(window)
    dialog = TemplateManagerDialog(controller.template_library)
    assert dialog.template_library is controller.template_library
    assert dialog.template_library is controller._recommendation_engine.template_library


def test_template_list_matches_library() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    names = [
        dialog.template_list.item(row).text()
        for row in range(dialog.template_list.count())
    ]
    assert names == [item.device_type for item in library.load_all()]


def test_selecting_template_updates_read_only_details() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None

    for row in range(dialog.template_list.count()):
        item = dialog.template_list.item(row)
        if item.text() == "Pump":
            dialog.template_list.setCurrentRow(row)
            break

    assert dialog.selected_template_id() == pump.id
    assert dialog.id_value.text() == pump.id
    assert dialog.name_value.text() == "Pump"
    assert dialog.signal_count_value.text() == str(len(pump.signals_in_order()))


def test_opening_dialog_does_not_modify_library() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    before_ids = [item.id for item in library.load_all()]
    before_pump = [
        (signal.id, signal.name) for signal in library.get_signals("Pump")
    ]
    dialog = TemplateManagerDialog(library)
    dialog.template_list.setCurrentRow(0)
    dialog.refresh_list()
    dialog.close()
    assert [item.id for item in library.load_all()] == before_ids
    assert [
        (signal.id, signal.name) for signal in library.get_signals("Pump")
    ] == before_pump


def test_toolbar_has_template_manager_button() -> None:
    _qt_app()
    window = MainWindow()
    controller = MainController(window)
    controller.bind()
    assert hasattr(window.toolbar, "template_manager_button")
    assert window.toolbar.template_manager_button.text() == "Template Manager"


if __name__ == "__main__":
    test_dialog_can_be_created()
    test_dialog_uses_shared_library_instance()
    test_template_list_matches_library()
    test_selecting_template_updates_read_only_details()
    test_opening_dialog_does_not_modify_library()
    test_toolbar_has_template_manager_button()
    print("OK")
