from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from scripts import verify_pr012_regions as verifier

ROOT = Path(__file__).resolve().parents[1]
_PRIVACY_FORBIDDEN = (
    "/tmp/",
    "\\\\",
    "00000000-",
    "SELECT ",
    "INSERT ",
    "key=",
    " x=",
    " y=",
)


def test_supported_success_is_exact(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verifier, "_unsupported_code", lambda: None)
    monkeypatch.setattr(verifier, "_run_supported", lambda: True)
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
    monkeypatch.setattr(verifier, "_run_supported", lambda: False)
    assert verifier.main() == 1
    assert capsys.readouterr().out == "PR012_VERIFY result=FAIL\n"
    monkeypatch.setattr(
        verifier,
        "_run_supported",
        lambda: (_ for _ in ()).throw(RuntimeError("private/path SELECT key coordinates")),
    )
    assert verifier.main() == 1
    assert capsys.readouterr().out == "PR012_VERIFY result=FAIL\n"


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
