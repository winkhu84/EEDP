"""EOS-014-A7.4.1: Template Manager read-only signal table."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QApplication

from app.engine.signal_template_library import SignalTemplateLibrary
from app.ui.dialogs.template_manager_dialog import (
    ROLE_TEMPLATE_ID,
    TemplateManagerDialog,
)


def _qt_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _library_snapshot(library: SignalTemplateLibrary) -> list[tuple]:
    return [
        (
            item.id,
            item.device_type,
            tuple(
                (signal.id, signal.name, signal.signal_type, signal.required)
                for signal in item.signals_in_order()
            ),
        )
        for item in library.load_all()
    ]


def _expected_rows(library: SignalTemplateLibrary, device_type: str) -> list[tuple[str, str, str]]:
    template = library.get_template(device_type)
    assert template is not None
    return [
        (
            signal.name,
            signal.signal_type,
            "Required" if signal.required else "Optional",
        )
        for signal in template.signals_in_order()
    ]


def _select_by_device_type(dialog: TemplateManagerDialog, device_type: str) -> None:
    library = dialog.template_library
    template = library.get_template(device_type)
    assert template is not None
    for row in range(dialog.template_list.count()):
        item = dialog.template_list.item(row)
        if item is not None and item.data(ROLE_TEMPLATE_ID) == template.id:
            dialog.template_list.setCurrentRow(row)
            return
    raise AssertionError(f"Template not found in list: {device_type!r}")


def test_signal_rows_match_selected_template() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    _select_by_device_type(dialog, "Pump")
    assert dialog.signal_table_rows() == _expected_rows(library, "Pump")
    assert dialog.signal_table.rowCount() == len(library.get_signals("Pump"))


def test_switching_templates_refreshes_signal_rows() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)

    _select_by_device_type(dialog, "Pump")
    pump_rows = dialog.signal_table_rows()
    assert pump_rows == _expected_rows(library, "Pump")

    _select_by_device_type(dialog, "Valve")
    valve_rows = dialog.signal_table_rows()
    assert valve_rows == _expected_rows(library, "Valve")
    assert valve_rows != pump_rows

    _select_by_device_type(dialog, "Fan")
    assert dialog.signal_table_rows() == _expected_rows(library, "Fan")


def test_signal_table_is_read_only() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    _select_by_device_type(dialog, "Pump")

    assert (
        dialog.signal_table.editTriggers()
        == QAbstractItemView.EditTrigger.NoEditTriggers
    )
    item = dialog.signal_table.item(0, 0)
    assert item is not None
    assert not bool(item.flags() & item.flags().ItemIsEditable)


def test_shared_library_not_mutated_by_signal_table() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    before = _library_snapshot(library)
    dialog = TemplateManagerDialog(library)

    _select_by_device_type(dialog, "Pump")
    _select_by_device_type(dialog, "Valve")
    _select_by_device_type(dialog, "Fan")
    # Touch draft path as well to ensure combined A7.3+A7.4.1 is inert.
    dialog.name_value.setText("Fan View Only")
    dialog.name_value.textEdited.emit("Fan View Only")
    dialog.apply_draft_button.click()
    dialog.close()

    assert _library_snapshot(library) == before


if __name__ == "__main__":
    test_signal_rows_match_selected_template()
    test_switching_templates_refreshes_signal_rows()
    test_signal_table_is_read_only()
    test_shared_library_not_mutated_by_signal_table()
    print("OK")
