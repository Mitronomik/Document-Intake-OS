"""Bootstrap smoke tests using no real document fixtures."""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from importlib import metadata

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from document_intake import __main__ as module_entrypoint
from document_intake.ui import app as ui_app
from document_intake.ui.app import APP_NAME, build_application, build_main_window, main


@pytest.fixture(autouse=True)
def close_top_level_widgets() -> Iterator[None]:
    yield
    application = QApplication.instance()
    if application is not None:
        for widget in application.topLevelWidgets():
            widget.close()
        application.processEvents()


def test_package_importable() -> None:
    package = importlib.import_module("document_intake")

    assert package.__version__ == "0.1.0"


def test_architecture_package_layout_importable() -> None:
    module_names = (
        "document_intake.domain.enums",
        "document_intake.domain.errors",
        "document_intake.application",
        "document_intake.persistence",
        "document_intake.storage",
        "document_intake.image_pipeline",
        "document_intake.recognition",
        "document_intake.terminal_adapters",
        "document_intake.ui",
    )

    for module_name in module_names:
        assert importlib.import_module(module_name).__name__ == module_name


def test_minimal_qt_window_builds() -> None:
    application = build_application(["document-intake-test"])
    window = build_main_window()

    try:
        assert application.applicationName() == APP_NAME
        assert window.windowTitle() == APP_NAME
        assert window.centralWidget().objectName() == "bootstrapPlaceholder"
    finally:
        window.close()
        application.processEvents()


def test_real_qt_event_loop_starts_and_exits() -> None:
    application = build_application(["document-intake-test"])
    QTimer.singleShot(0, application.quit)

    assert main(["document-intake-test"]) == 0


def test_module_entrypoint_delegates_to_real_main() -> None:
    assert module_entrypoint.main is ui_app.main


def test_console_entrypoint_resolves_to_real_main() -> None:
    scripts = metadata.entry_points(group="console_scripts")
    entrypoint = next(script for script in scripts if script.name == "document-intake")

    assert entrypoint.value == "document_intake.ui.app:main"
    assert entrypoint.load() is ui_app.main
