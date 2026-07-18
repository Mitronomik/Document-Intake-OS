from __future__ import annotations

import ctypes
import platform
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from spikes.windows_encryption.safe_report import ReportCheck, ResultStatus

STATUS_SUCCESS = 0
VER_NT_WORKSTATION = 1
WINDOWS_11_MIN_BUILD = 22000
IMAGE_FILE_MACHINE_UNKNOWN = 0x0000
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_ARM64 = 0xAA64


class WindowsProductType(StrEnum):
    WORKSTATION = "WORKSTATION"
    SERVER = "SERVER"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class WindowsMachine(StrEnum):
    AMD64 = "AMD64"
    ARM64 = "ARM64"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class WindowsVersionEvidence:
    major_version: int | None
    minor_version: int | None
    build_number: int | None
    product_type: WindowsProductType
    status: ResultStatus
    reason_code: str


@dataclass(frozen=True)
class WindowsArchitectureEvidence:
    native_machine: WindowsMachine
    process_machine: WindowsMachine
    pointer_width: int
    status: ResultStatus
    reason_code: str


@dataclass(frozen=True)
class WindowsTargetProbeResult:
    version: WindowsVersionEvidence
    architecture: WindowsArchitectureEvidence
    checks: tuple[ReportCheck, ...]
    windows_11_x64_result: ResultStatus


VersionQuery = Callable[[], WindowsVersionEvidence]
ArchitectureQuery = Callable[[], WindowsArchitectureEvidence]


class _RTL_OSVERSIONINFOEXW(ctypes.Structure):
    _fields_ = [
        ("dwOSVersionInfoSize", ctypes.c_ulong),
        ("dwMajorVersion", ctypes.c_ulong),
        ("dwMinorVersion", ctypes.c_ulong),
        ("dwBuildNumber", ctypes.c_ulong),
        ("dwPlatformId", ctypes.c_ulong),
        ("szCSDVersion", ctypes.c_wchar * 128),
        ("wServicePackMajor", ctypes.c_ushort),
        ("wServicePackMinor", ctypes.c_ushort),
        ("wSuiteMask", ctypes.c_ushort),
        ("wProductType", ctypes.c_ubyte),
        ("wReserved", ctypes.c_ubyte),
    ]


def _product_type(value: int) -> WindowsProductType:
    if value == VER_NT_WORKSTATION:
        return WindowsProductType.WORKSTATION
    if value in (2, 3):
        return WindowsProductType.SERVER
    return WindowsProductType.OTHER


def _machine(value: int) -> WindowsMachine:
    if value == IMAGE_FILE_MACHINE_AMD64:
        return WindowsMachine.AMD64
    if value == IMAGE_FILE_MACHINE_ARM64:
        return WindowsMachine.ARM64
    if value == IMAGE_FILE_MACHINE_UNKNOWN:
        return WindowsMachine.UNKNOWN
    return WindowsMachine.OTHER


def query_windows_version() -> WindowsVersionEvidence:
    if platform.system() != "Windows":
        return WindowsVersionEvidence(
            None,
            None,
            None,
            WindowsProductType.UNKNOWN,
            ResultStatus.UNSUPPORTED,
            "UNSUPPORTED_NON_WINDOWS",
        )
    try:
        info = _RTL_OSVERSIONINFOEXW()
        info.dwOSVersionInfoSize = ctypes.sizeof(_RTL_OSVERSIONINFOEXW)
        win_dll = cast(Any, ctypes.WinDLL)  # type: ignore[attr-defined,unused-ignore]
        rtl_get_version = win_dll("ntdll").RtlGetVersion
        rtl_get_version.argtypes = [ctypes.POINTER(_RTL_OSVERSIONINFOEXW)]
        rtl_get_version.restype = ctypes.c_long
        if rtl_get_version(ctypes.byref(info)) != STATUS_SUCCESS:
            return WindowsVersionEvidence(
                None,
                None,
                None,
                WindowsProductType.UNKNOWN,
                ResultStatus.FAIL,
                "ERR_WINDOWS_VERSION_QUERY",
            )
        return WindowsVersionEvidence(
            int(info.dwMajorVersion),
            int(info.dwMinorVersion),
            int(info.dwBuildNumber),
            _product_type(int(info.wProductType)),
            ResultStatus.PASS,
            "PASS",
        )
    except Exception:
        return WindowsVersionEvidence(
            None,
            None,
            None,
            WindowsProductType.UNKNOWN,
            ResultStatus.FAIL,
            "ERR_WINDOWS_VERSION_QUERY",
        )


def query_windows_architecture() -> WindowsArchitectureEvidence:
    pointer_width = ctypes.sizeof(ctypes.c_void_p)
    if platform.system() != "Windows":
        return WindowsArchitectureEvidence(
            WindowsMachine.UNKNOWN,
            WindowsMachine.UNKNOWN,
            pointer_width,
            ResultStatus.UNSUPPORTED,
            "UNSUPPORTED_NON_WINDOWS",
        )
    try:
        win_dll = cast(Any, ctypes.WinDLL)  # type: ignore[attr-defined,unused-ignore]
        kernel32 = win_dll("kernel32", use_last_error=False)
        get_current_process = kernel32.GetCurrentProcess
        get_current_process.argtypes = []
        get_current_process.restype = ctypes.c_void_p
        is_wow64_process2 = kernel32.IsWow64Process2
        is_wow64_process2.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ushort),
            ctypes.POINTER(ctypes.c_ushort),
        ]
        is_wow64_process2.restype = ctypes.c_int
        process_machine = ctypes.c_ushort(IMAGE_FILE_MACHINE_UNKNOWN)
        native_machine = ctypes.c_ushort(IMAGE_FILE_MACHINE_UNKNOWN)
        if not is_wow64_process2(
            get_current_process(), ctypes.byref(process_machine), ctypes.byref(native_machine)
        ):
            return WindowsArchitectureEvidence(
                WindowsMachine.UNKNOWN,
                WindowsMachine.UNKNOWN,
                pointer_width,
                ResultStatus.FAIL,
                "ERR_WINDOWS_ARCH_QUERY",
            )
        return WindowsArchitectureEvidence(
            _machine(int(native_machine.value)),
            _machine(int(process_machine.value)),
            pointer_width,
            ResultStatus.PASS,
            "PASS",
        )
    except Exception:
        return WindowsArchitectureEvidence(
            WindowsMachine.UNKNOWN,
            WindowsMachine.UNKNOWN,
            pointer_width,
            ResultStatus.FAIL,
            "ERR_WINDOWS_ARCH_QUERY",
        )


def _check(identifier: str, status: ResultStatus, reason_code: str) -> ReportCheck:
    return ReportCheck(identifier, status, reason_code)


def _version_dependent_checks(
    version: WindowsVersionEvidence,
) -> tuple[bool, bool, ReportCheck, ReportCheck, ReportCheck]:
    version_ok = version.status == ResultStatus.PASS
    workstation = version_ok and version.product_type == WindowsProductType.WORKSTATION
    build = (
        version_ok
        and version.major_version == 10
        and version.minor_version == 0
        and version.build_number is not None
        and version.build_number >= WINDOWS_11_MIN_BUILD
    )
    version_query_check = _check(
        "windows-target-version-query", version.status, version.reason_code
    )
    if version.status == ResultStatus.UNSUPPORTED:
        return (
            workstation,
            build,
            version_query_check,
            _check(
                "windows-target-workstation", ResultStatus.UNSUPPORTED, "UNSUPPORTED_NON_WINDOWS"
            ),
            _check("windows-target-build", ResultStatus.UNSUPPORTED, "UNSUPPORTED_NON_WINDOWS"),
        )
    if not version_ok:
        return (
            workstation,
            build,
            version_query_check,
            _check("windows-target-workstation", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"),
            _check("windows-target-build", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"),
        )
    return (
        workstation,
        build,
        version_query_check,
        _check(
            "windows-target-workstation",
            ResultStatus.PASS if workstation else ResultStatus.NOT_DEMONSTRATED,
            "PASS" if workstation else "NOT_DEMONSTRATED_WINDOWS11",
        ),
        _check(
            "windows-target-build",
            ResultStatus.PASS if build else ResultStatus.NOT_DEMONSTRATED,
            "PASS" if build else "NOT_DEMONSTRATED_WINDOWS11",
        ),
    )


def _architecture_checks(
    architecture: WindowsArchitectureEvidence,
    *,
    unexpected: bool = False,
) -> tuple[bool, bool, ReportCheck, ReportCheck]:
    if unexpected:
        return (
            False,
            False,
            _check(
                "windows-target-native-amd64",
                ResultStatus.FAIL,
                "ERR_WINDOWS_TARGET_UNEXPECTED",
            ),
            _check(
                "windows-target-process-amd64",
                ResultStatus.NOT_DEMONSTRATED,
                "NOT_DEMONSTRATED",
            ),
        )
    arch_ok = architecture.status == ResultStatus.PASS
    native_amd64 = arch_ok and architecture.native_machine == WindowsMachine.AMD64
    process_amd64 = (
        arch_ok
        and architecture.native_machine == WindowsMachine.AMD64
        and architecture.process_machine == WindowsMachine.UNKNOWN
        and architecture.pointer_width == 8
    )
    if architecture.status == ResultStatus.UNSUPPORTED:
        return (
            native_amd64,
            process_amd64,
            _check(
                "windows-target-native-amd64", ResultStatus.UNSUPPORTED, "UNSUPPORTED_NON_WINDOWS"
            ),
            _check(
                "windows-target-process-amd64", ResultStatus.UNSUPPORTED, "UNSUPPORTED_NON_WINDOWS"
            ),
        )
    if not arch_ok:
        return (
            native_amd64,
            process_amd64,
            _check("windows-target-native-amd64", ResultStatus.FAIL, architecture.reason_code),
            _check(
                "windows-target-process-amd64",
                ResultStatus.NOT_DEMONSTRATED,
                "NOT_DEMONSTRATED",
            ),
        )
    return (
        native_amd64,
        process_amd64,
        _check(
            "windows-target-native-amd64",
            ResultStatus.PASS if native_amd64 else ResultStatus.NOT_DEMONSTRATED,
            "PASS" if native_amd64 else "NOT_DEMONSTRATED_WINDOWS11",
        ),
        _check(
            "windows-target-process-amd64",
            ResultStatus.PASS if process_amd64 else ResultStatus.NOT_DEMONSTRATED,
            "PASS" if process_amd64 else "NOT_DEMONSTRATED_WINDOWS11",
        ),
    )


def _target_result(
    version: WindowsVersionEvidence,
    architecture: WindowsArchitectureEvidence,
    checks: tuple[ReportCheck, ...],
    aggregate: bool,
) -> WindowsTargetProbeResult:
    aggregate_status = ResultStatus.PASS if aggregate else ResultStatus.NOT_DEMONSTRATED
    return WindowsTargetProbeResult(
        version,
        architecture,
        (
            *checks,
            _check(
                "windows-11-x64",
                aggregate_status,
                "PASS" if aggregate else "NOT_DEMONSTRATED_WINDOWS11",
            ),
        ),
        aggregate_status,
    )


def run_windows_target_probe(
    version_query: VersionQuery = query_windows_version,
    architecture_query: ArchitectureQuery = query_windows_architecture,
) -> WindowsTargetProbeResult:
    try:
        version = version_query()
    except Exception:
        version = WindowsVersionEvidence(
            None,
            None,
            None,
            WindowsProductType.UNKNOWN,
            ResultStatus.FAIL,
            "ERR_WINDOWS_TARGET_UNEXPECTED",
        )
        architecture = WindowsArchitectureEvidence(
            WindowsMachine.UNKNOWN,
            WindowsMachine.UNKNOWN,
            0,
            ResultStatus.NOT_DEMONSTRATED,
            "NOT_DEMONSTRATED",
        )
        return _target_result(
            version,
            architecture,
            (
                _check(
                    "windows-target-version-query",
                    ResultStatus.FAIL,
                    "ERR_WINDOWS_TARGET_UNEXPECTED",
                ),
                _check(
                    "windows-target-workstation", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"
                ),
                _check("windows-target-build", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"),
                _check(
                    "windows-target-native-amd64", ResultStatus.NOT_DEMONSTRATED, "NOT_DEMONSTRATED"
                ),
                _check(
                    "windows-target-process-amd64",
                    ResultStatus.NOT_DEMONSTRATED,
                    "NOT_DEMONSTRATED",
                ),
            ),
            False,
        )

    workstation, build, version_query_check, workstation_check, build_check = (
        _version_dependent_checks(version)
    )
    try:
        architecture = architecture_query()
        native_amd64, process_amd64, native_check, process_check = _architecture_checks(
            architecture
        )
    except Exception:
        architecture = WindowsArchitectureEvidence(
            WindowsMachine.UNKNOWN,
            WindowsMachine.UNKNOWN,
            0,
            ResultStatus.FAIL,
            "ERR_WINDOWS_TARGET_UNEXPECTED",
        )
        native_amd64, process_amd64, native_check, process_check = _architecture_checks(
            architecture,
            unexpected=True,
        )

    return _target_result(
        version,
        architecture,
        (version_query_check, workstation_check, build_check, native_check, process_check),
        workstation and build and native_amd64 and process_amd64,
    )
