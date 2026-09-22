"""Template Manager dialog shell (View) — list + read-only details only."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.signal_template import SignalTemplate

ROLE_TEMPLATE_ID = Qt.ItemDataRole.UserRole


class TemplateManagerDialog(QDialog):
    """Browse Signal Templates from the shared library (no edit/CRUD yet)."""

    def __init__(
        self,
        library: SignalTemplateLibrary,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("templateManagerDialog")
        self.setWindowTitle("Template Manager")
        self.resize(720, 440)

        self._library = library
        self._templates_by_id: dict[str, SignalTemplate] = {}

        self.template_list = QListWidget()
        self.id_value = QLabel("-")
        self.name_value = QLabel("-")
        self.signal_count_value = QLabel("-")

        self._build_ui()
        self.template_list.currentItemChanged.connect(self._on_selection_changed)
        self.refresh_list()

    @property
    def template_library(self) -> SignalTemplateLibrary:
        """Shared SignalTemplateLibrary used by this dialog."""
        return self._library

    def selected_template_id(self) -> str | None:
        """Return the selected template id, or None."""
        item = self.template_list.currentItem()
        if item is None:
            return None
        value = item.data(ROLE_TEMPLATE_ID)
        return str(value) if value else None

    def refresh_list(self) -> None:
        """Reload the left list from the shared library without mutating templates."""
        previous = self.selected_template_id()
        templates = self._library.load_all()
        self._templates_by_id = {item.id: item for item in templates}

        self.template_list.blockSignals(True)
        self.template_list.clear()
        for template in templates:
            row = QListWidgetItem(template.device_type)
            row.setData(ROLE_TEMPLATE_ID, template.id)
            self.template_list.addItem(row)
        self.template_list.blockSignals(False)

        if previous and previous in self._templates_by_id:
            self._select_by_id(previous)
        elif self.template_list.count() > 0:
            self.template_list.setCurrentRow(0)
        else:
            self._clear_details()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(12)

        list_box = QGroupBox("Templates")
        list_layout = QVBoxLayout(list_box)
        self.template_list.setObjectName("templateManagerList")
        self.template_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        list_layout.addWidget(self.template_list)
        body.addWidget(list_box, stretch=2)

        details_box = QGroupBox("Template Details")
        details_form = QFormLayout(details_box)
        details_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        for label in (self.id_value, self.name_value, self.signal_count_value):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details_form.addRow("Template ID", self.id_value)
        details_form.addRow("Display Name", self.name_value)
        details_form.addRow("Number of Signals", self.signal_count_value)
        body.addWidget(details_box, stretch=3)

        root.addLayout(body, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setObjectName("templateManagerCloseButton")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def _select_by_id(self, template_id: str) -> None:
        for row in range(self.template_list.count()):
            item = self.template_list.item(row)
            if item is not None and item.data(ROLE_TEMPLATE_ID) == template_id:
                self.template_list.setCurrentRow(row)
                return

    def _on_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._clear_details()
            return
        template_id = str(current.data(ROLE_TEMPLATE_ID) or "")
        template = self._templates_by_id.get(template_id)
        if template is None:
            self._clear_details()
            return
        self.id_value.setText(template.id)
        self.name_value.setText(template.device_type)
        self.signal_count_value.setText(str(len(template.signals_in_order())))

    def _clear_details(self) -> None:
        self.id_value.setText("-")
        self.name_value.setText("-")
        self.signal_count_value.setText("-")
