"""PLC Module Mapping dialog (View)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.common.constants import PROJECT_AREAS
from app.model.plc_module_mapping import (
    STATUS_CONFLICT,
    STATUS_SPARE,
    STATUS_USED,
    PLCModuleMapping,
    PLCModuleMappingResult,
)

_USED_BG = QColor("#C8E6C9")
_SPARE_BG = QColor("#EEEEEE")
_CONFLICT_BG = QColor("#FFCDD2")

_CHANNEL_HEADERS = (
    "Channel",
    "Address",
    "Status",
    "Area",
    "Device Tag",
    "Device Type",
    "Signal Name",
)

_SUMMARY_HEADERS = (
    "I/O Type",
    "Module",
    "Cards",
    "Used",
    "Total Channels",
    "Spare",
    "Conflicts",
    "Utilization",
)


class PLCModuleMappingDialog(QDialog):
    """Detailed PLC card/channel mapping for project signals."""

    def __init__(
        self,
        result: PLCModuleMappingResult,
        *,
        refresh_callback: Callable[[], PLCModuleMappingResult] | None = None,
        rack_slot_changed: Callable[[str, int, str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PLC Module Mapping")
        self.resize(1150, 700)
        self.setModal(True)

        self._refresh_callback = refresh_callback
        self._rack_slot_changed = rack_slot_changed
        self._result = result
        self._selected_module: PLCModuleMapping | None = None

        self.io_filter = QComboBox()
        self.module_combo = QComboBox()
        self.area_filter = QComboBox()
        self.tag_search = QLineEdit()
        self.card_list = QListWidget()
        self.header_label = QLabel()
        self.rack_edit = QLineEdit()
        self.slot_edit = QLineEdit()
        self.channel_table = QTableWidget(0, len(_CHANNEL_HEADERS))
        self.summary_table = QTableWidget(0, len(_SUMMARY_HEADERS))
        self.issues_label = QLabel()
        self.refresh_button = QPushButton("Refresh")
        self.export_button = QPushButton("Export Mapping Excel")
        self.close_button = QPushButton("Close")

        self._build_ui()
        self._load_result(result)

        self.io_filter.currentIndexChanged.connect(self._rebuild_card_list)
        self.module_combo.currentIndexChanged.connect(self._on_module_combo_changed)
        self.area_filter.currentIndexChanged.connect(self._render_selected_card)
        self.tag_search.textChanged.connect(self._render_selected_card)
        self.card_list.currentRowChanged.connect(self._on_card_selected)
        self.rack_edit.editingFinished.connect(self._on_rack_slot_edited)
        self.slot_edit.editingFinished.connect(self._on_rack_slot_edited)
        self.refresh_button.clicked.connect(self._on_refresh)
        self.close_button.clicked.connect(self.accept)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("I/O Type"))
        self.io_filter.addItem("Show All", "")
        for io_type in ("DI", "DO", "AI", "AO"):
            self.io_filter.addItem(io_type, io_type)
        filters.addWidget(self.io_filter)

        filters.addWidget(QLabel("Module Card"))
        filters.addWidget(self.module_combo, stretch=1)

        filters.addWidget(QLabel("Area"))
        self.area_filter.addItem("Show All", "")
        for area in PROJECT_AREAS:
            self.area_filter.addItem(area, area)
        filters.addWidget(self.area_filter)

        filters.addWidget(QLabel("Device Tag"))
        self.tag_search.setPlaceholderText("Search tag…")
        self.tag_search.setClearButtonEnabled(True)
        filters.addWidget(self.tag_search, stretch=1)
        layout.addLayout(filters)

        self.issues_label.setWordWrap(True)
        self.issues_label.setStyleSheet("color: #B71C1C;")
        layout.addWidget(self.issues_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Module / Card List"))
        left_layout.addWidget(self.card_list)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.header_label.setWordWrap(True)
        right_layout.addWidget(self.header_label)

        rack_form = QFormLayout()
        self.rack_edit.setPlaceholderText("Optional")
        self.slot_edit.setPlaceholderText("Optional")
        rack_form.addRow("Rack", self.rack_edit)
        rack_form.addRow("Slot", self.slot_edit)
        right_layout.addLayout(rack_form)

        self.channel_table.setHorizontalHeaderLabels(list(_CHANNEL_HEADERS))
        self.channel_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.channel_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.channel_table.verticalHeader().setVisible(False)
        self.channel_table.horizontalHeader().setStretchLastSection(True)
        right_layout.addWidget(self.channel_table, stretch=1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        layout.addWidget(QLabel("Project Module Summary"))
        self.summary_table.setHorizontalHeaderLabels(list(_SUMMARY_HEADERS))
        self.summary_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.setMaximumHeight(160)
        layout.addWidget(self.summary_table)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        self.export_button.setEnabled(False)
        self.export_button.setToolTip("Mapping Excel export will be available later.")
        buttons.addWidget(self.export_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def _load_result(self, result: PLCModuleMappingResult) -> None:
        self._result = result
        self.issues_label.setText(
            f"Warnings: {result.warning_count}    Errors: {result.error_count}"
        )
        self._populate_summary()
        self._rebuild_card_list()

    def _filtered_modules(self) -> list[PLCModuleMapping]:
        io_type = self.io_filter.currentData()
        modules = self._result.modules
        if io_type:
            modules = [module for module in modules if module.io_type == io_type]
        return list(modules)

    def _rebuild_card_list(self) -> None:
        modules = self._filtered_modules()
        self.card_list.blockSignals(True)
        self.module_combo.blockSignals(True)
        self.card_list.clear()
        self.module_combo.clear()
        self.module_combo.addItem("Select card…", None)
        for module in modules:
            item = QListWidgetItem(module.list_label())
            item.setData(Qt.ItemDataRole.UserRole, module)
            self.card_list.addItem(item)
            self.module_combo.addItem(module.combo_label(), module)
        self.card_list.blockSignals(False)
        self.module_combo.blockSignals(False)

        if modules:
            self.card_list.setCurrentRow(0)
        else:
            self._selected_module = None
            self._render_selected_card()

    def _on_module_combo_changed(self, index: int) -> None:
        if index <= 0:
            return
        module = self.module_combo.itemData(index)
        if module is None:
            return
        for row in range(self.card_list.count()):
            item = self.card_list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) is module:
                self.card_list.setCurrentRow(row)
                break

    def _on_card_selected(self, row: int) -> None:
        if row < 0:
            self._selected_module = None
            self._render_selected_card()
            return
        item = self.card_list.item(row)
        if item is None:
            self._selected_module = None
        else:
            self._selected_module = item.data(Qt.ItemDataRole.UserRole)
            # Sync combo without recursion.
            for index in range(self.module_combo.count()):
                if self.module_combo.itemData(index) is self._selected_module:
                    self.module_combo.blockSignals(True)
                    self.module_combo.setCurrentIndex(index)
                    self.module_combo.blockSignals(False)
                    break
        self._render_selected_card()

    def _assignment_matches_filters(self, area: str, device_tag: str) -> bool:
        area_filter = self.area_filter.currentData()
        tag_query = self.tag_search.text().strip().casefold()
        if area_filter and area != area_filter:
            return False
        if tag_query and tag_query not in device_tag.casefold():
            return False
        return True

    def _render_selected_card(self) -> None:
        module = self._selected_module
        self.channel_table.setRowCount(0)
        if module is None:
            self.header_label.setText("No module card selected.")
            self.rack_edit.setText("")
            self.slot_edit.setText("")
            self.rack_edit.setEnabled(False)
            self.slot_edit.setEnabled(False)
            return

        self.rack_edit.setEnabled(True)
        self.slot_edit.setEnabled(True)
        self.rack_edit.blockSignals(True)
        self.slot_edit.blockSignals(True)
        self.rack_edit.setText(module.rack)
        self.slot_edit.setText(module.slot)
        self.rack_edit.blockSignals(False)
        self.slot_edit.blockSignals(False)

        self.header_label.setText(
            f"Module: {module.module_name}\n"
            f"Card: {module.io_type} Card {module.card_number}\n"
            f"Address Range: {module.start_address} - {module.end_address}\n"
            f"Used: {module.used_channels}    "
            f"Spare: {module.spare_channels}    "
            f"Conflict: {module.conflict_channels}    "
            f"Utilization: {module.utilization_percent:.1f}%"
        )

        rows: list[tuple[str, ...]] = []
        fills: list[QColor] = []
        for channel in module.channels:
            if channel.status == STATUS_USED:
                fill = _USED_BG
            elif channel.status == STATUS_CONFLICT:
                fill = _CONFLICT_BG
            else:
                fill = _SPARE_BG

            matching = [
                assignment
                for assignment in channel.assignments
                if self._assignment_matches_filters(
                    assignment.area,
                    assignment.device_tag,
                )
            ]

            if not matching:
                rows.append(
                    (
                        f"CH{channel.channel_index}",
                        channel.channel_address,
                        channel.status,
                        "",
                        "",
                        "",
                        "",
                    )
                )
                fills.append(fill)
                continue

            for assignment in matching:
                rows.append(
                    (
                        f"CH{channel.channel_index}",
                        channel.channel_address,
                        channel.status,
                        assignment.area,
                        assignment.device_tag,
                        assignment.device_type,
                        assignment.signal_name,
                    )
                )
                fills.append(fill)

        self.channel_table.setRowCount(len(rows))
        for row_index, (values, fill) in enumerate(zip(rows, fills, strict=True)):
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                item.setBackground(fill)
                if column in {0, 1, 2}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.channel_table.setItem(row_index, column, item)
        self.channel_table.resizeColumnsToContents()

    def _populate_summary(self) -> None:
        summaries = self._result.summaries
        self.summary_table.setRowCount(len(summaries))
        for row, summary in enumerate(summaries):
            values = (
                summary.io_type,
                summary.module_name,
                str(summary.cards),
                str(summary.used),
                str(summary.total_channels),
                str(summary.spare),
                str(summary.conflicts),
                f"{summary.utilization_percent:.1f}%",
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                if column >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.summary_table.setItem(row, column, item)
        self.summary_table.resizeColumnsToContents()

    def _on_rack_slot_edited(self) -> None:
        module = self._selected_module
        if module is None:
            return
        rack = self.rack_edit.text().strip()
        slot = self.slot_edit.text().strip()
        module.rack = rack
        module.slot = slot
        if self._rack_slot_changed is not None:
            self._rack_slot_changed(module.io_type, module.card_number, rack, slot)

    def _on_refresh(self) -> None:
        if self._refresh_callback is None:
            return
        selected_key = None
        if self._selected_module is not None:
            selected_key = (
                self._selected_module.io_type,
                self._selected_module.card_number,
            )
        self._load_result(self._refresh_callback())
        if selected_key is None:
            return
        for row in range(self.card_list.count()):
            item = self.card_list.item(row)
            if item is None:
                continue
            module = item.data(Qt.ItemDataRole.UserRole)
            if (
                module is not None
                and module.io_type == selected_key[0]
                and module.card_number == selected_key[1]
            ):
                self.card_list.setCurrentRow(row)
                break
