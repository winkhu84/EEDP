"""TIA Portal Tag Preview dialog (View)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
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
from app.model.tia_tag import STATUS_ERROR, STATUS_OK, STATUS_WARNING, TIATag

_HEADERS = (
    "No.",
    "Symbol Name",
    "Data Type",
    "Logical Address",
    "Comment",
    "Area",
    "Device Tag",
    "Signal Name",
    "I/O Type",
    "Status",
)

_WARNING_BG = QColor("#FFF9C4")
_ERROR_BG = QColor("#FFCDD2")


class TIATagPreviewDialog(QDialog):
    """Resizable preview of generated project TIA Portal tags."""

    export_csv_requested = Signal()

    def __init__(
        self,
        tags: Sequence[TIATag],
        *,
        warnings: Sequence[str] = (),
        errors: Sequence[str] = (),
        refresh_callback: Callable[[], tuple[list[TIATag], list[str], list[str]]]
        | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("TIA Portal Tag Preview")
        self.setMinimumSize(1100, 650)
        self.resize(1100, 650)
        self.setModal(True)

        self._refresh_callback = refresh_callback
        self._all_tags: tuple[TIATag, ...] = tuple(tags)
        self._warnings: tuple[str, ...] = tuple(warnings)
        self._errors: tuple[str, ...] = tuple(errors)

        self.summary_label = QLabel()
        self.issues_label = QLabel()
        self.area_filter = QComboBox()
        self.io_filter = QComboBox()
        self.status_filter = QComboBox()
        self.tag_search = QLineEdit()
        self.table = QTableWidget(0, len(_HEADERS))
        self.detail_symbol_name = QLabel()
        self.detail_device_tag = QLabel()
        self.detail_signal_name = QLabel()
        self.detail_logical_address = QLabel()
        self.detail_status = QLabel()
        self.detail_validation_messages = QLabel()
        self.refresh_button = QPushButton("Refresh")
        self.export_button = QPushButton("Export CSV")
        self.close_button = QPushButton("Close")

        self._build_ui()
        self._load_data(tags, warnings, errors)

        self.area_filter.currentIndexChanged.connect(self._apply_filters)
        self.io_filter.currentIndexChanged.connect(self._apply_filters)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        self.tag_search.textChanged.connect(self._apply_filters)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.refresh_button.clicked.connect(self._on_refresh)
        self.export_button.clicked.connect(self.export_csv_requested.emit)
        self.close_button.clicked.connect(self.accept)

    @property
    def all_tags(self) -> tuple[TIATag, ...]:
        """Full project tag list (not filter-limited)."""
        return self._all_tags

    @property
    def warnings(self) -> tuple[str, ...]:
        """Project-level TIA validation warnings."""
        return self._warnings

    @property
    def errors(self) -> tuple[str, ...]:
        """Project-level TIA validation errors."""
        return self._errors

    def refresh_data(self) -> None:
        """Regenerate tags from callback when available."""
        if self._refresh_callback is None:
            return
        tags, warnings, errors = self._refresh_callback()
        self._load_data(tags, warnings, errors)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self.summary_label)
        self.issues_label.setWordWrap(True)
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

        filters.addWidget(QLabel("Status"))
        self.status_filter.addItem("Show All", "")
        for status in (STATUS_OK, STATUS_WARNING, STATUS_ERROR):
            self.status_filter.addItem(status, status)
        filters.addWidget(self.status_filter)

        filters.addWidget(QLabel("Device Tag"))
        self.tag_search.setPlaceholderText("Search tag…")
        self.tag_search.setClearButtonEnabled(True)
        filters.addWidget(self.tag_search, stretch=1)
        layout.addLayout(filters)

        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, stretch=1)

        detail_group = QGroupBox("Selected Tag")
        detail_form = QFormLayout(detail_group)
        detail_form.setContentsMargins(10, 12, 10, 10)
        detail_form.addRow("Symbol Name", self.detail_symbol_name)
        detail_form.addRow("Device Tag", self.detail_device_tag)
        detail_form.addRow("Signal Name", self.detail_signal_name)
        detail_form.addRow("Logical Address", self.detail_logical_address)
        detail_form.addRow("Status", self.detail_status)
        self.detail_validation_messages.setWordWrap(True)
        self.detail_validation_messages.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        detail_form.addRow("Validation Messages", self.detail_validation_messages)
        layout.addWidget(detail_group)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        self.export_button.setEnabled(True)
        self.export_button.setToolTip("Export all project TIA tags to CSV.")
        buttons.addWidget(self.export_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _load_data(
        self,
        tags: Sequence[TIATag],
        warnings: Sequence[str],
        errors: Sequence[str],
    ) -> None:
        self._all_tags = tuple(tags)
        self._warnings = tuple(warnings)
        self._errors = tuple(errors)
        self._update_summary()
        self.issues_label.setText(self._format_issues(warnings, errors))
        self._apply_filters()

    @staticmethod
    def _count_data_types(tags: Sequence[TIATag]) -> tuple[int, int]:
        bool_count = sum(1 for tag in tags if tag.data_type == "Bool")
        int_count = sum(1 for tag in tags if tag.data_type == "Int")
        return bool_count, int_count

    def _update_summary(self, filtered_count: int | None = None) -> None:
        bool_count, int_count = self._count_data_types(self._all_tags)
        summary = (
            f"Total Tags: {len(self._all_tags)}    "
            f"Bool: {bool_count}    "
            f"Int: {int_count}    "
            f"Warnings: {len(self._warnings)}    "
            f"Errors: {len(self._errors)}"
        )
        if filtered_count is not None and filtered_count != len(self._all_tags):
            summary += f"    Showing: {filtered_count}"
        self.summary_label.setText(summary)

    @staticmethod
    def _format_issues(
        warnings: Sequence[str],
        errors: Sequence[str],
    ) -> str:
        shown_errors = list(errors[:8])
        shown_warnings = list(warnings[:8])
        lines: list[str] = []
        for message in shown_errors:
            lines.append(f"ERROR:\n{message}")
        for message in shown_warnings:
            lines.append(f"WARNING:\n{message}")
        remaining = (len(errors) - len(shown_errors)) + (
            len(warnings) - len(shown_warnings)
        )
        if remaining > 0:
            lines.append(f"… and {remaining} more")
        return "\n\n".join(lines)

    def _filtered_tags(self) -> list[TIATag]:
        area = self.area_filter.currentData()
        io_type = self.io_filter.currentData()
        status = self.status_filter.currentData()
        tag_query = self.tag_search.text().strip().casefold()

        tags: list[TIATag] = []
        for tag in self._all_tags:
            if area and tag.area != area:
                continue
            if io_type and tag.io_type != io_type:
                continue
            if status and tag.status != status:
                continue
            if tag_query and tag_query not in tag.device_tag.casefold():
                continue
            tags.append(tag)
        return tags

    def _apply_filters(self) -> None:
        tags = self._filtered_tags()
        self._update_summary(filtered_count=len(tags))
        self.table.setRowCount(0)
        self.table.setRowCount(len(tags))

        for index, tag in enumerate(tags):
            values = (
                str(index + 1),
                tag.symbol_name,
                tag.data_type,
                tag.logical_address,
                tag.comment,
                tag.area,
                tag.device_tag,
                tag.signal_name,
                tag.io_type,
                tag.status,
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                if tag.status == STATUS_ERROR:
                    item.setBackground(_ERROR_BG)
                elif tag.status == STATUS_WARNING:
                    item.setBackground(_WARNING_BG)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, tag)
                self.table.setItem(index, column, item)

        self.table.resizeColumnsToContents()
        if tags:
            self.table.selectRow(0)
        else:
            self._clear_detail_panel()

    def _selected_tag(self) -> TIATag | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None
        tag = item.data(Qt.ItemDataRole.UserRole)
        return tag if isinstance(tag, TIATag) else None

    def _on_selection_changed(self) -> None:
        tag = self._selected_tag()
        if tag is None:
            self._clear_detail_panel()
            return

        self.detail_symbol_name.setText(tag.symbol_name)
        self.detail_device_tag.setText(tag.device_tag)
        self.detail_signal_name.setText(tag.signal_name)
        self.detail_logical_address.setText(tag.logical_address)
        self.detail_status.setText(tag.status)
        if tag.validation_messages:
            self.detail_validation_messages.setText(
                "\n".join(tag.validation_messages)
            )
        else:
            self.detail_validation_messages.setText("(none)")

    def _clear_detail_panel(self) -> None:
        self.detail_symbol_name.clear()
        self.detail_device_tag.clear()
        self.detail_signal_name.clear()
        self.detail_logical_address.clear()
        self.detail_status.clear()
        self.detail_validation_messages.clear()

    def _on_refresh(self) -> None:
        if self._refresh_callback is None:
            return
        tags, warnings, errors = self._refresh_callback()
        self._load_data(tags, warnings, errors)
