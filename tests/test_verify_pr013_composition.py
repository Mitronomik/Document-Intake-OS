import sqlite3
from pathlib import Path

import pytest
from scripts import verify_pr013_composition as verifier

from document_intake.persistence import database


def _sqlite(path: Path, provider: object) -> sqlite3.Connection:
    del provider
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def test_synthetic_verifier_exercises_production_components(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(database, "_open_connection", _sqlite)
    verifier._run(tmp_path)


def test_verifier_stdout_is_stable_and_sanitized(capsys, monkeypatch) -> None:
    monkeypatch.setattr(verifier.importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(verifier, "_run", lambda _root: None)
    assert verifier.main() == 0
    output = capsys.readouterr().out
    assert output.splitlines() == list(verifier._LABELS)
    forbidden = (
        "/tmp/",
        "/private/",
        "C:\\",
        "00000000-",
        "SELECT",
        "INSERT",
        "sha256",
        "width",
        "height",
        "bytes",
        "quality",
    )
    assert not any(marker in output for marker in forbidden)
