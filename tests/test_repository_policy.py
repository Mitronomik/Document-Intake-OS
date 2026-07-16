"""Repository policy scanner tests for PR-003."""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_POLICY_PATH = REPO_ROOT / "scripts" / "check_repository_policy.py"
_POLICY_SPEC = importlib.util.spec_from_file_location("check_repository_policy", _POLICY_PATH)
assert _POLICY_SPEC is not None
assert _POLICY_SPEC.loader is not None
policy = importlib.util.module_from_spec(_POLICY_SPEC)
sys.modules[_POLICY_SPEC.name] = policy
_POLICY_SPEC.loader.exec_module(policy)


def _write(root: Path, repo_path: str, content: bytes | str = "safe text\n") -> None:
    target = root.joinpath(*repo_path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        target.write_text(content, encoding="utf-8")
    else:
        target.write_bytes(content)


def _scan(root: Path, paths: list[str]) -> list[policy.Violation]:
    return policy.scan_repository(policy.ScannerConfig(root=root, paths=tuple(paths)))


def _rules(violations: list[policy.Violation]) -> set[str]:
    return {violation.rule_id for violation in violations}


def test_current_repository_passes_policy() -> None:
    violations = policy.scan_current_repository(REPO_ROOT)
    assert violations == []


def test_forbidden_root_path_rejects_real_documents(tmp_path: Path) -> None:
    _write(tmp_path, "real-documents/passport.jpg", b"not a real document")
    violations = _scan(tmp_path, ["real-documents/passport.jpg"])
    assert policy.PATH_FORBIDDEN_ROOT in _rules(violations)


def test_application_storage_package_is_not_root_runtime_storage(tmp_path: Path) -> None:
    path = "src/document_intake/storage/__init__.py"
    _write(tmp_path, path)
    violations = _scan(tmp_path, [path])
    assert policy.PATH_FORBIDDEN_ROOT not in _rules(violations)


def test_terminal_workbook_path_is_rejected(tmp_path: Path) -> None:
    path = "resources/templates/terminal.xlsx"
    _write(tmp_path, path, b"temporary workbook bytes")
    violations = _scan(tmp_path, [path])
    assert policy.PATH_TERMINAL_TEMPLATE in _rules(violations)
    assert policy.EXT_FORBIDDEN in _rules(violations)


def test_resources_templates_exact_policy_marker_exception(tmp_path: Path) -> None:
    allowed = "resources/templates/README.md"
    rejected = [
        "resources/templates/terminal.xlsx",
        "resources/templates/.gitkeep",
        "resources/templates/subdirectory/README.md",
        "resources/templates/template-checksums.sha256",
    ]
    _write(tmp_path, allowed, "Repository policy marker only.\n")
    for path in rejected:
        _write(tmp_path, path)

    allowed_violations = _scan(tmp_path, [allowed])
    assert policy.PATH_TERMINAL_TEMPLATE not in _rules(allowed_violations)

    for path in rejected:
        violations = _scan(tmp_path, [path])
        assert policy.PATH_TERMINAL_TEMPLATE in _rules(violations)


def test_private_fixture_path_rejected_and_synthetic_text_allowed(tmp_path: Path) -> None:
    private_path = "tests/fixtures/private/example.txt"
    synthetic_path = "tests/fixtures/synthetic/example.txt"
    _write(tmp_path, private_path)
    _write(tmp_path, synthetic_path)

    private_violations = _scan(tmp_path, [private_path])
    synthetic_violations = _scan(tmp_path, [synthetic_path])

    assert policy.PATH_FIXTURE_LOCATION in _rules(private_violations)
    assert synthetic_violations == []


def test_image_location_policy(tmp_path: Path) -> None:
    outside = "docs/example.png"
    inside = "tests/fixtures/synthetic/example.png"
    _write(tmp_path, outside, b"image-like bytes")
    _write(tmp_path, inside, b"image-like bytes")

    outside_violations = _scan(tmp_path, [outside])
    inside_violations = _scan(tmp_path, [inside])

    assert policy.IMAGE_LOCATION in _rules(outside_violations)
    assert inside_violations == []


def test_oversized_synthetic_image_rejected(tmp_path: Path) -> None:
    path = "tests/fixtures/synthetic/large.jpg"
    _write(tmp_path, path, b"0" * (policy.MAX_SYNTHETIC_IMAGE_BYTES + 1))
    violations = _scan(tmp_path, [path])
    assert policy.IMAGE_SIZE in _rules(violations)


@pytest.mark.parametrize("repo_path", ["docs/file.pdf", "docs/file.docx", "docs/file.zip"])
def test_forbidden_document_and_archive_types(tmp_path: Path, repo_path: str) -> None:
    _write(tmp_path, repo_path, b"container")
    violations = _scan(tmp_path, [repo_path])
    assert policy.EXT_FORBIDDEN in _rules(violations)


@pytest.mark.parametrize("repo_path", [".env", ".env.local"])
def test_environment_files_rejected(tmp_path: Path, repo_path: str) -> None:
    _write(tmp_path, repo_path, "EXAMPLE=value\n")
    violations = _scan(tmp_path, [repo_path])
    assert policy.ENV_FORBIDDEN in _rules(violations)


def test_env_example_allowed_when_content_is_safe(tmp_path: Path) -> None:
    _write(tmp_path, ".env.example", "EXAMPLE=value\n")
    violations = _scan(tmp_path, [".env.example"])
    assert violations == []


def test_private_key_signature_detected_from_dynamic_value(tmp_path: Path) -> None:
    marker = "-" * 5 + "BEGIN " + "RSA " + "PRIVATE KEY" + "-" * 5
    path = "docs/key-marker.txt"
    _write(tmp_path, path, "prefix\n" + marker + "\n")
    violations = _scan(tmp_path, [path])
    assert policy.SECRET_PRIVATE_KEY in _rules(violations)


def _token(prefix: str, body_char: str, body_length: int) -> str:
    return prefix + (body_char * body_length)


@pytest.mark.parametrize(
    ("rule_id", "value"),
    [
        (policy.SECRET_AWS_ACCESS_KEY_ID, "AK" + "IA" + ("A" * 16)),
        (policy.SECRET_GITHUB_CLASSIC, "gh" + "p_" + ("A" * 36)),
        (policy.SECRET_GITHUB_FINE_GRAINED, "github" + "_pat_" + ("A" * 60)),
        (policy.SECRET_OPENAI, "sk" + "-" + ("A" * 40)),
        (policy.SECRET_GOOGLE_API_KEY, "AI" + "za" + ("A" * 35)),
        (policy.SECRET_SLACK, "xo" + "xb-" + ("A" * 20)),
        (policy.SECRET_STRIPE_LIVE, "sk" + "_live_" + ("A" * 24)),
    ],
)
def test_token_signatures_detected_from_dynamic_values(
    tmp_path: Path, rule_id: str, value: str
) -> None:
    path = f"docs/{rule_id.lower()}.txt"
    _write(tmp_path, path, "prefix " + value + " suffix\n")
    violations = _scan(tmp_path, [path])
    assert rule_id in _rules(violations)


def test_safe_diagnostics_exclude_secret_and_source_line(tmp_path: Path) -> None:
    secret = "gh" + "p_" + ("B" * 36)
    line = "surrounding " + secret + " text"
    path = "docs/token.txt"
    _write(tmp_path, path, line + "\n")
    violations = _scan(tmp_path, [path])
    output = policy.format_violations(violations)

    assert policy.SECRET_GITHUB_CLASSIC in output
    assert f"{path}:1" in output
    assert secret not in output
    assert line not in output
    assert "surrounding" not in output


def test_deterministic_ordering(tmp_path: Path) -> None:
    first = "b/.env"
    second = "a/file.zip"
    third = "a/.env"
    for path in [first, second, third]:
        _write(tmp_path, path, b"content")

    violations = _scan(tmp_path, [first, second, third])
    sort_keys = [(item.path, item.rule_id, item.line or 0) for item in violations]
    assert sort_keys == sorted(sort_keys)


def test_invalid_utf8_does_not_crash(tmp_path: Path) -> None:
    path = "docs/invalid.txt"
    _write(tmp_path, path, b"\xff\xfe\xfd")
    violations = _scan(tmp_path, [path])
    assert violations == []


def test_read_failure_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = "docs/unreadable.txt"
    _write(tmp_path, path)

    def fail_read_bytes(self: Path) -> bytes:
        if self.name == "unreadable.txt":
            raise OSError("simulated read failure")
        return b""

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)
    violations = _scan(tmp_path, [path])
    assert policy.FILE_READ_ERROR in _rules(violations)


def test_cli_reports_policy_failure_without_secret_value(tmp_path: Path) -> None:
    secret = "sk" + "-" + ("C" * 40)
    path = "secret.txt"
    _write(tmp_path, path, secret + "\n")
    repo = tmp_path
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", path], cwd=repo, check=True, capture_output=True)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/check_repository_policy.py")],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == policy.VIOLATIONS_EXIT
    assert policy.SECRET_OPENAI in result.stdout
    assert "secret.txt:1" in result.stdout
    assert secret not in result.stdout


def test_symlink_escape_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"outside-{tmp_path.name}.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = tmp_path / "linked.txt"
    try:
        link.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation is not available: {exc}")

    violations = _scan(tmp_path, ["linked.txt"])
    assert policy.PATH_SYMLINK_ESCAPE in _rules(violations)


def test_permission_style_unreadable_file_if_platform_enforces_it(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX permission-bit unreadable-file check is not portable on Windows")
    path = "docs/no-read.txt"
    _write(tmp_path, path)
    file_path = tmp_path / "docs" / "no-read.txt"
    original_mode = stat.S_IMODE(file_path.stat().st_mode)
    try:
        file_path.chmod(0)
        violations = _scan(tmp_path, [path])
    finally:
        file_path.chmod(original_mode)
    if os.geteuid() == 0:
        pytest.skip("running as root can still read chmod 000 files")
    assert policy.FILE_READ_ERROR in _rules(violations)
