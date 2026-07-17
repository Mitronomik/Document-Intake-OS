from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import struct
import subprocess
import sys
import tempfile
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAGIC = b"PR-S001-DPAPI\0\0\0"
VERSION = 1
KEY_LENGTH = 32
CHECKSUM_LENGTH = 32
CRYPTPROTECT_UI_FORBIDDEN = 0x1
CRYPTPROTECT_LOCAL_MACHINE = 0x4
DPAPI_FLAGS = CRYPTPROTECT_UI_FORBIDDEN


@dataclass(frozen=True)
class DpapiResult:
    status: str
    data: bytes = b""


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


@dataclass(frozen=True)
class _InputBlob:
    blob: DATA_BLOB
    buffer: ctypes.Array[ctypes.c_char]


def local_machine_scope_disabled() -> bool:
    return DPAPI_FLAGS & CRYPTPROTECT_LOCAL_MACHINE == 0


def build_wrapped_payload(key: bytes) -> bytes:
    if len(key) != KEY_LENGTH:
        raise ValueError("ERR_INVALID_SYNTHETIC_KEY_LENGTH")
    body = MAGIC + struct.pack(">II", VERSION, len(key)) + key
    return body + hashlib.sha256(body).digest()


def parse_wrapped_payload(payload: bytes) -> bytes:
    expected = len(MAGIC) + 8 + KEY_LENGTH + CHECKSUM_LENGTH
    if len(payload) != expected:
        raise ValueError("ERR_DPAPI_WRAPPER_INVALID")
    body = payload[:-CHECKSUM_LENGTH]
    checksum = payload[-CHECKSUM_LENGTH:]
    if hashlib.sha256(body).digest() != checksum:
        raise ValueError("ERR_DPAPI_WRAPPER_CHECKSUM")
    magic = body[: len(MAGIC)]
    version, length = struct.unpack(">II", body[len(MAGIC) : len(MAGIC) + 8])
    if magic != MAGIC or version != VERSION or length != KEY_LENGTH:
        raise ValueError("ERR_DPAPI_WRAPPER_INVALID")
    return body[len(MAGIC) + 8 :]


def _make_input_blob(data: bytes) -> _InputBlob:
    buffer = ctypes.create_string_buffer(data)
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    return _InputBlob(blob=blob, buffer=buffer)


def _load_windows_functions() -> tuple[Any, Any, Any]:
    _WinDLL = getattr(ctypes, "WinDLL", None)
    if _WinDLL is None:
        raise RuntimeError("ERR_WIN32_API_UNAVAILABLE: ctypes.WinDLL missing")
    crypt32 = _WinDLL("crypt32", use_last_error=True)
    kernel32 = _WinDLL("kernel32", use_last_error=True)
    protect = crypt32.CryptProtectData
    protect.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    protect.restype = wintypes.BOOL
    unprotect = crypt32.CryptUnprotectData
    unprotect.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    unprotect.restype = wintypes.BOOL
    local_free = kernel32.LocalFree
    local_free.argtypes = [wintypes.HLOCAL]
    local_free.restype = wintypes.HLOCAL
    return protect, unprotect, local_free


def protect_current_user(key: bytes) -> DpapiResult:
    if platform.system() != "Windows":
        return DpapiResult("UNSUPPORTED_NON_WINDOWS")
    if not local_machine_scope_disabled():
        return DpapiResult("ERR_LOCAL_MACHINE_SCOPE")
    payload = build_wrapped_payload(key)
    input_blob = _make_input_blob(payload)
    out_blob = DATA_BLOB()
    protect, _, local_free = _load_windows_functions()
    ok = protect(
        ctypes.byref(input_blob.blob),
        None,
        None,
        None,
        None,
        DPAPI_FLAGS,
        ctypes.byref(out_blob),
    )
    _ = input_blob.buffer
    if not ok:
        return DpapiResult("ERR_DPAPI_PROTECT_FAILED")
    try:
        return DpapiResult("PASS", ctypes.string_at(out_blob.pbData, out_blob.cbData))
    finally:
        local_free(ctypes.cast(out_blob.pbData, wintypes.HLOCAL))


def unprotect_current_user(protected_blob: bytes) -> DpapiResult:
    if platform.system() != "Windows":
        return DpapiResult("UNSUPPORTED_NON_WINDOWS")
    if not protected_blob:
        return DpapiResult("ERR_DPAPI_ARTIFACT_INVALID")
    input_blob = _make_input_blob(protected_blob)
    out_blob = DATA_BLOB()
    _, unprotect, local_free = _load_windows_functions()
    ok = unprotect(
        ctypes.byref(input_blob.blob),
        None,
        None,
        None,
        None,
        DPAPI_FLAGS,
        ctypes.byref(out_blob),
    )
    _ = input_blob.buffer
    if not ok:
        return DpapiResult("ERR_DPAPI_UNPROTECT_FAILED")
    try:
        payload = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return DpapiResult("PASS", parse_wrapped_payload(payload))
    except ValueError:
        return DpapiResult("ERR_DPAPI_WRAPPER_INVALID")
    finally:
        local_free(ctypes.cast(out_blob.pbData, wintypes.HLOCAL))


def _transient_expected_digest(key: bytes, marker: bytes) -> str:
    return hashlib.sha256(key + marker).hexdigest()


def verify_same_runner_blob(protected_blob: bytes, expected_key: bytes) -> str:
    current = unprotect_current_user(protected_blob)
    if current.status != "PASS" or current.data != expected_key:
        return "ERR_DPAPI_CURRENT_PROCESS_VERIFY_FAILED"
    marker = os.urandom(16)
    expected = _transient_expected_digest(expected_key, marker)
    with tempfile.TemporaryDirectory() as tmp_name:
        blob_path = Path(tmp_name) / "protected.blob"
        marker_path = Path(tmp_name) / "marker.bin"
        blob_path.write_bytes(protected_blob)
        marker_path.write_bytes(marker)
        code = (
            "import hashlib, sys;"
            "from pathlib import Path;"
            "from spikes.windows_encryption.dpapi_probe import unprotect_current_user;"
            "blob = Path(r'" + str(blob_path) + "').read_bytes();"
            "mk = Path(r'" + str(marker_path) + "').read_bytes();"
            "r = unprotect_current_user(blob);"
            "if r.status != 'PASS':"
            "  print('ERR_DPAPI_SUBPROCESS_KEY_MISMATCH'); sys.exit(1);"
            "transient = hashlib.sha256(r.data + mk).hexdigest();"
            "print(transient);"
            "sys.exit(0 if transient == r'" + expected + "' else 1)"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
    if completed.returncode != 0:
        stdout_val = completed.stdout.strip()
        if "ERR_DPAPI_SUBPROCESS_KEY_MISMATCH" in stdout_val:
            return "ERR_DPAPI_SUBPROCESS_KEY_MISMATCH"
        return "ERR_DPAPI_SUBPROCESS_VERIFY_FAILED"
    return "PASS"


def create_validated_cross_runner_blob(output: Path) -> str:
    key = os.urandom(KEY_LENGTH)
    protected = protect_current_user(key)
    if protected.status != "PASS":
        return protected.status
    verify_status = verify_same_runner_blob(protected.data, key)
    if verify_status != "PASS":
        return verify_status
    output.write_bytes(protected.data)
    return "PASS"
