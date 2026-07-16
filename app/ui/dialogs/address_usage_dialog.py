"""PLC Address Usage dialog (View)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.engine.address_usage_engine import (
    STATUS_CONFLICT,
    STATUS_SPARE,
    STATUS_USED,
    CardUsage,
    ChannelUsage,
    build_all_card_usage,
)
from app.model.device import Device
from app.model.plc_card_config import PlcCardConfig


_COLOR_SPARE = QColor("#9E9E9E")
_COLOR_USED = QColor("#2E7D32")
_COLOR_CONFLICT = QColor("#C62828")
_COLOR_SELECTED_BORDER = QColor("#1565C0")


class ChannelLampWidget(QWidget):
    """Small circular lamp with address label and tooltip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = STATUS_SPARE
        self._highlight = False
        self._address = ""
        self.setFixedSize(70, 52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_channel(
        self,
        channel: ChannelUsage,
        *,
        highlight: bool = False,
    ) -> None:
        self._address = channel.address
        self._status = channel.status
        self._highlight = highlight
        self.setToolTip(channel.tooltip())
        self.setAccessibleName(f"{channel.address} {channel.status}")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._status == STATUS_USED:
            color = _COLOR_USED
        elif self._status == STATUS_CONFLICT:
            color = _COLOR_CONFLICT
        else:
            color = _COLOR_SPARE

        lamp_size = 16
        cx = self.width() // 2
        cy = 14
        painter.setBrush(color)
        if self._highlight and self._status == STATUS_USED:
            painter.setPen(_COLOR_SELECTED_BORDER)
            painter.setBrush(color)
            painter.drawEllipse(
                cx - lamp_size // 2 - 1,
                cy - lamp_size // 2 - 1,
                lamp_size + 2,
                lamp_size + 2,
            )
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                cx - lamp_size // 2,
                cy - lamp_size // 2,
                lamp_size,
                lamp_size,
            )

        painter.setPen(QColor("#212121"))
        painter.drawText(
            self.rect().adjusted(0, 22, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            self._address,
        )
        painter.end()


class IoTypeUsagePanel(QWidget):
    """One I/O-type tab: card selector + channel grid + header stats."""

    def __init__(
        self,
        io_type: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._io_type = io_type
        self._cards: tuple[CardUsage, ...] = ()
        self._selected_device_id: str | None = None
        self._lamps: list[ChannelLampWidget] = []

        self.header_label = QLabel("No assigned addresses.")
        self.card_combo = QComboBox()
        self.empty_label = QLabel(
            f"No {io_type} addresses assigned in this project."
        )
        self.grid_host = QWidget()
        self.grid_layout = QGridLayout(self.grid_host)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setHorizontalSpacing(4)
        self.grid_layout.setVerticalSpacing(8)

        self._build_ui()
        self.card_combo.currentIndexChanged.connect(self._on_card_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Card:"))
        selector_row.addWidget(self.card_combo, stretch=1)
        layout.addLayout(selector_row)

        self.header_label.setObjectName("addressUsageHeader")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.grid_host)
        layout.addWidget(scroll, stretch=1)

        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

    def set_cards(
        self,
        cards: Sequence[CardUsage],
        *,
        selected_device_id: str | None = None,
    ) -> None:
        self._cards = tuple(cards)
        self._selected_device_id = selected_device_id
        self.card_combo.blockSignals(True)
        self.card_combo.clear()
        for card in self._cards:
            self.card_combo.addItem(card.combo_label())
        self.card_combo.blockSignals(False)

        has_cards = bool(self._cards)
        self.card_combo.setEnabled(has_cards)
        self.grid_host.setVisible(has_cards)
        self.header_label.setVisible(has_cards)
        self.empty_label.setVisible(not has_cards)

        if has_cards:
            self.card_combo.setCurrentIndex(0)
            self._render_card(self._cards[0])
        else:
            self._clear_grid()
            self.header_label.setText("No assigned addresses.")

    def _on_card_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._cards):
            return
        self._render_card(self._cards[index])

    def _clear_grid(self) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._lamps.clear()

    def _render_card(self, card: CardUsage) -> None:
        self.header_label.setText(
            f"Module: {card.module_name}\n"
            f"Address Range: {card.start_address} - {card.end_address}\n"
            f"Used: {card.used}    Spare: {card.spare}    Conflict: {card.conflicts}"
        )
        self._clear_grid()

        columns = 8 if self._io_type in {"DI", "DO"} else 4
        for index, channel in enumerate(card.channels):
            lamp = ChannelLampWidget()
            highlight = False
            if self._selected_device_id and channel.status == STATUS_USED:
                highlight = any(
                    item.device_id == self._selected_device_id
                    for item in channel.assignments
                )
            lamp.set_channel(channel, highlight=highlight)
            row = index // columns
            col = index % columns
            self.grid_layout.addWidget(lamp, row, col)
            self._lamps.append(lamp)


class AddressUsageDialog(QDialog):
    """Modal dialog showing project PLC address channel usage."""

    def __init__(
        self,
        devices: Sequence[Device],
        *,
        card_configurations: Sequence[PlcCardConfig] | None = None,
        selected_device_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PLC Address Usage")
        self.resize(720, 520)
        self.setModal(True)

        self._tabs = QTabWidget()
        self._panels: dict[str, IoTypeUsagePanel] = {}
        for io_type in ("DI", "DO", "AI", "AO"):
            panel = IoTypeUsagePanel(io_type)
            self._panels[io_type] = panel
            self._tabs.addTab(panel, io_type)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.clicked.connect(self.accept)
        layout.addWidget(buttons)

        usage = build_all_card_usage(
            devices,
            card_configurations=card_configurations,
            selected_device_id=selected_device_id,
        )
        for io_type, panel in self._panels.items():
            panel.set_cards(
                usage.get(io_type, ()),
                selected_device_id=selected_device_id,
            )
