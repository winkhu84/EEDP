"""Main window controller (Controller).

Wires the view to business services. No domain rules inline.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from app.engine.device_manager import DeviceDraft, DeviceManager
from app.engine.io_list_parser import IoListParser
from app.engine.recommendation_engine import RecommendationEngine, build_io_summary
from app.ui.main_window import MainWindow


class MainController:
    """Coordinates the main window UI with in-memory services."""

    def __init__(
        self,
        view: MainWindow,
        device_manager: DeviceManager | None = None,
        recommendation_engine: RecommendationEngine | None = None,
        io_list_parser: IoListParser | None = None,
    ) -> None:
        self._view = view
        self._device_manager = device_manager or DeviceManager()
        self._recommendation_engine = recommendation_engine or RecommendationEngine()
        self._io_list_parser = io_list_parser or IoListParser()

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

        self._view.project_tree.tree.itemSelectionChanged.connect(
            self._on_tree_selection_changed
        )
        self._view.property_editor.recommendation_changed.connect(
            self._on_recommendation_changed
        )
        self._update_device_action_state()

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
        device = self._device_manager.add_device(draft)
        if device is None:
            return

        item = self._view.project_tree.add_device(device)
        if item is not None:
            self._view.project_tree.select_device_item(item)

    def _on_remove_device(self) -> None:
        device_id = self._view.project_tree.selected_device_id()
        if device_id is None:
            return

        device = self._device_manager.get_by_id(device_id)
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

        removed = self._device_manager.remove_device(device_id)
        if removed is None:
            return

        self._view.project_tree.remove_device_by_id(device_id)
        self._view.property_editor.clear()
        self._update_device_action_state()

    def _on_duplicate_device(self) -> None:
        device_id = self._view.project_tree.selected_device_id()
        if device_id is None:
            return

        device = self._device_manager.duplicate_device(device_id)
        if device is None:
            return

        item = self._view.project_tree.add_device(device)
        if item is not None:
            self._view.project_tree.select_device_item(item)

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

    def _on_tree_selection_changed(self) -> None:
        device_id = self._view.project_tree.selected_device_id()
        self._update_device_action_state()

        if device_id is None:
            self._view.property_editor.clear()
            return

        device = self._device_manager.get_by_id(device_id)
        if device is None:
            self._view.property_editor.clear()
            return

        result = self._recommendation_engine.recommend(device)
        self._view.property_editor.show_device(device, result)
        self._refresh_io_summary()

    def _on_recommendation_changed(self) -> None:
        self._refresh_io_summary()

    def _refresh_io_summary(self) -> None:
        summary = build_io_summary(self._view.property_editor.enabled_signal_types())
        self._view.property_editor.set_io_summary(summary)

    def _update_device_action_state(self) -> None:
        has_device = self._view.project_tree.selected_device_id() is not None
        self._view.toolbar.set_device_actions_enabled(has_device)

    def _on_new_project(self) -> None:
        return

    def _on_open_project(self) -> None:
        return

    def _on_save_project(self) -> None:
        return

    def _on_generate(self) -> None:
        return
