"""Device Signal Editor widget (View)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.model.signal import Signal as DeviceSignal

COL_ENABLE = 0
COL_NAME = 1
COL_IO_TYPE = 2
COL_REQUIRED = 3
COL_DESCRIPTION = 4
COL_ADDRESS = 5
COL_REMARK = 6

_HEADERS = (
    "Enable",
    "Signal Name",
    "IO Type",
    "Required",
    "Description",
    "Address",
    "Remark",
)


class SignalEditorWidget(QWidget):
    """Editable table of Device Signal objects."""

    signal_changed = Signal()
    add_requested = Signal()
    remove_requested = Signal()
    duplicate_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("signalEditor")

        self.table = QTableWidget(0, len(_HEADERS))
        self.add_button = QPushButton("Add Signal")
        self.remove_button = QPushButton("Remove Signal")
        self.duplicate_button = QPushButton("Duplicate Signal")

        self._build_ui()
        self.table.itemChanged.connect(self._on_item_changed)
        self.add_button.clicked.connect(self.add_requested.emit)
        self.remove_button.clicked.connect(self.remove_requested.emit)
        self.duplicate_button.clicked.connect(self.duplicate_requested.emit)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.table.setObjectName("signalEditorTable")
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.duplicate_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def clear(self) -> None:
        """Clear all rows."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.blockSignals(False)

    def populate(self, signals: list[DeviceSignal]) -> None:
        """Fill the table from device.signals."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.setRowCount(len(signals))

        for row, signal in enumerate(signals):
            self._set_row(row, signal)

        self.table.resizeColumnsToContents()
        self.table.blockSignals(False)

    def selected_row(self) -> int:
        """Return selected row index, or -1."""
        items = self.table.selectedItems()
        if not items:
            return -1
        return items[0].row()

    def row_count(self) -> int:
        return self.table.rowCount()

    def read_editable_fields(self, row: int) -> tuple[bool, str, str, str]:
        """Return (enabled, description, address, remark) for a row."""
        enable_item = self.table.item(row, COL_ENABLE)
        description_item = self.table.item(row, COL_DESCRIPTION)
        address_item = self.table.item(row, COL_ADDRESS)
        remark_item = self.table.item(row, COL_REMARK)

        enabled = (
            enable_item is not None
            and enable_item.checkState() == Qt.CheckState.Checked
        )
        description = description_item.text() if description_item else ""
        address = address_item.text() if address_item else ""
        remark = remark_item.text() if remark_item else ""
        return enabled, description, address, remark

    def _set_row(self, row: int, signal: DeviceSignal) -> None:
        enable_item = QTableWidgetItem()
        enable_item.setFlags(
            Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        enable_item.setCheckState(
            Qt.CheckState.Checked if signal.enabled else Qt.CheckState.Unchecked
        )
        enable_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        name_item = self._read_only_item(signal.name)
        io_item = self._read_only_item(signal.io_type)
        required_item = self._read_only_item("Yes" if signal.required else "No")

        description_item = QTableWidgetItem(signal.description)
        address_item = QTableWidgetItem(signal.address)
        remark_item = QTableWidgetItem(signal.remark)

        self.table.setItem(row, COL_ENABLE, enable_item)
        self.table.setItem(row, COL_NAME, name_item)
        self.table.setItem(row, COL_IO_TYPE, io_item)
        self.table.setItem(row, COL_REQUIRED, required_item)
        self.table.setItem(row, COL_DESCRIPTION, description_item)
        self.table.setItem(row, COL_ADDRESS, address_item)
        self.table.setItem(row, COL_REMARK, remark_item)

    @staticmethod
    def _read_only_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        )
        return item

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() in {
            COL_ENABLE,
            COL_DESCRIPTION,
            COL_ADDRESS,
            COL_REMARK,
        }:
            self.signal_changed.emit()
