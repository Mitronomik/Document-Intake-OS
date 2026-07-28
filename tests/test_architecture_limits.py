import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_limits_pass() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_architecture_limits.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert result.stdout == "architecture_limits PASS 0\n"
