"""FC_IO Preview dialog (View)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.common.constants import PROJECT_AREAS
from app.engine.fc_io_generator import (
    FCIOGenerationResult,
    FCIOIssue,
    row_severity,
)
from app.model.fc_io_row import FCIORow

_HEADERS = (
    "No.",
    "Area",
    "Device Type",
    "Device Tag",
    "Device Description",
    "Signal Name",
    "I/O Type",
    "PLC Address",
    "Required",
    "Signal Description",
    "Remark",
)

_WARNING_BG = QColor("#FFF9C4")
_ERROR_BG = QColor("#FFCDD2")


class FCIOPreviewDialog(QDialog):
    """Resizable preview of generated project FC_IO rows."""

    export_excel_requested = Signal()

    def __init__(
        self,
        result: FCIOGenerationResult,
        *,
        refresh_callback: Callable[[], FCIOGenerationResult] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("FC_IO Preview")
        self.resize(1100, 640)
        self.setModal(True)

        self._refresh_callback = refresh_callback
        self._result = result
        self._all_rows: tuple[FCIORow, ...] = result.rows

        self.summary_label = QLabel()
        self.issues_label = QLabel()
        self.area_filter = QComboBox()
        self.io_filter = QComboBox()
        self.tag_search = QLineEdit()
        self.table = QTableWidget(0, len(_HEADERS))
        self.refresh_button = QPushButton("Refresh")
        self.export_button = QPushButton("Export Excel")
        self.close_button = QPushButton("Close")

        self._build_ui()
        self._load_result(result)

        self.area_filter.currentIndexChanged.connect(self._apply_filters)
        self.io_filter.currentIndexChanged.connect(self._apply_filters)
        self.tag_search.textChanged.connect(self._apply_filters)
        self.refresh_button.clicked.connect(self._on_refresh)
        self.export_button.clicked.connect(self._on_export_excel)
        self.close_button.clicked.connect(self.accept)

    @property
    def result(self) -> FCIOGenerationResult:
        """Latest full-project FC_IO result (not filter-limited)."""
        return self._result

    def refresh_result(self) -> FCIOGenerationResult:
        """Regenerate from callback when available and return full result."""
        if self._refresh_callback is not None:
            self._load_result(self._refresh_callback())
        return self._result

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self.summary_label)
        self.issues_label.setWordWrap(True)
        self.issues_label.setStyleSheet("color: #B71C1C;")
        layout.addWidget(self.issues_label)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        filters.addWidget(QLabel("Area"))
        self.area_filter.addItem("Show All", "")
        for area in PROJECT_AREAS:
            self.area_filter.addItem(area, area)
        filters.addWidget(self.area_filter)

        filters.addWidget(QLabel("I/O Type"))
        self.io_filter.addItem("Show All", "")
        for io_type in ("DI", "DO", "AI", "AO"):
            self.io_filter.addItem(io_type, io_type)
        filters.addWidget(self.io_filter)

        filters.addWidget(QLabel("Device Tag"))
        self.tag_search.setPlaceholderText("Search tag…")
        self.tag_search.setClearButtonEnabled(True)
        filters.addWidget(self.tag_search, stretch=1)
        layout.addLayout(filters)

        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, stretch=1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        self.export_button.setEnabled(True)
        self.export_button.setToolTip("Export the full project FC_IO to Excel.")
        buttons.addWidget(self.export_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _load_result(self, result: FCIOGenerationResult) -> None:
        self._result = result
        self._all_rows = result.rows
        self.summary_label.setText(
            f"Rows: {result.total_count}    "
            f"DI: {result.di_count}    "
            f"DO: {result.do_count}    "
            f"AI: {result.ai_count}    "
            f"AO: {result.ao_count}    "
            f"Warnings: {result.warning_count}    "
            f"Errors: {result.error_count}"
        )
        self.issues_label.setText(self._format_issues(result.warnings, result.errors))
        self._apply_filters()

    @staticmethod
    def _format_issues(
        warnings: Sequence[FCIOIssue],
        errors: Sequence[FCIOIssue],
    ) -> str:
        lines: list[str] = []
        for issue in errors[:8]:
            lines.append(f"ERROR: {issue.message}")
        for issue in warnings[:8]:
            lines.append(f"WARNING: {issue.message}")
        remaining = (len(errors) + len(warnings)) - len(lines)
        if remaining > 0:
            lines.append(f"… and {remaining} more")
        return "\n".join(lines)

    def _filtered_rows(self) -> list[FCIORow]:
        area = self.area_filter.currentData()
        io_type = self.io_filter.currentData()
        tag_query = self.tag_search.text().strip().casefold()

        rows: list[FCIORow] = []
        for row in self._all_rows:
            if area and row.area != area:
                continue
            if io_type and row.io_type != io_type:
                continue
            if tag_query and tag_query not in row.device_tag.casefold():
                continue
            rows.append(row)
        return rows

    def _apply_filters(self) -> None:
        rows = self._filtered_rows()
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))

        for index, row in enumerate(rows):
            values = (
                str(index + 1),
                row.area,
                row.device_type,
                row.device_tag,
                row.device_description,
                row.signal_name,
                row.io_type,
                row.plc_address,
                "Yes" if row.required else "No",
                row.signal_description,
                row.remark,
            )
            severity = row_severity(row, self._result.warnings, self._result.errors)
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                if severity == "error":
                    item.setBackground(_ERROR_BG)
                elif severity == "warning":
                    item.setBackground(_WARNING_BG)
                self.table.setItem(index, column, item)

        self.table.resizeColumnsToContents()

    def _on_refresh(self) -> None:
        self.refresh_result()

    def _on_export_excel(self) -> None:
        self.refresh_result()
        self.export_excel_requested.emit()
