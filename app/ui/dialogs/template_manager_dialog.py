"""Template Manager dialog — properties draft + read-only signal table."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.engine.signal_template_library import SignalTemplateLibrary
from app.model.signal_template import SignalTemplate, TemplateSignal

ROLE_TEMPLATE_ID = Qt.ItemDataRole.UserRole

_SIGNAL_COLUMNS = ("Signal Name", "I/O Type", "Required / Optional")
_COL_NAME = 0
_COL_IO_TYPE = 1
_COL_REQUIRED = 2


@dataclass
class TemplatePropertyDraft:
    """Dialog-local draft for one template (never written to the library)."""

    template_id: str
    display_name: str
    signal_count: int
    list_label: str


class TemplateManagerDialog(QDialog):
    """Browse templates, draft property edits, and view signals (read-only)."""

    def __init__(
        self,
        library: SignalTemplateLibrary,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("templateManagerDialog")
        self.setWindowTitle("Template Manager")
        self.resize(780, 560)

        self._library = library
        self._templates_by_id: dict[str, SignalTemplate] = {}
        self._drafts: dict[str, TemplatePropertyDraft] = {}

        self.template_list = QListWidget()
        self.id_value = QLabel("-")
        self.name_value = QLineEdit()
        self.signal_count_value = QLabel("-")
        self.apply_draft_button = QPushButton("Apply Draft")
        self.signal_table = QTableWidget(0, len(_SIGNAL_COLUMNS))

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

    def signal_table_rows(self) -> list[tuple[str, str, str]]:
        """Return current signal-table cells as (name, io_type, required_label)."""
        rows: list[tuple[str, str, str]] = []
        for row in range(self.signal_table.rowCount()):
            name_item = self.signal_table.item(row, _COL_NAME)
            io_item = self.signal_table.item(row, _COL_IO_TYPE)
            req_item = self.signal_table.item(row, _COL_REQUIRED)
            rows.append(
                (
                    name_item.text() if name_item is not None else "",
                    io_item.text() if io_item is not None else "",
                    req_item.text() if req_item is not None else "",
                )
            )
        return rows

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

        right = QVBoxLayout()
        right.setSpacing(10)

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
        right.addWidget(details_box)

        signals_box = QGroupBox("Signals")
        signals_layout = QVBoxLayout(signals_box)
        self.signal_table.setObjectName("templateManagerSignalTable")
        self.signal_table.setHorizontalHeaderLabels(list(_SIGNAL_COLUMNS))
        self.signal_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.signal_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.signal_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.signal_table.verticalHeader().setVisible(False)
        header = self.signal_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)
        signals_layout.addWidget(self.signal_table)
        right.addWidget(signals_box, stretch=1)

        body.addLayout(right, stretch=3)
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
        self._populate_signal_table(template.signals_in_order())

    def _populate_signal_table(self, signals: tuple[TemplateSignal, ...]) -> None:
        """Fill the read-only signal table from library template signals."""
        self.signal_table.setRowCount(0)
        self.signal_table.setRowCount(len(signals))
        for row, signal in enumerate(signals):
            required_label = "Required" if signal.required else "Optional"
            values = (signal.name, signal.signal_type, required_label)
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                self.signal_table.setItem(row, column, item)

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
        self.signal_table.setRowCount(0)
