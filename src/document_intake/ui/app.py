"""Minimal PySide6 application entry point for PR-001.

The bootstrap window intentionally contains no document, OCR, persistence, image processing,
network, telemetry, or export functionality.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any, cast

APP_NAME = "Document Intake OS"


def _qt_widgets() -> tuple[type[Any], type[Any], type[Any]]:
    """Import Qt widgets lazily so the package remains importable before dependency sync."""

    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

    return QApplication, QLabel, QMainWindow


def build_application(argv: Sequence[str] | None = None) -> Any:
    """Create the Qt application without starting the event loop."""

    QApplication, _, _ = _qt_widgets()
    existing = QApplication.instance()
    if existing is not None:
        return existing

    qt_argv = list(argv) if argv is not None else sys.argv
    application = QApplication(qt_argv)
    application.setApplicationName(APP_NAME)
    return application


def build_main_window() -> Any:
    """Create the minimal main window shell."""

    _, QLabel, QMainWindow = _qt_widgets()
    window = QMainWindow()
    window.setWindowTitle(APP_NAME)
    label = QLabel("Document Intake OS bootstrap")
    label.setObjectName("bootstrapPlaceholder")
    window.setCentralWidget(label)
    return window


def main(argv: Sequence[str] | None = None) -> int:
    """Start the minimal desktop application."""

    application = build_application(argv)
    window = build_main_window()
    window.show()
    return cast(int, application.exec())
