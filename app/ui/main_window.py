"""Main application window (View)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.common.constants import APP_TITLE, STATUS_READY, WINDOW_HEIGHT, WINDOW_WIDTH
from app.ui.widgets.device_manager_widget import DeviceManagerWidget
from app.ui.widgets.project_toolbar import ProjectToolbar
from app.ui.widgets.project_tree import ProjectTreeWidget
from app.ui.widgets.property_editor import PropertyEditorWidget


class MainWindow(QMainWindow):
    """Primary UI shell for EEDP Studio."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.toolbar = ProjectToolbar()
        self.project_tree = ProjectTreeWidget()
        self.device_manager = DeviceManagerWidget()
        self.property_editor = PropertyEditorWidget()

        self._build_ui()
        self._build_status_bar()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self.toolbar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.project_tree.setFixedWidth(300)
        body_layout.addWidget(self.project_tree)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self.device_manager)
        right_layout.addWidget(self.property_editor, stretch=1)

        body_layout.addWidget(right, stretch=1)
        root_layout.addWidget(body, stretch=1)

    def _build_status_bar(self) -> None:
        status_bar = QStatusBar()
        status_bar.showMessage(STATUS_READY)
        self.setStatusBar(status_bar)
