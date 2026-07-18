from __future__ import annotations

import json
import platform
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

WELL_KNOWN_SYSTEM = "S-1-5-18"
WELL_KNOWN_ADMINISTRATORS = "S-1-5-32-544"
WELL_KNOWN_USERS = "S-1-5-32-545"
WELL_KNOWN_AUTHENTICATED_USERS = "S-1-5-11"
WELL_KNOWN_EVERYONE = "S-1-1-0"

REQUIRED_FULL_CONTROL_SIDS = (WELL_KNOWN_SYSTEM, WELL_KNOWN_ADMINISTRATORS)
BROAD_WRITE_SIDS = (WELL_KNOWN_USERS, WELL_KNOWN_AUTHENTICATED_USERS, WELL_KNOWN_EVERYONE)


@dataclass(frozen=True)
class AclEvidence:
    current_user_rights: bool = False
    system_rights: bool = False
    administrators_rights: bool = False
    broad_write_blocked: bool = False


@dataclass(frozen=True)
class AclProbeResult:
    status: str
    current_user_rights: bool = False
    system_rights: bool = False
    administrators_rights: bool = False
    broad_write_blocked: bool = False
    broad_write_allowed: bool = False
    directory_removed: bool = False


def _ace_has_full_control(rights: str) -> bool:
    return "FullControl" in {part.strip() for part in rights.split(",")}


BROAD_WRITE_RIGHTS = frozenset(
    {
        "Write",
        "WriteData",
        "AppendData",
        "WriteAttributes",
        "WriteExtendedAttributes",
        "CreateFiles",
        "CreateDirectories",
        "Modify",
        "FullControl",
        "Delete",
        "DeleteSubdirectoriesAndFiles",
        "ChangePermissions",
        "TakeOwnership",
    }
)


def _ace_has_broad_write(rights: str) -> bool:
    parts = {part.strip() for part in rights.split(",")}
    return bool(parts & BROAD_WRITE_RIGHTS)


def _principal_has_allow_full_control(rules: dict[str, list[str]], sid: str) -> bool:
    return any(_ace_has_full_control(rights) for rights in rules.get(sid, ()))


def _principal_has_broad_write(rules: dict[str, list[str]], sid: str) -> bool:
    return any(_ace_has_broad_write(rights) for rights in rules.get(sid, ()))


def evaluate_acl_rules(rules: dict[str, list[str]], current_user_sid: str) -> AclEvidence:
    broad_write_allowed = any(_principal_has_broad_write(rules, sid) for sid in BROAD_WRITE_SIDS)
    return AclEvidence(
        current_user_rights=_principal_has_allow_full_control(rules, current_user_sid),
        system_rights=_principal_has_allow_full_control(rules, WELL_KNOWN_SYSTEM),
        administrators_rights=_principal_has_allow_full_control(rules, WELL_KNOWN_ADMINISTRATORS),
        broad_write_blocked=not broad_write_allowed,
    )


def acl_failure_reason(evidence: AclEvidence) -> str:
    if not evidence.current_user_rights:
        return "ERR_ACL_CURRENT_USER_RIGHTS"
    if not evidence.system_rights:
        return "ERR_ACL_SYSTEM_RIGHTS"
    if not evidence.administrators_rights:
        return "ERR_ACL_ADMINISTRATORS_RIGHTS"
    if not evidence.broad_write_blocked:
        return "ERR_ACL_BROAD_WRITE"
    return "PASS"


def _run_command(command: list[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def _current_user_sid() -> str:
    sid_raw = (
        _run_command(["whoami", "/user", "/fo", "csv", "/nh"]).split(",")[-1].strip().strip('"')
    )
    if not sid_raw.startswith("S-"):
        raise RuntimeError("ERR_CURRENT_USER_SID")
    return sid_raw


def _apply_acl(temp_root: Path, current_user_sid: str) -> None:
    commands = [
        ["icacls", str(temp_root), "/inheritance:r"],
        ["icacls", str(temp_root), "/grant:r", f"*{WELL_KNOWN_SYSTEM}:(OI)(CI)F"],
        ["icacls", str(temp_root), "/grant:r", f"*{WELL_KNOWN_ADMINISTRATORS}:(OI)(CI)F"],
        ["icacls", str(temp_root), "/grant:r", f"*{current_user_sid}:(OI)(CI)F"],
    ]
    for command in commands:
        _run_command(command)


def _normalized_acl_rules(temp_root: Path) -> dict[str, list[str]]:
    script = r"""
$acl = Get-Acl -LiteralPath $args[0]
$rules = $acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])
$rules | Where-Object { $_.AccessControlType -eq 'Allow' } | ForEach-Object {
    [PSCustomObject]@{ Sid = $_.IdentityReference.Value; Rights = $_.FileSystemRights.ToString() }
} | ConvertTo-Json -Compress
"""
    output = _run_command(["powershell", "-NoProfile", "-Command", script, str(temp_root)])

    if not output.strip():
        return {}
    data = json.loads(output)
    rows = data if isinstance(data, list) else [data]
    rules: dict[str, list[str]] = {}
    for row in rows:
        if (
            isinstance(row, dict)
            and isinstance(row.get("Sid"), str)
            and isinstance(row.get("Rights"), str)
        ):
            rules.setdefault(row["Sid"], []).append(row["Rights"])
    return rules


def _remove_directory(temp_root: Path, rmtree: Callable[[Path], None] = shutil.rmtree) -> bool:
    try:
        rmtree(temp_root)
    except OSError:
        return False
    return not temp_root.exists()


def run_acl_probe() -> AclProbeResult:
    temp_root = Path(tempfile.mkdtemp(prefix="pr-s001-acl-"))
    directory_removed = False
    try:
        if platform.system() != "Windows":
            directory_removed = _remove_directory(temp_root)
            return AclProbeResult("UNSUPPORTED_NON_WINDOWS", directory_removed=directory_removed)
        current_user_sid = _current_user_sid()
        _apply_acl(temp_root, current_user_sid)
        evidence = evaluate_acl_rules(_normalized_acl_rules(temp_root), current_user_sid)
        directory_removed = _remove_directory(temp_root)
        cleanup_status = "PASS" if directory_removed else "ERR_ACL_CLEANUP_FAILED"
        reason = acl_failure_reason(evidence)
        status = cleanup_status if reason == "PASS" else reason
        return AclProbeResult(
            status=status,
            current_user_rights=evidence.current_user_rights,
            system_rights=evidence.system_rights,
            administrators_rights=evidence.administrators_rights,
            broad_write_blocked=evidence.broad_write_blocked,
            broad_write_allowed=not evidence.broad_write_blocked,
            directory_removed=directory_removed,
        )
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError):
        if temp_root.exists():
            try:
                directory_removed = _remove_directory(temp_root)
            except OSError:
                directory_removed = False
        return AclProbeResult("ERR_ACL_PROBE_FAILED", directory_removed=directory_removed)
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)


def probe_directory_is_removed() -> bool:
    temp_root = Path(tempfile.mkdtemp(prefix="pr-s001-acl-removal-"))
    try:
        (temp_root / "test.txt").write_text("test", encoding="utf-8")
        return _remove_directory(temp_root)
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
