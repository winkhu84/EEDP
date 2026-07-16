"""Main window controller (Controller).

Wires the view to business services. No domain rules inline.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from app.engine.device_manager import DeviceDraft, DeviceManager, suggest_next_tag
from app.engine.io_list_parser import IoListParser
from app.engine.io_summary_engine import summarize_device, summarize_project
from app.engine.plc_card_calculator import calculate_project_cards
from app.engine.recommendation_engine import RecommendationEngine
from app.engine.signal_engine import SignalEngine
from app.model.plc_card_config import PlcCardConfig, default_plc_card_configurations
from app.ui.main_window import MainWindow


class MainController:
    """Coordinates the main window UI with in-memory services."""

    def __init__(
        self,
        view: MainWindow,
        device_manager: DeviceManager | None = None,
        recommendation_engine: RecommendationEngine | None = None,
        io_list_parser: IoListParser | None = None,
        signal_engine: SignalEngine | None = None,
    ) -> None:
        self._view = view
        self._device_manager = device_manager or DeviceManager()
        self._recommendation_engine = recommendation_engine or RecommendationEngine()
        self._io_list_parser = io_list_parser or IoListParser()
        self._signal_engine = signal_engine or SignalEngine()
        self._plc_card_configs: tuple[PlcCardConfig, ...] = (
            default_plc_card_configurations()
        )

    def bind(self) -> None:
        """Connect view signals to controller handlers."""
        toolbar = self._view.toolbar
        toolbar.new_project_button.clicked.connect(self._on_new_project)
        toolbar.open_project_button.clicked.connect(self._on_open_project)
        toolbar.save_project_button.clicked.connect(self._on_save_project)
        toolbar.generate_button.clicked.connect(self._on_generate)

        toolbar.add_device_button.clicked.connect(self._on_add_device)
        toolbar.remove_device_button.clicked.connect(self._on_remove_device)
        toolbar.duplicate_device_button.clicked.connect(self._on_duplicate_device)
        toolbar.import_io_list_button.clicked.connect(self._on_import_io_list)
        toolbar.debug_button.clicked.connect(self._on_debug)

        self._view.project_tree.tree.itemSelectionChanged.connect(
            self._on_tree_selection_changed
        )
        self._view.property_editor.recommendation_changed.connect(
            self._on_recommendation_changed
        )

        signal_editor = self._view.property_editor.signal_editor
        signal_editor.signal_changed.connect(self._on_signal_editor_changed)
        signal_editor.add_requested.connect(self._on_add_signal)
        signal_editor.remove_requested.connect(self._on_remove_signal)
        signal_editor.duplicate_requested.connect(self._on_duplicate_signal)

        self._update_device_action_state()
        self._refresh_io_summaries()

    def _selected_device(self):
        device_id = self._view.project_tree.selected_device_id()
        if device_id is None:
            return None
        return self._device_manager.get_by_id(device_id)

    def _on_add_device(self) -> None:
        panel = self._view.device_manager
        draft = DeviceDraft(
            area=panel.area_combo.currentText(),
            category=panel.category_combo.currentText(),
            type=panel.type_combo.currentText(),
            tag=panel.tag_edit.text().strip(),
            description=panel.description_edit.text().strip(),
            quantity=panel.quantity_spin.value(),
        )
        result = self._device_manager.add_devices_from_draft(draft)
        if not result.ok:
            message = result.error or "Failed to add device."
            QMessageBox.warning(self._view, "Add Device", message)
            return

        last_item = None
        for device in result.devices:
            self._recommendation_engine.ensure_signals(device)
            item = self._view.project_tree.add_device(device)
            if item is not None:
                last_item = item
        if last_item is not None:
            self._view.project_tree.select_device_item(last_item)

        panel.quantity_spin.setValue(1)
        last_tag = result.devices[-1].tag
        panel.tag_edit.setText(
            suggest_next_tag(last_tag, self._device_manager.tags())
        )
        self._refresh_io_summaries()

    def _on_remove_device(self) -> None:
        device = self._selected_device()
        if device is None:
            return

        reply = QMessageBox.question(
            self._view,
            "Remove Device",
            f"Remove device '{device.tag}' from the project?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        removed = self._device_manager.remove_device(device.id)
        if removed is None:
            return

        self._view.project_tree.remove_device_by_id(device.id)
        self._view.property_editor.clear()
        self._update_device_action_state()
        self._refresh_io_summaries()

    def _on_duplicate_device(self) -> None:
        device = self._selected_device()
        if device is None:
            return

        duplicated = self._device_manager.duplicate_device(device.id)
        if duplicated is None:
            return

        item = self._view.project_tree.add_device(duplicated)
        if item is not None:
            self._view.project_tree.select_device_item(item)
        self._refresh_io_summaries()

    def _on_import_io_list(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self._view,
            "Import IO List",
            "",
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        try:
            result = self._io_list_parser.parse(file_path)
        except ValueError as exc:
            QMessageBox.warning(self._view, "Import IO List", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - surface Excel read failures to user
            QMessageBox.warning(
                self._view,
                "Import IO List",
                f"Failed to read Excel file:\n{exc}",
            )
            return

        created = 0
        for draft in result.drafts:
            device = self._device_manager.add_device(draft)
            if device is None:
                continue
            self._view.project_tree.add_device(device)
            created += 1

        status = self._view.statusBar()
        if status is not None:
            status.showMessage(
                f"Imported {created} device(s) "
                f"({result.unique_tags} unique tags from {result.source_rows} rows).",
                6000,
            )
        self._refresh_io_summaries()

    def _on_tree_selection_changed(self) -> None:
        self._update_device_action_state()

        device = self._selected_device()
        if device is None:
            self._view.property_editor.clear()
            self._refresh_io_summaries()
            return

        # Apply recommendation when empty or when legacy Local/Remote Mode exists.
        result = self._recommendation_engine.ensure_signals(device)

        # DEBUG (testing only) — remove later
        print(device)
        print(len(device.signals))
        for signal in device.signals:
            print(signal.name)

        self._view.property_editor.show_device(device, result)
        self._refresh_io_summaries()

    def _on_recommendation_changed(self) -> None:
        device = self._selected_device()
        if device is not None:
            states = self._view.property_editor.recommendation_enable_states()
            for signal in device.signals:
                if signal.name in states:
                    signal.enabled = states[signal.name]
            self._view.property_editor.show_device_signals(device.signals)
        self._refresh_io_summaries()

    def _on_signal_editor_changed(self) -> None:
        device = self._selected_device()
        if device is None:
            return

        editor = self._view.property_editor.signal_editor
        for row in range(min(editor.row_count(), len(device.signals))):
            enabled, io_type, description, address, remark = editor.read_editable_fields(
                row
            )
            signal = device.signals[row]
            signal.enabled = enabled
            signal.io_type = io_type
            signal.description = description
            signal.address = address
            signal.remark = remark

        self._view.property_editor.sync_recommendation_enables(device.signals)
        self._refresh_io_summaries()

    def _on_add_signal(self) -> None:
        device = self._selected_device()
        if device is None:
            return

        name, ok = QInputDialog.getText(self._view, "Add Signal", "Signal Name:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return

        existing = {signal.name for signal in device.signals}
        if name in existing:
            QMessageBox.warning(self._view, "Add Signal", f"Signal '{name}' already exists.")
            return

        io_type, ok = QInputDialog.getItem(
            self._view,
            "Add Signal",
            "IO Type:",
            ["DI", "DO", "AI", "AO"],
            0,
            False,
        )
        if not ok:
            return

        signal = self._signal_engine.create_signal(
            name=name,
            io_type=io_type,
            required=False,
            enabled=True,
        )
        device.add_signal(signal)
        self._refresh_selected_device_view(device)

    def _on_remove_signal(self) -> None:
        device = self._selected_device()
        if device is None:
            return

        row = self._view.property_editor.signal_editor.selected_row()
        if row < 0 or row >= len(device.signals):
            return

        signal = device.signals[row]
        device.remove_signal(signal)
        self._refresh_selected_device_view(device)

    def _on_duplicate_signal(self) -> None:
        device = self._selected_device()
        if device is None:
            return

        row = self._view.property_editor.signal_editor.selected_row()
        if row < 0 or row >= len(device.signals):
            return

        source = device.signals[row]
        new_name = self._next_signal_name(source.name, {s.name for s in device.signals})
        signal = self._signal_engine.create_signal(
            name=new_name,
            io_type=source.io_type,
            required=False,
            enabled=source.enabled,
            address="",
            terminal=source.terminal,
            cable=source.cable,
            description=source.description,
            remark=source.remark,
        )
        device.add_signal(signal)
        self._refresh_selected_device_view(device)

    def _refresh_selected_device_view(self, device) -> None:
        result = self._recommendation_engine.recommendation_result(device)
        self._view.property_editor.show_device(device, result)
        self._refresh_io_summaries()

    @staticmethod
    def _next_signal_name(base_name: str, existing: set[str]) -> str:
        candidate = f"{base_name} Copy"
        if candidate not in existing:
            return candidate
        index = 2
        while f"{base_name} Copy {index}" in existing:
            index += 1
        return f"{base_name} Copy {index}"

    def _refresh_io_summaries(self) -> None:
        device = self._selected_device()
        device_summary = summarize_device(device, apply_quantity=False)
        project_summary = summarize_project(self._device_manager.devices)
        plc_requirements = calculate_project_cards(
            project_summary,
            self._plc_card_configs,
        )
        self._view.property_editor.set_device_io_summary(device_summary)
        self._view.property_editor.set_project_io_summary(project_summary)
        self._view.property_editor.set_plc_card_summary(plc_requirements)

    def _update_device_action_state(self) -> None:
        has_device = self._view.project_tree.selected_device_id() is not None
        self._view.toolbar.set_device_actions_enabled(has_device)

    def _on_debug(self) -> None:
        """Temporary debug dialog for the selected device."""
        device = self._selected_device()
        if device is None:
            QMessageBox.information(
                self._view,
                "Debug",
                "No device selected.",
            )
            return

        signal_names = "\n".join(f"- {signal.name}" for signal in device.signals)
        if not signal_names:
            signal_names = "(none)"

        message = (
            f"Device Tag: {device.tag}\n"
            f"Signal Count: {len(device.signals)}\n\n"
            f"Signal Names:\n{signal_names}"
        )
        QMessageBox.information(self._view, "Debug", message)

    def _on_new_project(self) -> None:
        return

    def _on_open_project(self) -> None:
        return

    def _on_save_project(self) -> None:
        return

    def _on_generate(self) -> None:
        return
