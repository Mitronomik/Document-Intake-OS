from __future__ import annotations

import os
import platform

import pytest

from spikes.windows_encryption.dpapi_probe import CRYPTPROTECT_LOCAL_MACHINE, build_wrapped_payload, parse_wrapped_payload, protect_current_user, unprotect_current_user


def test_wrapper_validation_detects_modification() -> None:
    key = os.urandom(32)
    payload = build_wrapped_payload(key)
    assert parse_wrapped_payload(payload) == key
    tampered = payload[:-1] + bytes([payload[-1] ^ 1])
    with pytest.raises(ValueError, match="ERR_DPAPI_WRAPPER_CHECKSUM"):
        parse_wrapped_payload(tampered)
    with pytest.raises(ValueError, match="ERR_DPAPI_WRAPPER_INVALID"):
        parse_wrapped_payload(payload[:10])
    assert CRYPTPROTECT_LOCAL_MACHINE == 0x4


def test_dpapi_current_user_roundtrip_or_unsupported() -> None:
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
