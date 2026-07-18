from __future__ import annotations

import base64
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WELL_KNOWN_SYSTEM = "S-1-5-18"
WELL_KNOWN_ADMINISTRATORS = "S-1-5-32-544"
WELL_KNOWN_USERS = "S-1-5-32-545"
WELL_KNOWN_AUTHENTICATED_USERS = "S-1-5-11"
WELL_KNOWN_EVERYONE = "S-1-1-0"

REQUIRED_FULL_CONTROL_SIDS = (WELL_KNOWN_SYSTEM, WELL_KNOWN_ADMINISTRATORS)
BROAD_WRITE_SIDS = (WELL_KNOWN_USERS, WELL_KNOWN_AUTHENTICATED_USERS, WELL_KNOWN_EVERYONE)

ACL_STAGE_CURRENT_USER_SID = "acl-stage-current-user-sid"
ACL_STAGE_APPLY = "acl-stage-apply"
ACL_STAGE_READ = "acl-stage-read"
ACL_STAGE_NORMALIZE_TO_SID = "acl-stage-normalize-to-sid"
ACL_STAGE_JSON_SERIALIZE = "acl-stage-json-serialize"
ACL_STAGE_JSON_PARSE = "acl-stage-json-parse"
ACL_DIRECTORY_CLEANUP = "acl-directory-cleanup"
ACL_OPERATIONAL_STAGES = (
    ACL_STAGE_CURRENT_USER_SID,
    ACL_STAGE_APPLY,
    ACL_STAGE_READ,
    ACL_STAGE_NORMALIZE_TO_SID,
    ACL_STAGE_JSON_SERIALIZE,
    ACL_STAGE_JSON_PARSE,
)
ACL_STAGES = (*ACL_OPERATIONAL_STAGES, ACL_DIRECTORY_CLEANUP)

_SID_PATTERN = re.compile(r"^S-(?:\d+-)+\d+$")


@dataclass(frozen=True)
class AclEvidence:
    current_user_rights: bool = False
    system_rights: bool = False
    administrators_rights: bool = False
    broad_write_blocked: bool = False


@dataclass(frozen=True)
class AclStageResult:
    identifier: str
    status: str
    reason_code: str


@dataclass(frozen=True)
class AclProbeResult:
    status: str
    current_user_rights: bool = False
    system_rights: bool = False
    administrators_rights: bool = False
    broad_write_blocked: bool = False
    broad_write_allowed: bool = False
    directory_removed: bool = False
    stages: tuple[AclStageResult, ...] = ()
    rights_evaluated: bool = False


@dataclass(frozen=True)
class _AclStageFailure(Exception):
    stage: str
    reason_code: str


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


def _principal_has_allow_full_control(rules: Mapping[str, Sequence[str]], sid: str) -> bool:
    return any(_ace_has_full_control(rights) for rights in rules.get(sid, ()))


def _principal_has_broad_write(rules: Mapping[str, Sequence[str]], sid: str) -> bool:
    return any(_ace_has_broad_write(rights) for rights in rules.get(sid, ()))


def evaluate_acl_rules(rules: Mapping[str, Sequence[str]], current_user_sid: str) -> AclEvidence:
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


def _encoded_powershell_command(script: str) -> list[str]:
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-EncodedCommand",
        encoded,
    ]


def _run_powershell(script: str, env: Mapping[str, str] | None = None) -> str:
    child_env = None if env is None else {**os.environ, **env}
    try:
        return subprocess.run(
            _encoded_powershell_command(script),
            check=True,
            capture_output=True,
            text=True,
            env=child_env,
        ).stdout
    except FileNotFoundError as exc:
        raise _AclStageFailure(ACL_STAGE_READ, "ERR_ACL_POWERSHELL_LAUNCH") from exc


def _clean_output(output: str) -> str:
    return output.lstrip("\ufeff").strip()


def _current_user_sid() -> str:
    script = "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value"
    try:
        sid_raw = _clean_output(_run_powershell(script))
    except (OSError, subprocess.CalledProcessError, _AclStageFailure) as exc:
        raise _AclStageFailure(ACL_STAGE_CURRENT_USER_SID, "ERR_ACL_SID_LOOKUP") from exc
    if "\n" in sid_raw or "\r" in sid_raw or not _SID_PATTERN.fullmatch(sid_raw):
        raise _AclStageFailure(ACL_STAGE_CURRENT_USER_SID, "ERR_ACL_SID_LOOKUP")
    return sid_raw


def _run_icacls(command: list[str], reason_code: str) -> None:
    try:
        _run_command(command)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise _AclStageFailure(ACL_STAGE_APPLY, reason_code) from exc


def _apply_acl(temp_root: Path, current_user_sid: str) -> None:
    _run_icacls(["icacls", str(temp_root), "/inheritance:r"], "ERR_ACL_APPLY_INHERITANCE")
    _run_icacls(
        ["icacls", str(temp_root), "/grant:r", f"*{WELL_KNOWN_SYSTEM}:(OI)(CI)F"],
        "ERR_ACL_APPLY_SYSTEM",
    )
    _run_icacls(
        ["icacls", str(temp_root), "/grant:r", f"*{WELL_KNOWN_ADMINISTRATORS}:(OI)(CI)F"],
        "ERR_ACL_APPLY_ADMINISTRATORS",
    )
    _run_icacls(
        ["icacls", str(temp_root), "/grant:r", f"*{current_user_sid}:(OI)(CI)F"],
        "ERR_ACL_APPLY_CURRENT_USER",
    )


def _acl_inspection_script() -> str:
    return r"""
$target = $env:PR_S001_ACL_TARGET
try { $acl = Get-Acl -LiteralPath $target } catch { '{"ok":false,"stage":"read"}'; exit 0 }
try {
  $rules = $acl.GetAccessRules($true, $false, [System.Security.Principal.SecurityIdentifier])
  $rows = @($rules | Where-Object { $_.AccessControlType -eq 'Allow' } | ForEach-Object {
    [PSCustomObject]@{ sid = $_.IdentityReference.Value; rights = $_.FileSystemRights.ToString() }
  })
} catch { '{"ok":false,"stage":"normalize"}'; exit 0 }
try {
  @{ ok = $true; stage = 'complete'; rules = $rows } | ConvertTo-Json -Compress -Depth 4
} catch { '{"ok":false,"stage":"serialize"}'; exit 0 }
"""


def _normalize_rule_rows(data: Any) -> dict[str, list[str]]:
    if not isinstance(data, dict) or data.get("ok") is not True or data.get("stage") != "complete":
        raise _AclStageFailure(ACL_STAGE_JSON_PARSE, "ERR_ACL_RESULT_SHAPE")
    raw_rules = data.get("rules")
    rows = [] if raw_rules is None else (raw_rules if isinstance(raw_rules, list) else [raw_rules])
    if not isinstance(rows, list):
        raise _AclStageFailure(ACL_STAGE_JSON_PARSE, "ERR_ACL_RESULT_SHAPE")
    rules: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise _AclStageFailure(ACL_STAGE_JSON_PARSE, "ERR_ACL_RESULT_SHAPE")
        sid = row.get("sid")
        rights = row.get("rights")
        if (
            not isinstance(sid, str)
            or not isinstance(rights, str)
            or not _SID_PATTERN.fullmatch(sid)
        ):
            raise _AclStageFailure(ACL_STAGE_JSON_PARSE, "ERR_ACL_RESULT_SHAPE")
        rules.setdefault(sid, []).append(rights)
    return rules


def _rules_from_acl_envelope(output: str) -> dict[str, list[str]]:
    try:
        data = json.loads(_clean_output(output))
    except json.JSONDecodeError as exc:
        raise _AclStageFailure(ACL_STAGE_JSON_PARSE, "ERR_ACL_JSON_PARSE") from exc
    if isinstance(data, dict) and data.get("ok") is False:
        stage = data.get("stage")
        if stage == "read":
            raise _AclStageFailure(ACL_STAGE_READ, "ERR_ACL_READ")
        if stage == "normalize":
            raise _AclStageFailure(ACL_STAGE_NORMALIZE_TO_SID, "ERR_ACL_NORMALIZE_TO_SID")
        if stage == "serialize":
            raise _AclStageFailure(ACL_STAGE_JSON_SERIALIZE, "ERR_ACL_JSON_SERIALIZE")
        raise _AclStageFailure(ACL_STAGE_JSON_PARSE, "ERR_ACL_RESULT_SHAPE")
    return _normalize_rule_rows(data)


def _normalized_acl_rules(temp_root: Path) -> dict[str, list[str]]:
    env = {"PR_S001_ACL_TARGET": str(temp_root)}
    try:
        output = _run_powershell(_acl_inspection_script(), env=env)
    except subprocess.CalledProcessError as exc:
        raise _AclStageFailure(ACL_STAGE_READ, "ERR_ACL_POWERSHELL_LAUNCH") from exc
    return _rules_from_acl_envelope(output)


def _remove_directory(temp_root: Path, rmtree: Callable[[Path], None] = shutil.rmtree) -> bool:
    try:
        rmtree(temp_root)
    except OSError:
        return False
    return not temp_root.exists()


def _stage_results(
    failed: _AclStageFailure | None, cleanup_removed: bool
) -> tuple[AclStageResult, ...]:
    results: list[AclStageResult] = []
    blocked = False
    for stage in ACL_OPERATIONAL_STAGES:
        if failed is not None and stage == failed.stage:
            results.append(AclStageResult(stage, "FAIL", failed.reason_code))
            blocked = True
        elif blocked or (
            failed is not None
            and ACL_OPERATIONAL_STAGES.index(stage) > ACL_OPERATIONAL_STAGES.index(failed.stage)
        ):
            results.append(AclStageResult(stage, "NOT_DEMONSTRATED", "NOT_DEMONSTRATED"))
        else:
            results.append(AclStageResult(stage, "PASS", "PASS"))
    results.append(
        AclStageResult(
            ACL_DIRECTORY_CLEANUP,
            "PASS" if cleanup_removed else "FAIL",
            "PASS" if cleanup_removed else "ERR_ACL_CLEANUP_FAILED",
        )
    )
    return tuple(results)


def _unsupported_stages(cleanup_removed: bool) -> tuple[AclStageResult, ...]:
    return tuple(
        [
            *(
                AclStageResult(stage, "UNSUPPORTED", "UNSUPPORTED_NON_WINDOWS")
                for stage in ACL_OPERATIONAL_STAGES
            ),
            AclStageResult(
                ACL_DIRECTORY_CLEANUP,
                "PASS" if cleanup_removed else "FAIL",
                "PASS" if cleanup_removed else "ERR_ACL_CLEANUP_FAILED",
            ),
        ]
    )


def run_acl_probe() -> AclProbeResult:
    temp_root = Path(tempfile.mkdtemp(prefix="pr-s001-acl-"))
    directory_removed = False
    failed: _AclStageFailure | None = None
    evidence = AclEvidence()
    rights_evaluated = False
    try:
        if platform.system() != "Windows":
            return AclProbeResult("UNSUPPORTED_NON_WINDOWS")
        current_user_sid = _current_user_sid()
        _apply_acl(temp_root, current_user_sid)
        rules = _normalized_acl_rules(temp_root)
        evidence = evaluate_acl_rules(rules, current_user_sid)
        rights_evaluated = True
    except _AclStageFailure as exc:
        failed = exc
    except Exception:
        failed = _AclStageFailure(ACL_STAGE_CURRENT_USER_SID, "ERR_ACL_UNEXPECTED")
    finally:
        if temp_root.exists():
            directory_removed = _remove_directory(temp_root)
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
    if platform.system() != "Windows":
        return AclProbeResult(
            "UNSUPPORTED_NON_WINDOWS",
            directory_removed=directory_removed,
            stages=_unsupported_stages(directory_removed),
        )
    stages = _stage_results(failed, directory_removed)
    if failed is not None:
        return AclProbeResult(
            failed.reason_code, directory_removed=directory_removed, stages=stages
        )
    reason = acl_failure_reason(evidence)
    status = "ERR_ACL_CLEANUP_FAILED" if reason == "PASS" and not directory_removed else reason
    return AclProbeResult(
        status=status,
        current_user_rights=evidence.current_user_rights,
        system_rights=evidence.system_rights,
        administrators_rights=evidence.administrators_rights,
        broad_write_blocked=evidence.broad_write_blocked,
        broad_write_allowed=not evidence.broad_write_blocked,
        directory_removed=directory_removed,
        stages=stages,
        rights_evaluated=rights_evaluated,
    )


def probe_directory_is_removed() -> bool:
    temp_root = Path(tempfile.mkdtemp(prefix="pr-s001-acl-removal-"))
    try:
        (temp_root / "test.txt").write_text("test", encoding="utf-8")
        return _remove_directory(temp_root)
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
