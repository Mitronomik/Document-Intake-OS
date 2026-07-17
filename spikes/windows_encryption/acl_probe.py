from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

WELL_KNOWN_SYSTEM = "S-1-5-18"
WELL_KNOWN_ADMINISTRATORS = "S-1-5-32-544"
WELL_KNOWN_USERS = "S-1-5-32-545"
WELL_KNOWN_AUTHENTICATED_USERS = "S-1-5-11"
WELL_KNOWN_EVERYONE = "S-1-1-0"


@dataclass(frozen=True)
class AclProbeResult:
    status: str
    broad_write_allowed: bool = False
    directory_removed: bool = False


def _parse_ace_for_principal(acl_text: str, principal: str) -> str:
    for line in acl_text.splitlines():
        if principal in line:
            return line.strip()
    return ""


def _ace_permits_write(ace_line: str) -> bool:
    if not ace_line:
        return False
    perms_part = ace_line.split("):", maxsplit=1)[-1] if "):" in ace_line else ace_line
    return any(token in perms_part for token in ("F", "W", "M"))


def run_acl_probe() -> AclProbeResult:
    temp_root = Path(tempfile.mkdtemp(prefix="pr-s001-acl-"))
    try:
        if platform.system() != "Windows":
            return AclProbeResult("UNSUPPORTED_NON_WINDOWS")
        sid_raw = (
            subprocess.run(
                ["whoami", "/user", "/fo", "csv", "/nh"],
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout.split(",")[-1]
            .strip()
            .strip('"')
        )
        if not sid_raw.startswith("S-"):
            return AclProbeResult("ERR_CURRENT_USER_SID")
        commands = [
            ["icacls", str(temp_root), "/inheritance:r"],
            ["icacls", str(temp_root), "/grant:r", f"*{WELL_KNOWN_SYSTEM}:(OI)(CI)F"],
            ["icacls", str(temp_root), "/grant:r", f"*{WELL_KNOWN_ADMINISTRATORS}:(OI)(CI)F"],
            ["icacls", str(temp_root), "/grant:r", f"*{sid_raw}:(OI)(CI)F"],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True, text=True)
        acl_text = subprocess.run(
            ["icacls", str(temp_root)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        current_user_ace = _parse_ace_for_principal(acl_text, sid_raw)
        system_ace = _parse_ace_for_principal(acl_text, WELL_KNOWN_SYSTEM)
        admin_ace = _parse_ace_for_principal(acl_text, WELL_KNOWN_ADMINISTRATORS)

        has_write = any(
            _ace_permits_write(ace) for ace in [current_user_ace, system_ace, admin_ace] if ace
        )

        if not has_write:
            return AclProbeResult("FAIL_MISSING_PRINCIPAL")

        broad_principals = (
            WELL_KNOWN_USERS,
            WELL_KNOWN_AUTHENTICATED_USERS,
            WELL_KNOWN_EVERYONE,
        )
        broad_write = any(
            _ace_permits_write(_parse_ace_for_principal(acl_text, principal))
            for principal in broad_principals
        )
        if broad_write:
            return AclProbeResult("FAIL_BROAD_WRITE", True)
        return AclProbeResult("PASS")
    except (OSError, subprocess.CalledProcessError):
        return AclProbeResult("ERR_ACL_PROBE_FAILED")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def probe_directory_is_removed() -> bool:
    temp_root = Path(tempfile.mkdtemp(prefix="pr-s001-acl-removal-"))
    try:
        if platform.system() != "Windows":
            return True
        (temp_root / "test.txt").write_text("test", encoding="utf-8")
        shutil.rmtree(temp_root, ignore_errors=False)
        return not temp_root.exists()
    except OSError:
        return False
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
