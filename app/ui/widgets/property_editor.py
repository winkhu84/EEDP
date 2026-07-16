"""Property editor widget (View)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.common.constants import NO_DEVICE_SELECTED
from app.model.device import Device
from app.model.recommendation import IoSummary, Recommendation, RecommendationResult
from app.model.signal import Signal as DeviceSignal
from app.ui.widgets.signal_editor_widget import SignalEditorWidget


class PropertyEditorWidget(QWidget):
    """Displays device properties, recommendations, signals, and I/O summary."""

    recommendation_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("propertyEditor")

        self._stack = QStackedWidget()
        self.placeholder_label = QLabel(NO_DEVICE_SELECTED)

        self._tag_value = QLabel("-")
        self._area_value = QLabel("-")
        self._category_value = QLabel("-")
        self._type_value = QLabel("-")
        self._description_value = QLabel("-")
        self._quantity_value = QLabel("-")

        self.recommendation_table = QTableWidget(0, 4)
        self.signal_editor = SignalEditorWidget()
        self._di_value = QLabel("DI : 0")
        self._do_value = QLabel("DO : 0")
        self._ai_value = QLabel("AI : 0")
        self._ao_value = QLabel("AO : 0")

        self._build_ui()
        self.recommendation_table.itemChanged.connect(self._on_item_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.placeholder_label.setObjectName("noDeviceLabel")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        details = QGroupBox("Device Properties")
        form = QFormLayout(details)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addRow("Tag", self._tag_value)
        form.addRow("Area", self._area_value)
        form.addRow("Category", self._category_value)
        form.addRow("Type", self._type_value)
        form.addRow("Description", self._description_value)
        form.addRow("Quantity", self._quantity_value)

        recommendation_box = QGroupBox("Recommended Signals")
        recommendation_layout = QVBoxLayout(recommendation_box)
        self.recommendation_table.setObjectName("recommendedSignalsTable")
        self.recommendation_table.setHorizontalHeaderLabels(
            ["Enable", "Signal Name", "Signal Type", "Category"]
        )
        self.recommendation_table.horizontalHeader().setStretchLastSection(True)
        self.recommendation_table.verticalHeader().setVisible(False)
        self.recommendation_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.recommendation_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        recommendation_layout.addWidget(self.recommendation_table)

        signals_box = QGroupBox("Device Signals")
        signals_layout = QVBoxLayout(signals_box)
        signals_layout.addWidget(self.signal_editor)

        io_box = QGroupBox("I/O Summary")
        io_layout = QVBoxLayout(io_box)
        io_layout.addWidget(self._di_value)
        io_layout.addWidget(self._do_value)
        io_layout.addWidget(self._ai_value)
        io_layout.addWidget(self._ao_value)

        placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_page)
        placeholder_layout.addWidget(self.placeholder_label)

        details_page = QWidget()
        details_layout = QVBoxLayout(details_page)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.addWidget(details)
        details_layout.addWidget(recommendation_box, stretch=1)
        details_layout.addWidget(signals_box, stretch=1)
        details_layout.addWidget(io_box)

        self._stack.addWidget(placeholder_page)
        self._stack.addWidget(details_page)
        layout.addWidget(self._stack)
        self.clear()

    def clear(self) -> None:
        """Show the empty selection state."""
        self.recommendation_table.blockSignals(True)
        self.recommendation_table.setRowCount(0)
        self.recommendation_table.blockSignals(False)
        self.signal_editor.clear()
        self.set_io_summary(IoSummary())
        self._stack.setCurrentIndex(0)

    def show_device(
        self,
        device: Device,
        result: RecommendationResult | None = None,
    ) -> None:
        """Populate properties, recommendations, and signal editor."""
        self._tag_value.setText(device.tag)
        self._area_value.setText(device.area)
        self._category_value.setText(device.category)
        self._type_value.setText(device.type)
        self._description_value.setText(device.description or "-")
        self._quantity_value.setText(str(device.quantity))

        recommendations = () if result is None else result.recommendations
        self._populate_recommendations(recommendations, device.signals)
        self.show_device_signals(device.signals)
        self._stack.setCurrentIndex(1)

    def show_device_signals(self, signals: list[DeviceSignal]) -> None:
        """Refresh the Device Signals editor from domain objects."""
        self.signal_editor.populate(signals)

    def set_io_summary(self, summary: IoSummary) -> None:
        """Update the I/O summary labels."""
        self._di_value.setText(f"DI : {summary.di}")
        self._do_value.setText(f"DO : {summary.do}")
        self._ai_value.setText(f"AI : {summary.ai}")
        self._ao_value.setText(f"AO : {summary.ao}")

    def enabled_signal_types(self) -> list[str]:
        """Return IO types for currently enabled device signals."""
        types: list[str] = []
        table = self.signal_editor.table
        for row in range(table.rowCount()):
            enable_item = table.item(row, 0)
            type_item = table.item(row, 2)
            if enable_item is None or type_item is None:
                continue
            if enable_item.checkState() == Qt.CheckState.Checked:
                types.append(type_item.text())
        return types

    def recommendation_enable_states(self) -> dict[str, bool]:
        """Return signal name → enabled map from the recommendation table."""
        states: dict[str, bool] = {}
        for row in range(self.recommendation_table.rowCount()):
            enable_item = self.recommendation_table.item(row, 0)
            name_item = self.recommendation_table.item(row, 1)
            if enable_item is None or name_item is None:
                continue
            states[name_item.text()] = (
                enable_item.checkState() == Qt.CheckState.Checked
            )
        return states

    def sync_recommendation_enables(self, signals: list[DeviceSignal]) -> None:
        """Update recommendation Enable checkboxes from device.signals."""
        enabled_by_name = {signal.name: signal.enabled for signal in signals}
        self.recommendation_table.blockSignals(True)
        for row in range(self.recommendation_table.rowCount()):
            name_item = self.recommendation_table.item(row, 1)
            enable_item = self.recommendation_table.item(row, 0)
            if name_item is None or enable_item is None:
                continue
            if name_item.text() in enabled_by_name:
                enable_item.setCheckState(
                    Qt.CheckState.Checked
                    if enabled_by_name[name_item.text()]
                    else Qt.CheckState.Unchecked
                )
        self.recommendation_table.blockSignals(False)

    def _populate_recommendations(
        self,
        recommendations: tuple[Recommendation, ...],
        device_signals: list[DeviceSignal],
    ) -> None:
        enabled_by_name = {signal.name: signal.enabled for signal in device_signals}

        self.recommendation_table.blockSignals(True)
        self.recommendation_table.setRowCount(0)
        self.recommendation_table.setRowCount(len(recommendations))

        for row, recommendation in enumerate(recommendations):
            enable_item = QTableWidgetItem()
            enable_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            is_enabled = enabled_by_name.get(
                recommendation.name,
                recommendation.required,
            )
            enable_item.setCheckState(
                Qt.CheckState.Checked if is_enabled else Qt.CheckState.Unchecked
            )
            enable_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            name_item = QTableWidgetItem(recommendation.name)
            type_item = QTableWidgetItem(recommendation.signal_type)
            category_item = QTableWidgetItem(recommendation.category)

            self.recommendation_table.setItem(row, 0, enable_item)
            self.recommendation_table.setItem(row, 1, name_item)
            self.recommendation_table.setItem(row, 2, type_item)
            self.recommendation_table.setItem(row, 3, category_item)

        self.recommendation_table.resizeColumnsToContents()
        self.recommendation_table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        self.recommendation_changed.emit()
