"""Generate Preview dialog (View)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.engine.generate_preview_engine import (
    GeneratePreviewResult,
    ValidationEntry,
)
from app.model.generate_item import (
    STATUS_ERROR,
    STATUS_NOT_IMPLEMENTED,
    STATUS_READY,
    STATUS_WARNING,
    GenerateItem,
)

_TABLE_HEADERS = (
    "Select",
    "Category",
    "Deliverable",
    "Format",
    "File Name",
    "Status",
    "Warnings",
    "Errors",
    "Description",
)

_STATUS_COLORS = {
    STATUS_READY: QColor("#FFFFFF"),
    STATUS_WARNING: QColor("#FFF9C4"),
    STATUS_ERROR: QColor("#FFCDD2"),
    STATUS_NOT_IMPLEMENTED: QColor("#EEEEEE"),
}


class GeneratePreviewDialog(QDialog):
    """Unified preview of project outputs before generation."""

    generate_requested = Signal(object, str)  # list[GenerateItem], output_dir

    def __init__(
        self,
        result: GeneratePreviewResult,
        *,
        refresh_callback: Callable[[], GeneratePreviewResult] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generate Preview")
        self.resize(1050, 680)
        self.setModal(True)

        self._refresh_callback = refresh_callback
        self._result = result

        self._summary_labels: dict[str, QLabel] = {}
        self.output_dir_edit = QLineEdit()
        self.browse_button = QPushButton("Browse")
        self.open_folder_button = QPushButton("Open Folder")
        self.items_table = QTableWidget(0, len(_TABLE_HEADERS))
        self.detail_form = QFormLayout()
        self.detail_host = QWidget()
        self.warnings_list = QListWidget()
        self.errors_list = QListWidget()
        self.refresh_button = QPushButton("Refresh")
        self.select_ready_button = QPushButton("Select All Ready")
        self.clear_selection_button = QPushButton("Clear Selection")
        self.generate_button = QPushButton("Generate Selected")
        self.close_button = QPushButton("Close")

        self._detail_labels: dict[str, QLabel] = {
            key: QLabel("-")
            for key in (
                "deliverable",
                "file_name",
                "format",
                "status",
                "dependencies",
                "description",
                "fc_io_rows",
                "fc_io_counts",
                "unaddressed",
                "duplicates",
            )
        }

        self._build_ui()
        self._load_result(result)

        self.browse_button.clicked.connect(self._on_browse_output_dir)
        self.open_folder_button.clicked.connect(self._on_open_output_folder)
        self.items_table.itemSelectionChanged.connect(self._on_item_selected)
        self.items_table.cellChanged.connect(self._on_cell_changed)
        self.refresh_button.clicked.connect(self._on_refresh)
        self.select_ready_button.clicked.connect(self._on_select_all_ready)
        self.clear_selection_button.clicked.connect(self._on_clear_selection)
        self.generate_button.clicked.connect(self._on_generate_selected)
        self.close_button.clicked.connect(self.reject)

    @property
    def result(self) -> GeneratePreviewResult:
        return self._result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        summary_box = QGroupBox("Project Summary")
        summary_grid = QGridLayout(summary_box)
        fields = (
            ("customer", "Customer"),
            ("project_name", "Project Name"),
            ("revision", "Revision"),
            ("device_count", "Device Count"),
            ("enabled_signals", "Enabled Signal Count"),
            ("di", "DI Count"),
            ("do", "DO Count"),
            ("ai", "AI Count"),
            ("ao", "AO Count"),
            ("warnings", "Validation Warnings"),
            ("errors", "Validation Errors"),
        )
        for index, (key, label) in enumerate(fields):
            row = index // 3
            col = (index % 3) * 2
            summary_grid.addWidget(QLabel(label), row, col)
            value_label = QLabel("-")
            self._summary_labels[key] = value_label
            summary_grid.addWidget(value_label, row, col + 1)
        layout.addWidget(summary_box)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Output Directory"))
        self.output_dir_edit.setMinimumWidth(400)
        dir_row.addWidget(self.output_dir_edit, stretch=1)
        dir_row.addWidget(self.browse_button)
        dir_row.addWidget(self.open_folder_button)
        layout.addLayout(dir_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.items_table.setHorizontalHeaderLabels(list(_TABLE_HEADERS))
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.items_table.verticalHeader().setVisible(False)
        header = self.items_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        top_layout.addWidget(self.items_table)

        detail_box = QGroupBox("Deliverable Details")
        detail_layout = QVBoxLayout(detail_box)
        form = QFormLayout()
        form.addRow("Deliverable", self._detail_labels["deliverable"])
        form.addRow("File Name", self._detail_labels["file_name"])
        form.addRow("Output Format", self._detail_labels["format"])
        form.addRow("Status", self._detail_labels["status"])
        form.addRow("Dependencies", self._detail_labels["dependencies"])
        form.addRow("Description", self._detail_labels["description"])
        form.addRow("FC_IO Rows", self._detail_labels["fc_io_rows"])
        form.addRow("FC_IO Counts", self._detail_labels["fc_io_counts"])
        form.addRow("Unaddressed Signals", self._detail_labels["unaddressed"])
        form.addRow("Duplicate Addresses", self._detail_labels["duplicates"])
        detail_layout.addLayout(form)
        top_layout.addWidget(detail_box)
        splitter.addWidget(top)

        validation = QWidget()
        val_layout = QHBoxLayout(validation)
        val_layout.setContentsMargins(0, 0, 0, 0)
        warnings_box = QGroupBox("Warnings")
        warnings_layout = QVBoxLayout(warnings_box)
        warnings_layout.addWidget(self.warnings_list)
        errors_box = QGroupBox("Errors")
        errors_layout = QVBoxLayout(errors_box)
        errors_layout.addWidget(self.errors_list)
        val_layout.addWidget(warnings_box)
        val_layout.addWidget(errors_box)
        splitter.addWidget(validation)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.select_ready_button)
        buttons.addWidget(self.clear_selection_button)
        buttons.addStretch(1)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _load_result(self, result: GeneratePreviewResult) -> None:
        self._result = result
        summary = result.summary
        self._summary_labels["customer"].setText(summary.customer or "-")
        self._summary_labels["project_name"].setText(summary.display_project_name)
        self._summary_labels["revision"].setText(summary.revision or "-")
        self._summary_labels["device_count"].setText(str(summary.device_count))
        self._summary_labels["enabled_signals"].setText(
            str(summary.enabled_signal_count)
        )
        self._summary_labels["di"].setText(str(summary.di_count))
        self._summary_labels["do"].setText(str(summary.do_count))
        self._summary_labels["ai"].setText(str(summary.ai_count))
        self._summary_labels["ao"].setText(str(summary.ao_count))
        self._summary_labels["warnings"].setText(str(summary.warning_count))
        self._summary_labels["errors"].setText(str(summary.error_count))

        self.output_dir_edit.setText(result.output_directory)
        self._populate_items_table()
        self._populate_validation_lists()
        if self.items_table.rowCount() > 0:
            self.items_table.selectRow(0)

    def _populate_items_table(self) -> None:
        self.items_table.blockSignals(True)
        self.items_table.setRowCount(0)
        self.items_table.setRowCount(len(self._result.items))

        for row, item in enumerate(self._result.items):
            select_item = QTableWidgetItem()
            if item.is_generatable:
                select_item.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable,
                )
                select_item.setCheckState(
                    Qt.CheckState.Checked
                    if item.selected
                    else Qt.CheckState.Unchecked
                )
            else:
                select_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                select_item.setCheckState(Qt.CheckState.Unchecked)

            values = (
                select_item,
                QTableWidgetItem(item.category),
                QTableWidgetItem(item.display_name),
                QTableWidgetItem(item.output_format),
                QTableWidgetItem(item.file_name),
                QTableWidgetItem(item.status),
                QTableWidgetItem(str(item.warning_count)),
                QTableWidgetItem(str(item.error_count)),
                QTableWidgetItem(item.description),
            )
            fill = _STATUS_COLORS.get(item.status, QColor("#FFFFFF"))
            for column, cell in enumerate(values):
                if column == 0:
                    self.items_table.setItem(row, column, cell)
                    continue
                cell.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                cell.setBackground(fill)
                if column in {5, 6, 7}:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.items_table.setItem(row, column, cell)
            self.items_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.item_id)

        self.items_table.resizeColumnsToContents()
        self.items_table.blockSignals(False)

    def _populate_validation_lists(self) -> None:
        self.warnings_list.clear()
        self.errors_list.clear()
        for entry in self._result.warnings:
            self.warnings_list.addItem(self._format_validation_entry(entry))
        for entry in self._result.errors:
            self.errors_list.addItem(self._format_validation_entry(entry))

    @staticmethod
    def _format_validation_entry(entry: ValidationEntry) -> str:
        parts = [entry.severity.upper() + ":"]
        if entry.device_tag and entry.signal_name:
            parts.append(f"{entry.device_tag} / {entry.signal_name}")
        parts.append(entry.message)
        return " ".join(parts)

    def _selected_item(self) -> GenerateItem | None:
        row = self.items_table.currentRow()
        if row < 0 or row >= len(self._result.items):
            return None
        return self._result.items[row]

    def _on_item_selected(self) -> None:
        item = self._selected_item()
        summary = self._result.summary
        if item is None:
            return
        self._detail_labels["deliverable"].setText(item.display_name)
        self._detail_labels["file_name"].setText(item.file_name)
        self._detail_labels["format"].setText(item.output_format)
        self._detail_labels["status"].setText(item.status)
        self._detail_labels["dependencies"].setText(
            ", ".join(item.dependencies) if item.dependencies else "-"
        )
        self._detail_labels["description"].setText(item.description or "-")
        self._detail_labels["fc_io_rows"].setText(str(summary.fc_io_row_count))
        self._detail_labels["fc_io_counts"].setText(
            f"DI {summary.di_count}  DO {summary.do_count}  "
            f"AI {summary.ai_count}  AO {summary.ao_count}"
        )
        self._detail_labels["unaddressed"].setText(str(summary.unaddressed_count))
        self._detail_labels["duplicates"].setText(
            str(summary.duplicate_address_count)
        )

    def _on_cell_changed(self, row: int, column: int) -> None:
        if column != 0 or row < 0 or row >= len(self._result.items):
            return
        item = self._result.items[row]
        if not item.is_generatable:
            return
        cell = self.items_table.item(row, 0)
        if cell is None:
            return
        item.selected = cell.checkState() == Qt.CheckState.Checked

    def _sync_selection_from_table(self) -> None:
        for row, item in enumerate(self._result.items):
            if not item.is_generatable:
                item.selected = False
                continue
            cell = self.items_table.item(row, 0)
            if cell is None:
                continue
            item.selected = cell.checkState() == Qt.CheckState.Checked

    def _on_browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_dir_edit.text().strip() or str(Path.home()),
        )
        if path:
            self.output_dir_edit.setText(path)
            self._update_item_output_paths(path)

    def _update_item_output_paths(self, directory: str) -> None:
        out = Path(directory)
        for item in self._result.items:
            if item.file_name and item.file_name != "(no file)":
                item.output_path = str(out / item.file_name)

    def _on_open_output_folder(self) -> None:
        path = Path(self.output_dir_edit.text().strip())
        if path.exists():
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _on_refresh(self) -> None:
        if self._refresh_callback is None:
            return
        self._sync_selection_from_table()
        output_dir = self.output_dir_edit.text().strip()
        refreshed = self._refresh_callback()
        if output_dir:
            refreshed.output_directory = output_dir
            self._update_item_output_paths(output_dir)
        self._load_result(refreshed)

    def _on_select_all_ready(self) -> None:
        self.items_table.blockSignals(True)
        for row, item in enumerate(self._result.items):
            if not item.is_generatable:
                continue
            if item.status in {STATUS_READY, STATUS_WARNING}:
                item.selected = True
            cell = self.items_table.item(row, 0)
            if cell is not None and item.is_generatable:
                cell.setCheckState(
                    Qt.CheckState.Checked
                    if item.selected
                    else Qt.CheckState.Unchecked
                )
        self.items_table.blockSignals(False)

    def _on_clear_selection(self) -> None:
        self.items_table.blockSignals(True)
        for row, item in enumerate(self._result.items):
            if not item.is_generatable:
                continue
            item.selected = False
            cell = self.items_table.item(row, 0)
            if cell is not None:
                cell.setCheckState(Qt.CheckState.Unchecked)
        self.items_table.blockSignals(False)

    def _selected_generatable_items(self) -> list[GenerateItem]:
        self._sync_selection_from_table()
        return [item for item in self._result.items if item.selected and item.is_generatable]

    def _on_generate_selected(self) -> None:
        selected = self._selected_generatable_items()
        if not selected:
            QMessageBox.information(
                self,
                "Generate Selected",
                "Select at least one output item.",
            )
            return

        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(
                self,
                "Generate Selected",
                "Output directory is required.",
            )
            return

        if self._result.summary.error_count > 0:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Generate Selected")
            box.setText("Generation errors exist. Generate anyway?")
            generate_anyway = box.addButton(
                "Generate Anyway",
                QMessageBox.ButtonRole.AcceptRole,
            )
            cancel = box.addButton(QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is not generate_anyway:
                return

        self._update_item_output_paths(output_dir)
        self.generate_requested.emit(selected, output_dir)

    def show_generation_result(
        self,
        *,
        generated: list[str],
        failed: list[str],
        output_folder: str,
        warning_count: int,
        error_count: int,
    ) -> None:
        """Show post-generation result dialog."""
        generated_text = "\n".join(f"- {name}" for name in generated) or "None"
        failed_text = "\n".join(f"- {name}" for name in failed) or "None"
        message = (
            "Generation completed.\n\n"
            f"Generated:\n{generated_text}\n\n"
            f"Failed:\n{failed_text}\n\n"
            f"Output Folder:\n{output_folder}\n\n"
            f"Warnings: {warning_count}\n"
            f"Errors: {error_count}"
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Generation Result")
        box.setText(message)
        open_button = box.addButton(
            "Open Output Folder",
            QMessageBox.ButtonRole.ActionRole,
        )
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is open_button:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(output_folder).resolve()))
            )
