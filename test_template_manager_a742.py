"""EOS-014-A7.4.2: Template Manager dialog-local signal draft editing."""

from __future__ import annotations

from PySide6.QtCore import Qt
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


def test_signal_name_draft_edit() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None
    original = pump.signals_in_order()[0].name

    _select_by_device_type(dialog, "Pump")
    _set_cell(dialog, 0, 0, "Start Command Draft")
    assert dialog.signal_table_rows()[0][0] == "Start Command Draft"
    drafts = dialog.signal_drafts_for(pump.id)
    assert drafts[0].name == "Start Command Draft"
    assert library.get_template_by_id(pump.id).signals_in_order()[0].name == original


def test_io_type_draft_edit() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None
    original = pump.signals_in_order()[0].signal_type

    _select_by_device_type(dialog, "Pump")
    _set_cell(dialog, 0, 1, "AI")
    assert dialog.signal_table_rows()[0][1] == "AI"
    assert dialog.signal_drafts_for(pump.id)[0].signal_type == "AI"
    assert (
        library.get_template_by_id(pump.id).signals_in_order()[0].signal_type
        == original
    )


def test_required_optional_draft_edit() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None
    original = pump.signals_in_order()[0].required

    _select_by_device_type(dialog, "Pump")
    _set_cell(dialog, 0, 2, "Optional")
    assert dialog.signal_table_rows()[0][2] == "Optional"
    assert dialog.signal_drafts_for(pump.id)[0].required is False
    assert (
        library.get_template_by_id(pump.id).signals_in_order()[0].required == original
    )


def test_switching_templates_preserves_signal_drafts() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    valve = library.get_template("Valve")
    assert pump is not None and valve is not None

    _select_by_device_type(dialog, "Pump")
    _set_cell(dialog, 0, 0, "Pump Signal Draft")
    _set_cell(dialog, 0, 1, "AO")
    _set_cell(dialog, 0, 2, "Optional")

    _select_by_device_type(dialog, "Valve")
    _set_cell(dialog, 0, 0, "Valve Signal Draft")
    _set_cell(dialog, 0, 1, "AI")

    _select_by_device_type(dialog, "Pump")
    assert dialog.signal_table_rows()[0] == ("Pump Signal Draft", "AO", "Optional")
    assert dialog.signal_drafts_for(pump.id)[0].name == "Pump Signal Draft"
    assert dialog.signal_drafts_for(pump.id)[0].signal_type == "AO"
    assert dialog.signal_drafts_for(pump.id)[0].required is False

    _select_by_device_type(dialog, "Valve")
    assert dialog.signal_table_rows()[0][0] == "Valve Signal Draft"
    assert dialog.signal_table_rows()[0][1] == "AI"
    assert dialog.signal_drafts_for(valve.id)[0].name == "Valve Signal Draft"


def test_library_remains_unchanged_after_signal_drafts() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    before = _library_snapshot(library)
    dialog = TemplateManagerDialog(library)

    _select_by_device_type(dialog, "Pump")
    _set_cell(dialog, 0, 0, "Mutated")
    _set_cell(dialog, 0, 1, "AO")
    _set_cell(dialog, 1, 2, "Optional")
    _select_by_device_type(dialog, "Fan")
    _set_cell(dialog, 0, 0, "Fan Mutated")
    dialog.close()

    assert _library_snapshot(library) == before


def test_reopening_dialog_restores_library_values() -> None:
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
    _set_cell(dialog1, 0, 0, "Temporary Name")
    _set_cell(dialog1, 0, 1, "AO")
    _set_cell(dialog1, 0, 2, "Optional")
    dialog1.name_value.setText("Pump Draft")
    dialog1.name_value.textEdited.emit("Pump Draft")
    dialog1.apply_draft_button.click()
    dialog1.close()

    dialog2 = TemplateManagerDialog(library)
    _select_by_device_type(dialog2, "Pump")
    assert dialog2.name_value.text() == "Pump"
    assert dialog2.signal_table_rows() == original_rows
    assert _library_snapshot(library) == before


def test_display_name_draft_still_works() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    fan = library.get_template("Fan")
    assert fan is not None

    _select_by_device_type(dialog, "Fan")
    dialog.name_value.setText("Exhaust Fan")
    dialog.name_value.textEdited.emit("Exhaust Fan")
    dialog.apply_draft_button.click()
    assert dialog.template_list.currentItem().text() == "Exhaust Fan"

    _select_by_device_type(dialog, "Valve")
    for row in range(dialog.template_list.count()):
        item = dialog.template_list.item(row)
        if item is not None and item.data(ROLE_TEMPLATE_ID) == fan.id:
            assert item.text() == "Exhaust Fan"
            dialog.template_list.setCurrentRow(row)
            break
    assert dialog.name_value.text() == "Exhaust Fan"
    assert library.get_template_by_id(fan.id).device_type == "Fan"


def test_signal_cells_are_editable() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    _select_by_device_type(dialog, "Pump")
    item = dialog.signal_table.item(0, 0)
    assert item is not None
    assert bool(item.flags() & Qt.ItemFlag.ItemIsEditable)
    assert dialog.signal_table.itemDelegateForColumn(1) is not None
    assert dialog.signal_table.itemDelegateForColumn(2) is not None


if __name__ == "__main__":
    test_signal_name_draft_edit()
    test_io_type_draft_edit()
    test_required_optional_draft_edit()
    test_switching_templates_preserves_signal_drafts()
    test_library_remains_unchanged_after_signal_drafts()
    test_reopening_dialog_restores_library_values()
    test_display_name_draft_still_works()
    test_signal_cells_are_editable()
    print("OK")
