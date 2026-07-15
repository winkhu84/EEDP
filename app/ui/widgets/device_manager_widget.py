"""Device Manager panel (View)."""

from __future__ import annotations

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
