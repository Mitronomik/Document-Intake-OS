"""Bootstrap smoke tests using no real document fixtures."""

from __future__ import annotations

import importlib

from pytest import MonkeyPatch

from document_intake.ui.app import APP_NAME, build_application, build_main_window


def test_package_importable() -> None:
    package = importlib.import_module("document_intake")

    assert package.__version__ == "0.1.0"


def test_minimal_qt_window_builds(monkeypatch: MonkeyPatch) -> None:
    import pytest

    pytest.importorskip("PySide6.QtWidgets")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    application = build_application(["document-intake-test"])
    window = build_main_window()

    assert application.applicationName() == APP_NAME
    assert window.windowTitle() == APP_NAME
    assert window.centralWidget().objectName() == "bootstrapPlaceholder"
