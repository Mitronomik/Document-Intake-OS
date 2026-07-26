from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from scripts import check_pr011_acceptance as checker


def manifest() -> dict[str, object]:
    return json.loads(checker.MANIFEST.read_text())


def write_test(root: Path) -> str:
    path = root / "tests/test_evidence.py"
    path.parent.mkdir(parents=True)
    path.write_text("def test_evidence():\n    pass\n")
    return "tests/test_evidence.py::test_evidence"


def test_valid_blocked_inventory_with_pending_entries(tmp_path: Path) -> None:
    report = checker.validate(manifest(), tmp_path, require_complete=False)
    assert not report.errors and report.pending


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda d: d["entries"].pop(), "REQUIRED_ID_MISSING"),
        (lambda d: d["entries"].append(copy.deepcopy(d["entries"][0])), "DUPLICATE_ID"),
        (
            lambda d: d["entries"].__setitem__(0, {**d["entries"][0], "id": "PR011-UNKNOWN-001"}),
            "UNKNOWN_ID",
        ),
        (lambda d: d["entries"][0].__setitem__("status", "waived"), "INVALID_STATUS"),
    ],
)
def test_manifest_identity_and_status_failures(mutation, code: str, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    data = manifest()
    mutation(data)
    assert code in checker.validate(data, tmp_path, require_complete=False).errors


def test_missing_evidence_file_and_selector(tmp_path: Path) -> None:
    data = manifest()
    entry = data["entries"][0]
    entry.update(
        status="implemented",
        evidence_files=["missing"],
        test_selectors=["tests/missing.py::test_x"],
    )
    report = checker.validate(data, tmp_path, require_complete=False)
    assert "EVIDENCE_FILE_MISSING" in report.errors
    assert "TEST_SELECTOR_MISSING" in report.errors


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("class _Uow: pass", "FORBIDDEN_ARTIFICIAL_UOW"),
        ("PRAGMA foreign_keys=OFF", "FOREIGN_KEYS_DISABLED"),
        ("inspect.getsource(PreparedImageArtifactRepo)", "SOURCE_INSPECTION_ONLY"),
    ],
)
def test_scoped_guardrails_detect_existing_anti_patterns(
    tmp_path: Path, content: str, code: str
) -> None:
    path = tmp_path / "tests/persistence/test_prepared_jpeg_repository.py"
    path.parent.mkdir(parents=True)
    path.write_text(content)
    assert code in checker.guardrail_codes(tmp_path)


def test_require_complete_fails_pending() -> None:
    report = checker.validate(manifest(), checker.ROOT, require_complete=True)
    assert "PENDING_EVIDENCE" in report.errors


def test_complete_synthetic_manifest_passes(tmp_path: Path) -> None:
    selector = write_test(tmp_path)
    data = manifest()
    data["current_status"] = "READY_FOR_HUMAN_REVIEW"
    for entry in data["entries"]:
        entry.update(
            status="implemented",
            test_selectors=[selector],
            evidence_files=["tests/test_evidence.py"],
        )
    assert checker.validate(data, tmp_path, require_complete=True).errors == ()


def test_invalid_json_is_sanitized(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "manifest.json"
    bad.write_text("{private path")
    monkeypatch.setattr(checker, "MANIFEST", bad)
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    assert checker.main(["--inventory"]) == 1
    output = capsys.readouterr()
    assert "MANIFEST_INVALID" in output.out
    assert "private" not in output.out and output.err == ""
