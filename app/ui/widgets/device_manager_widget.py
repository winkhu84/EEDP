"""Device Manager panel (View)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.common.constants import DEVICE_AREAS, DEVICE_CATEGORIES, DEVICE_TYPES


class DeviceManagerWidget(QWidget):
    """Form for new-device fields (actions live on the toolbar)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("deviceManager")

        self.area_combo = QComboBox()
        self.category_combo = QComboBox()
        self.type_combo = QComboBox()
        self.tag_edit = QLineEdit()
        self.description_edit = QLineEdit()
        self.quantity_spin = QSpinBox()

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        title = QLabel("Device Manager")
        title.setObjectName("deviceManagerTitle")
        root.addWidget(title)

        form_box = QGroupBox("New Device")
        form = QFormLayout(form_box)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.area_combo.addItems(DEVICE_AREAS)
        self.category_combo.addItems(DEVICE_CATEGORIES)
        # Temporary fallback until MainController.refresh_device_types() runs.
        self.type_combo.addItems(DEVICE_TYPES)

        self.tag_edit.setPlaceholderText("Tag")
        self.description_edit.setPlaceholderText("Description")

        self.quantity_spin.setMinimum(1)
        self.quantity_spin.setMaximum(100)
        self.quantity_spin.setValue(1)

        form.addRow("Area", self.area_combo)
        form.addRow("Category", self.category_combo)
        form.addRow("Type", self.type_combo)
        form.addRow("Tag", self.tag_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Quantity", self.quantity_spin)

        root.addWidget(form_box)
        root.addStretch(1)

    def set_device_types(
        self,
        types: Sequence[str],
        *,
        selected: str | None = None,
    ) -> None:
        """Replace Type combo items. Preserve the current selection when possible."""
        previous = selected if selected is not None else self.type_combo.currentText()
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItems(list(types))
        index = self.type_combo.findText(previous)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        elif self.type_combo.count() > 0:
            self.type_combo.setCurrentIndex(0)
        self.type_combo.blockSignals(False)

    def device_types(self) -> tuple[str, ...]:
        """Return Type combo items in display order."""
        return tuple(
            self.type_combo.itemText(index)
            for index in range(self.type_combo.count())
        )
