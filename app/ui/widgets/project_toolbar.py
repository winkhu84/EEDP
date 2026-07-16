"""Top project toolbar widget."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class ProjectToolbar(QWidget):
    """Project controls, device actions, and workflow buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("projectToolbar")

        self.customer_combo = QComboBox()
        self.project_name_edit = QLineEdit()
        self.new_project_button = QPushButton("New Project")
        self.open_project_button = QPushButton("Open Project")
        self.save_project_button = QPushButton("Save Project")
        self.fc_io_preview_button = QPushButton("FC_IO Preview")
        self.generate_button = QPushButton("Generate")

        self.add_device_button = QPushButton("Add Device")
        self.remove_device_button = QPushButton("Remove Device")
        self.duplicate_device_button = QPushButton("Duplicate Device")
        self.import_io_list_button = QPushButton("Import IO List")
        self.debug_button = QPushButton("Debug")

        self._build_ui()
        self.set_device_actions_enabled(False)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Project"))
        layout.addSpacing(8)

        layout.addWidget(QLabel("Customer"))
        self.customer_combo.setMinimumWidth(140)
        self.customer_combo.setEditable(False)
        layout.addWidget(self.customer_combo)

        layout.addWidget(QLabel("Project Name"))
        self.project_name_edit.setMinimumWidth(160)
        self.project_name_edit.setPlaceholderText("Project Name")
        layout.addWidget(self.project_name_edit)

        layout.addWidget(self._separator())

        layout.addWidget(self.add_device_button)
        layout.addWidget(self.remove_device_button)
        layout.addWidget(self.duplicate_device_button)
        layout.addWidget(self.import_io_list_button)
        layout.addWidget(self.debug_button)

        layout.addStretch(1)

        layout.addWidget(self.new_project_button)
        layout.addWidget(self.open_project_button)
        layout.addWidget(self.save_project_button)
        layout.addWidget(self.fc_io_preview_button)
        layout.addWidget(self.generate_button)

    def set_device_actions_enabled(self, enabled: bool) -> None:
        """Enable Remove / Duplicate only when a device is selected."""
        self.remove_device_button.setEnabled(enabled)
        self.duplicate_device_button.setEnabled(enabled)

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line
