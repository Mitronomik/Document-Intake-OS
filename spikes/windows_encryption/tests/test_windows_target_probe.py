from __future__ import annotations

import json

import pytest

from spikes.windows_encryption.safe_report import ResultStatus
from spikes.windows_encryption.windows_target_probe import (
    WindowsArchitectureEvidence,
    WindowsMachine,
    WindowsProductType,
    WindowsTargetProbeResult,
    WindowsVersionEvidence,
    run_windows_target_probe,
)


def version(
    build: int | None = 22000,
    product: WindowsProductType = WindowsProductType.WORKSTATION,
    status: ResultStatus = ResultStatus.PASS,
    reason: str = "PASS",
) -> WindowsVersionEvidence:
    return WindowsVersionEvidence(
        10 if build is not None else None,
        0 if build is not None else None,
        build,
        product,
        status,
        reason,
    )


def arch(
    native: WindowsMachine = WindowsMachine.AMD64,
    process: WindowsMachine = WindowsMachine.UNKNOWN,
    pointer: int = 8,
    status: ResultStatus = ResultStatus.PASS,
    reason: str = "PASS",
) -> WindowsArchitectureEvidence:
    return WindowsArchitectureEvidence(native, process, pointer, status, reason)


def statuses(result: WindowsTargetProbeResult) -> dict[str, tuple[ResultStatus, str]]:
    return {check.identifier: (check.status, check.reason_code) for check in result.checks}


@pytest.mark.parametrize("build", [22000, 26000])
def test_windows_11_or_later_workstation_amd64_passes(build: int) -> None:
    result = run_windows_target_probe(lambda: version(build), arch)
    assert all(check.status == ResultStatus.PASS for check in result.checks)
    assert result.windows_11_x64_result == ResultStatus.PASS


def test_windows_server_build_above_22000_is_not_windows_11() -> None:
    result = run_windows_target_probe(lambda: version(26000, WindowsProductType.SERVER), arch)
    got = statuses(result)
    assert got["windows-target-workstation"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED_WINDOWS11",
    )
    assert got["windows-target-build"] == (ResultStatus.PASS, "PASS")
    assert got["windows-11-x64"] == (ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED_WINDOWS11")


def test_windows_10_workstation_build_below_22000_is_not_demonstrated() -> None:
    result = run_windows_target_probe(lambda: version(19045), arch)
    got = statuses(result)
    assert got["windows-target-workstation"] == (ResultStatus.PASS, "PASS")
    assert got["windows-target-build"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED_WINDOWS11",
    )
    assert got["windows-11-x64"][0] == ResultStatus.NOT_DEMONSTRATED


def test_windows_11_arm64_is_not_accepted() -> None:
    result = run_windows_target_probe(lambda: version(22631), lambda: arch(WindowsMachine.ARM64))
    got = statuses(result)
    assert got["windows-target-native-amd64"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED_WINDOWS11",
    )
    assert got["windows-11-x64"][0] == ResultStatus.NOT_DEMONSTRATED


def test_wow64_x86_process_is_not_accepted() -> None:
    result = run_windows_target_probe(
        lambda: version(22631), lambda: arch(process=WindowsMachine.OTHER)
    )
    got = statuses(result)
    assert got["windows-target-native-amd64"] == (ResultStatus.PASS, "PASS")
    assert got["windows-target-process-amd64"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED_WINDOWS11",
    )
    assert got["windows-11-x64"][0] == ResultStatus.NOT_DEMONSTRATED


def test_32_bit_pointer_width_is_not_accepted() -> None:
    result = run_windows_target_probe(lambda: version(22631), lambda: arch(pointer=4))
    got = statuses(result)
    assert got["windows-target-process-amd64"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED_WINDOWS11",
    )
    assert got["windows-11-x64"][0] == ResultStatus.NOT_DEMONSTRATED


def test_non_windows_is_unsupported_for_operational_queries() -> None:
    result = run_windows_target_probe(
        lambda: version(
            None, WindowsProductType.UNKNOWN, ResultStatus.UNSUPPORTED, "UNSUPPORTED_NON_WINDOWS"
        ),
        lambda: arch(
            WindowsMachine.UNKNOWN,
            WindowsMachine.UNKNOWN,
            8,
            ResultStatus.UNSUPPORTED,
            "UNSUPPORTED_NON_WINDOWS",
        ),
    )
    got = statuses(result)
    assert got["windows-target-version-query"] == (
        ResultStatus.UNSUPPORTED,
        "UNSUPPORTED_NON_WINDOWS",
    )
    assert got["windows-target-native-amd64"] == (
        ResultStatus.UNSUPPORTED,
        "UNSUPPORTED_NON_WINDOWS",
    )
    assert got["windows-11-x64"] == (ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED_WINDOWS11")


def test_rtl_get_version_failure_is_stable_reason() -> None:
    result = run_windows_target_probe(
        lambda: version(
            None, WindowsProductType.UNKNOWN, ResultStatus.FAIL, "ERR_WINDOWS_VERSION_QUERY"
        ),
        arch,
    )
    assert statuses(result)["windows-target-version-query"] == (
        ResultStatus.FAIL,
        "ERR_WINDOWS_VERSION_QUERY",
    )
    assert statuses(result)["windows-target-workstation"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED",
    )


def test_is_wow64_process2_failure_is_stable_reason() -> None:
    result = run_windows_target_probe(
        lambda: version(22631),
        lambda: arch(
            WindowsMachine.UNKNOWN,
            WindowsMachine.UNKNOWN,
            8,
            ResultStatus.FAIL,
            "ERR_WINDOWS_ARCH_QUERY",
        ),
    )
    got = statuses(result)
    assert got["windows-target-native-amd64"] == (ResultStatus.FAIL, "ERR_WINDOWS_ARCH_QUERY")
    assert got["windows-target-process-amd64"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED",
    )


def test_unexpected_internal_failure_is_stable_and_sanitized() -> None:
    def broken() -> WindowsVersionEvidence:
        raise RuntimeError("secret-hostname raw 0x123")

    result = run_windows_target_probe(broken, arch)
    text = repr(result)
    assert statuses(result)["windows-target-version-query"] == (
        ResultStatus.FAIL,
        "ERR_WINDOWS_TARGET_UNEXPECTED",
    )
    assert "secret-hostname" not in text
    assert "0x123" not in text


def test_unexpected_architecture_failure_preserves_version_stage_and_sanitizes() -> None:
    def broken_architecture() -> WindowsArchitectureEvidence:
        raise RuntimeError("fake-host C:\\private\\runner 123456")

    result = run_windows_target_probe(lambda: version(22631), broken_architecture)
    got = statuses(result)
    serialized = json.dumps(
        [
            {
                "identifier": check.identifier,
                "status": check.status,
                "reason_code": check.reason_code,
            }
            for check in result.checks
        ],
        sort_keys=True,
    )
    combined = repr(result) + serialized

    assert got["windows-target-version-query"] == (ResultStatus.PASS, "PASS")
    assert got["windows-target-workstation"] == (ResultStatus.PASS, "PASS")
    assert got["windows-target-build"] == (ResultStatus.PASS, "PASS")
    assert got["windows-target-native-amd64"] == (
        ResultStatus.FAIL,
        "ERR_WINDOWS_TARGET_UNEXPECTED",
    )
    assert got["windows-target-process-amd64"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED",
    )
    assert got["windows-11-x64"] == (
        ResultStatus.NOT_DEMONSTRATED,
        "NOT_DEMONSTRATED_WINDOWS11",
    )
    assert result.windows_11_x64_result == ResultStatus.NOT_DEMONSTRATED
    assert "fake-host" not in combined
    assert "private" not in combined
    assert "123456" not in combined
