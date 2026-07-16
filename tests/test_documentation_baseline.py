"""Documentation-baseline contract tests for PR-002."""

from __future__ import annotations

import re
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


def test_lifecycle_state_records_gate_m0_review_state() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    progress = (REPO_ROOT / "docs/progress.md").read_text(encoding="utf-8")
    handoff = (REPO_ROOT / "docs/handoff.md").read_text(encoding="utf-8")
    roadmap = (REPO_ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
    implementation_plan = (REPO_ROOT / "docs/implementation-plan.md").read_text(encoding="utf-8")
    task = (REPO_ROOT / "docs/tasks/GATE-M0-requirements-lock.md").read_text(encoding="utf-8")
    combined_current = "\n".join([progress, handoff, roadmap, implementation_plan, task])
    adr_016 = _adr_section(
        decisions, "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization"
    )
    adr_017 = _adr_section(decisions, "## ADR-017 — MVP Workstation Topology")

    assert "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization" in adr_016
    assert "**Status:** ACCEPTED" in adr_016
    assert "**Date:** 2026-07-16" in adr_016
    assert "## ADR-017 — MVP Workstation Topology" in adr_017
    assert "**Status:** ACCEPTED" in adr_017
    assert "**Date:** 2026-07-16" in adr_017
    assert "PR-003 COMPLETED" in progress
    assert "ad5782045473d3ef5eb0a097cc8f6982bab821c7" in combined_current
    assert "M1 ACCEPTED" in progress
    assert "M0 DECISION APPROVED, NOT YET RECORDED IN MAIN" in progress
    assert "GATE-M0 IN REVIEW" in progress
    assert "PR-004 BLOCKED UNTIL GATE-M0 PR MERGE AND HUMAN ACCEPTANCE" in progress
    assert "Authorization is limited to PR-004 — Core Domain" in task
    assert "PR-005 and PR-006 remain entirely unauthorized" in task
    assert "PR-005 and PR-006 remain blocked" in roadmap
    assert "SENSITIVE-DATA / PRIVATE-CONTOUR GATE — OPEN" in progress
    assert "REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE" in progress
    assert "PR-004 implementation is not started" in progress
    assert "PR-004 is not started" not in combined_current
    assert "privacy gate closed" not in combined_current.lower()
    assert "PR-004 IN PROGRESS" not in combined_current
    assert "PR-005: AUTHORIZED" not in combined_current
    assert "PR-006: AUTHORIZED" not in combined_current


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


def _question_status(section: str) -> str:
    match = re.search(r"^\*\*Status:\*\* ([A-Z_]+)$", section, flags=re.MULTILINE)
    assert match is not None, "Question section is missing exactly formatted status"
    return match.group(1)


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
        "Q-010": "OPEN",
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
        assert "outside Git, Codex and CI" in section

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

    assert _question_status(q010) == "OPEN"
    assert "separate accepted security ADR" in q010
    assert "blocks PR-005 and PR-006" in q010
    assert "No encryption technology is selected" in decisions

    assert _question_status(q019) == "SUPERSEDED"
    assert "ADR-002 and NFR-02" in q019
    assert "Windows 11 x64 is first" in q019
    assert "macOS initial-release question superseded by ADR-002 and NFR-02" in (technical_spec)


def test_terminal_staging_rule_prevents_placeholder_values() -> None:
    task = (REPO_ROOT / "docs/tasks/GATE-M0-requirements-lock.md").read_text(encoding="utf-8")
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")

    assert "no placeholder terminal value is invented" in task
    for question_id in ["Q-001", "Q-002", "Q-003", "Q-004", "Q-005"]:
        section = _question_section(open_questions, question_id)
        assert "**Placeholder rule:**" in section


def test_adr_014_is_only_partially_superseded_by_template_policy() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    adr_014 = _adr_section(decisions, "## ADR-014 — Temporary public repository during bootstrap")

    assert "**Status:** ACCEPTED" in adr_014
    assert "**Partially superseded by:** ADR-016" in adr_014
    assert "approved non-sensitive terminal templates" in adr_014
    assert "This exception does not permit real documents" in adr_014
    assert "any personal data" in adr_014
    assert "PII, databases, database journals, logs, backups" in adr_014
    assert "OCR outputs, MRZ payloads" in adr_014
    assert "secrets, keys, passwords, certificates or tokens" in adr_014
    assert "unapproved terminal templates" in adr_014
    assert "## ADR-014 — Temporary public repository during bootstrap" in adr_014
    assert "SUPERSEDED" not in adr_014


def test_adr_016_records_template_artifact_policy_and_restrictions() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    adr_016 = _adr_section(
        decisions, "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization"
    )

    assert "three real terminal Excel templates" in adr_016
    assert "non-sensitive project contract files" in adr_016
    assert "do not contain personal data" in adr_016
    assert "do not contain real application rows" in adr_016
    assert "do not contain document images" in adr_016
    assert "private keys or secret tokens" in adr_016
    assert "cleaned or anonymized template copies" in adr_016
    assert "binary golden files" in adr_016
    assert "screenshots" in adr_016
    assert "checksums" in adr_016
    assert "manifests" in adr_016
    assert "machine-generated mappings" in adr_016
    assert "manually maintained mappings" in adr_016
    assert "structural metadata" in adr_016
    assert "synthetic output workbooks" in adr_016
    assert "workbook format, sheet names, headers, comments" in adr_016
    assert "validations, named ranges, tables, styles" in adr_016
    assert "merged cells, external connections" in adr_016
    assert "adapter mappings" in adr_016
    assert "No encryption technology is selected" in adr_016


def test_adr_016_template_artifacts_cannot_contain_personal_data_or_secrets() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    adr_016 = _adr_section(
        decisions, "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization"
    )

    assert "no permitted template artifact may contain real personal" in adr_016
    assert "real application records" in adr_016
    assert "real document images" in adr_016
    assert "OCR/MRZ payloads from real documents" in adr_016
    assert "secrets or credentials" in adr_016
    assert "Golden files produced from real application data remain prohibited" in adr_016
    assert "A mapping artifact must not contain real application data or secret values" in adr_016
    assert "Screenshots containing personal data remain prohibited" in adr_016
    assert "A manifest must not contain credentials, personal data" in adr_016


def test_adr_016_records_transitional_enforcement_before_template_artifacts() -> None:
    decisions = (REPO_ROOT / "docs/decisions.md").read_text(encoding="utf-8")
    task = (REPO_ROOT / "docs/tasks/GATE-M0-requirements-lock.md").read_text(encoding="utf-8")
    adr_016 = _adr_section(
        decisions, "## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization"
    )

    for text in (adr_016, task):
        assert "current repository scanner and `.gitignore` remain intentionally more" in text
        assert "separate repository-policy implementation PR" in text
        assert "scripts/check_repository_policy.py" in text
        assert "tests/test_repository_policy.py" in text
        assert "resources/templates/README.md" in text
        assert "docs/security.md" in text
        assert "docs/testing-strategy.md" in text
        assert "docs/development-workflow.md" in text
        assert "The future enforcement PR does not block PR-004" in text
        assert "No template artifact is added by GATE-M0" in text


def test_pr_5_adds_no_template_or_template_derived_binary_artifact() -> None:
    tracked_files = set(subprocess_run_git_ls_files())
    forbidden_suffixes = {
        ".xls",
        ".xlsx",
        ".xlsm",
        ".xlsb",
        ".xlt",
        ".xltx",
        ".xltm",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".gif",
        ".tif",
        ".tiff",
    }

    template_paths = [path for path in tracked_files if path.startswith("resources/templates/")]
    assert template_paths == ["resources/templates/README.md"]
    binary_artifacts = [
        path for path in tracked_files if Path(path).suffix.lower() in forbidden_suffixes
    ]
    assert not binary_artifacts, "Unexpected tracked template/binary artifacts: " + ", ".join(
        sorted(binary_artifacts)
    )


def subprocess_run_git_ls_files() -> list[str]:
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def test_open_questions_q001_through_q020_remain_present() -> None:
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")

    missing = []
    for question_number in range(1, 21):
        heading = f"### Q-{question_number:03d}"
        if heading not in open_questions:
            missing.append(heading)

    assert not missing, "Missing open-question headings: " + ", ".join(missing)
