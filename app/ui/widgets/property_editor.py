"""Property editor widget (View)."""

from __future__ import annotations

from typing import Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.common.constants import NO_DEVICE_SELECTED
from app.model.device import Device
from app.model.recommendation import Recommendation, RecommendationResult
from app.model.signal import Signal as DeviceSignal
from app.ui.widgets.signal_editor_widget import SignalEditorWidget


class PropertyEditorWidget(QWidget):
    """Displays device properties, recommendations, signals, and I/O summaries."""

    recommendation_changed = Signal()
    quantity_changed = Signal(int)

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
        self.quantity_spin = QSpinBox()

        self.recommendation_table = QTableWidget(0, 4)
        self.signal_editor = SignalEditorWidget()

        self._device_di = QLabel("0")
        self._device_do = QLabel("0")
        self._device_ai = QLabel("0")
        self._device_ao = QLabel("0")
        self._device_total = QLabel("0")

        self._project_di = QLabel("0")
        self._project_do = QLabel("0")
        self._project_ai = QLabel("0")
        self._project_ao = QLabel("0")
        self._project_total = QLabel("0")

        self._build_ui()
        self.recommendation_table.itemChanged.connect(self._on_item_changed)
        self.quantity_spin.valueChanged.connect(self.quantity_changed.emit)

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

        self.quantity_spin.setMinimum(1)
        self.quantity_spin.setMaximum(100)
        self.quantity_spin.setValue(1)
        form.addRow("Quantity", self.quantity_spin)

        recommendation_box = QGroupBox("Recommended Signals")
        recommendation_layout = QVBoxLayout(recommendation_box)
        self.recommendation_table.setObjectName("recommendedSignalsTable")
        self.recommendation_table.setHorizontalHeaderLabels(
            ["Enable", "Signal Name", "Signal Type", "Category"]
        )
        reco_header = self.recommendation_table.horizontalHeader()
        reco_header.setStretchLastSection(False)
        reco_header.setMinimumSectionSize(48)
        reco_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.recommendation_table.verticalHeader().setVisible(False)
        self.recommendation_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.recommendation_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.recommendation_table.setMinimumWidth(280)
        recommendation_layout.addWidget(self.recommendation_table)

        signals_box = QGroupBox("Device Signals")
        signals_layout = QVBoxLayout(signals_box)
        signals_layout.addWidget(self.signal_editor)

        signals_row = QWidget()
        signals_row.setObjectName("signalsRow")
        signals_row_layout = QHBoxLayout(signals_row)
        signals_row_layout.setContentsMargins(0, 0, 0, 0)
        signals_row_layout.setSpacing(10)
        signals_row_layout.addWidget(recommendation_box, stretch=1)
        signals_row_layout.addWidget(signals_box, stretch=1)

        device_io_box = self._build_summary_panel(
            title="Device I/O Summary",
            accent="#2F6FED",
            di_label=self._device_di,
            do_label=self._device_do,
            ai_label=self._device_ai,
            ao_label=self._device_ao,
            total_label=self._device_total,
        )
        project_io_box = self._build_summary_panel(
            title="Project I/O Summary",
            accent="#2E7D32",
            di_label=self._project_di,
            do_label=self._project_do,
            ai_label=self._project_ai,
            ao_label=self._project_ao,
            total_label=self._project_total,
        )

        summary_row = QWidget()
        summary_row.setObjectName("ioSummaryRow")
        summary_layout = QHBoxLayout(summary_row)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)
        summary_layout.addWidget(device_io_box, stretch=1)
        summary_layout.addWidget(project_io_box, stretch=1)

        summary_band = QWidget()
        summary_band.setObjectName("ioSummaryBand")
        summary_band_layout = QHBoxLayout(summary_band)
        summary_band_layout.setContentsMargins(0, 0, 0, 0)
        summary_band_layout.setSpacing(0)
        # Occupy ~1/3 of content width; keep left-aligned (stretch 1 + spacer 2).
        summary_band_layout.addWidget(summary_row, stretch=1)
        summary_band_layout.addStretch(2)

        placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_page)
        placeholder_layout.addWidget(self.placeholder_label)

        details_page = QWidget()
        details_layout = QVBoxLayout(details_page)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(8)
        details_layout.addWidget(details)
        details_layout.addWidget(signals_row, stretch=1)

        self._stack.addWidget(placeholder_page)
        self._stack.addWidget(details_page)
        layout.addWidget(self._stack, stretch=1)
        layout.addWidget(summary_band)
        self.clear()

    def clear(self) -> None:
        """Show the empty selection state."""
        self.recommendation_table.blockSignals(True)
        self.recommendation_table.setRowCount(0)
        self.recommendation_table.blockSignals(False)
        self.signal_editor.clear()
        self.quantity_spin.blockSignals(True)
        self.quantity_spin.setValue(1)
        self.quantity_spin.blockSignals(False)
        self.set_device_io_summary(
            {"DI": 0, "DO": 0, "AI": 0, "AO": 0, "TOTAL": 0}
        )
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

        self.quantity_spin.blockSignals(True)
        self.quantity_spin.setValue(max(1, int(device.quantity)))
        self.quantity_spin.blockSignals(False)

        recommendations = () if result is None else result.recommendations
        self._populate_recommendations(recommendations, device.signals)
        self.show_device_signals(device.signals)
        self._stack.setCurrentIndex(1)

    def show_device_signals(self, signals: list[DeviceSignal]) -> None:
        """Refresh the Device Signals editor from domain objects."""
        self.signal_editor.populate(signals)

    def set_device_io_summary(self, summary: Mapping[str, int]) -> None:
        """Update Device I/O Summary labels."""
        self._device_di.setText(str(summary.get("DI", 0)))
        self._device_do.setText(str(summary.get("DO", 0)))
        self._device_ai.setText(str(summary.get("AI", 0)))
        self._device_ao.setText(str(summary.get("AO", 0)))
        self._device_total.setText(str(summary.get("TOTAL", 0)))

    def set_project_io_summary(self, summary: Mapping[str, int]) -> None:
        """Update Project I/O Summary labels."""
        self._project_di.setText(str(summary.get("DI", 0)))
        self._project_do.setText(str(summary.get("DO", 0)))
        self._project_ai.setText(str(summary.get("AI", 0)))
        self._project_ao.setText(str(summary.get("AO", 0)))
        self._project_total.setText(str(summary.get("TOTAL", 0)))

    @staticmethod
    def _build_summary_panel(
        *,
        title: str,
        accent: str,
        di_label: QLabel,
        do_label: QLabel,
        ai_label: QLabel,
        ao_label: QLabel,
        total_label: QLabel,
    ) -> QGroupBox:
        """Build a compact equal-width I/O summary panel."""
        box = QGroupBox(title)
        box.setObjectName("ioSummaryPanel")
        box.setStyleSheet(
            f"""
            QGroupBox#ioSummaryPanel {{
                font-weight: 600;
                border: 1px solid {accent};
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 4px;
            }}
            QGroupBox#ioSummaryPanel::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {accent};
            }}
            """
        )

        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        rows = (
            ("DI", di_label),
            ("DO", do_label),
            ("AI", ai_label),
            ("AO", ao_label),
            ("Total", total_label),
        )
        for name, value_label in rows:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            name_label = QLabel(name)
            name_label.setMinimumWidth(40)
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if name == "Total":
                name_label.setStyleSheet("font-weight: 600;")
                value_label.setStyleSheet("font-weight: 600;")
            row.addWidget(name_label)
            row.addStretch(1)
            row.addWidget(value_label)
            layout.addLayout(row)

        return box

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
