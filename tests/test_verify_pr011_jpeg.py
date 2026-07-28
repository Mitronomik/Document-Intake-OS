from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
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
    statuses = verifier._run_production(tmp_path)
    assert statuses == verifier._LABELS[:-2]
    assert verifier._render_success(statuses, ()) == tuple(
        f"PR011_VERIFY {item}" for item in verifier._LABELS
    )


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


def test_privacy_forbidden_marker_blocks_success() -> None:
    with pytest.raises(RuntimeError):
        verifier._render_success(verifier._LABELS[:-2], ("PR011_VERIFY",))


@pytest.mark.parametrize("status", verifier._LABELS[:-2])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "failed", "reordered"])
def test_success_renderer_rejects_every_status_mutation(status: str, mutation: str) -> None:
    statuses = list(verifier._LABELS[:-2])
    index = statuses.index(status)
    if mutation == "missing":
        statuses.pop(index)
    elif mutation == "duplicate":
        statuses.insert(index, status)
    elif mutation == "failed":
        statuses[index] = (
            status.replace("=PASS", "=FAIL") if "=PASS" in status else status + "=FAIL"
        )
    else:
        other = (index + 1) % len(statuses)
        statuses[index], statuses[other] = statuses[other], statuses[index]
    with pytest.raises(RuntimeError):
        verifier._render_success(tuple(statuses), ())


@pytest.mark.parametrize(
    "marker",
    [
        ".db",
        ".jpg",
        ".jpeg",
        ".png",
        "/",
        "\\",
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "Traceback",
        "Exception",
        "sha256=",
        "key=",
        "quality=",
        "resize=",
        "width=",
        "height=",
    ],
)
def test_success_renderer_rejects_generic_privacy_markers(marker: str) -> None:
    statuses = (*verifier._LABELS[:-3], verifier._LABELS[-3] + marker)
    with pytest.raises(RuntimeError):
        verifier._render_success(statuses, ())


@pytest.mark.parametrize(
    "runtime_value",
    [
        "C:/temporary/private-root",
        "synthetic-source.png",
        "verification.db",
        "encrypted-storage",
        "00000000-0000-0000-0000-000000000001",
        "0123456789abcdef" * 4,
        "abcdef0123456789" * 4,
    ],
)
def test_success_renderer_rejects_runtime_sensitive_values(runtime_value: str) -> None:
    statuses = (*verifier._LABELS[:-3], verifier._LABELS[-3] + runtime_value)
    with pytest.raises(RuntimeError):
        verifier._render_success(statuses, (runtime_value,))


@pytest.mark.parametrize(
    "secret",
    [
        "C:/private/source.jpg",
        "SELECT * FROM secret",
        "uuid=00000000-0000-0000-0000-000000000001",
        "sha256=deadbeef",
        "key=secret",
        "width=1200 height=1600 quality=95 resize=100",
    ],
)
def test_every_unexpected_failure_is_sanitized(monkeypatch, capsys, secret: str) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(verifier.platform, "system", lambda: "Windows")
    monkeypatch.setattr(verifier.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        verifier, "_run_production", lambda root: (_ for _ in ()).throw(RuntimeError(secret))
    )
    assert verifier.main() == 1
    captured = capsys.readouterr()
    assert captured.out == "PR011_VERIFY result=FAIL\n"
    assert captured.err == ""
