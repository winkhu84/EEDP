"""EOS-014-A7.3: Template Manager dialog-local property draft editing."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

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
            tuple((signal.id, signal.name) for signal in item.signals_in_order()),
        )
        for item in library.load_all()
    ]


def _select_by_name(dialog: TemplateManagerDialog, name: str) -> None:
    for row in range(dialog.template_list.count()):
        item = dialog.template_list.item(row)
        if item is not None and item.text() == name:
            dialog.template_list.setCurrentRow(row)
            return
    raise AssertionError(f"Template list row not found: {name!r}")


def test_selected_template_loads_correct_properties() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None

    _select_by_name(dialog, "Pump")
    assert dialog.selected_template_id() == pump.id
    assert dialog.id_value.text() == pump.id
    assert dialog.name_value.text() == "Pump"
    assert dialog.signal_count_value.text() == str(len(pump.signals_in_order()))


def test_template_id_is_read_only() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    assert isinstance(dialog.id_value, QLabel)
    assert not isinstance(dialog.id_value, QLineEdit)


def test_display_name_is_editable() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    assert isinstance(dialog.name_value, QLineEdit)
    assert dialog.name_value.isReadOnly() is False
    assert dialog.name_value.isEnabled() is True


def test_apply_draft_updates_dialog_local_list_only() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    before = _library_snapshot(library)
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    assert pump is not None

    _select_by_name(dialog, "Pump")
    dialog.name_value.setText("Pump Draft")
    dialog.name_value.textEdited.emit("Pump Draft")
    dialog.apply_draft_button.click()

    assert dialog.template_list.currentItem().text() == "Pump Draft"
    draft = dialog.draft_for(pump.id)
    assert draft is not None
    assert draft.display_name == "Pump Draft"
    assert draft.list_label == "Pump Draft"
    assert library.get_template("Pump") is not None
    assert library.get_template_by_id(pump.id).device_type == "Pump"
    assert _library_snapshot(library) == before


def test_switching_templates_preserves_applied_drafts() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    dialog = TemplateManagerDialog(library)
    pump = library.get_template("Pump")
    valve = library.get_template("Valve")
    assert pump is not None and valve is not None

    _select_by_name(dialog, "Pump")
    dialog.name_value.setText("Pump Draft")
    dialog.name_value.textEdited.emit("Pump Draft")
    dialog.apply_draft_button.click()

    _select_by_name(dialog, "Valve")
    dialog.name_value.setText("Valve Draft")
    dialog.name_value.textEdited.emit("Valve Draft")
    dialog.apply_draft_button.click()

    pump_row = None
    valve_row = None
    for row in range(dialog.template_list.count()):
        item = dialog.template_list.item(row)
        assert item is not None
        item_id = item.data(ROLE_TEMPLATE_ID)
        if item_id == pump.id:
            pump_row = row
            assert item.text() == "Pump Draft"
        if item_id == valve.id:
            valve_row = row
            assert item.text() == "Valve Draft"

    assert pump_row is not None and valve_row is not None
    dialog.template_list.setCurrentRow(pump_row)
    assert dialog.name_value.text() == "Pump Draft"
    dialog.template_list.setCurrentRow(valve_row)
    assert dialog.name_value.text() == "Valve Draft"


def test_shared_library_unchanged_after_draft_edits() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    before = _library_snapshot(library)
    dialog = TemplateManagerDialog(library)

    _select_by_name(dialog, "Pump")
    dialog.name_value.setText("Mutated Pump")
    dialog.name_value.textEdited.emit("Mutated Pump")
    dialog.apply_draft_button.click()
    _select_by_name(dialog, "Valve")
    dialog.name_value.setText("Mutated Valve")
    dialog.name_value.textEdited.emit("Mutated Valve")
    # Switch away without Apply — draft preserved, library untouched.
    _select_by_name(dialog, "Fan")
    dialog.close()

    assert _library_snapshot(library) == before


def test_closing_and_reopening_restores_library_values() -> None:
    _qt_app()
    library = SignalTemplateLibrary()
    before = _library_snapshot(library)

    dialog1 = TemplateManagerDialog(library)
    _select_by_name(dialog1, "Pump")
    dialog1.name_value.setText("Temporary Name")
    dialog1.name_value.textEdited.emit("Temporary Name")
    dialog1.apply_draft_button.click()
    assert dialog1.template_list.currentItem().text() == "Temporary Name"
    dialog1.close()

    dialog2 = TemplateManagerDialog(library)
    names = [
        dialog2.template_list.item(row).text()
        for row in range(dialog2.template_list.count())
    ]
    assert names == [item.device_type for item in library.load_all()]
    _select_by_name(dialog2, "Pump")
    assert dialog2.name_value.text() == "Pump"
    assert _library_snapshot(library) == before


if __name__ == "__main__":
    test_selected_template_loads_correct_properties()
    test_template_id_is_read_only()
    test_display_name_is_editable()
    test_apply_draft_updates_dialog_local_list_only()
    test_switching_templates_preserves_applied_drafts()
    test_shared_library_unchanged_after_draft_edits()
    test_closing_and_reopening_restores_library_values()
    print("OK")
