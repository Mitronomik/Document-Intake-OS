from __future__ import annotations

import os
import platform

import pytest

from spikes.windows_encryption.dpapi_probe import (
    CRYPTPROTECT_LOCAL_MACHINE,
    DPAPI_FLAGS,
    build_wrapped_payload,
    create_validated_cross_runner_blob,
    local_machine_scope_disabled,
    parse_wrapped_payload,
    protect_current_user,
    unprotect_current_user,
)


def test_wrapper_validation_detects_malformed_truncated_and_modified() -> None:
    key = os.urandom(32)
    payload = build_wrapped_payload(key)
    assert parse_wrapped_payload(payload) == key
    with pytest.raises(ValueError, match="ERR_DPAPI_WRAPPER_CHECKSUM"):
        parse_wrapped_payload(payload[:-1] + bytes([payload[-1] ^ 1]))
    with pytest.raises(ValueError, match="ERR_DPAPI_WRAPPER_INVALID"):
        parse_wrapped_payload(payload[:10])
    with pytest.raises(ValueError, match="ERR_DPAPI_WRAPPER_INVALID"):
        parse_wrapped_payload(b"malformed")
    assert DPAPI_FLAGS & CRYPTPROTECT_LOCAL_MACHINE == 0
    assert local_machine_scope_disabled()


def test_dpapi_roundtrip_and_blob_creation(tmp_path, capsys) -> None:
    key = os.urandom(32)
    protected = protect_current_user(key)
    if platform.system() != "Windows":
        assert protected.status == "UNSUPPORTED_NON_WINDOWS"
        return
    assert protected.status == "PASS"
    assert protected.data != key
    unprotected = unprotect_current_user(protected.data)
    assert unprotected.status == "PASS"
    assert unprotected.data == key
    blob_path = tmp_path / "blob.bin"
    assert create_validated_cross_runner_blob(blob_path) == "PASS"
    assert blob_path.exists() and blob_path.stat().st_size > 0
    captured = capsys.readouterr()
    assert key.hex() not in captured.out + captured.err
