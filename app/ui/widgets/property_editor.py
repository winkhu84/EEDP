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


class PropertyEditorWidget(QWidget):
    """Displays device properties, recommendations, and I/O summary."""

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
        self.set_io_summary(IoSummary())
        self._stack.setCurrentIndex(0)

    def show_device(
        self,
        device: Device,
        result: RecommendationResult | None = None,
    ) -> None:
        """Populate properties and optional recommendations."""
        self._tag_value.setText(device.tag)
        self._area_value.setText(device.area)
        self._category_value.setText(device.category)
        self._type_value.setText(device.type)
        self._description_value.setText(device.description or "-")
        self._quantity_value.setText(str(device.quantity))

        recommendations = () if result is None else result.recommendations
        self._populate_recommendations(recommendations)
        self._stack.setCurrentIndex(1)

    def set_io_summary(self, summary: IoSummary) -> None:
        """Update the I/O summary labels."""
        self._di_value.setText(f"DI : {summary.di}")
        self._do_value.setText(f"DO : {summary.do}")
        self._ai_value.setText(f"AI : {summary.ai}")
        self._ao_value.setText(f"AO : {summary.ao}")

    def enabled_signal_types(self) -> list[str]:
        """Return signal types for currently enabled recommendation rows."""
        types: list[str] = []
        for row in range(self.recommendation_table.rowCount()):
            enable_item = self.recommendation_table.item(row, 0)
            type_item = self.recommendation_table.item(row, 2)
            if enable_item is None or type_item is None:
                continue
            if enable_item.checkState() == Qt.CheckState.Checked:
                types.append(type_item.text())
        return types

    def _populate_recommendations(
        self,
        recommendations: tuple[Recommendation, ...],
    ) -> None:
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
            enable_item.setCheckState(
                Qt.CheckState.Checked
                if recommendation.required
                else Qt.CheckState.Unchecked
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
