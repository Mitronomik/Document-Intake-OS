"""Documentation-baseline contract tests for PR-002 and GATE-M0."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCUMENTS = (
    "AGENTS.md",
    "README.md",
    "docs/technical-specification.md",
    "docs/project-charter.md",
    "docs/product-spec.md",
    "docs/architecture.md",
    "docs/domain-model.md",
    "docs/image-pipeline.md",
    "docs/recognition-strategy.md",
    "docs/excel-adapters.md",
    "docs/file-storage-model.md",
    "docs/security.md",
    "docs/non-functional-requirements.md",
    "docs/testing-strategy.md",
    "docs/acceptance-criteria.md",
    "docs/traceability-matrix.md",
    "docs/implementation-plan.md",
    "docs/roadmap.md",
    "docs/development-workflow.md",
    "docs/decisions.md",
    "docs/open-questions.md",
    "docs/terminology.md",
    "docs/progress.md",
    "docs/handoff.md",
    "docs/tasks/PR-001-repository-bootstrap.md",
    "docs/tasks/PR-002-documentation-baseline.md",
    "docs/tasks/PR-003-ci-privacy-guardrails.md",
    "docs/tasks/GATE-M0-requirements-lock.md",
    "docs/tasks/PR-004-core-domain.md",
    "docs/tasks/GATE-S1-encryption-staging.md",
    "docs/tasks/GATE-S1-acceptance.md",
    "docs/tasks/PR-S001-F1-windows-cleanup-acl-evidence.md",
    "docs/tasks/PR-S001-F2-wal-journal-evidence.md",
    "docs/tasks/PR-S001-F3-windows-acl-diagnostics.md",
    "docs/tasks/PR-S001-F4-windows11-target-attestation.md",
    "docs/tasks/PR-005-encrypted-sqlite-persistence.md",
)

CANONICAL_SOURCE_ORDER = (
    "docs/technical-specification.md",
    "docs/decisions.md",
    "docs/product-spec.md",
    "docs/architecture.md",
    "docs/domain-model.md",
    "docs/security.md",
    "docs/testing-strategy.md",
)

INLINE_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _repo_relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _markdown_files() -> list[Path]:
    docs = sorted((REPO_ROOT / "docs").glob("**/*.md"))
    return [REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md", *docs]


def _without_fenced_code_blocks(markdown: str) -> str:
    in_fence = False
    kept_lines: list[str] = []
    for line in markdown.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            kept_lines.append("")
            continue
        kept_lines.append("" if in_fence else line)
    return "\n".join(kept_lines)


def _is_skipped_link(target: str) -> bool:
    return (
        target.startswith("http://")
        or target.startswith("https://")
        or target.startswith("mailto:")
        or target.startswith("#")
    )


def _file_part(target: str) -> str:
    return target.split("#", 1)[0]


def _canonical_section(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    assert start is not None, f"Missing canonical source section heading: {heading}"

    section_lines: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section_lines.append(line)
    return "\n".join(section_lines)


def _adr_section(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index
            break
    assert start is not None, f"Missing ADR heading: {heading}"

    section_lines: list[str] = []
    for line in lines[start:]:
        if section_lines and line.startswith("## "):
            break
        section_lines.append(line)
    return "\n".join(section_lines)


def _question_section(markdown: str, question_id: str) -> str:
    heading = f"### {question_id}"
    lines = markdown.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index
            break
    assert start is not None, f"Missing open-question heading: {heading}"

    section_lines: list[str] = []
    for line in lines[start:]:
        if section_lines and line.startswith("### Q-"):
            break
        section_lines.append(line)
    return "\n".join(section_lines)


def _compact(text: str) -> str:
    return " ".join(text.split())


def _question_status(section: str) -> str:
    match = re.search(r"^\*\*Status:\*\* ([A-Z_]+)$", section, flags=re.MULTILINE)
    assert match is not None, "Question section is missing exactly formatted status"
    return match.group(1)


def test_required_documentation_files_exist() -> None:
    missing = [path for path in REQUIRED_DOCUMENTS if not (REPO_ROOT / path).is_file()]
    assert not missing, "Missing required documentation files: " + ", ".join(missing)


def test_relative_markdown_links_resolve() -> None:
    failures: list[str] = []

    for markdown_file in _markdown_files():
        text = _without_fenced_code_blocks(markdown_file.read_text(encoding="utf-8"))
        for match in INLINE_LINK_RE.finditer(text):
            target = match.group(1).strip()
            if _is_skipped_link(target):
                continue

            file_part = _file_part(target)
            if not file_part:
                continue

            resolved = (markdown_file.parent / file_part).resolve()
            if not resolved.is_relative_to(REPO_ROOT):
                failures.append(
                    f"{_repo_relative(markdown_file)} -> {target} escapes repository root"
                )
                continue
            if not resolved.exists():
                failures.append(
                    f"{_repo_relative(markdown_file)} -> {target} resolves to missing {resolved}"
                )

    assert not failures, "Unresolved relative Markdown links:\n" + "\n".join(failures)


def test_readme_and_agents_use_canonical_source_order() -> None:
    sections = {
        "README.md": _canonical_section(
            (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            "## Приоритет источников",
        ),
        "AGENTS.md": _canonical_section(
            (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8"),
            "## Authoritative sources",
        ),
    }

    for source_file, section in sections.items():
        positions = []
        for path in CANONICAL_SOURCE_ORDER:
            position = section.find(path)
            assert position != -1, f"{source_file} canonical source section is missing {path}"
            positions.append(position)
        assert positions == sorted(positions), (
            f"{source_file} canonical source section is out of order"
        )


def test_lifecycle_state_records_pr005_accepted_state() -> None:
    lifecycle_files = (
        "docs/progress.md",
        "docs/roadmap.md",
        "docs/implementation-plan.md",
        "docs/handoff.md",
        "docs/traceability-matrix.md",
    )
    required_by_file = (
        "GATE-M0: COMPLETED",
        "M0: ACCEPTED",
        "M1: ACCEPTED",
        "PR-004: COMPLETED AND HUMAN ACCEPTED",
        "GATE-S1: COMPLETED AND HUMAN ACCEPTED",
        "ADR-018: ACCEPTED",
        "Q-010: ACCEPTED",
        "PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK",
        "RISK-S001-W11",
        "PR-005: COMPLETED AND HUMAN ACCEPTED",
        "PR-006: UNAUTHORIZED",
        "PR-007 AND LATER: UNAUTHORIZED",
        "Gate 1: NOT ACCEPTED",
        "M2: NOT COMPLETED",
        "2161fbbf7fb4065a5913fb6e62c207546caf5dd9",
        "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500",
    )
    stale_current_state = (
        "GATE-M0 is in review",
        "GATE-M0 IN REVIEW",
        "M0 DECISION APPROVED, NOT YET RECORDED IN MAIN",
        "PR-004 remains blocked until GATE-M0",
        "PR-004 BLOCKED UNTIL GATE-M0",
        "Complete review, CI and human acceptance for the GATE-M0 PR",
        "The next safe step is GATE-M0 review",
        "GATE-M0 does not start PR-004",
        "do not start PR-004 until",
        "After this PR is merged and accepted, the next repository update may prepare PR-004",
        "See current lifecycle state below. See current lifecycle state below",
        "but See current lifecycle state below",
        "next safe step is GATE-M0",
        "PR-004: IN REVIEW",
        "PR-004: NOT COMPLETED BEFORE MERGE AND PRODUCT-OWNER ACCEPTANCE",
        "PR-004 is the only authorized implementation task",
        "PR-004 is in review",
        "PR-004 Core Domain is the only authorized implementation task",
        "GATE-S1: IN REVIEW",
        "ADR-018: PROPOSED",
        "Q-010: OPEN",
        "PR-S001: PROPOSED, NOT AUTHORIZED",
        "PR-S001 FINAL ACCEPTANCE: NOT ACCEPTED",
        "PR-S001: IN REVIEW",
        "PR-S001 is in review",
        "PR-S001-F4: CURRENT CORRECTION",
        "PR-005 and later tasks remain unauthorized",
        "PR-005: UNAUTHORIZED",
        "PR-005 remains unauthorized",
        "authorize PR-005 entry, not implementation start",
        "do not start PR-005 until separately authorized",
        "PR-005 must not start without",
        "later authorization",
        "Explicit non-authorization of PR-005 and PR-006",
        "review PR-S001 evidence and make a product-owner feasibility decision",
        "PR-005: AUTHORIZED, NOT STARTED",
        "PR-005: IN REVIEW",
        "PR-005 is IN REVIEW",
        "PR-005 remains IN REVIEW",
        "PR-005 remains in review",
        "PR-005 implementation is in review",
        "PR-005 remains in review and not accepted",
        "Windows CI evidence remains required",
        "Gate 1: ACCEPTED",
        "M2: COMPLETED",
        "review and product-owner decision on GATE-S1 / ADR-018",
    )

    for filename in lifecycle_files:
        text = (REPO_ROOT / filename).read_text(encoding="utf-8")
        for required in required_by_file:
            assert required in text, filename
        assert (
            "preparing and reviewing the exact PR-006 task" in text
            or "Prepare and review the exact PR-006 task" in text
        ), filename
        assert (
            "implementation remains prohibited" in text
            or "implementation prohibited" in text
            or "implementation cannot start" in text
            or "Filesystem-storage implementation cannot start" in text
            or "No filesystem-storage implementation may begin" in text
        ), filename
        old_next_step = (
            "review PR-005 code, Windows SQLCipher CI evidence, migrations, "
            "repository round trips, transaction tests and privacy checks"
        )
        assert old_next_step not in text, filename
        for stale in stale_current_state:
            assert stale not in text, filename

    progress = (REPO_ROOT / "docs/progress.md").read_text(encoding="utf-8")
    assert "PR-S001-F1 is the current correction" not in progress
    assert "PR-S001-F2 is the current correction" not in progress
    assert "PR-S001-F3 is the current correction" not in progress
    assert "**Обновлено:** 2026-07-17" not in progress
    assert "**Обновлено:** 2026-07-18" not in progress
    assert "**Обновлено:** 2026-07-19" in progress
    assert "- [x] GATE-S1: COMPLETED AND HUMAN ACCEPTED;" in progress
    assert "- [x] ADR-018: ACCEPTED;" in progress
    assert "- [x] Q-010: ACCEPTED;" in progress
    assert "- [x] PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11;" in progress
    assert "PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13" in progress
    assert "985fae37c7645e8f65edbe4d1609100ee24a2097" in progress
    assert "- [ ] PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK" not in progress
    assert "- [x] PR-005: COMPLETED AND HUMAN ACCEPTED;" in progress
    assert "- [ ] PR-005: IN REVIEW, NOT ACCEPTED;" not in progress
    assert "- [ ] PR-006: UNAUTHORIZED;" in progress
    assert "- [ ] GATE-S1: COMPLETED AND HUMAN ACCEPTED;" not in progress
    assert "- [ ] ADR-018: ACCEPTED;" not in progress
    assert "- [ ] Q-010: ACCEPTED;" not in progress

    task = (REPO_ROOT / "docs/tasks/PR-005-encrypted-sqlite-persistence.md").read_text(
        encoding="utf-8"
    )
    assert "Status: COMPLETED AND HUMAN ACCEPTED" in task
    assert "GitHub PR #15" in task
    assert "325b49555dee49fa22b008d9522bbbc6eb873ca2" in task
    assert "2161fbbf7fb4065a5913fb6e62c207546caf5dd9" in task
    assert "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500" in task

    domain_model = (REPO_ROOT / "docs/domain-model.md").read_text(encoding="utf-8")
    assert "The PR-005 persistence slice for FR-13 is COMPLETED AND HUMAN ACCEPTED" in domain_model
    assert (
        "FR-13 remains not fully complete beyond the accepted persisted PR-004 domain scope"
        in domain_model
    )


def test_gate_s1_encryption_staging_acceptance_contract() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")
    task = (REPO_ROOT / "docs/tasks/GATE-S1-encryption-staging.md").read_text(encoding="utf-8")
    pr004 = (REPO_ROOT / "docs/tasks/PR-004-core-domain.md").read_text(encoding="utf-8")
    adr_018_heading = "## ADR-018 — Encryption Staging and Windows Key Protection"

    assert decisions.count(adr_018_heading) == 1
    adr_018 = _adr_section(decisions, adr_018_heading)
    q010 = _question_section(open_questions, "Q-010")

    assert "**Status:** ACCEPTED" in adr_018
    assert "**Accepted date:** 2026-07-17" in adr_018
    assert "**GATE-S1 merge commit:** fb9984036f7df0c34badfc3a93f6faec1bc5d38e" in adr_018
    assert "ADR-018 is accepted as the architecture direction." in adr_018
    assert _question_status(q010) == "ACCEPTED"
    assert "**Decision reference:** ADR-018" in q010
    assert "ADR-018 accepted after merge of GitHub PR #7" in q010
    assert "Option C — Encryption-first application architecture" in q010
    assert "architecture and sequencing level" in q010
    assert "Production plaintext persistence is prohibited" in q010
    assert "PR-S001 is authorized, not started" in q010
    assert "PR-005 and PR-006 remain unauthorized" in q010
    assert "no encryption technology has yet been implemented" in q010
    assert "does not finally select a package, edition, binding, version" in q010
    assert "PR-S001 evidence" in q010

    assert "PR-004: COMPLETED" in pr004
    assert "GitHub PR: #6" in pr004
    assert "Merge commit: 6f3021a38305cb92d733a46426cde427828bac04" in pr004
    assert "Product-owner acceptance: CONFIRMED" in pr004

    compact_adr = _compact(adr_018)
    assert "No production-capable database or document storage" in compact_adr
    assert "may write personal data to disk in plaintext" in compact_adr
    assert "silently falls back to plaintext" in compact_adr
    assert "Failure to initialize encryption must fail closed" in compact_adr
    assert "raw key is never stored in source code" in compact_adr
    assert "configuration, environment variables, logs or database rows" in compact_adr
    assert "kept separate from encrypted database and storage content" in compact_adr
    assert "Copying only the DPAPI blob is not a portable backup strategy" in compact_adr
    assert (
        "does not choose a final Python binding, package version or SQLCipher edition"
        in compact_adr
    )
    assert "exact cryptography package" in compact_adr
    assert "offline theft or copying of the workstation disk" in compact_adr
    assert "malicious code running under the same Windows user credentials" in compact_adr
    assert (
        "DPAPI Current User allows applications running under the same Windows credentials"
        in compact_adr
    )
    assert "not claimed to provide application-to-application isolation" in compact_adr
    assert "must not be used directly as the database encryption key" in compact_adr
    assert "purpose/domain separation is mandatory" in compact_adr
    assert "must not automatically expose other purpose keys" in compact_adr
    assert "Python code must not claim guaranteed secure zeroization" in compact_adr
    assert "full-database encryption with integrity authentication through SQLCipher" in compact_adr
    assert "verify SQLCipher encryption is active for every production connection" in compact_adr
    assert "verify WAL and rollback-journal page content is encrypted" in compact_adr
    assert "file-based SQLite temporary stores cannot contain plaintext" in compact_adr
    assert "SQL-string key injection" in compact_adr
    assert "format magic/version" in compact_adr
    assert "canonical authenticated metadata schema" in compact_adr
    assert "rollback/replay control" in compact_adr
    assert "partially written objects must fail authentication" in compact_adr
    assert "does not by itself prove that the object is the latest accepted version" in compact_adr
    assert "not treated as its own independent rollback anchor" in compact_adr
    assert (
        "authoritative expected-state record outside the replaceable encrypted object"
        in compact_adr
    )
    assert "expected object generation or immutable version" in compact_adr
    assert "key version is not accepted" in compact_adr
    assert "prior valid envelope while leaving the authoritative record unchanged" in compact_adr
    assert "does not claim detection of a coordinated rollback" in compact_adr
    assert "complete encrypted database" in compact_adr
    assert "complete encrypted storage" in compact_adr
    assert "external or monotonic trust anchor" in compact_adr
    assert "No TPM counter, remote service, online timestamp" in compact_adr

    compact_task = _compact(task)
    assert "Envelope authentication proves integrity and authenticity" in compact_task
    assert "does not prove freshness or latest-version status" in compact_task
    assert "not its own rollback anchor" in compact_task
    assert "authoritative expected state outside the replaceable encrypted object" in compact_task
    assert "old valid envelope" in compact_task
    assert "Coordinated rollback of all local state" in compact_task
    assert "not claimed as solved" in compact_task
    assert "Exact persistence transaction boundaries" in compact_task

    assert "**Final state:** REJECTED" in adr_018
    assert "**Final state:** REJECTED AS SOLE CONTROL" in adr_018
    assert "**Final state:** ACCEPTED" in adr_018
    assert "Accepted direction: DPAPI Current User-protected" in adr_018

    assert "PR-S001 is authorized, not started" in adr_018
    assert (
        "current encrypted object opens when its independent authoritative record matches"
        in adr_018
    )
    assert "bit modification fails authentication" in adr_018
    assert "older valid envelope fails" in adr_018
    assert "copying an envelope to another artifact ID fails" in adr_018
    assert "key-version mismatch fails closed" in adr_018
    assert "crash-consistency design" in adr_018
    assert "database transaction first" in adr_018
    assert "object publication first" in adr_018
    assert "staged pending state" in adr_018
    assert "recovery reconciliation" in adr_018
    assert "PR-005 and PR-006 remain unauthorized" in adr_018
    assert "PR-007 AND LATER: UNAUTHORIZED" in task
    assert "Gate 1: NOT ACCEPTED" in task
    assert "M2: NOT COMPLETED" in task
    assert "## Original task base SHA\n\n`6f3021a38305cb92d733a46426cde427828bac04`" in task
    assert "Original task base:" in task
    assert "Resulting GATE-S1 merge commit:" in task
    assert task.index("Original task base:") < task.index("Resulting GATE-S1 merge commit:")
    assert "Product-owner acceptance: CONFIRMED" in task
    assert "GitHub PR: #7" in task
    assert "Merge commit: fb9984036f7df0c34badfc3a93f6faec1bc5d38e" in task


def test_gate_s1_acceptance_security_and_lifecycle_boundaries() -> None:
    security = (REPO_ROOT / "docs/security.md").read_text(encoding="utf-8")
    acceptance = (REPO_ROOT / "docs/tasks/GATE-S1-acceptance.md").read_text(encoding="utf-8")
    lifecycle_files = (
        "docs/progress.md",
        "docs/roadmap.md",
        "docs/implementation-plan.md",
        "docs/handoff.md",
        "docs/traceability-matrix.md",
    )

    compact_security = _compact(security)
    assert "ADR-018 is accepted" in compact_security
    assert "Windows DPAPI Current User" in compact_security
    assert "purpose separation" in compact_security
    assert "SQLCipher or a separately validated equivalent" in compact_security
    assert "authenticated application-level encryption" in compact_security
    assert (
        "does not isolate applications running under the same Windows credentials"
        in compact_security
    )
    assert "Object-level rollback detection requires expected state outside" in compact_security
    assert "Coordinated rollback of the full encrypted database" in compact_security
    assert "Final packages and versions" in compact_security
    assert "final Python database binding" in compact_security
    assert "exact KDF/wrapping mechanics" in compact_security
    assert "exact encrypted-envelope format" in compact_security

    compact_acceptance = _compact(acceptance)
    assert "This PR records the accepted decision." in compact_acceptance
    assert "This PR does not implement PR-S001." in compact_acceptance
    assert "This PR does not authorize PR-005 or PR-006." in compact_acceptance
    assert "No encryption technology has yet been implemented" in compact_acceptance

    for filename in lifecycle_files:
        text = (REPO_ROOT / filename).read_text(encoding="utf-8")
        assert "PR-005: COMPLETED AND HUMAN ACCEPTED" in text, filename
        assert "PR-006: UNAUTHORIZED" in text, filename
        assert "Q-017 remains deferred" in text, filename
        assert (
            "real documents and personal data remain prohibited in Git, Codex and CI" in text
            or "Real documents and personal data remain prohibited in Git, Codex and CI" in text
        ), filename


def test_pr005_pr006_sequences_remain_blocked_after_gate_s1_acceptance() -> None:
    implementation_plan = (REPO_ROOT / "docs/implementation-plan.md").read_text(encoding="utf-8")

    assert (
        "accepted PR-S001 review and explicit follow-up authorization, accepted PR-S001"
        not in implementation_plan
    )
    assert "PR-005 is COMPLETED AND HUMAN ACCEPTED through GitHub PR #15" in implementation_plan
    assert "2161fbbf7fb4065a5913fb6e62c207546caf5dd9" in implementation_plan
    assert "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500" in implementation_plan
    assert "separate explicit product-owner authorization of PR-005" not in implementation_plan
    assert "PR-S001 does not create a production persistence API" in implementation_plan
    assert (
        "PR-006 remains blocked until PR-S001 is merged, reviewed and human accepted"
        not in implementation_plan
    )
    assert "PR-006 remains blocked" not in implementation_plan
    assert "PR-006 and later tasks remain UNAUTHORIZED" in implementation_plan
    assert "PR-006 remains subject to a separate exact task review" in implementation_plan
    assert "filesystem-storage implementation remains prohibited" in implementation_plan
    assert "PR-S001 does not create production filesystem storage" in implementation_plan


def test_q001_through_q020_statuses_other_than_q010_are_unchanged() -> None:
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")
    expected_statuses = {
        "Q-001": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-002": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-003": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-004": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-005": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-006": "DEFERRED",
        "Q-007": "DEFERRED",
        "Q-008": "ACCEPTED",
        "Q-009": "DEFERRED",
        "Q-010": "ACCEPTED",
        "Q-011": "DEFERRED",
        "Q-012": "LOCAL_EVIDENCE_REQUIRED",
        "Q-013": "LOCAL_EVIDENCE_REQUIRED",
        "Q-014": "LOCAL_EVIDENCE_REQUIRED",
        "Q-015": "LOCAL_EVIDENCE_REQUIRED",
        "Q-016": "DEFERRED",
        "Q-017": "DEFERRED",
        "Q-018": "DEFERRED",
        "Q-019": "SUPERSEDED",
        "Q-020": "DEFERRED",
    }
    for question_id, expected_status in expected_statuses.items():
        assert _question_status(_question_section(open_questions, question_id)) == expected_status


def test_open_questions_q001_through_q020_remain_present_with_valid_statuses() -> None:
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")

    expected_statuses = {
        "Q-001": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-002": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-003": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-004": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-005": "EXTERNAL_CONFIRMATION_REQUIRED",
        "Q-006": "DEFERRED",
        "Q-007": "DEFERRED",
        "Q-008": "ACCEPTED",
        "Q-009": "DEFERRED",
        "Q-010": "ACCEPTED",
        "Q-011": "DEFERRED",
        "Q-012": "LOCAL_EVIDENCE_REQUIRED",
        "Q-013": "LOCAL_EVIDENCE_REQUIRED",
        "Q-014": "LOCAL_EVIDENCE_REQUIRED",
        "Q-015": "LOCAL_EVIDENCE_REQUIRED",
        "Q-016": "DEFERRED",
        "Q-017": "DEFERRED",
        "Q-018": "DEFERRED",
        "Q-019": "SUPERSEDED",
        "Q-020": "DEFERRED",
    }
    valid_statuses = {
        "OPEN",
        "ACCEPTED",
        "DEFERRED",
        "EXTERNAL_CONFIRMATION_REQUIRED",
        "LOCAL_EVIDENCE_REQUIRED",
        "SUPERSEDED",
    }

    for question_id, expected_status in expected_statuses.items():
        section = _question_section(open_questions, question_id)
        statuses = re.findall(r"^\*\*Status:\*\* ([A-Z_]+)$", section, flags=re.MULTILINE)
        assert statuses == [expected_status], f"{question_id} has invalid statuses: {statuses}"
        assert statuses[0] in valid_statuses


def test_open_question_status_metadata_is_complete() -> None:
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")

    external_questions = {"Q-001", "Q-002", "Q-003", "Q-004", "Q-005"}
    local_evidence_questions = {"Q-012", "Q-013", "Q-014", "Q-015"}
    deferred_questions = {
        "Q-006",
        "Q-007",
        "Q-009",
        "Q-011",
        "Q-016",
        "Q-017",
        "Q-018",
        "Q-020",
    }

    for question_id in external_questions:
        section = _question_section(open_questions, question_id)
        assert _question_status(section) == "EXTERNAL_CONFIRMATION_REQUIRED"
        assert "**Required evidence:**" in section
        assert "**Owner:**" in section
        assert "**Target:**" in section
        assert "**Implementation block:**" in section
        assert "**Placeholder rule:**" in section

    for question_id in local_evidence_questions:
        section = _question_section(open_questions, question_id)
        assert _question_status(section) == "LOCAL_EVIDENCE_REQUIRED"
        assert "**Required evidence:**" in section
        assert "**Target:**" in section
        assert "outside Git, Codex and CI" in section or "remains local" in section

    for question_id in deferred_questions:
        section = _question_section(open_questions, question_id)
        assert _question_status(section) == "DEFERRED"
        assert "**Target:**" in section


def test_gate_m0_specific_question_requirements_are_recorded() -> None:
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    technical_spec = (REPO_ROOT / "docs/technical-specification.md").read_text(encoding="utf-8")
    architecture = (REPO_ROOT / "docs/architecture.md").read_text(encoding="utf-8")

    q008 = _question_section(open_questions, "Q-008")
    q010 = _question_section(open_questions, "Q-010")
    q019 = _question_section(open_questions, "Q-019")

    assert _question_status(q008) == "ACCEPTED"
    assert "**Decision reference:** ADR-017" in q008
    assert "one Windows 11 x64 workstation with one active operator session" in q008
    assert "one Windows 11 x64 workstation with one active operator session" in decisions
    assert "one Windows 11 x64 workstation with one active operator session" in architecture

    assert _question_status(q010) == "ACCEPTED"
    assert "**Decision reference:** ADR-018" in q010
    assert "PR-005 and PR-006 authorization remain blocked" in q010
    assert "This acceptance does not implement encryption" in decisions

    assert _question_status(q019) == "SUPERSEDED"
    assert "ADR-002 and NFR-02" in q019
    assert "Windows 11 x64 is first" in q019
    assert "macOS initial-release question superseded by ADR-002 and NFR-02" in technical_spec


def test_terminal_staging_rule_prevents_placeholder_values() -> None:
    task = (REPO_ROOT / "docs/tasks/GATE-M0-requirements-lock.md").read_text(encoding="utf-8")
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")

    assert "no placeholder terminal value is invented" in task
    for question_id in ["Q-001", "Q-002", "Q-003", "Q-004", "Q-005"]:
        section = _question_section(open_questions, question_id)
        assert "**Placeholder rule:**" in section


def test_adr_014_is_partially_superseded_for_approved_templates_only() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    adr_014 = _adr_section(decisions, "## ADR-014 — Temporary public repository during bootstrap")

    assert "**Status:** ACCEPTED" in adr_014
    assert "**Partially superseded by:** ADR-016 for the three product-owner-approved" in adr_014
    assert "PII-free technical derivatives" in adr_014
    assert "ADR-014 remains fully active for real documents" in adr_014
    assert "personal data" in adr_014
    assert "real databases and journals" in adr_014
    assert "real exports" in adr_014
    assert "operational logs" in adr_014
    assert "backups" in adr_014
    assert "OCR and MRZ payloads from real documents" in adr_014
    assert "private acceptance datasets" in adr_014
    assert "secrets and credentials" in adr_014
    assert "categorically prohibits the three approved terminal templates" in adr_014
    assert "## ADR-014 — Temporary public repository during bootstrap" in adr_014
    assert "**Status:** SUPERSEDED" not in adr_014


def test_adr_016_records_approved_template_artifacts() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    adr_016 = _adr_section(
        decisions, "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization"
    )

    compact_adr_016 = _compact(adr_016)
    for template in ("TSPMAINFILE.xls", "visitors_example.xlsx", "MGSMAINFILE.xlsx"):
        assert template in compact_adr_016
    assert "approved terminal artifacts" in compact_adr_016.lower()
    assert "cleaned copies" in compact_adr_016
    assert "anonymized copies" in compact_adr_016
    assert "empty structural copies" in compact_adr_016
    assert "binary golden files" in compact_adr_016
    assert "synthetic output workbooks" in compact_adr_016
    assert "screenshots showing template structure" in compact_adr_016
    assert "real template checksum values" in compact_adr_016
    assert "extracted structural manifests" in compact_adr_016
    assert "machine-generated mappings" in compact_adr_016
    assert "manually maintained mappings" in compact_adr_016
    assert "workbook structural metadata" in compact_adr_016
    assert "sheet names and order" in compact_adr_016
    assert "exact headers" in compact_adr_016
    assert "comments" in compact_adr_016
    assert "validations" in compact_adr_016
    assert "named ranges" in compact_adr_016
    assert "tables and ranges" in compact_adr_016
    assert "styles" in compact_adr_016
    assert "merged-cell definitions" in compact_adr_016
    assert "external-connection metadata" in compact_adr_016
    assert "No separate product-owner decision is required" in compact_adr_016


def test_adr_016_records_content_based_template_restrictions() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    adr_016 = _adr_section(
        decisions, "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization"
    )

    compact_adr_016 = _compact(adr_016)
    assert "Template origin or binary format does not make a file prohibited" in compact_adr_016
    for prohibited in (
        "real driver or visitor records",
        "real application rows",
        "real names",
        "real dates of birth",
        "real passport",
        "real phone numbers",
        "real registration addresses",
        "real VINs",
        "real vehicle or trailer registration",
        "photographs or scans of real documents",
        "OCR output from real documents",
        "MRZ payloads from real documents",
        "authentication credentials",
        "passwords",
        "API tokens",
        "private keys",
        "confidential connection strings",
        "confidential local or network paths",
    ):
        assert prohibited in compact_adr_016
    assert (
        "Golden files generated from a real application or real participant data remain prohibited"
        in compact_adr_016
    )
    assert "Screenshots containing real personal data remain prohibited" in compact_adr_016
    assert "no real personal or operational records" in compact_adr_016


def test_adr_016_records_inspection_and_transitional_enforcement() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    task = (REPO_ROOT / "docs/tasks/GATE-M0-requirements-lock.md").read_text(encoding="utf-8")
    adr_016 = _adr_section(
        decisions, "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization"
    )

    for text in (adr_016, task):
        compact_text = _compact(text)
        for inspection_item in (
            "visible cells",
            "hidden sheets",
            "hidden rows and columns",
            "comments and notes",
            "workbook and document properties",
            "author and last-editor metadata",
            "custom properties",
            "defined names",
            "external links",
            "Power Query and workbook connections",
            "cached connection results",
            "embedded objects",
            "images",
            "macros",
            "local usernames",
            "local filesystem paths",
            "network paths",
            "credentials and connection strings",
        ):
            assert inspection_item in compact_text
        assert (
            "current scanner and `.gitignore` remain temporarily more restrictive" in compact_text
        )
        assert "separate repository-policy enforcement PR" in compact_text
        assert "does not block PR-004" in compact_text
        assert "No template artifact is added" in compact_text


def test_current_policy_documents_allow_approved_templates_without_weakening_pii_rules() -> None:
    current_policy_files = (
        "AGENTS.md",
        "README.md",
        "docs/security.md",
        "docs/testing-strategy.md",
        "docs/development-workflow.md",
        "docs/handoff.md",
        "docs/progress.md",
        "docs/technical-specification.md",
        "resources/templates/README.md",
    )
    for filename in current_policy_files:
        text = (REPO_ROOT / filename).read_text(encoding="utf-8")
        assert "ADR-016" in text, filename
        assert "PII" in text or "personal data" in text, filename
    resources_readme = (REPO_ROOT / "resources/templates/README.md").read_text(encoding="utf-8")
    assert "TSPMAINFILE.xls" in resources_readme
    assert "visitors_example.xlsx" in resources_readme
    assert "MGSMAINFILE.xlsx" in resources_readme
    assert "Do not add the actual Excel templates" in resources_readme


def test_fixture_policy_documents_use_transitional_rules() -> None:
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    security = (REPO_ROOT / "docs/security.md").read_text(encoding="utf-8")

    assert "Current enforcement state" in agents
    assert "Product-policy state after enforcement update" in agents
    assert "No Excel template or template-derived binary artifact may be committed yet" in agents
    assert "the three approved source templates may be tracked" in agents
    assert "PII-free binary golden files may be tracked" in agents
    assert "PII-free structural screenshots, manifests and mappings may be tracked" in agents
    assert "While the repository is public, allowed fixtures are limited to" not in agents

    forbidden_readme_sentence = (
        "Only synthetic/no-document source-code tests are allowed in this repository and CI."
    )
    assert forbidden_readme_sentence not in readme
    assert "Under the current scanner and `.gitignore` enforcement" in readme
    assert "committed test data remains limited to currently approved synthetic paths" in readme
    assert "After the separate repository-policy enforcement PR" in readme
    assert "binary golden files with fully fictional values" in readme
    assert "Real documents, real application data, PII and secrets remain prohibited" in readme

    assert "### Current scanner enforcement" in security
    assert "ordinary committed document/data fixtures are permitted only under" in security
    assert "tracked images are permitted only under the current synthetic-image path" in security
    assert "resources/templates/README.md` is the only tracked template-directory file" in security
    assert "### ADR-016 exception after enforcement update" in security
    assert "approved source templates may use explicitly approved template paths" in security
    assert "approved binary golden files and synthetic output workbooks" in security
    assert "PII-free structural template screenshots" in security
    assert "manifests and mappings may use explicitly approved metadata paths" in security
    assert "must define those exact template paths" in security
    assert "golden-file paths" in security
    assert "screenshot paths" in security
    assert "manifest/mapping paths" in security
    assert "Real document images remain prohibited" in security
    assert "Real application workbooks remain prohibited" in security
    assert "PII-bearing screenshots and golden files remain prohibited" in security
    assert "Secrets and credentials remain prohibited" in security


def test_adr_014_and_adr_016_contract_text_remains_present() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    adr_014 = _adr_section(decisions, "## ADR-014 — Temporary public repository during bootstrap")
    adr_016 = _adr_section(
        decisions, "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization"
    )

    assert "**Partially superseded by:** ADR-016 for the three product-owner-approved" in adr_014
    assert "ADR-014 remains fully active for real documents" in adr_014
    assert (
        "ADR-014 no longer categorically prohibits the three approved terminal templates" in adr_014
    )
    assert "`TSPMAINFILE.xls`, `visitors_example.xlsx` and `MGSMAINFILE.xlsx`" in adr_016
    assert "scanner and `.gitignore` remain temporarily more restrictive" in _compact(adr_016)
    assert "No template artifact is added by GATE-M0 / PR #5" in adr_016
    assert (
        "PR-005, PR-006, PR-007 and every later implementation task remain unauthorized"
        in _compact(adr_016)
    )


def test_pr_5_adds_no_template_or_template_derived_artifact() -> None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked_files = result.stdout.splitlines()
    forbidden_suffixes = (
        ".xls",
        ".xlsx",
        ".xlsm",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".gif",
        ".tif",
        ".tiff",
        ".json",
    )
    artifacts = [
        path
        for path in tracked_files
        if path.startswith("resources/templates/") and path != "resources/templates/README.md"
    ]
    binary_or_manifest_artifacts = [
        path for path in artifacts if Path(path).suffix.lower() in forbidden_suffixes
    ]
    assert not artifacts
    assert not binary_or_manifest_artifacts


def test_open_questions_q001_through_q020_remain_present() -> None:
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")

    missing = []
    for question_number in range(1, 21):
        heading = f"### Q-{question_number:03d}"
        if heading not in open_questions:
            missing.append(heading)

    assert not missing, "Missing open-question headings: " + ", ".join(missing)


def test_pr_s001_d1_acceptance_decision_document() -> None:
    decision = REPO_ROOT / "docs/decisions/PR-S001-D1-encryption-feasibility-acceptance.md"
    assert decision.exists()
    text = decision.read_text(encoding="utf-8")
    for required in (
        "## Status",
        "ACCEPTED",
        "## Decision owner",
        "Product owner",
        "Accept PR-S001 feasibility with residual risk RISK-S001-W11",
        "An actual Windows 11 x64 execution was not performed by product-owner decision.",
        "ACCEPTED BY PRODUCT OWNER",
        "Windows 11 x64 remains the first production platform",
        "Windows 11 x64 remains NOT_DEMONSTRATED",
        (
            "Windows 11 x64 verification is mandatory before installer, "
            "pilot or production-release acceptance."
        ),
        "Gate 1 remains NOT ACCEPTED",
        "M2 remains NOT COMPLETED",
        "final SQLCipher package/edition",
        "final production key API",
        "final key hierarchy",
        "final encrypted-object format",
        "backup/recovery design",
        "installer design",
        "licensing/redistribution disposition",
        "PR-006: UNAUTHORIZED",
        "PR-007 AND LATER: UNAUTHORIZED",
    ):
        assert required in text
    for forbidden in (
        "report JSON",
        "host identifiers",
        "paths, SIDs",
        "wheel binaries",
        "DPAPI blobs",
        "raw logs",
    ):
        assert forbidden in text


def test_pr_s001_spike_documentation_and_scope() -> None:
    task_doc = REPO_ROOT / "docs/tasks/PR-S001-windows-encryption-feasibility.md"
    assert task_doc.exists()
    assert "edc895ffaf26f496bd8f60dbcbb87f3d5cfb09f4" in task_doc.read_text(encoding="utf-8")
    report = (REPO_ROOT / "docs/research/PR-S001-windows-encryption-feasibility.md").read_text(
        encoding="utf-8"
    )
    assert "CONDITIONALLY FEASIBLE" in report
    assert "does not select a final production package" in report
    assert "coordinated rollback" in report and "not claimed as detected" in report
    assert "Technical" in report or "Technical".lower() in report.lower()
    assert "Security" in report or "security" in report.lower()
    assert "Packaging" in report or "packaging" in report.lower()
    assert "Licensing" in report or "licensing" in report.lower()
    stale_research_phrases = (
        "Status: CI run #42 results",
        "Windows runtime probes: NOT EXECUTED",
        "DPAPI cross-runner: NOT EXECUTED",
        "No Ubuntu or Windows CI has executed since the last harness correction",
        "NOT_DEMONSTRATED until Windows CI executes",
    )
    for stale_phrase in stale_research_phrases:
        assert stale_phrase not in report
    for required_phrase in (
        "CI #57",
        "Windows Server 2025 AMD64",
        "CONDITIONALLY FEASIBLE",
        "Windows 11 x64: NOT_DEMONSTRATED",
        "RISK-PR005-RAWKEY-PRAGMA",
        "PR-006: UNAUTHORIZED",
    ):
        assert required_phrase in report
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_block = pyproject.split("[project.scripts]", maxsplit=1)[0]
    assert (
        "sqlcipher3==0.6.2; sys_platform == 'win32' and platform_machine == 'AMD64'"
        in project_block
    )
    assert "cryptography" not in project_block
    assert "encryption-spike" in pyproject
    progress = (REPO_ROOT / "docs/progress.md").read_text(encoding="utf-8")
    assert "PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11" in progress
    assert "PR-S001-F1, PR-S001-F2 and PR-S001-F3: COMPLETED" in progress
    assert "PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13" in progress
    assert "985fae37c7645e8f65edbe4d1609100ee24a2097" in progress
    lifecycle_files = [
        "docs/progress.md",
        "docs/handoff.md",
        "docs/roadmap.md",
        "docs/implementation-plan.md",
        "docs/traceability-matrix.md",
    ]
    for lifecycle in lifecycle_files:
        text = (REPO_ROOT / lifecycle).read_text(encoding="utf-8")
        assert "PR-005: COMPLETED AND HUMAN ACCEPTED" in text
        assert "PR-006: UNAUTHORIZED" in text
        assert "PR-005 has not started" not in text
        assert "PR-005: IN REVIEW, NOT ACCEPTED" not in text
