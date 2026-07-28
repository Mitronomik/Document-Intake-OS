from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts import check_architecture_limits as checker

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {
    "base_commit": "base",
    "limits": {"module_lines": 400, "symbol_lines": 80, "class_lines": 300, "complexity": 12},
    "legacy": {},
}


def rules(path: str, text: str, *, legacy=None, base_text="") -> set[str]:
    config = json.loads(json.dumps(CONFIG))
    config["legacy"] = legacy or {}
    return {rule for rule, _ in checker._violations(path, text, config, base_text=base_text)}


def function(lines: int) -> str:
    return "def target():\n" + "\n".join("    pass" for _ in range(lines - 1))


def klass(lines: int) -> str:
    return "class Target:\n" + "\n".join("    pass" for _ in range(lines - 1))


def branching(count: int) -> str:
    return "def target(value):\n" + "\n".join(f"    if value == {n}: pass" for n in range(count))


def test_architecture_limits_pass() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_architecture_limits.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert result.stdout == "architecture_limits PASS 0\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("pass\n" * 401, "MODULE_LINES"),
        (function(81), "FUNCTION_LINES"),
        (klass(301), "CLASS_LINES"),
        (branching(12), "COMPLEXITY"),
    ],
)
def test_size_and_complexity_rejections(text: str, rule: str) -> None:
    assert rule in rules("src/document_intake/new.py", text)


@pytest.mark.parametrize("text", ["pass\n" * 400, function(80), klass(300), branching(11)])
def test_exact_boundaries_are_accepted(text: str) -> None:
    assert not rules("src/document_intake/new.py", text)


@pytest.mark.parametrize(
    ("path", "text", "rule"),
    [
        ("src/document_intake/new.py", "from somewhere import *\n", "WILDCARD_IMPORT"),
        ("src/document_intake/new.py", "# ruff: noqa\nvalue=1\n", "FILE_NOQA"),
        ("src/document_intake/new.py", "# noqa\nvalue=1\n", "FILE_NOQA"),
        (
            "src/document_intake/persistence/database.py",
            "class AddedRepo:\n    pass\n",
            "DATABASE_REPOSITORY",
        ),
        (
            "src/document_intake/persistence/repositories/new.py",
            "from document_intake.persistence.database import AddedRepo\n",
            "REPOSITORY_REEXPORT",
        ),
        (
            "src/document_intake/application/services/new.py",
            "QUERY='SELECT value FROM table'\n",
            "SERVICE_SQL",
        ),
        (
            "src/document_intake/persistence/migrations/new.py",
            "from document_intake.application.services.x import run\n",
            "MIGRATION_SERVICE",
        ),
    ],
)
def test_responsibility_rejections(path: str, text: str, rule: str) -> None:
    assert rule in rules(path, text)


def test_line_specific_noqa_is_allowed() -> None:
    assert "FILE_NOQA" not in rules("src/document_intake/new.py", "value = 1  # noqa: E501\n")


def test_legacy_module_and_symbol_cannot_grow() -> None:
    legacy = {
        "src/document_intake/old.py": {"module_lines": 401, "symbols": {"target": {"lines": 81}}}
    }
    assert "MODULE_LINES" in rules(
        "src/document_intake/old.py", "\n" * 401 + function(82), legacy=legacy
    )
    assert "FUNCTION_LINES" in rules("src/document_intake/old.py", function(82), legacy=legacy)


def test_missing_baseline_is_controlled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        checker,
        "_tracked",
        lambda commit=None: (
            (_ for _ in ()).throw(checker.ArchitectureInputError()) if commit else ()
        ),
    )
    assert checker.main() == 1
    captured = capsys.readouterr()
    assert captured.out == "config/architecture_limits.json BASE_UNAVAILABLE 0\n"
    assert captured.err == ""
