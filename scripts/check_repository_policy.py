"""Tracked-file repository privacy and safety policy scanner."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

SUCCESS_EXIT: Final = 0
VIOLATIONS_EXIT: Final = 1
SCANNER_FAILURE_EXIT: Final = 2

MAX_SYNTHETIC_IMAGE_BYTES: Final = 1_992_294
TEXT_SAMPLE_BYTES: Final = 8192

PATH_FORBIDDEN_ROOT: Final = "PATH_FORBIDDEN_ROOT"
PATH_TERMINAL_TEMPLATE: Final = "PATH_TERMINAL_TEMPLATE"
PATH_FIXTURE_LOCATION: Final = "PATH_FIXTURE_LOCATION"
PATH_SYMLINK_ESCAPE: Final = "PATH_SYMLINK_ESCAPE"
PATH_OUTSIDE_REPOSITORY: Final = "PATH_OUTSIDE_REPOSITORY"
EXT_FORBIDDEN: Final = "EXT_FORBIDDEN"
ENV_FORBIDDEN: Final = "ENV_FORBIDDEN"
IMAGE_LOCATION: Final = "IMAGE_LOCATION"
IMAGE_SIZE: Final = "IMAGE_SIZE"
FILE_READ_ERROR: Final = "FILE_READ_ERROR"
SECRET_PRIVATE_KEY: Final = "SECRET_PRIVATE_KEY"
SECRET_AWS_ACCESS_KEY_ID: Final = "SECRET_AWS_ACCESS_KEY_ID"
SECRET_GITHUB_CLASSIC: Final = "SECRET_GITHUB_CLASSIC"
SECRET_GITHUB_FINE_GRAINED: Final = "SECRET_GITHUB_FINE_GRAINED"
SECRET_OPENAI: Final = "SECRET_OPENAI"
SECRET_GOOGLE_API_KEY: Final = "SECRET_GOOGLE_API_KEY"
SECRET_SLACK: Final = "SECRET_SLACK"
SECRET_STRIPE_LIVE: Final = "SECRET_STRIPE_LIVE"

FORBIDDEN_ROOT_PREFIXES: Final[tuple[str, ...]] = (
    "data/",
    "runtime/",
    "storage/",
    "database/",
    "backups/",
    "exports/",
    "logs/",
    "temp/",
    "tmp/",
    "source-documents/",
    "real-documents/",
    "personal-data/",
    "private-fixtures/",
    "local-acceptance/",
)

TERMINAL_TEMPLATE_PREFIX: Final = "resources/templates/"
TERMINAL_TEMPLATE_POLICY_MARKER: Final = "resources/templates/README.md"
FIXTURE_PREFIX: Final = "tests/fixtures/"
SYNTHETIC_FIXTURE_PREFIX: Final = "tests/fixtures/synthetic/"

FORBIDDEN_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".xls",
        ".xlsx",
        ".xlsm",
        ".xlsb",
        ".xlt",
        ".xltx",
        ".xltm",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".db-wal",
        ".db-shm",
        ".key",
        ".pem",
        ".pfx",
        ".p12",
        ".crt",
        ".cer",
        ".jks",
        ".keystore",
        ".pdf",
        ".doc",
        ".docx",
        ".odt",
        ".rtf",
        ".zip",
        ".7z",
        ".rar",
        ".tar",
        ".tgz",
        ".gz",
    }
)

IMAGE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif", ".tif", ".tiff"}
)

BINARY_EXTENSIONS: Final[frozenset[str]] = (
    FORBIDDEN_EXTENSIONS
    | IMAGE_EXTENSIONS
    | frozenset({".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".ico"})
)

TEMPORARY_OFFICE_PREFIX: Final = "~$"

_SECRET_PRIVATE_KEY_PATTERN: Final = re.compile(r"-{5}BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-{5}")
_SECRET_AWS_ACCESS_KEY_PATTERN: Final = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_SECRET_GITHUB_CLASSIC_PATTERN: Final = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b")
_SECRET_GITHUB_FINE_GRAINED_PATTERN: Final = re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")
_SECRET_OPENAI_PATTERN: Final = re.compile(r"\bsk-[A-Za-z0-9_-]{40,}\b")
_SECRET_GOOGLE_API_KEY_PATTERN: Final = re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")
_SECRET_SLACK_PATTERN: Final = re.compile(r"\bxox[bpars]-[A-Za-z0-9-]{20,}\b")
_SECRET_STRIPE_LIVE_PATTERN: Final = re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b")

SECRET_PATTERNS: Final[tuple[tuple[str, re.Pattern[str], str], ...]] = (
    (SECRET_PRIVATE_KEY, _SECRET_PRIVATE_KEY_PATTERN, "Private key marker detected"),
    (SECRET_AWS_ACCESS_KEY_ID, _SECRET_AWS_ACCESS_KEY_PATTERN, "AWS access-key ID detected"),
    (SECRET_GITHUB_CLASSIC, _SECRET_GITHUB_CLASSIC_PATTERN, "GitHub classic token detected"),
    (
        SECRET_GITHUB_FINE_GRAINED,
        _SECRET_GITHUB_FINE_GRAINED_PATTERN,
        "GitHub fine-grained token detected",
    ),
    (SECRET_OPENAI, _SECRET_OPENAI_PATTERN, "OpenAI-style key detected"),
    (SECRET_GOOGLE_API_KEY, _SECRET_GOOGLE_API_KEY_PATTERN, "Google API key detected"),
    (SECRET_SLACK, _SECRET_SLACK_PATTERN, "Slack token detected"),
    (SECRET_STRIPE_LIVE, _SECRET_STRIPE_LIVE_PATTERN, "Stripe live secret key detected"),
)


@dataclass(frozen=True, order=True)
class Violation:
    """A stable repository-policy violation."""

    path: str
    rule_id: str
    line: int | None
    message: str

    def format(self) -> str:
        """Format a violation without exposing file content or matched secrets."""
        location = self.path if self.line is None else f"{self.path}:{self.line}"
        return f"{self.rule_id} {location} {self.message}"


@dataclass(frozen=True)
class ScannerConfig:
    """Repository scanner configuration."""

    root: Path
    paths: tuple[str, ...]


def repository_root(start: Path | None = None) -> Path:
    """Resolve the Git repository root."""
    cwd = start or Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Unable to determine repository root with git rev-parse")
    return Path(result.stdout.strip()).resolve()


def tracked_files(root: Path) -> tuple[str, ...]:
    """Collect tracked paths from the Git index using NUL separation."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Unable to collect tracked files with git ls-files")
    return tuple(
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    )


def normalize_tracked_path(path: str) -> str | None:
    """Normalize a tracked path to a safe repository-relative POSIX path."""
    if not path or "\x00" in path:
        return None
    candidate = PurePosixPath(path.replace(os.sep, "/"))
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        return None
    return candidate.as_posix()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def path_for(root: Path, repo_path: str) -> Path:
    """Return the filesystem path for a normalized repository path."""
    return root.joinpath(*PurePosixPath(repo_path).parts)


def extension_for(repo_path: str) -> str:
    """Return a policy extension, including special compound database journal suffixes."""
    lower_path = repo_path.lower()
    for suffix in (".db-wal", ".db-shm"):
        if lower_path.endswith(suffix):
            return suffix
    return PurePosixPath(lower_path).suffix


def evaluate_path_policy(repo_path: str) -> list[Violation]:
    """Evaluate repository-relative path policy."""
    violations: list[Violation] = []
    if repo_path.startswith(FORBIDDEN_ROOT_PREFIXES):
        violations.append(
            Violation(
                repo_path,
                PATH_FORBIDDEN_ROOT,
                None,
                "Tracked file is under a forbidden repository-root path",
            )
        )
    if (
        repo_path.startswith(TERMINAL_TEMPLATE_PREFIX)
        and repo_path != TERMINAL_TEMPLATE_POLICY_MARKER
    ):
        violations.append(
            Violation(
                repo_path,
                PATH_TERMINAL_TEMPLATE,
                None,
                "Only resources/templates/README.md may be tracked under resources/templates",
            )
        )
    if repo_path.startswith(FIXTURE_PREFIX) and not repo_path.startswith(SYNTHETIC_FIXTURE_PREFIX):
        violations.append(
            Violation(
                repo_path,
                PATH_FIXTURE_LOCATION,
                None,
                "Tracked fixtures are permitted only under tests/fixtures/synthetic",
            )
        )
    return violations


def evaluate_extension_policy(repo_path: str) -> list[Violation]:
    """Evaluate forbidden extensions and temporary Office files."""
    file_name = PurePosixPath(repo_path).name
    if file_name.startswith(TEMPORARY_OFFICE_PREFIX):
        return [
            Violation(
                repo_path,
                EXT_FORBIDDEN,
                None,
                "Temporary Office files must not be tracked",
            )
        ]
    if extension_for(repo_path) in FORBIDDEN_EXTENSIONS:
        return [
            Violation(
                repo_path,
                EXT_FORBIDDEN,
                None,
                "Forbidden file type must not be tracked",
            )
        ]
    return []


def evaluate_environment_policy(repo_path: str) -> list[Violation]:
    """Evaluate environment-file policy."""
    file_name = PurePosixPath(repo_path).name
    if file_name == ".env" or (file_name.startswith(".env.") and file_name != ".env.example"):
        return [
            Violation(
                repo_path,
                ENV_FORBIDDEN,
                None,
                "Environment files are forbidden except .env.example",
            )
        ]
    return []


def evaluate_symlink_policy(root: Path, repo_path: str) -> list[Violation]:
    """Reject tracked symlinks that resolve outside the repository."""
    file_path = path_for(root, repo_path)
    if not file_path.is_symlink():
        return []
    try:
        resolved = file_path.resolve(strict=True)
    except OSError:
        return [
            Violation(
                repo_path,
                FILE_READ_ERROR,
                None,
                "Tracked symlink could not be resolved",
            )
        ]
    if not _is_relative_to(resolved, root):
        return [
            Violation(
                repo_path,
                PATH_SYMLINK_ESCAPE,
                None,
                "Tracked symlink resolves outside the repository",
            )
        ]
    return []


def evaluate_location_policy(root: Path, repo_path: str) -> list[Violation]:
    """Reject paths that are not files inside the repository root."""
    file_path = path_for(root, repo_path)
    try:
        parent = file_path.parent.resolve(strict=False)
    except OSError:
        return [
            Violation(repo_path, PATH_OUTSIDE_REPOSITORY, None, "Path cannot be resolved safely")
        ]
    if not _is_relative_to(parent, root):
        return [
            Violation(
                repo_path,
                PATH_OUTSIDE_REPOSITORY,
                None,
                "Tracked path is not inside the repository",
            )
        ]
    return []


def evaluate_image_policy(root: Path, repo_path: str) -> list[Violation]:
    """Evaluate tracked image location and size policy."""
    if extension_for(repo_path) not in IMAGE_EXTENSIONS:
        return []

    violations: list[Violation] = []
    if not repo_path.startswith(SYNTHETIC_FIXTURE_PREFIX):
        violations.append(
            Violation(
                repo_path,
                IMAGE_LOCATION,
                None,
                "Tracked images are permitted only under tests/fixtures/synthetic",
            )
        )
    try:
        size = path_for(root, repo_path).stat().st_size
    except OSError:
        violations.append(
            Violation(repo_path, FILE_READ_ERROR, None, "Tracked image metadata could not be read")
        )
    else:
        if repo_path.startswith(SYNTHETIC_FIXTURE_PREFIX) and size > MAX_SYNTHETIC_IMAGE_BYTES:
            violations.append(
                Violation(
                    repo_path,
                    IMAGE_SIZE,
                    None,
                    "Tracked synthetic image exceeds 1,992,294 bytes",
                )
            )
    return violations


def is_probably_text(root: Path, repo_path: str) -> bool:
    """Return whether a tracked file should be decoded and scanned as text."""
    if extension_for(repo_path) in BINARY_EXTENSIONS:
        return False
    file_path = path_for(root, repo_path)
    try:
        with file_path.open("rb") as stream:
            sample = stream.read(TEXT_SAMPLE_BYTES)
    except OSError:
        return True
    return b"\0" not in sample


def evaluate_secret_line(repo_path: str, line_number: int, line: str) -> list[Violation]:
    """Evaluate high-confidence secret signatures for a single text line."""
    violations: list[Violation] = []
    for rule_id, pattern, message in SECRET_PATTERNS:
        if pattern.search(line):
            violations.append(Violation(repo_path, rule_id, line_number, message))
    return violations


def evaluate_secret_file(root: Path, repo_path: str) -> list[Violation]:
    """Evaluate high-confidence secret signatures using bounded-memory text streaming."""
    file_path = path_for(root, repo_path)
    violations: list[Violation] = []
    try:
        with file_path.open("r", encoding="utf-8", errors="replace") as stream:
            for line_number, line in enumerate(stream, start=1):
                violations.extend(evaluate_secret_line(repo_path, line_number, line))
    except OSError:
        return [Violation(repo_path, FILE_READ_ERROR, None, "Tracked file could not be read")]
    return violations


def has_unsafe_filesystem_violation(violations: Iterable[Violation]) -> bool:
    """Return whether content and metadata inspection must stop for a path."""
    return any(
        violation.rule_id in {PATH_OUTSIDE_REPOSITORY, PATH_SYMLINK_ESCAPE, FILE_READ_ERROR}
        for violation in violations
    )


def evaluate_file(root: Path, raw_path: str) -> list[Violation]:
    """Evaluate all policy rules for one tracked path."""
    repo_path = normalize_tracked_path(raw_path)
    if repo_path is None:
        return [
            Violation(raw_path, PATH_OUTSIDE_REPOSITORY, None, "Tracked path is not normalized")
        ]

    violations: list[Violation] = []

    # Static checks only inspect the tracked path string and must still run even when
    # later filesystem safety checks reject the path.
    violations.extend(evaluate_path_policy(repo_path))
    violations.extend(evaluate_extension_policy(repo_path))
    violations.extend(evaluate_environment_policy(repo_path))

    filesystem_violations: list[Violation] = []
    filesystem_violations.extend(evaluate_location_policy(root, repo_path))
    filesystem_violations.extend(evaluate_symlink_policy(root, repo_path))
    violations.extend(filesystem_violations)

    if has_unsafe_filesystem_violation(filesystem_violations):
        return violations

    violations.extend(evaluate_image_policy(root, repo_path))

    if is_probably_text(root, repo_path):
        violations.extend(evaluate_secret_file(root, repo_path))

    return violations


def scan_repository(config: ScannerConfig) -> list[Violation]:
    """Scan configured tracked paths and return deterministically sorted violations."""
    violations: list[Violation] = []
    for raw_path in config.paths:
        violations.extend(evaluate_file(config.root, raw_path))
    return sorted(
        violations, key=lambda item: (item.path, item.rule_id, item.line or 0, item.message)
    )


def scan_current_repository(start: Path | None = None) -> list[Violation]:
    """Scan the current Git repository tracked file set."""
    root = repository_root(start)
    return scan_repository(ScannerConfig(root=root, paths=tracked_files(root)))


def format_violations(violations: Iterable[Violation]) -> str:
    """Format violations for CLI output."""
    return "\n".join(violation.format() for violation in violations)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    return argparse.ArgumentParser(description="Check tracked files against repository policy.")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the repository policy scanner."""
    parser = build_parser()
    parser.parse_args(argv)
    try:
        violations = scan_current_repository()
    except RuntimeError as exc:
        print(f"Repository policy scanner failed: {exc}", file=sys.stderr)
        return SCANNER_FAILURE_EXIT

    if violations:
        print("Repository policy violations found:")
        print(format_violations(violations))
        return VIOLATIONS_EXIT

    print("Repository policy check passed for tracked files.")
    return SUCCESS_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
