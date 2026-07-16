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


def test_lifecycle_state_is_current_and_not_closed() -> None:
    progress = (REPO_ROOT / "docs/progress.md").read_text(encoding="utf-8")
    handoff = (REPO_ROOT / "docs/handoff.md").read_text(encoding="utf-8")

    assert "PR-002 IN REVIEW" in progress
    assert "PR-002 COMPLETED" not in progress
    assert "PRE-IMPLEMENTATION" not in handoff

    forbidden_pr001_states = (
        "PR-001 is the current task",
        "PR-001 is current",
        "PR-001 is the next",
        "PR-001 Repository bootstrap:",
        "PR-001 remains under review",
        "PR-001 IN REVIEW",
        "PR-001 is incomplete",
        "PR-001 incomplete",
    )
    for forbidden_state in forbidden_pr001_states:
        assert forbidden_state not in handoff
        assert forbidden_state not in progress

    assert "PR-002 is the current repository-safety task" in handoff
    assert "M0 remains open" in progress
    assert "M0 remains open" in handoff
    assert "privacy gate remains open" in progress
    assert "privacy gate remain unresolved" in handoff
    assert "Formal M1 entry is not asserted" in handoff
    assert "Project phase: M1 Safe Repository" not in handoff
    assert "requires an explicit product-owner decision" in handoff
    assert "PR-003 must not begin before PR-002 acceptance" in handoff
    assert "that sequencing decision" in handoff
    assert "PR-003 must not start before PR-002 acceptance" in progress
    assert "explicit product-owner decision on M0/M1 lifecycle sequencing" in progress
    assert "permits repository-safety work to continue" in progress
    assert "after PR-002 acceptance and an explicit product-owner" in progress
    assert "only if that decision permits" in progress
    assert "after PR-002 acceptance, prepare PR-003" not in progress
    assert "M0/M1 lifecycle sequencing remains unresolved" in progress
    assert "M0 COMPLETED" not in progress
    assert "privacy gate closed" not in progress.lower()


def test_open_questions_q001_through_q020_remain_present() -> None:
    open_questions = (REPO_ROOT / "docs/open-questions.md").read_text(encoding="utf-8")

    missing = []
    for question_number in range(1, 21):
        heading = f"### Q-{question_number:03d}"
        if heading not in open_questions:
            missing.append(heading)

    assert not missing, "Missing open-question headings: " + ", ".join(missing)
