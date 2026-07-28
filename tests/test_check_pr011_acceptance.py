from __future__ import annotations

import json

import pytest
from scripts import check_pr011_acceptance as checker


def manifest():
    return json.loads(checker.MANIFEST.read_text())


def entry(data, i):
    return next(e for e in data["entries"] if e["id"] == i)


def path_for(i):
    if "-SVC-" in i:
        return "tests/application/test_prepared_jpeg_service.py"
    if "-REP-" in i:
        return "tests/persistence/test_prepared_jpeg_repository.py"
    if "-ENC-" in i:
        return "tests/image_pipeline/test_jpeg_preparer.py"
    if "-MIG-" in i:
        return "tests/persistence/test_migrations.py"
    return "tests/persistence/test_windows_sqlcipher_integration.py"


def add_test(root, i, body="assert 1 == 1"):
    path = path_for(i)
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    name = "test_" + i.lower().replace("-", "_") + "_evidence"
    with p.open("a") as f:
        f.write(f"\ndef {name}():\n    {body}\n")
    return f"{path}::{name}", path


def implement(data, root, i, body="assert 1 == 1"):
    e = entry(data, i)
    if e["evidence_type"] == "pytest":
        s, p = add_test(root, i, body)
        e.update(status="implemented", test_selectors=[s], evidence_files=[p])
    else:
        ref = {
            "pr_metadata": "github:pr:30:body",
            "ci": "github:ci:1:2:" + "a" * 40 + ":success",
            "independent_audit": "audit:docs/audit.md#result",
        }[e["evidence_type"]]
        e.update(status="implemented", evidence_refs=[ref])


def test_schema_v2_and_exact_ids():
    d = manifest()
    assert d["schema_version"] == 2
    assert {e["id"] for e in d["entries"]} == checker.REQUIRED_IDS
    assert len(d["entries"]) == 57


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("schema_version", 1, "MANIFEST_INVALID"),
        ("stage", "bad", "INVALID_STAGE"),
        ("evidence_type", "bad", "INVALID_EVIDENCE_TYPE"),
    ],
)
def test_contract_rejections(tmp_path, field, value, code):
    d = manifest()
    (d if field == "schema_version" else d["entries"][0])[field] = value
    assert code in checker.validate(d, tmp_path).errors


def test_pytest_requires_files_selector_id_and_allowed_path(tmp_path):
    d = manifest()
    e = d["entries"][0]
    e["status"] = "implemented"
    r = checker.validate(d, tmp_path)
    assert "TEST_SELECTOR_MISSING" in r.errors
    s, p = add_test(tmp_path, e["id"])
    e.update(test_selectors=[s.replace("svc_001", "svc_999")], evidence_files=[p])
    assert "TEST_SELECTOR_MISSING" in checker.validate(d, tmp_path).errors
    e["test_selectors"] = [s]
    e["evidence_files"] = ["tests/test_evidence.py"]
    assert "EVIDENCE_PATH_INVALID" in checker.validate(d, tmp_path).errors


def test_selector_cannot_satisfy_two_ids(tmp_path):
    d = manifest()
    implement(d, tmp_path, "PR011-SVC-001")
    e = entry(d, "PR011-SVC-002")
    e.update(
        status="implemented",
        test_selectors=entry(d, "PR011-SVC-001")["test_selectors"],
        evidence_files=entry(d, "PR011-SVC-001")["evidence_files"],
    )
    assert "DUPLICATE_EVIDENCE_SELECTOR" in checker.validate(d, tmp_path).errors


@pytest.mark.parametrize("body", ["pass", "...", '"doc"', "assert True", "return None"])
def test_trivial_evidence_rejected(tmp_path, body):
    d = manifest()
    implement(d, tmp_path, "PR011-SVC-001", body)
    assert "TRIVIAL_TEST_EVIDENCE" in checker.validate(d, tmp_path).errors


def test_nontrivial_id_named_test_is_accepted(tmp_path):
    d = manifest()
    implement(d, tmp_path, "PR011-SVC-001")
    assert checker.validate(d, tmp_path).errors == ()


def test_non_pytest_reference_rules(tmp_path):
    d = manifest()
    e = entry(d, "PR011-FIN-002")
    e.update(status="implemented", test_selectors=["x"])
    assert {"UNEXPECTED_TEST_SELECTOR", "EVIDENCE_REF_MISSING"} <= set(
        checker.validate(d, tmp_path).errors
    )
    e.update(test_selectors=[], evidence_refs=["bad"])
    assert "EVIDENCE_REF_INVALID" in checker.validate(d, tmp_path).errors


@pytest.mark.parametrize(
    ("i", "ref"),
    [
        ("PR011-FIN-001", "github:pr:30:body"),
        ("PR011-FIN-002", "github:ci:1:2:" + "a" * 40 + ":success"),
        ("PR011-FIN-006", "audit:docs/audit.md#result"),
    ],
)
def test_reference_syntax(tmp_path, i, ref):
    d = manifest()
    e = entry(d, i)
    e.update(status="implemented", evidence_refs=[ref])
    assert checker.validate(d, tmp_path).errors == ()


def test_stage_gates_are_cumulative_and_guardrails_are_scoped(tmp_path):
    d = manifest()
    repo = tmp_path / "tests/persistence/test_prepared_jpeg_repository.py"
    repo.parent.mkdir(parents=True)
    repo.write_text(
        "class _Uow: pass\nPRAGMA foreign_keys=OFF\ninspect.getsource(PreparedImageArtifactRepo)"
    )
    assert (
        "PENDING_EVIDENCE"
        in checker.validate(d, tmp_path, required_stage="application_service").errors
    )
    assert (
        "FORBIDDEN_ARTIFICIAL_UOW"
        not in checker.validate(d, tmp_path, required_stage="application_service").errors
    )
    assert (
        "FORBIDDEN_ARTIFICIAL_UOW"
        in checker.validate(d, tmp_path, required_stage="repository_core").errors
    )
    assert (
        "SOURCE_INSPECTION_ONLY"
        in checker.validate(d, tmp_path, required_stage="repository_corruption").errors
    )
    assert "PENDING_EVIDENCE" in checker.validate(d, tmp_path, required_stage="migration").errors
    assert "PENDING_EVIDENCE" in checker.validate(d, tmp_path, required_stage="final").errors


def test_complete_manifest_uses_unique_nontrivial_evidence(tmp_path):
    d = manifest()
    d["current_status"] = "READY_FOR_HUMAN_REVIEW"
    for e in d["entries"]:
        implement(d, tmp_path, e["id"])
    assert checker.validate(d, tmp_path, require_complete=True).errors == ()


def test_invalid_json_output_is_private(tmp_path, capsys, monkeypatch):
    p = tmp_path / "x"
    p.write_text("{private")
    monkeypatch.setattr(checker, "MANIFEST", p)
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    assert checker.main(["--inventory"]) == 1
    o = capsys.readouterr()
    assert "private" not in o.out and not o.err


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", True), ("pr", True), ("entries", "not-a-list"), ("current_status", 123)],
)
def test_top_level_malformed_types_fail_closed(tmp_path, field, value):
    d = manifest()
    d[field] = value
    assert "MANIFEST_INVALID" in checker.validate(d, tmp_path).errors


def test_list_manifest_fails_closed(tmp_path):
    assert "MANIFEST_INVALID" in checker.validate([], tmp_path).errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", 123),
        ("stage", None),
        ("workstream", []),
        ("requirement", 123),
        ("status", []),
        ("platform", None),
        ("evidence_type", 1),
        ("test_selectors", "selector"),
        ("test_selectors", [123]),
        ("evidence_files", "file"),
        ("evidence_files", [None]),
        ("evidence_refs", {}),
        ("evidence_refs", [1]),
        ("notes", []),
    ],
)
def test_entry_malformed_types_fail_closed(tmp_path, field, value):
    d = manifest()
    d["entries"][0][field] = value
    assert "MANIFEST_INVALID" in checker.validate(d, tmp_path).errors


def test_every_evidence_file_is_validated(tmp_path):
    d = manifest()
    implement(d, tmp_path, "PR011-SVC-001")
    e = entry(d, "PR011-SVC-001")
    e["evidence_files"].append("tests/application/missing.txt")
    assert "EVIDENCE_FILE_MISSING" in checker.validate(d, tmp_path).errors
    supporting = tmp_path / "tests/application/support.txt"
    supporting.write_text("synthetic")
    e["evidence_files"][-1] = "tests/application/support.txt"
    assert checker.validate(d, tmp_path).errors == ()


@pytest.mark.parametrize("path", ["/absolute/file", "../outside", "tests/../../outside"])
def test_unsafe_evidence_paths_are_rejected(tmp_path, path):
    d = manifest()
    implement(d, tmp_path, "PR011-SVC-001")
    entry(d, "PR011-SVC-001")["evidence_files"].append(path)
    assert "EVIDENCE_PATH_INVALID" in checker.validate(d, tmp_path).errors


def test_malformed_typed_cli_output_is_private(tmp_path, capsys, monkeypatch):
    bad = tmp_path / "manifest.json"
    bad.write_text(json.dumps({"schema_version": True, "private": str(tmp_path)}))
    monkeypatch.setattr(checker, "MANIFEST", bad)
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    assert checker.main(["--inventory"]) == 1
    captured = capsys.readouterr()
    assert (
        captured.err == "" and "Traceback" not in captured.out and "TypeError" not in captured.out
    )
    assert str(tmp_path) not in captured.out and "private" not in captured.out
