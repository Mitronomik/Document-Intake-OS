from pathlib import Path


def test_current_lifecycle_state_not_contradictory():
    text = Path("docs/progress.md").read_text(encoding="utf-8")
    assert "PR-008 — File import and duplicate detection is IMPLEMENTED AND IN REVIEW, NOT ACCEPTED" in text
    assert "codex/pr-008-file-import-duplicate-detection" not in text
