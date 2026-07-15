"""EEDP Studio application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_controller import MainController
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("EEDP Studio")

    window = MainWindow()
    controller = MainController(window)
    controller.bind()

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
