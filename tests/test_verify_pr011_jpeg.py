from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts import verify_pr011_jpeg as verifier

from document_intake.persistence import database


def _sqlite(path: Path, provider: object) -> sqlite3.Connection:
    del provider
    connection = sqlite3.connect(path, isolation_level=None)
    return connection


def test_unsupported_is_exact(monkeypatch, capsys):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier.platform, "system", lambda: "Linux")
    assert verifier.main() == 2
    assert capsys.readouterr().out == "PR011_VERIFY result=INCONCLUSIVE\n"


def test_missing_windows_dependency_is_inconclusive(monkeypatch, capsys):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier.platform, "system", lambda: "Windows")
    monkeypatch.setattr(verifier.importlib.util, "find_spec", lambda name: None)
    assert verifier.main() == 2
    assert capsys.readouterr().out == "PR011_VERIFY result=INCONCLUSIVE\n"


def test_real_components_produce_every_status(monkeypatch, tmp_path):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(database, "_open_connection", _sqlite)
    assert verifier._run_production(tmp_path) == verifier._LABELS


def test_failure_is_sanitized(monkeypatch, capsys):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier.platform, "system", lambda: "Windows")
    monkeypatch.setattr(verifier.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        verifier,
        "_run_production",
        lambda root: (_ for _ in ()).throw(RuntimeError("private.db SELECT")),
    )
    assert verifier.main() == 1
    assert capsys.readouterr().out == "PR011_VERIFY result=FAIL\n"
