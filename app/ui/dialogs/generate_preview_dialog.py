"""Generate Preview dialog (View)."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from app.engine.generate_manager import GenerateManager, GenerationOptions
from app.engine.generate_preview_engine import (
    GeneratePreviewResult,
)
from app.model.device import Device
from app.model.generate_item import (
    STATUS_ERROR,
    STATUS_NOT_IMPLEMENTED,
    STATUS_READY,
    STATUS_WARNING,
    GenerateItem,
)
from app.model.generation_result import (
    GeneratedArtifact,
    GenerationResult,
    GenerationStatus,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUTPUT_GENERATED = _PROJECT_ROOT / "output" / "generated"
_DEFAULT_OUTPUT_PARENT = _PROJECT_ROOT / "output"

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

_ARTIFACT_STATUS_COLORS = {
    GenerationStatus.SUCCESS: QColor("#C8E6C9"),
    GenerationStatus.WARNING: QColor("#FFF9C4"),
    GenerationStatus.ERROR: QColor("#FFCDD2"),
    GenerationStatus.SKIPPED: QColor("#EEEEEE"),
}

_ARTIFACT_STATUS_LABELS = {
    GenerationStatus.SUCCESS: "● SUCCESS",
    GenerationStatus.WARNING: "● WARNING",
    GenerationStatus.ERROR: "● ERROR",
    GenerationStatus.SKIPPED: "● SKIPPED",
}

_ARTIFACT_STATUS_FG = {
    GenerationStatus.SUCCESS: QColor("#1B5E20"),
    GenerationStatus.WARNING: QColor("#E65100"),
    GenerationStatus.ERROR: QColor("#B71C1C"),
    GenerationStatus.SKIPPED: QColor("#424242"),
}

_ARTIFACT_CATEGORIES = {
    "FC_IO": "Engineering Data",
    "TIA_CSV": "PLC Integration",
    "TIA_XLSX": "PLC Integration",
    "GENERATION_REPORT": "Report",
}

_COL_SELECT = 0
_COL_FILE_NAME = 4
_COL_STATUS = 5
_COL_DESCRIPTION = 8
_MIN_FILE_NAME_WIDTH = 120
_MIN_STATUS_WIDTH = 100

_VALIDATION_OVERALL_STYLES = {
    "READY": ("#C8E6C9", "#1B5E20"),
    "WARNING": ("#FFF9C4", "#E65100"),
    "ERROR": ("#FFCDD2", "#B71C1C"),
}

_VALIDATION_CHECK_COUNT = 7

_VALIDATION_DETAILS_HEADERS = (
    "Severity",
    "Category",
    "Message",
)

_VALIDATION_SEVERITY_LABELS = {
    "PASS": "✔ PASS",
    "WARNING": "⚠ WARNING",
    "ERROR": "✖ ERROR",
}

_VALIDATION_SEVERITY_FG = {
    "PASS": QColor("#1B5E20"),
    "WARNING": QColor("#E65100"),
    "ERROR": QColor("#B71C1C"),
}

_VALIDATION_CHECK_CATEGORIES = {
    "devices": "Project",
    "enabled_signals": "Signal",
    "unaddressed_signals": "Address",
    "duplicate_addresses": "Address",
    "duplicate_tags": "Device",
    "output_directory": "Output",
    "engineering_outputs": "Export",
}


@dataclass(frozen=True)
class _ValidationSummaryCounts:
    """Aggregated validation summary values for the dialog header."""

    checks: int
    passed: int
    warnings: int
    errors: int
    overall_status: str


@dataclass(frozen=True)
class _ValidationIssue:
    """One validation summary issue shown in Warnings or Errors."""

    severity: str
    check_name: str
    message: str
    category: str = "Project"


class GeneratePreviewDialog(QDialog):
    """Unified preview of project outputs before generation."""

    generate_requested = Signal(object, str)  # list[GenerateItem], output_dir

    def __init__(
        self,
        result: GeneratePreviewResult,
        *,
        refresh_callback: Callable[[], GeneratePreviewResult] | None = None,
        devices_provider: Callable[[], list[Device]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generate Preview")
        self.setModal(True)
        self._apply_screen_limited_size(1050, 760)

        self._refresh_callback = refresh_callback
        self._devices_provider = devices_provider
        self._result = result
        self._last_generation_result: GenerationResult | None = None
        self._showing_generation_result = False
        self._validation_issues: list[_ValidationIssue] = []
        self._generate_button_label = "Generate Selected"

        self._summary_labels: dict[str, QLabel] = {}
        self._validation_summary_labels: dict[str, QLabel] = {}
        self.output_dir_edit = QLineEdit()
        self.browse_button = QPushButton("Browse")
        self.open_folder_button = QPushButton("Open Folder")
        self.fc_io_option_check = QCheckBox("FC_IO Excel")
        self.tia_csv_option_check = QCheckBox("TIA Tag CSV")
        self.tia_xlsx_option_check = QCheckBox("TIA Portal V20 Tags")
        self.generation_report_option_check = QCheckBox("Generation Report")
        self.timestamp_folder_option_check = QCheckBox(
            "Create timestamped run folder"
        )
        self.items_table = QTableWidget(0, len(_TABLE_HEADERS))
        self.validation_details_table = QTableWidget(
            0, len(_VALIDATION_DETAILS_HEADERS)
        )
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
                "output_path",
                "warnings",
                "errors",
                "fc_io_rows",
                "fc_io_counts",
                "unaddressed",
                "duplicates",
                "generated_at",
            )
        }
        for label in self._detail_labels.values():
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
        self._detail_labels["output_path"].setWordWrap(True)

        self._build_ui()
        self.set_generation_options(GenerationOptions())
        self._load_result(result)

        self.output_dir_edit.textChanged.connect(self.refresh_validation_summary)
        for option_check in (
            self.fc_io_option_check,
            self.tia_csv_option_check,
            self.tia_xlsx_option_check,
            self.timestamp_folder_option_check,
        ):
            option_check.toggled.connect(self.refresh_validation_summary)
        self.browse_button.clicked.connect(self._on_browse_output_dir)
        self.open_folder_button.clicked.connect(self._on_open_output_folder)
        self.items_table.itemSelectionChanged.connect(self._on_item_selected)
        self.items_table.cellChanged.connect(self._on_cell_changed)
        self.items_table.itemDoubleClicked.connect(self._on_result_row_double_clicked)
        self.items_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.items_table.customContextMenuRequested.connect(
            self._on_result_table_context_menu
        )
        self.refresh_button.clicked.connect(self._on_refresh)
        self.select_ready_button.clicked.connect(self._on_select_all_ready)
        self.clear_selection_button.clicked.connect(self._on_clear_selection)
        self.generate_button.clicked.connect(self._on_generate_selected)
        self.close_button.clicked.connect(self.reject)

    @property
    def result(self) -> GeneratePreviewResult:
        return self._result

    def _apply_screen_limited_size(
        self,
        preferred_width: int,
        preferred_height: int,
    ) -> None:
        """Resize within available screen geometry so the dialog fits on screen."""
        screen = self.screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(preferred_width, preferred_height)
            return

        available = screen.availableGeometry()
        margin = 48
        max_width = max(640, available.width() - margin)
        max_height = max(480, available.height() - margin)
        width = min(preferred_width, max_width)
        height = min(preferred_height, max_height)
        self.setMaximumHeight(max_height)
        self.resize(width, height)

    def get_generation_options(self) -> GenerationOptions:
        """Return GenerationOptions from the Generate Options checkboxes."""
        return GenerationOptions(
            generate_fc_io=self.fc_io_option_check.isChecked(),
            generate_tia_csv=self.tia_csv_option_check.isChecked(),
            generate_tia_xlsx=self.tia_xlsx_option_check.isChecked(),
            create_run_subdirectory=self.timestamp_folder_option_check.isChecked(),
        )

    def set_generation_options(self, options: GenerationOptions) -> None:
        """Update Generate Options checkboxes from GenerationOptions."""
        self.fc_io_option_check.setChecked(options.generate_fc_io)
        self.tia_csv_option_check.setChecked(options.generate_tia_csv)
        self.tia_xlsx_option_check.setChecked(options.generate_tia_xlsx)
        self.timestamp_folder_option_check.setChecked(
            options.create_run_subdirectory
        )
        # Generation Report remains checked and disabled (created automatically).
        self.generation_report_option_check.setChecked(True)
        self.generation_report_option_check.setEnabled(False)
        self.refresh_validation_summary()

    def refresh_validation_summary(self) -> None:
        """Recalculate summary and sync details/warning/error views."""
        issues = self._collect_validation_issues()
        self._validation_issues = issues
        counts = self._counts_from_validation_issues(issues)
        self._validation_summary_labels["checks"].setText(str(counts.checks))
        self._validation_summary_labels["passed"].setText(str(counts.passed))
        self._validation_summary_labels["warnings"].setText(str(counts.warnings))
        self._validation_summary_labels["errors"].setText(str(counts.errors))
        self._validation_summary_labels["overall_status"].setText(
            counts.overall_status
        )
        self._apply_validation_overall_status_style(counts.overall_status)
        self._populate_validation_details_table(issues)
        if not self._showing_generation_result:
            self._populate_validation_issue_panels(issues)

    def _collect_validation_issues(self) -> list[_ValidationIssue]:
        """Build the shared validation issue list for summary and panels."""
        summary = self._result.summary
        options = self.get_generation_options()
        output_dir = self.get_output_directory()
        issues: list[_ValidationIssue] = []

        if summary.device_count <= 0:
            issues.append(
                self._make_validation_issue(
                    "ERROR",
                    "devices",
                    "Project contains no devices.",
                )
            )

        if summary.enabled_signal_count <= 0:
            issues.append(
                self._make_validation_issue(
                    "WARNING",
                    "enabled_signals",
                    "Project has no enabled signals.",
                )
            )

        if summary.unaddressed_count > 0:
            issues.append(
                self._make_validation_issue(
                    "WARNING",
                    "unaddressed_signals",
                    (
                        "Enabled signals are missing PLC addresses "
                        f"({summary.unaddressed_count})."
                    ),
                )
            )

        if summary.duplicate_address_count > 0:
            issues.append(
                self._make_validation_issue(
                    "ERROR",
                    "duplicate_addresses",
                    (
                        "Duplicate PLC addresses exist "
                        f"({summary.duplicate_address_count})."
                    ),
                )
            )

        duplicate_tag = self._duplicate_tag_check_severity()
        if duplicate_tag is not None:
            issues.append(
                self._make_validation_issue(
                    duplicate_tag.upper(),
                    "duplicate_tags",
                    "Duplicate device tags exist.",
                )
            )

        if not output_dir:
            issues.append(
                self._make_validation_issue(
                    "ERROR",
                    "output_directory",
                    "Output directory is required.",
                )
            )

        if not (
            options.generate_fc_io
            or options.generate_tia_csv
            or options.generate_tia_xlsx
        ):
            issues.append(
                self._make_validation_issue(
                    "ERROR",
                    "engineering_outputs",
                    "Select at least one engineering output.",
                )
            )

        return issues

    @staticmethod
    def _make_validation_issue(
        severity: str,
        check_name: str,
        message: str,
    ) -> _ValidationIssue:
        """Create one ValidationIssue with a mapped display category."""
        return _ValidationIssue(
            severity=severity,
            check_name=check_name,
            message=message,
            category=_VALIDATION_CHECK_CATEGORIES.get(check_name, "Project"),
        )

    @staticmethod
    def _counts_from_validation_issues(
        issues: list[_ValidationIssue],
    ) -> _ValidationSummaryCounts:
        """Derive Validation Summary counts from the shared issue list."""
        checks = _VALIDATION_CHECK_COUNT
        warnings = sum(1 for issue in issues if issue.severity == "WARNING")
        errors = sum(1 for issue in issues if issue.severity == "ERROR")
        passed = max(0, checks - warnings - errors)
        if errors > 0:
            overall_status = "ERROR"
        elif warnings > 0:
            overall_status = "WARNING"
        else:
            overall_status = "READY"
        return _ValidationSummaryCounts(
            checks=checks,
            passed=passed,
            warnings=warnings,
            errors=errors,
            overall_status=overall_status,
        )

    def _populate_validation_issue_panels(
        self,
        issues: list[_ValidationIssue],
    ) -> None:
        """Fill Warnings/Errors panels from the shared validation issues."""
        self.warnings_list.clear()
        self.errors_list.clear()
        for issue in issues:
            if issue.severity == "WARNING":
                self.warnings_list.addItem(issue.message)
            elif issue.severity == "ERROR":
                self.errors_list.addItem(issue.message)

    def _populate_validation_details_table(
        self,
        issues: list[_ValidationIssue],
    ) -> None:
        """Fill Validation Details from the shared validation issue list."""
        rows: list[_ValidationIssue]
        if issues:
            rows = list(issues)
        else:
            rows = [
                _ValidationIssue(
                    severity="PASS",
                    check_name="none",
                    message="No validation issues detected.",
                    category="Project",
                )
            ]

        self.validation_details_table.setRowCount(0)
        self.validation_details_table.setRowCount(len(rows))
        for row, issue in enumerate(rows):
            severity_text = _VALIDATION_SEVERITY_LABELS.get(
                issue.severity,
                issue.severity,
            )
            severity_item = QTableWidgetItem(severity_text)
            category_item = QTableWidgetItem(issue.category)
            message_item = QTableWidgetItem(issue.message)
            fg = _VALIDATION_SEVERITY_FG.get(issue.severity, QColor("#212121"))
            for column, cell in enumerate(
                (severity_item, category_item, message_item)
            ):
                cell.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                cell.setForeground(fg)
                if column == 0:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.validation_details_table.setItem(row, column, cell)

        self.validation_details_table.resizeColumnToContents(0)
        self.validation_details_table.resizeColumnToContents(1)

    def _duplicate_tag_check_severity(self) -> str | None:
        """Return duplicate-tag severity from existing validation entries."""
        for entry in self._result.errors:
            if "Duplicate Device Tag" in entry.message:
                return "error"
        for entry in self._result.warnings:
            if "Duplicate Device Tag" in entry.message:
                return "warning"
        fc_io_result = self._result.fc_io_result
        if fc_io_result is not None:
            for issue in (*fc_io_result.errors, *fc_io_result.warnings):
                if issue.code == "DUPLICATE_DEVICE_TAG":
                    return issue.severity
        return None

    def _apply_validation_overall_status_style(self, overall_status: str) -> None:
        """Apply READY/WARNING/ERROR colors to the overall status label."""
        label = self._validation_summary_labels["overall_status"]
        bg_color, fg_color = _VALIDATION_OVERALL_STYLES.get(
            overall_status,
            ("#FFFFFF", "#212121"),
        )
        label.setAutoFillBackground(True)
        label.setStyleSheet(
            f"background-color: {bg_color}; color: {fg_color}; padding: 2px 8px;"
        )

    def get_output_directory(self) -> str:
        """Return a stripped absolute normalized path, or blank when empty."""
        text = self.output_dir_edit.text().strip()
        if not text:
            return ""
        return str(Path(text).expanduser().resolve(strict=False))

    def set_output_directory(self, path: str) -> None:
        """Update the Output Directory field from a blank or absolute path."""
        text = path.strip()
        if not text:
            self.output_dir_edit.clear()
            return
        normalized = str(Path(text).expanduser().resolve(strict=False))
        self.output_dir_edit.setText(normalized)
        self._update_item_output_paths(normalized)

    def _browse_start_directory(self) -> str:
        """Return the preferred starting folder for Browse."""
        current = self.output_dir_edit.text().strip()
        if current:
            current_path = Path(current).expanduser()
            if current_path.is_dir():
                return str(current_path.resolve())
            parent = current_path.parent
            if parent.is_dir():
                return str(parent.resolve())
        if _DEFAULT_OUTPUT_PARENT.is_dir():
            return str(_DEFAULT_OUTPUT_PARENT.resolve())
        return str(Path.home())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        content = QWidget()
        content.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(8)
        content_layout.setSizeConstraint(
            QVBoxLayout.SizeConstraint.SetMinimumSize
        )

        summary_box = QGroupBox("Project Summary", content)
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
        content_layout.addWidget(summary_box, 0)

        validation_summary_box = QGroupBox("Validation Summary", content)
        validation_grid = QGridLayout(validation_summary_box)
        validation_fields = (
            ("checks", "Checks"),
            ("passed", "Passed"),
            ("warnings", "Warnings"),
            ("errors", "Errors"),
            ("overall_status", "Overall Status"),
        )
        for index, (key, label) in enumerate(validation_fields):
            row = index // 3
            col = (index % 3) * 2
            validation_grid.addWidget(QLabel(label), row, col)
            value_label = QLabel("-")
            self._validation_summary_labels[key] = value_label
            validation_grid.addWidget(value_label, row, col + 1)
        content_layout.addWidget(validation_summary_box, 0)

        validation_details_box = QGroupBox("Validation Details", content)
        validation_details_layout = QVBoxLayout(validation_details_box)
        validation_details_layout.setContentsMargins(8, 8, 8, 8)
        self.validation_details_table.setHorizontalHeaderLabels(
            list(_VALIDATION_DETAILS_HEADERS)
        )
        self.validation_details_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.validation_details_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.validation_details_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.validation_details_table.verticalHeader().setVisible(False)
        self.validation_details_table.verticalHeader().setDefaultSectionSize(22)
        self.validation_details_table.setMinimumHeight(90)
        self.validation_details_table.setMaximumHeight(140)
        details_header = self.validation_details_table.horizontalHeader()
        details_header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        details_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        details_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        validation_details_layout.addWidget(self.validation_details_table)
        content_layout.addWidget(validation_details_box, 0)

        output_dir_row = QWidget(content)
        dir_row = QHBoxLayout(output_dir_row)
        dir_row.setContentsMargins(0, 0, 0, 0)
        dir_row.addWidget(QLabel("Output Directory"))
        self.output_dir_edit.setMinimumWidth(400)
        dir_row.addWidget(self.output_dir_edit, stretch=1)
        self.browse_button.setToolTip(
            "Select the parent folder for generated output."
        )
        self.open_folder_button.setToolTip("Open the selected output folder.")
        dir_row.addWidget(self.browse_button)
        dir_row.addWidget(self.open_folder_button)
        content_layout.addWidget(output_dir_row, 0)

        options_box = QGroupBox("Generate Options", content)
        options_layout = QHBoxLayout(options_box)
        options_layout.setContentsMargins(8, 8, 8, 8)
        options_layout.setSpacing(16)
        self.fc_io_option_check.setChecked(True)
        self.tia_csv_option_check.setChecked(True)
        self.tia_xlsx_option_check.setChecked(True)
        self.generation_report_option_check.setChecked(True)
        self.generation_report_option_check.setEnabled(False)
        self.generation_report_option_check.setToolTip(
            "Generation Report is created automatically."
        )
        self.timestamp_folder_option_check.setChecked(True)
        options_layout.addWidget(self.fc_io_option_check)
        options_layout.addWidget(self.tia_csv_option_check)
        options_layout.addWidget(self.tia_xlsx_option_check)
        options_layout.addWidget(self.generation_report_option_check)
        options_layout.addWidget(self.timestamp_folder_option_check)
        options_layout.addStretch()
        content_layout.addWidget(options_box, 0)

        # Row 1: deliverable table
        self.items_table.setParent(content)
        self.items_table.setHorizontalHeaderLabels(list(_TABLE_HEADERS))
        self.items_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.items_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.verticalHeader().setDefaultSectionSize(24)
        self.items_table.setMinimumHeight(180)
        self.items_table.setMaximumHeight(230)
        self.items_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._configure_table_column_sizing()
        content_layout.addWidget(self.items_table, 0)

        # Row 2: deliverable details (single instance)
        detail_box = QGroupBox("Deliverable Details", content)
        detail_grid = QGridLayout(detail_box)
        detail_grid.setContentsMargins(8, 8, 8, 8)
        detail_grid.setHorizontalSpacing(12)
        detail_grid.setVerticalSpacing(4)
        detail_rows = (
            (
                ("Deliverable", "deliverable"),
                ("File Name", "file_name"),
            ),
            (
                ("Output Format", "format"),
                ("Status", "status"),
            ),
            (
                ("Dependencies", "dependencies"),
                ("Output Path", "output_path"),
            ),
            (
                ("FC_IO Rows", "fc_io_rows"),
                ("FC_IO Counts", "fc_io_counts"),
            ),
            (
                ("Warnings", "warnings"),
                ("Errors", "errors"),
            ),
            (
                ("Unaddressed", "unaddressed"),
                ("Duplicate", "duplicates"),
            ),
        )
        for row_index, pairs in enumerate(detail_rows):
            for pair_index, (field_label, value_key) in enumerate(pairs):
                label_column = pair_index * 2
                value_column = label_column + 1
                name_label = QLabel(field_label)
                name_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                detail_grid.addWidget(name_label, row_index, label_column)
                detail_grid.addWidget(
                    self._detail_labels[value_key],
                    row_index,
                    value_column,
                )
        generated_label = QLabel("Generated At")
        generated_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        detail_grid.addWidget(generated_label, len(detail_rows), 0)
        detail_grid.addWidget(
            self._detail_labels["generated_at"],
            len(detail_rows),
            1,
            1,
            3,
        )
        detail_grid.setColumnStretch(1, 1)
        detail_grid.setColumnStretch(3, 1)
        detail_box.setMinimumHeight(150)
        detail_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._deliverable_details_box = detail_box
        content_layout.addWidget(detail_box, 0)

        # Row 3: warnings / errors side-by-side
        warnings_errors_row = QWidget(content)
        warnings_errors_layout = QHBoxLayout(warnings_errors_row)
        warnings_errors_layout.setContentsMargins(0, 0, 0, 0)
        warnings_errors_layout.setSpacing(8)
        warnings_box = QGroupBox("Warnings", warnings_errors_row)
        warnings_layout = QVBoxLayout(warnings_box)
        warnings_layout.addWidget(self.warnings_list)
        errors_box = QGroupBox("Errors", warnings_errors_row)
        errors_layout = QVBoxLayout(errors_box)
        errors_layout.addWidget(self.errors_list)
        self.warnings_list.setMinimumHeight(110)
        self.errors_list.setMinimumHeight(110)
        warnings_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        errors_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        warnings_errors_row.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        warnings_errors_layout.addWidget(warnings_box, 1)
        warnings_errors_layout.addWidget(errors_box, 1)
        content_layout.addWidget(warnings_errors_row, 0)

        scroll_area.setWidget(content)
        layout.addWidget(scroll_area, stretch=1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.select_ready_button)
        buttons.addWidget(self.clear_selection_button)
        buttons.addStretch(1)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    @staticmethod
    def _format_generated_at(output_path: str) -> str:
        """Return a readable generation timestamp from an output path."""
        if not output_path.strip():
            return "-"
        path = Path(output_path)
        if path.is_file():
            return datetime.fromtimestamp(path.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        parent_name = path.parent.name
        try:
            return datetime.strptime(parent_name, "%Y%m%d_%H%M%S").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            pass
        parent = path.parent
        if parent.is_dir():
            return datetime.fromtimestamp(parent.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        return "-"

    def _load_result(self, result: GeneratePreviewResult) -> None:
        self._showing_generation_result = False
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

        default_dir = result.output_directory.strip()
        if not default_dir:
            default_dir = str(_DEFAULT_OUTPUT_GENERATED)
        self.set_output_directory(default_dir)
        self._populate_items_table()
        if self.items_table.rowCount() > 0:
            self.items_table.selectRow(0)
        self.refresh_validation_summary()

    def display_generation_result(self, result: GenerationResult | None) -> None:
        """Replace preview rows with actual GenerateManager artifact results."""
        self._last_generation_result = result
        if result is None or not result.artifacts:
            self._showing_generation_result = False
            self._clear_generation_result_view()
            self.refresh_validation_summary()
            return

        self._showing_generation_result = True
        self._populate_generation_result_table(result)
        self.warnings_list.clear()
        self.errors_list.clear()
        if self.items_table.rowCount() > 0:
            self.items_table.selectRow(0)
            self._on_item_selected()
        else:
            self._clear_detail_panel()
        self.refresh_validation_summary()

    def _clear_generation_result_view(self) -> None:
        """Clear table, details, warnings, and errors."""
        self.items_table.blockSignals(True)
        self.items_table.setRowCount(0)
        self.items_table.blockSignals(False)
        self._clear_detail_panel()
        self.warnings_list.clear()
        self.errors_list.clear()

    def _clear_detail_panel(self) -> None:
        """Reset all deliverable detail labels."""
        for label in self._detail_labels.values():
            label.setText("-")

    @staticmethod
    def _artifact_category(artifact_type: str) -> str:
        return _ARTIFACT_CATEGORIES.get(artifact_type, "Other")

    @staticmethod
    def _format_from_path(output_path: str) -> str:
        suffix = Path(output_path).suffix.lstrip(".").upper()
        return suffix or "-"

    @staticmethod
    def _status_display_text(status: GenerationStatus) -> str:
        """Return table status text with a bullet indicator."""
        return _ARTIFACT_STATUS_LABELS.get(status, f"● {status.value}")

    def _configure_table_column_sizing(self) -> None:
        """Size Select compactly, stretch Description, keep key columns readable."""
        header = self.items_table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in range(len(_TABLE_HEADERS)):
            if column == _COL_SELECT:
                header.setSectionResizeMode(
                    column, QHeaderView.ResizeMode.Fixed
                )
            elif column == _COL_DESCRIPTION:
                header.setSectionResizeMode(
                    column, QHeaderView.ResizeMode.Stretch
                )
            else:
                header.setSectionResizeMode(
                    column, QHeaderView.ResizeMode.ResizeToContents
                )
        self.items_table.setColumnWidth(_COL_SELECT, 52)

    def _apply_result_column_sizing(self) -> None:
        """Resize result columns after populate while preserving stretch rules."""
        self._configure_table_column_sizing()
        self.items_table.resizeColumnsToContents()
        self.items_table.setColumnWidth(_COL_SELECT, 52)
        if self.items_table.columnWidth(_COL_FILE_NAME) < _MIN_FILE_NAME_WIDTH:
            self.items_table.setColumnWidth(_COL_FILE_NAME, _MIN_FILE_NAME_WIDTH)
        if self.items_table.columnWidth(_COL_STATUS) < _MIN_STATUS_WIDTH:
            self.items_table.setColumnWidth(_COL_STATUS, _MIN_STATUS_WIDTH)
        header = self.items_table.horizontalHeader()
        header.setSectionResizeMode(
            _COL_DESCRIPTION, QHeaderView.ResizeMode.Stretch
        )

    def _populate_generation_result_table(self, result: GenerationResult) -> None:
        """Fill the deliverables table from GeneratedArtifact rows."""
        self.items_table.blockSignals(True)
        self.items_table.setRowCount(0)
        self.items_table.setRowCount(len(result.artifacts))

        for row, artifact in enumerate(result.artifacts):
            checked = artifact.status in {
                GenerationStatus.SUCCESS,
                GenerationStatus.WARNING,
            }
            select_item = QTableWidgetItem()
            select_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable,
            )
            select_item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            select_item.setData(Qt.ItemDataRole.UserRole, row)

            warning_count = 1 if artifact.status is GenerationStatus.WARNING else 0
            error_count = 1 if artifact.status is GenerationStatus.ERROR else 0
            file_name = Path(artifact.output_path).name
            status_item = QTableWidgetItem(
                self._status_display_text(artifact.status)
            )
            status_item.setForeground(
                _ARTIFACT_STATUS_FG.get(artifact.status, QColor("#212121"))
            )
            file_item = QTableWidgetItem(file_name)
            description_item = QTableWidgetItem(artifact.message)
            if artifact.output_path:
                file_item.setToolTip(artifact.output_path)
            if artifact.message:
                status_item.setToolTip(artifact.message)
                description_item.setToolTip(artifact.message)

            values = (
                select_item,
                QTableWidgetItem(self._artifact_category(artifact.artifact_type)),
                QTableWidgetItem(artifact.display_name),
                QTableWidgetItem(self._format_from_path(artifact.output_path)),
                file_item,
                status_item,
                QTableWidgetItem(str(warning_count)),
                QTableWidgetItem(str(error_count)),
                description_item,
            )
            fill = _ARTIFACT_STATUS_COLORS.get(
                artifact.status,
                QColor("#FFFFFF"),
            )
            for column, cell in enumerate(values):
                if column == 0:
                    self.items_table.setItem(row, column, cell)
                    continue
                cell.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                cell.setBackground(fill)
                if column in {_COL_STATUS, 6, 7}:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.items_table.setItem(row, column, cell)

        self._apply_result_column_sizing()
        self.items_table.blockSignals(False)

    def _selected_artifact(self) -> GeneratedArtifact | None:
        """Return the GeneratedArtifact for the selected result row."""
        if (
            not self._showing_generation_result
            or self._last_generation_result is None
        ):
            return None
        row = self.items_table.currentRow()
        artifacts = self._last_generation_result.artifacts
        if row < 0 or row >= len(artifacts):
            return None
        return artifacts[row]

    def _open_artifact_containing_folder(
        self,
        artifact: GeneratedArtifact,
        *,
        require_file: bool = False,
    ) -> None:
        """Open the parent folder of an artifact output path."""
        output = Path(artifact.output_path)
        if require_file and not output.is_file():
            QMessageBox.warning(
                self,
                "Open Containing Folder",
                f"Output file does not exist:\n{artifact.output_path}",
            )
            return

        folder = output.parent
        if not folder.is_dir():
            QMessageBox.critical(
                self,
                "Open Containing Folder",
                f"Containing folder does not exist:\n{folder}",
            )
            return

        try:
            self._open_directory_in_explorer(folder)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Open Containing Folder",
                f"Failed to open containing folder:\n{exc}",
            )

    def _on_result_row_double_clicked(self, item: QTableWidgetItem) -> None:
        """Open the selected artifact folder when a result row is double-clicked."""
        if not self._showing_generation_result:
            return
        artifact = self._selected_artifact()
        if artifact is None:
            row = item.row()
            if (
                self._last_generation_result is None
                or row < 0
                or row >= len(self._last_generation_result.artifacts)
            ):
                return
            artifact = self._last_generation_result.artifacts[row]
        self._open_artifact_containing_folder(artifact, require_file=True)

    def _on_result_table_context_menu(self, pos: QPoint) -> None:
        """Show result-table actions for opening folder or copying path."""
        if not self._showing_generation_result:
            return

        index = self.items_table.indexAt(pos)
        if index.isValid():
            self.items_table.selectRow(index.row())

        menu = QMenu(self)
        open_action = QAction("Open Containing Folder", self)
        copy_action = QAction("Copy Output Path", self)
        open_action.triggered.connect(self._on_open_artifact_containing_folder)
        copy_action.triggered.connect(self._on_copy_artifact_output_path)
        menu.addAction(open_action)
        menu.addAction(copy_action)
        menu.exec(self.items_table.viewport().mapToGlobal(pos))

    def _on_open_artifact_containing_folder(self) -> None:
        """Open the selected artifact's parent directory."""
        if not self._showing_generation_result:
            return
        artifact = self._selected_artifact()
        if artifact is None:
            QMessageBox.warning(
                self,
                "Open Containing Folder",
                "Select a generation result row first.",
            )
            return
        self._open_artifact_containing_folder(artifact, require_file=False)

    def _on_copy_artifact_output_path(self) -> None:
        """Copy the selected artifact output path to the clipboard."""
        if not self._showing_generation_result:
            return
        artifact = self._selected_artifact()
        if artifact is None:
            QMessageBox.warning(
                self,
                "Copy Output Path",
                "Select a generation result row first.",
            )
            return
        path = artifact.output_path or ""
        QApplication.clipboard().setText(path)
        QToolTip.showText(
            QCursor.pos(),
            "Output path copied",
            self.items_table,
        )

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

    def _selected_item(self) -> GenerateItem | None:
        if self._showing_generation_result:
            return None
        row = self.items_table.currentRow()
        if row < 0 or row >= len(self._result.items):
            return None
        return self._result.items[row]

    def _on_item_selected(self) -> None:
        if self._showing_generation_result:
            self._update_generation_result_details()
            return

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
        self._detail_labels["output_path"].setText(item.output_path or "-")
        self._detail_labels["warnings"].setText(str(item.warning_count))
        self._detail_labels["errors"].setText(str(item.error_count))
        self._detail_labels["fc_io_rows"].setText(str(summary.fc_io_row_count))
        self._detail_labels["fc_io_counts"].setText(
            f"DI {summary.di_count}  DO {summary.do_count}  "
            f"AI {summary.ai_count}  AO {summary.ao_count}"
        )
        self._detail_labels["unaddressed"].setText(str(summary.unaddressed_count))
        self._detail_labels["duplicates"].setText(
            str(summary.duplicate_address_count)
        )
        self._detail_labels["generated_at"].setText("-")

    def _update_generation_result_details(self) -> None:
        """Update detail/warning/error panels from the selected artifact."""
        artifact = self._selected_artifact()
        self.warnings_list.clear()
        self.errors_list.clear()
        if artifact is None:
            self._clear_detail_panel()
            return

        warning_count = 1 if artifact.status is GenerationStatus.WARNING else 0
        error_count = 1 if artifact.status is GenerationStatus.ERROR else 0
        self._detail_labels["deliverable"].setText(artifact.display_name)
        self._detail_labels["file_name"].setText(Path(artifact.output_path).name)
        self._detail_labels["format"].setText(
            self._format_from_path(artifact.output_path)
        )
        self._detail_labels["status"].setText(artifact.status.value)
        self._detail_labels["dependencies"].setText("-")
        self._detail_labels["output_path"].setText(artifact.output_path or "-")
        self._detail_labels["warnings"].setText(str(warning_count))
        self._detail_labels["errors"].setText(str(error_count))
        self._detail_labels["fc_io_rows"].setText("-")
        self._detail_labels["fc_io_counts"].setText("-")
        self._detail_labels["unaddressed"].setText("-")
        self._detail_labels["duplicates"].setText("-")
        self._detail_labels["generated_at"].setText(
            self._format_generated_at(artifact.output_path)
        )

        if artifact.status is GenerationStatus.WARNING and artifact.message:
            self.warnings_list.addItem(artifact.message)
        if artifact.status is GenerationStatus.ERROR and artifact.message:
            self.errors_list.addItem(artifact.message)

    def _on_cell_changed(self, row: int, column: int) -> None:
        if column != 0:
            return
        if self._showing_generation_result:
            return
        if row < 0 or row >= len(self._result.items):
            return
        item = self._result.items[row]
        if not item.is_generatable:
            return
        cell = self.items_table.item(row, 0)
        if cell is None:
            return
        item.selected = cell.checkState() == Qt.CheckState.Checked

    def _sync_selection_from_table(self) -> None:
        if self._showing_generation_result:
            return
        for row, item in enumerate(self._result.items):
            if not item.is_generatable:
                item.selected = False
                continue
            cell = self.items_table.item(row, 0)
            if cell is None:
                continue
            item.selected = cell.checkState() == Qt.CheckState.Checked

    def _on_browse_output_dir(self) -> None:
        """Open a folder picker and update Output Directory when accepted."""
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self._browse_start_directory(),
        )
        if not selected:
            return
        self.set_output_directory(selected)

    def _update_item_output_paths(self, directory: str) -> None:
        out = Path(directory)
        for item in self._result.items:
            if item.file_name and item.file_name != "(no file)":
                item.output_path = str(out / item.file_name)

    def _open_directory_in_explorer(self, directory: Path) -> None:
        """Open a directory in the OS file explorer."""
        path = str(directory.resolve())
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)

    def _on_open_output_folder(self) -> None:
        """Open the Output Directory, creating it after confirmation if needed."""
        text = self.output_dir_edit.text().strip()
        if not text:
            QMessageBox.warning(
                self,
                "Open Folder",
                "Output Directory is blank.\nSelect a folder first.",
            )
            return

        path = Path(text).expanduser().resolve(strict=False)
        if not path.exists():
            confirm = QMessageBox.question(
                self,
                "Open Folder",
                (
                    "The output directory does not exist:\n"
                    f"{path}\n\n"
                    "Create it now?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(
                    self,
                    "Open Folder",
                    f"Failed to create output directory:\n{exc}",
                )
                return
            self.set_output_directory(str(path))

        if not path.is_dir():
            QMessageBox.critical(
                self,
                "Open Folder",
                f"Output path is not a directory:\n{path}",
            )
            return

        try:
            self._open_directory_in_explorer(path)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Open Folder",
                f"Failed to open output directory:\n{exc}",
            )

    def _on_refresh(self) -> None:
        if self._refresh_callback is None:
            return
        self._sync_selection_from_table()
        output_dir = self.get_output_directory()
        refreshed = self._refresh_callback()
        if output_dir:
            refreshed.output_directory = output_dir
            self._update_item_output_paths(output_dir)
        self._load_result(refreshed)

    def _on_select_all_ready(self) -> None:
        if self._showing_generation_result:
            artifacts = (
                self._last_generation_result.artifacts
                if self._last_generation_result is not None
                else []
            )
            self.items_table.blockSignals(True)
            for row in range(self.items_table.rowCount()):
                cell = self.items_table.item(row, 0)
                if cell is None:
                    continue
                status = (
                    artifacts[row].status
                    if row < len(artifacts)
                    else GenerationStatus.SKIPPED
                )
                cell.setCheckState(
                    Qt.CheckState.Checked
                    if status
                    in {GenerationStatus.SUCCESS, GenerationStatus.WARNING}
                    else Qt.CheckState.Unchecked
                )
            self.items_table.blockSignals(False)
            return

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
        if self._showing_generation_result:
            for row in range(self.items_table.rowCount()):
                cell = self.items_table.item(row, 0)
                if cell is not None:
                    cell.setCheckState(Qt.CheckState.Unchecked)
            self.items_table.blockSignals(False)
            return

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

    def _current_devices(self) -> list[Device]:
        """Return the current project devices from the provider."""
        if self._devices_provider is None:
            return []
        return list(self._devices_provider())

    def _on_generate_selected(self) -> None:
        """Validate options and run GenerateManager for selected outputs."""
        if self._refresh_callback is not None:
            self._on_refresh()

        options = self.get_generation_options()
        output_dir = self.get_output_directory()
        devices = self._current_devices()

        if not output_dir:
            QMessageBox.warning(
                self,
                "Generate Selected",
                "Output directory is required.",
            )
            return

        if not (
            options.generate_fc_io
            or options.generate_tia_csv
            or options.generate_tia_xlsx
        ):
            QMessageBox.warning(
                self,
                "Generate Selected",
                (
                    "Select at least one engineering output:\n"
                    "FC_IO Excel, TIA Tag CSV, or TIA Portal V20 Tags."
                ),
            )
            return

        if not devices:
            QMessageBox.warning(
                self,
                "Generate Selected",
                "The project must contain at least one device.",
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

        self.generate_button.setEnabled(False)
        self.generate_button.setText("Generating...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        result: GenerationResult | None = None
        failure: BaseException | None = None
        try:
            result = GenerateManager().generate(
                output_directory=output_dir,
                options=options,
                devices=devices,
            )
            self._last_generation_result = result
        except Exception as exc:  # noqa: BLE001 — keep UI resilient
            self._last_generation_result = None
            failure = exc
        finally:
            QApplication.restoreOverrideCursor()
            self.generate_button.setEnabled(True)
            self.generate_button.setText(self._generate_button_label)
            QApplication.processEvents()

        if failure is not None:
            QMessageBox.critical(
                self,
                "Generation Failed",
                f"Generation failed: {failure}",
            )
            return

        if result is not None:
            self.display_generation_result(result)
            self._show_generation_manager_summary(result)

    def _show_generation_manager_summary(self, result: GenerationResult) -> None:
        """Show a concise GenerationResult summary dialog."""
        message = (
            f"Output Directory:\n{result.output_directory}\n\n"
            f"Success: {result.success_count}\n"
            f"Warning: {result.warning_count}\n"
            f"Error: {result.error_count}\n"
            f"Skipped: {result.skipped_count}"
        )
        if result.has_errors:
            QMessageBox.warning(
                self,
                "Generation Completed with Errors",
                message,
            )
            return
        if result.is_successful:
            QMessageBox.information(
                self,
                "Generation Complete",
                message,
            )
            return
        QMessageBox.information(
            self,
            "Generation Complete",
            message,
        )

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
