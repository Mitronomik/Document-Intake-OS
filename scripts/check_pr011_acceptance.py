#!/usr/bin/env python3
"""Deterministic, privacy-safe structural gate for PR-011 acceptance evidence."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/tasks/PR-011-acceptance-manifest.json"
PREFIX_COUNTS = {"SVC": 17, "REP": 17, "ENC": 5, "MIG": 7, "WIN": 4, "FIN": 7}
REQUIRED_IDS = frozenset(
    f"PR011-{prefix}-{number:03d}"
    for prefix, count in PREFIX_COUNTS.items()
    for number in range(1, count + 1)
)
REQUIRED_FIELDS = frozenset(
    {
        "id",
        "workstream",
        "requirement",
        "status",
        "platform",
        "test_selectors",
        "evidence_files",
        "notes",
    }
)
STATUSES = {"pending", "implemented"}
PLATFORMS = {"cross_platform", "windows", "documentation"}


@dataclass(frozen=True, slots=True)
class Report:
    schema_version: int
    total: int
    implemented: tuple[str, ...]
    pending: tuple[str, ...]
    errors: tuple[str, ...]
    findings: tuple[str, ...]


def _selector_exists(root: Path, selector: str) -> bool:
    parts = selector.split("::")
    if len(parts) != 2 or not parts[1].startswith("test_"):
        return False
    path = root / parts[0]
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == parts[1]
        for node in tree.body
    )


def guardrail_codes(root: Path) -> tuple[str, ...]:
    path = root / "tests/persistence/test_prepared_jpeg_repository.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ()
    codes: list[str] = []
    if "class _Uow" in text:
        codes.append("FORBIDDEN_ARTIFICIAL_UOW")
    if "PRAGMA foreign_keys=OFF" in text or "PRAGMA foreign_keys = OFF" in text:
        codes.append("FOREIGN_KEYS_DISABLED")
    if "inspect.getsource(PreparedImageArtifactRepo)" in text:
        codes.append("SOURCE_INSPECTION_ONLY")
    return tuple(codes)


def validate(data: Any, root: Path, *, require_complete: bool) -> Report:
    errors: list[str] = []
    if not isinstance(data, dict):
        return Report(0, 0, (), (), ("MANIFEST_INVALID",), ())
    expected = {
        "schema_version": 1,
        "pr": 30,
        "contract": "PR-011",
        "implementation_base": "f007fb5a04a5c69c70a37faf7ba12fa6775ae819",
    }
    if any(data.get(key) != value for key, value in expected.items()) or not isinstance(
        data.get("entries"), list
    ):
        errors.append("MANIFEST_INVALID")
    entries = data.get("entries", []) if isinstance(data.get("entries"), list) else []
    ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE_ID")
    observed = {item for item in ids if isinstance(item, str)}
    if REQUIRED_IDS - observed:
        errors.append("REQUIRED_ID_MISSING")
    if observed - REQUIRED_IDS:
        errors.append("UNKNOWN_ID")
    implemented: list[str] = []
    pending: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != REQUIRED_FIELDS:
            errors.append("MANIFEST_INVALID")
            continue
        status = entry["status"]
        if status not in STATUSES:
            errors.append("INVALID_STATUS")
            continue
        if entry["platform"] not in PLATFORMS or not all(
            isinstance(entry[key], expected_type)
            for key, expected_type in (
                ("id", str),
                ("workstream", str),
                ("requirement", str),
                ("test_selectors", list),
                ("evidence_files", list),
                ("notes", str),
            )
        ):
            errors.append("MANIFEST_INVALID")
            continue
        target = implemented if status == "implemented" else pending
        target.append(entry["id"])
        for evidence in entry["evidence_files"]:
            if not isinstance(evidence, str) or not (root / evidence).is_file():
                errors.append("EVIDENCE_FILE_MISSING")
        if status == "implemented":
            if not entry["test_selectors"]:
                errors.append("TEST_SELECTOR_MISSING")
            for selector in entry["test_selectors"]:
                if not isinstance(selector, str) or not _selector_exists(root, selector):
                    errors.append("TEST_SELECTOR_MISSING")
    if pending and data.get("current_status") != "BLOCKED":
        errors.append("LIFECYCLE_STATUS_INVALID")
    findings = guardrail_codes(root)
    if require_complete:
        if pending:
            errors.append("PENDING_EVIDENCE")
        if data.get("current_status") != "READY_FOR_HUMAN_REVIEW":
            errors.append("LIFECYCLE_STATUS_INVALID")
        fin7 = next(
            (
                entry
                for entry in entries
                if isinstance(entry, dict) and entry.get("id") == "PR011-FIN-007"
            ),
            {},
        )
        if fin7.get("status") != "implemented":
            errors.append("PENDING_EVIDENCE")
        errors.extend(findings)
    return Report(
        int(data.get("schema_version", 0)),
        len(entries),
        tuple(sorted(implemented)),
        tuple(sorted(pending)),
        tuple(dict.fromkeys(errors)),
        findings,
    )


def run(manifest: Path, root: Path, *, require_complete: bool) -> Report:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return Report(0, 0, (), (), ("MANIFEST_INVALID",), ())
    return validate(data, root, require_complete=require_complete)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inventory", action="store_true")
    mode.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    report = run(MANIFEST, ROOT, require_complete=args.require_complete)
    print(f"PR011_ACCEPTANCE mode={'require_complete' if args.require_complete else 'inventory'}")
    print(f"PR011_ACCEPTANCE schema_version={report.schema_version}")
    print(f"PR011_ACCEPTANCE total={report.total}")
    print(f"PR011_ACCEPTANCE implemented={len(report.implemented)}")
    print(f"PR011_ACCEPTANCE pending={len(report.pending)}")
    for code in (*report.findings, *report.errors):
        print(f"PR011_ACCEPTANCE code={code}")
    print(f"PR011_ACCEPTANCE result={'FAIL' if report.errors else 'PASS'}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
