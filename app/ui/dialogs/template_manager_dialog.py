"""Template Manager dialog — list + dialog-local property draft editing (A7.3)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.signal_template import SignalTemplate

ROLE_TEMPLATE_ID = Qt.ItemDataRole.UserRole


@dataclass
class TemplatePropertyDraft:
    """Dialog-local draft for one template (never written to the library)."""

    template_id: str
    display_name: str
    signal_count: int
    list_label: str


class TemplateManagerDialog(QDialog):
    """Browse and draft-edit Signal Template properties (no library/YAML persist)."""

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
        self._drafts: dict[str, TemplatePropertyDraft] = {}

        self.template_list = QListWidget()
        self.id_value = QLabel("-")
        self.name_value = QLineEdit()
        self.signal_count_value = QLabel("-")
        self.apply_draft_button = QPushButton("Apply Draft")

        self._build_ui()
        self.template_list.currentItemChanged.connect(self._on_selection_changed)
        self.name_value.textEdited.connect(self._on_display_name_edited)
        self.apply_draft_button.clicked.connect(self._on_apply_draft)
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

    def draft_for(self, template_id: str) -> TemplatePropertyDraft | None:
        """Return the dialog-local draft for ``template_id``, if any."""
        return self._drafts.get(template_id)

    def refresh_list(self) -> None:
        """Reload the left list from the shared library without mutating templates."""
        previous = self.selected_template_id()
        if previous is not None:
            self._flush_editor_to_draft(previous)

        templates = self._library.load_all()
        self._templates_by_id = {item.id: item for item in templates}

        for template in templates:
            self._ensure_draft(template)

        self.template_list.blockSignals(True)
        self.template_list.clear()
        for template in templates:
            draft = self._drafts[template.id]
            row = QListWidgetItem(draft.list_label)
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

        details_box = QGroupBox("Template Properties")
        details_form = QFormLayout(details_box)
        details_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.id_value.setObjectName("templateManagerIdValue")
        self.id_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.name_value.setObjectName("templateManagerDisplayNameEdit")
        self.signal_count_value.setObjectName("templateManagerSignalCountValue")
        self.signal_count_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.apply_draft_button.setObjectName("templateManagerApplyDraftButton")

        details_form.addRow("Template ID", self.id_value)
        details_form.addRow("Display Name", self.name_value)
        details_form.addRow("Number of Signals", self.signal_count_value)
        details_form.addRow("", self.apply_draft_button)
        body.addWidget(details_box, stretch=3)

        root.addLayout(body, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setObjectName("templateManagerCloseButton")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def _ensure_draft(self, template: SignalTemplate) -> TemplatePropertyDraft:
        existing = self._drafts.get(template.id)
        if existing is not None:
            # Keep dialog-local edits; refresh read-only signal count from library.
            existing.signal_count = len(template.signals_in_order())
            return existing
        draft = TemplatePropertyDraft(
            template_id=template.id,
            display_name=template.device_type,
            signal_count=len(template.signals_in_order()),
            list_label=template.device_type,
        )
        self._drafts[template.id] = draft
        return draft

    def _flush_editor_to_draft(self, template_id: str) -> None:
        draft = self._drafts.get(template_id)
        if draft is None:
            return
        draft.display_name = self.name_value.text()

    def _select_by_id(self, template_id: str) -> None:
        for row in range(self.template_list.count()):
            item = self.template_list.item(row)
            if item is not None and item.data(ROLE_TEMPLATE_ID) == template_id:
                self.template_list.setCurrentRow(row)
                return

    def _on_selection_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        if previous is not None:
            previous_id = str(previous.data(ROLE_TEMPLATE_ID) or "")
            if previous_id:
                self._flush_editor_to_draft(previous_id)

        if current is None:
            self._clear_details()
            return

        template_id = str(current.data(ROLE_TEMPLATE_ID) or "")
        template = self._templates_by_id.get(template_id)
        if template is None:
            self._clear_details()
            return

        draft = self._ensure_draft(template)
        self.id_value.setText(draft.template_id)
        self.name_value.blockSignals(True)
        self.name_value.setText(draft.display_name)
        self.name_value.blockSignals(False)
        self.signal_count_value.setText(str(draft.signal_count))
        self.apply_draft_button.setEnabled(True)

    def _on_display_name_edited(self, text: str) -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            return
        draft = self._drafts.get(template_id)
        if draft is None:
            return
        draft.display_name = text

    def _on_apply_draft(self) -> None:
        template_id = self.selected_template_id()
        if template_id is None:
            return
        draft = self._drafts.get(template_id)
        if draft is None:
            return

        draft.display_name = self.name_value.text()
        draft.list_label = draft.display_name

        item = self.template_list.currentItem()
        if item is not None:
            item.setText(draft.list_label)

    def _clear_details(self) -> None:
        self.id_value.setText("-")
        self.name_value.blockSignals(True)
        self.name_value.setText("")
        self.name_value.blockSignals(False)
        self.signal_count_value.setText("-")
        self.apply_draft_button.setEnabled(False)
