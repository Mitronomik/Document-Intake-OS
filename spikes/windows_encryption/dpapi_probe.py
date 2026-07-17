from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import struct
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"PR-S001-DPAPI\0\0\0"
VERSION = 1
CRYPTPROTECT_UI_FORBIDDEN = 0x1
CRYPTPROTECT_LOCAL_MACHINE = 0x4


@dataclass(frozen=True)
class DpapiResult:
    status: str
    data: bytes = b""


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def build_wrapped_payload(key: bytes) -> bytes:
    if len(key) != 32:
        raise ValueError("ERR_INVALID_SYNTHETIC_KEY_LENGTH")
    body = MAGIC + struct.pack(">II", VERSION, len(key)) + key
    return body + hashlib.sha256(body).digest()


def parse_wrapped_payload(payload: bytes) -> bytes:
    min_len = len(MAGIC) + 8 + 32
    if len(payload) != min_len + 32:
        raise ValueError("ERR_DPAPI_WRAPPER_INVALID")
    body, checksum = payload[:-32], payload[-32:]
    if hashlib.sha256(body).digest() != checksum:
        raise ValueError("ERR_DPAPI_WRAPPER_CHECKSUM")
    magic = body[: len(MAGIC)]
    version, length = struct.unpack(">II", body[len(MAGIC) : len(MAGIC) + 8])
    if magic != MAGIC or version != VERSION or length != 32:
        raise ValueError("ERR_DPAPI_WRAPPER_INVALID")
    return body[len(MAGIC) + 8 :]


def _blob(data: bytes) -> DATA_BLOB:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))


def protect_current_user(key: bytes) -> DpapiResult:
    if platform.system() != "Windows":
        return DpapiResult("UNSUPPORTED_NON_WINDOWS")
    payload = build_wrapped_payload(key)
    in_blob = _blob(payload)
    out_blob = DATA_BLOB()
    if CRYPTPROTECT_LOCAL_MACHINE & CRYPTPROTECT_UI_FORBIDDEN == CRYPTPROTECT_LOCAL_MACHINE:
        raise AssertionError("ERR_LOCAL_MACHINE_SCOPE")
    ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob))
    if not ok:
        return DpapiResult("ERR_DPAPI_PROTECT_FAILED")
    try:
        data = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return DpapiResult("PASS", data)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def unprotect_current_user(protected_blob: bytes) -> DpapiResult:
    if platform.system() != "Windows":
        return DpapiResult("UNSUPPORTED_NON_WINDOWS")
    in_blob = _blob(protected_blob)
    out_blob = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob))
    if not ok:
        return DpapiResult("ERR_DPAPI_UNPROTECT_FAILED")
    try:
        payload = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return DpapiResult("PASS", parse_wrapped_payload(payload))
    except ValueError:
        return DpapiResult("ERR_DPAPI_WRAPPER_INVALID")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def write_cross_runner_blob(output: Path) -> str:
    result = protect_current_user(os.urandom(32))
    if result.status != "PASS":
        return result.status
    output.write_bytes(result.data)
    return "PASS"
