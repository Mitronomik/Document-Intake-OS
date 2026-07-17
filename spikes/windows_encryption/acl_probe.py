from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AclProbeResult:
    status: str
    broad_write_allowed: bool = False
    directory_removed: bool = False


def run_acl_probe() -> AclProbeResult:
    temp_root = Path(tempfile.mkdtemp(prefix="pr-s001-acl-"))
    try:
        if platform.system() != "Windows":
            return AclProbeResult("UNSUPPORTED_NON_WINDOWS", directory_removed=False)
        sid = (
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
        if not sid.startswith("S-"):
            return AclProbeResult("ERR_CURRENT_USER_SID")
        commands = [
            ["icacls", str(temp_root), "/inheritance:r"],
            ["icacls", str(temp_root), "/grant:r", f"*{sid}:(OI)(CI)F"],
            ["icacls", str(temp_root), "/grant:r", "SYSTEM:(OI)(CI)F"],
            ["icacls", str(temp_root), "/grant:r", "Administrators:(OI)(CI)F"],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True, text=True)
        acl_text = subprocess.run(
            ["icacls", str(temp_root)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        broad_tokens = ("Everyone:(", "Users:(", "Authenticated Users:(")
        broad_write = any(token in acl_text and "W" in acl_text for token in broad_tokens)
        return AclProbeResult("PASS" if not broad_write else "FAIL_BROAD_WRITE", broad_write)
    except (OSError, subprocess.CalledProcessError):
        return AclProbeResult("ERR_ACL_PROBE_FAILED")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def probe_directory_is_removed() -> bool:
    result = run_acl_probe()
    return result.status == "UNSUPPORTED_NON_WINDOWS" or result.status in {
        "PASS",
        "FAIL_BROAD_WRITE",
    }
