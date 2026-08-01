from __future__ import annotations

import ast
import dataclasses
import inspect
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import pr012_regions_verifier_support as support
from scripts import verify_pr012_regions as verifier

from document_intake.persistence import database
from document_intake.persistence.migrations.v0008_document_regions import MIGRATION

ROOT = Path(__file__).resolve().parents[1]
_PRIVACY_FORBIDDEN = (
    "/tmp/",
    "/private/",
    "C:\\",
    "\\Users\\",
    "\\\\",
    "00000000-",
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "PRAGMA key",
    "key=",
    "synthetic-source",
    "synthetic-image-marker",
    "coordinate-marker",
    "raw-exception-marker",
)


def _passing_evidence() -> support.VerifierEvidence:
    return support.VerifierEvidence(**dict.fromkeys(support.EVIDENCE_FIELDS, True))


def test_supported_success_is_exact(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(verifier, "_run_supported", _passing_evidence)
    assert verifier.main() == 0
    captured = capsys.readouterr()
    assert tuple(captured.out.splitlines()) == verifier._LABELS
    assert captured.err == ""


def test_unsupported_platform_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: "UNSUPPORTED_PLATFORM")
    assert verifier.main() == 2
    assert tuple(capsys.readouterr().out.splitlines()) == verifier._UNSUPPORTED


def test_failed_invariant_and_exception_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(
        verifier,
        "_run_supported",
        lambda: dataclasses.replace(_passing_evidence(), populated_migration=False),
    )
    assert verifier.main() == 1
    assert capsys.readouterr().out == "PR012_VERIFY result=FAIL\n"
    monkeypatch.setattr(
        verifier,
        "_run_supported",
        lambda: (_ for _ in ()).throw(RuntimeError("private/path SELECT key coordinates")),
    )
    assert verifier.main() == 1
    assert capsys.readouterr().out == "PR012_VERIFY result=FAIL\n"


@pytest.mark.parametrize("field", support.EVIDENCE_FIELDS)
def test_each_false_structured_evidence_field_rejects_all_partial_pass_output(
    field: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(
        verifier,
        "_run_supported",
        lambda: dataclasses.replace(_passing_evidence(), **{field: False}),
    )

    assert verifier.main() == 1
    captured = capsys.readouterr()
    assert captured.out == "PR012_VERIFY result=FAIL\n"
    assert "=PASS" not in captured.out
    assert captured.err == ""


def test_runtime_output_has_exact_allowlist() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/verify_pr012_regions.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.stderr == ""
    assert tuple(completed.stdout.splitlines()) in (verifier._LABELS, verifier._UNSUPPORTED)
    assert not any(value in completed.stdout for value in _PRIVACY_FORBIDDEN)


def test_configured_output_allowlists_are_privacy_safe() -> None:
    for line in (*verifier._LABELS, *verifier._UNSUPPORTED):
        assert not any(value in line for value in _PRIVACY_FORBIDDEN)


def test_candidate_checksum_label_matches_production_migration() -> None:
    assert verifier._LABELS[1] == f"PR012_VERIFY candidate_v0008_checksum={MIGRATION.checksum}"
    assert MIGRATION.checksum == "ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b"


def test_support_result_is_frozen_boolean_only_and_imports_no_tests_package() -> None:
    fields = dataclasses.fields(support.VerifierEvidence)
    assert tuple(field.name for field in fields) == support.EVIDENCE_FIELDS
    evidence = _passing_evidence()
    assert all(type(getattr(evidence, field.name)) is bool for field in fields)
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.populated_migration = False  # type: ignore[misc]

    tree = ast.parse(inspect.getsource(support))
    imported = {
        name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in (
            *((node.module,) if isinstance(node, ast.ImportFrom) else ()),
            *(alias.name for alias in node.names),
        )
        if name is not None
    }
    assert not any(name == "tests" or name.startswith("tests.") for name in imported)


def test_supported_run_keeps_all_files_inside_supplied_temporary_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[Path] = []

    def run(root: Path, wrong_key_check) -> support.VerifierEvidence:  # type: ignore[no-untyped-def]
        del wrong_key_check
        observed.append(root)
        return _passing_evidence()

    monkeypatch.setattr(support, "run_populated_verification", run)
    assert verifier._run_supported(tmp_path) == _passing_evidence()
    assert observed == [tmp_path]
    assert tuple(tmp_path.iterdir()) == ()


def test_populated_product_flow_uses_production_repositories_and_services(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def sqlite_open(path: Path, provider: object) -> sqlite3.Connection:
        del provider
        connection = sqlite3.connect(path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    monkeypatch.setattr(database, "_open_connection", sqlite_open)
    monkeypatch.setattr(support.VerificationScenario, "encrypted_header", lambda self: True)
    monkeypatch.setattr(support.VerificationScenario, "plain_sqlite_rejected", lambda self: True)
    sibling_state = set(tmp_path.parent.iterdir())

    evidence = support.run_populated_verification(tmp_path, lambda path: path.exists())

    assert evidence == _passing_evidence()
    assert set(tmp_path.parent.iterdir()) == sibling_state
    assert {item.name for item in tmp_path.iterdir()} == {"state.db"}


def test_wrong_key_probe_isolated_with_suppressed_native_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: dict[str, object] = {}

    def run(command, **options):
        observed["command"] = command
        observed.update(options)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(verifier.subprocess, "run", run)
    path = tmp_path / "private.db"
    assert verifier._wrong_key_rejected(path)
    assert observed["stdout"] is subprocess.DEVNULL
    assert observed["stderr"] is subprocess.DEVNULL
    assert observed["check"] is False
    assert str(path) not in observed["command"]
    assert (b"W" * 32).hex() not in observed["command"]
    environment = observed["env"]
    assert environment[verifier._PROBE_PATH] == str(path)
    assert environment[verifier._PROBE_KEY] == (b"W" * 32).hex()
