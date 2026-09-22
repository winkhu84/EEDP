"""EOS-014-A7.4.3: Template Manager draft add/delete signals."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

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


def _select_by_device_type(dialog: TemplateManagerDialog, device_type: str) -> None:
    template = dialog.template_library.get_template(device_type)
    assert template is not None
    for row in range(dialog.template_list.count()):
        item = dialog.template_list.item(row)
        if item is not None and item.data(ROLE_TEMPLATE_ID) == template.id:
            dialog.template_list.setCurrentRow(row)
            return
    raise AssertionError(f"Template not found: {device_type!r}")


def _set_cell(dialog: TemplateManagerDialog, row: int, column: int, text: str) -> None:
    item = dialog.signal_table.item(row, column)
    assert item is not None
    item.setText(text)


def test_add_signal_appends_default_row() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None
    original_count = len(pump.signals_in_order())

    _select_by_device_type(dialog, "Pump")
    dialog.add_signal_button.click()

    assert dialog.signal_table.rowCount() == original_count + 1
    assert dialog.signal_count_value.text() == str(original_count + 1)
    assert dialog.signal_table_rows()[-1] == ("New Signal", "DI", "Optional")
    drafts = dialog.signal_drafts_for(pump.id)
    assert len(drafts) == original_count + 1
    assert drafts[-1].name == "New Signal"
    assert drafts[-1].signal_type == "DI"
    assert drafts[-1].required is False


def test_edit_newly_added_signal() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None

    _select_by_device_type(dialog, "Pump")
    dialog.add_signal_button.click()
    row = dialog.signal_table.rowCount() - 1
    _set_cell(dialog, row, 0, "Custom New")
    _set_cell(dialog, row, 1, "AO")
    _set_cell(dialog, row, 2, "Required")

    assert dialog.signal_table_rows()[row] == ("Custom New", "AO", "Required")
    draft = dialog.signal_drafts_for(pump.id)[row]
    assert draft.name == "Custom New"
    assert draft.signal_type == "AO"
    assert draft.required is True


def test_delete_selected_signal() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None
    original_count = len(pump.signals_in_order())
    first_name = pump.signals_in_order()[0].name

    _select_by_device_type(dialog, "Pump")
    dialog.signal_table.selectRow(0)
    dialog.delete_signal_button.click()

    assert dialog.signal_table.rowCount() == original_count - 1
    assert dialog.signal_count_value.text() == str(original_count - 1)
    assert all(row[0] != first_name for row in dialog.signal_table_rows())
    assert len(dialog.signal_drafts_for(pump.id)) == original_count - 1


def test_delete_with_no_selection_is_safe() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None
    original_count = len(pump.signals_in_order())

    _select_by_device_type(dialog, "Pump")
    dialog.signal_table.clearSelection()
    dialog.signal_table.setCurrentCell(-1, -1)
    assert dialog.signal_table.currentRow() < 0
    dialog.delete_signal_button.click()

    assert dialog.signal_table.rowCount() == original_count
    assert dialog.signal_count_value.text() == str(original_count)
    assert len(dialog.signal_drafts_for(pump.id)) == original_count


def test_number_of_signals_updates_on_add_and_delete() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    _select_by_device_type(dialog, "Fan")
    base = int(dialog.signal_count_value.text())

    dialog.add_signal_button.click()
    assert dialog.signal_count_value.text() == str(base + 1)
    dialog.signal_table.selectRow(0)
    dialog.delete_signal_button.click()
    assert dialog.signal_count_value.text() == str(base)


def test_switching_preserves_add_delete_drafts() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    valve = library.get_template("Valve")
    assert pump is not None and valve is not None
    pump_base = len(pump.signals_in_order())
    valve_base = len(valve.signals_in_order())

    _select_by_device_type(dialog, "Pump")
    dialog.add_signal_button.click()
    _set_cell(dialog, dialog.signal_table.rowCount() - 1, 0, "Pump Extra")

    _select_by_device_type(dialog, "Valve")
    dialog.signal_table.selectRow(0)
    deleted_name = dialog.signal_table_rows()[0][0]
    dialog.delete_signal_button.click()
    dialog.add_signal_button.click()
    _set_cell(dialog, dialog.signal_table.rowCount() - 1, 0, "Valve Extra")

    _select_by_device_type(dialog, "Pump")
    assert dialog.signal_table.rowCount() == pump_base + 1
    assert dialog.signal_table_rows()[-1][0] == "Pump Extra"
    assert dialog.signal_count_value.text() == str(pump_base + 1)

    _select_by_device_type(dialog, "Valve")
    assert dialog.signal_table.rowCount() == valve_base  # -1 +1
    assert dialog.signal_count_value.text() == str(valve_base)
    names = [row[0] for row in dialog.signal_table_rows()]
    assert deleted_name not in names
    assert "Valve Extra" in names


def test_drafts_independent_between_templates() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    fan = library.get_template("Fan")
    assert pump is not None and fan is not None

    _select_by_device_type(dialog, "Pump")
    dialog.add_signal_button.click()
    pump_count = len(dialog.signal_drafts_for(pump.id))

    _select_by_device_type(dialog, "Fan")
    assert len(dialog.signal_drafts_for(fan.id)) == len(fan.signals_in_order())
    assert len(dialog.signal_drafts_for(pump.id)) == pump_count


def test_library_unchanged_and_reopen_restores() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    before = _library_snapshot(library)
    pump = library.get_template("Pump")
    assert pump is not None
    original_rows = [
        (
            signal.name,
            signal.signal_type,
            "Required" if signal.required else "Optional",
        )
        for signal in pump.signals_in_order()
    ]

    dialog1 = TemplateManagerDialog(library)
    _select_by_device_type(dialog1, "Pump")
    dialog1.signal_table.selectRow(0)
    dialog1.delete_signal_button.click()
    dialog1.add_signal_button.click()
    _set_cell(dialog1, dialog1.signal_table.rowCount() - 1, 0, "Temp Extra")
    dialog1.close()

    assert _library_snapshot(library) == before

    dialog2 = TemplateManagerDialog(library)
    _select_by_device_type(dialog2, "Pump")
    assert dialog2.signal_table_rows() == original_rows
    assert dialog2.signal_count_value.text() == str(len(original_rows))
    assert _library_snapshot(library) == before


def test_a742_edit_still_works_after_add() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None
    original = pump.signals_in_order()[0]

    _select_by_device_type(dialog, "Pump")
    _set_cell(dialog, 0, 0, "Edited Existing")
    dialog.add_signal_button.click()
    assert dialog.signal_drafts_for(pump.id)[0].name == "Edited Existing"
    assert library.get_template_by_id(pump.id).signals_in_order()[0].name == original.name


if __name__ == "__main__":
    test_add_signal_appends_default_row()
    test_edit_newly_added_signal()
    test_delete_selected_signal()
    test_delete_with_no_selection_is_safe()
    test_number_of_signals_updates_on_add_and_delete()
    test_switching_preserves_add_delete_drafts()
    test_drafts_independent_between_templates()
    test_library_unchanged_and_reopen_restores()
    test_a742_edit_still_works_after_add()
    print("OK")
