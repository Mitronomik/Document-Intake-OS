#!/usr/bin/env python3
"""Deterministic, privacy-safe structural gate for PR-011 evidence."""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/tasks/PR-011-acceptance-manifest.json"
STAGES = (
    "application_service",
    "repository_core",
    "repository_corruption",
    "encoder",
    "migration",
    "windows",
    "final",
)
PREFIX_COUNTS = {"SVC": 17, "REP": 17, "ENC": 5, "MIG": 7, "WIN": 4, "FIN": 7}
REQUIRED_IDS = frozenset(
    f"PR011-{p}-{n:03d}" for p, c in PREFIX_COUNTS.items() for n in range(1, c + 1)
)
FIELDS = frozenset(
    {
        "id",
        "stage",
        "workstream",
        "requirement",
        "status",
        "platform",
        "evidence_type",
        "test_selectors",
        "evidence_files",
        "evidence_refs",
        "notes",
    }
)
TYPES = {"pytest", "ci", "pr_metadata", "independent_audit"}
PLATFORMS = {"cross_platform", "windows", "documentation"}


@dataclass(frozen=True, slots=True)
class Report:
    schema_version: int
    total: int
    implemented: tuple[str, ...]
    pending: tuple[str, ...]
    errors: tuple[str, ...]
    findings: tuple[str, ...]
    requested_stage: str | None
    completed_stages: int


def expected_stage(i: str) -> str:
    if "-SVC-" in i:
        return "application_service"
    if "-REP-" in i:
        return "repository_core" if int(i[-3:]) <= 11 else "repository_corruption"
    if "-ENC-" in i:
        return "encoder"
    if "-MIG-" in i:
        return "migration"
    if "-WIN-" in i:
        return "windows"
    return "final"


def expected_type(i: str) -> str:
    if i == "PR011-FIN-001":
        return "pr_metadata"
    if i in {"PR011-FIN-002", "PR011-FIN-003", "PR011-FIN-004", "PR011-FIN-005"}:
        return "ci"
    if "-FIN-" in i:
        return "independent_audit"
    return "pytest"


def _function(root: Path, selector: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    parts = selector.split("::")
    if len(parts) != 2:
        return None
    try:
        tree = ast.parse((root / parts[0]).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return None
    return next(
        (
            n
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == parts[1]
        ),
        None,
    )


def _trivial(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = list(fn.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body:
        return True
    if len(body) != 1:
        return False
    node = body[0]
    return (
        isinstance(node, ast.Pass)
        or (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and node.value.value is Ellipsis
        )
        or (
            isinstance(node, ast.Assert)
            and isinstance(node.test, ast.Constant)
            and node.test.value is True
        )
        or (
            isinstance(node, ast.Return)
            and (
                node.value is None
                or (isinstance(node.value, ast.Constant) and node.value.value is None)
            )
        )
    )


def _allowed_path(i: str, path: str) -> bool:
    p = Path(path)
    name = p.name
    if "-SVC-" in i:
        return p.parent == Path("tests/application") and (
            name == "test_prepared_jpeg_service.py" or name.startswith("test_prepared_jpeg_")
        )
    if "-REP-" in i:
        return p.parent == Path("tests/persistence") and name.startswith("test_prepared_jpeg_")
    if "-ENC-" in i:
        return path == "tests/image_pipeline/test_jpeg_preparer.py"
    if "-MIG-" in i:
        return path == "tests/persistence/test_migrations.py" or (
            p.parent == Path("tests/persistence") and name.startswith("test_pr011_migration_")
        )
    if "-WIN-" in i:
        return path == "tests/persistence/test_windows_sqlcipher_integration.py"
    return True


def guardrail_codes(root: Path) -> tuple[str, ...]:
    try:
        t = (root / "tests/persistence/test_prepared_jpeg_repository.py").read_text()
    except OSError:
        return ()
    out = []
    if "class _Uow" in t:
        out.append("FORBIDDEN_ARTIFICIAL_UOW")
    if "PRAGMA foreign_keys=OFF" in t or "PRAGMA foreign_keys = OFF" in t:
        out.append("FOREIGN_KEYS_DISABLED")
    if "inspect.getsource(PreparedImageArtifactRepo)" in t:
        out.append("SOURCE_INSPECTION_ONLY")
    return tuple(out)


def _ref_valid(typ: str, ref: str) -> bool:
    if typ == "pr_metadata":
        return ref == "github:pr:30:body"
    if typ == "ci":
        return re.fullmatch(r"github:ci:\d+:\d+:[0-9a-f]{40}:success", ref) is not None
    return (
        typ == "independent_audit"
        and re.fullmatch(r"audit:[A-Za-z0-9_./-]+#[A-Za-z0-9_.-]+", ref) is not None
    )


def validate(
    data: Any, root: Path, *, required_stage: str | None = None, require_complete: bool = False
) -> Report:
    errors: list[str] = []
    implemented: list[str] = []
    pending: list[str] = []
    selectors: dict[str, list[str]] = {}
    top_valid = (
        isinstance(data, dict)
        and type(data.get("schema_version")) is int
        and data.get("schema_version") == 2
        and type(data.get("pr")) is int
        and data.get("pr") == 30
        and isinstance(data.get("contract"), str)
        and isinstance(data.get("implementation_base"), str)
        and isinstance(data.get("current_status"), str)
        and isinstance(data.get("entries"), list)
    )
    if not top_valid:
        return Report(0, 0, (), (), ("MANIFEST_INVALID",), (), required_stage, 0)
    entries = data["entries"]
    if (
        data.get("pr") != 30
        or data.get("contract") != "PR-011"
        or data.get("implementation_base") != "f007fb5a04a5c69c70a37faf7ba12fa6775ae819"
        or not isinstance(entries, list)
    ):
        errors.append("MANIFEST_INVALID")
    valid_entries: list[dict[str, Any]] = []
    for e in entries:
        if not isinstance(e, dict) or set(e) != FIELDS:
            errors.append("MANIFEST_INVALID")
            continue
        scalar_fields = (
            "id",
            "stage",
            "workstream",
            "requirement",
            "status",
            "platform",
            "evidence_type",
            "notes",
        )
        list_fields = ("test_selectors", "evidence_files", "evidence_refs")
        if any(not isinstance(e[k], str) or not e[k] for k in scalar_fields) or any(
            type(e[k]) is not list or any(not isinstance(v, str) or not v for v in e[k])
            for k in list_fields
        ):
            errors.append("MANIFEST_INVALID")
            continue
        valid_entries.append(e)
    ids = [e["id"] for e in valid_entries]
    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE_ID")
    observed = {i for i in ids if isinstance(i, str)}
    if REQUIRED_IDS - observed:
        errors.append("REQUIRED_ID_MISSING")
    if observed - REQUIRED_IDS:
        errors.append("UNKNOWN_ID")
    for e in valid_entries:
        i = e["id"]
        status = e["status"]
        if status not in {"pending", "implemented"}:
            errors.append("INVALID_STATUS")
            continue
        (implemented if status == "implemented" else pending).append(i)
        if e["stage"] not in STAGES or e["stage"] != expected_stage(i):
            errors.append("INVALID_STAGE")
        if e["evidence_type"] not in TYPES or e["evidence_type"] != expected_type(i):
            errors.append("INVALID_EVIDENCE_TYPE")
        if e["platform"] not in PLATFORMS:
            errors.append("MANIFEST_INVALID")
        for evidence in e["evidence_files"]:
            candidate = Path(evidence)
            try:
                resolved = (root / candidate).resolve()
                inside = resolved.is_relative_to(root.resolve())
            except (OSError, RuntimeError):
                inside = False
            if candidate.is_absolute() or ".." in candidate.parts or not inside:
                errors.append("EVIDENCE_PATH_INVALID")
            elif not resolved.is_file():
                errors.append("EVIDENCE_FILE_MISSING")
        if status == "implemented" and e["evidence_type"] == "pytest":
            if not e["test_selectors"] or not e["evidence_files"]:
                errors.append("TEST_SELECTOR_MISSING")
            token = "test_" + i.lower().replace("-", "_") + "_"
            for s in e["test_selectors"]:
                selectors.setdefault(s, []).append(i)
                path = s.split("::")[0]
                if path not in e["evidence_files"] or not _allowed_path(i, path):
                    errors.append("EVIDENCE_PATH_INVALID")
                fn = _function(root, s)
                if fn is None:
                    errors.append("TEST_SELECTOR_MISSING")
                elif token not in fn.name:
                    errors.append("TEST_SELECTOR_ID_MISMATCH")
                elif _trivial(fn):
                    errors.append("TRIVIAL_TEST_EVIDENCE")
        elif status == "implemented":
            if e["test_selectors"]:
                errors.append("UNEXPECTED_TEST_SELECTOR")
            if not e["evidence_refs"]:
                errors.append("EVIDENCE_REF_MISSING")
            elif any(
                not isinstance(r, str) or not _ref_valid(e["evidence_type"], r)
                for r in e["evidence_refs"]
            ):
                errors.append("EVIDENCE_REF_INVALID")
    if any(len(v) > 1 for v in selectors.values()):
        errors.append("DUPLICATE_EVIDENCE_SELECTOR")
    findings = guardrail_codes(root)
    stage = "final" if require_complete else required_stage
    if stage is not None:
        upto = set(STAGES[: STAGES.index(stage) + 1])
        required = [e["id"] for e in valid_entries if e["stage"] in upto]
        if any(i in pending for i in required):
            errors.append("PENDING_EVIDENCE")
        if STAGES.index(stage) >= 1:
            errors.extend(
                c for c in findings if c in {"FORBIDDEN_ARTIFICIAL_UOW", "FOREIGN_KEYS_DISABLED"}
            )
        if STAGES.index(stage) >= 2:
            errors.extend(c for c in findings if c == "SOURCE_INSPECTION_ONLY")
    if pending and data.get("current_status") != "BLOCKED":
        errors.append("LIFECYCLE_STATUS_INVALID")
    if (require_complete or stage == "final") and data.get(
        "current_status"
    ) != "READY_FOR_HUMAN_REVIEW":
        errors.append("LIFECYCLE_STATUS_INVALID")
    completed = sum(
        all(e.get("status") == "implemented" for e in valid_entries if e["stage"] == s)
        for s in STAGES
    )
    return Report(
        int(data.get("schema_version", 0)) if isinstance(data, dict) else 0,
        len(entries),
        tuple(sorted(implemented)),
        tuple(sorted(pending)),
        tuple(dict.fromkeys(errors)),
        findings,
        stage,
        completed,
    )


def run(
    manifest: Path, root: Path, *, required_stage: str | None = None, require_complete: bool = False
) -> Report:
    try:
        data = json.loads(manifest.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return Report(0, 0, (), (), ("MANIFEST_INVALID",), (), required_stage, 0)
    try:
        return validate(
            data, root, required_stage=required_stage, require_complete=require_complete
        )
    except Exception:
        return Report(0, 0, (), (), ("CHECKER_INTERNAL_ERROR",), (), required_stage, 0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--inventory", action="store_true")
    g.add_argument("--require-complete", action="store_true")
    g.add_argument("--require-stage", choices=STAGES)
    a = p.parse_args(argv)
    r = run(MANIFEST, ROOT, required_stage=a.require_stage, require_complete=a.require_complete)
    mode = (
        "require_complete"
        if a.require_complete
        else ("require_stage" if a.require_stage else "inventory")
    )
    print(f"PR011_ACCEPTANCE mode={mode}")
    print(f"PR011_ACCEPTANCE requested_stage={r.requested_stage or 'none'}")
    print(f"PR011_ACCEPTANCE completed_stages={r.completed_stages}")
    print(f"PR011_ACCEPTANCE schema_version={r.schema_version}")
    print(f"PR011_ACCEPTANCE total={r.total}")
    print(f"PR011_ACCEPTANCE implemented={len(r.implemented)}")
    print(f"PR011_ACCEPTANCE pending={len(r.pending)}")
    for c in (*r.findings, *r.errors):
        print(f"PR011_ACCEPTANCE code={c}")
    print(f"PR011_ACCEPTANCE result={'FAIL' if r.errors else 'PASS'}")
    return 1 if r.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
