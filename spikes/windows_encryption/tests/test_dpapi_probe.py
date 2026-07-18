from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from spikes.windows_encryption.dpapi_probe import (
    CRYPTPROTECT_LOCAL_MACHINE,
    DPAPI_FLAGS,
    DpapiResult,
    _build_dpapi_subprocess_script,
    _mutate_opaque_blob,
    build_wrapped_payload,
    classify_dpapi_mutations,
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


def test_dpapi_roundtrip_and_blob_creation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only test")
def test_empty_blob_returns_invalid() -> None:
    result = unprotect_current_user(b"")
    assert result.status == "ERR_DPAPI_ARTIFACT_INVALID"


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only test")
def test_truncated_real_blob() -> None:
    key = os.urandom(32)
    protected = protect_current_user(key)
    if protected.status != "PASS":
        pytest.skip("DPAPI protect failed")
    result = unprotect_current_user(protected.data[:10])
    expected = {"ERR_DPAPI_UNPROTECT_FAILED", "ERR_DPAPI_WRAPPER_INVALID"}
    assert result.status in expected


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only test")
def test_modified_real_blob() -> None:
    key = os.urandom(32)
    protected = protect_current_user(key)
    if protected.status != "PASS":
        pytest.skip("DPAPI protect failed")
    result = classify_dpapi_mutations(protected.data, key)
    assert result == "PASS", f"Mutation evidence failed: {result}"


def test_dpapi_subprocess_script_compiles_unix() -> None:
    blob_path = Path("/tmp/blob.bin")
    marker_path = Path("/tmp/marker.bin")
    script = _build_dpapi_subprocess_script(blob_path, marker_path)
    compile(script, "<dpapi-subprocess>", "exec")
    assert "read_bytes" in script
    assert "ERR_DPAPI_SUBPROCESS_KEY_MISMATCH" in script


def test_dpapi_subprocess_script_compiles_win() -> None:
    blob_path = Path("C:/Temp/dpapi/blob.bin")
    marker_path = Path("C:/Temp/dpapi/marker.bin")
    script = _build_dpapi_subprocess_script(blob_path, marker_path)
    compile(script, "<dpapi-subprocess>", "exec")
    assert "C:\\\\Temp\\\\dpapi\\\\blob.bin" in script or "C:/Temp/dpapi/blob.bin" in script


def test_mutate_opaque_blob_uses_multiple_positions() -> None:
    blob = os.urandom(200)
    positions = [0, len(blob) // 2, len(blob) - 1]
    mutated = _mutate_opaque_blob(blob, positions)
    assert len(mutated) == 3
    for pos, copy in mutated.items():
        assert copy != blob, f"Position {pos} not mutated"
        assert copy[pos] == blob[pos] ^ 0xFF


def test_mutate_opaque_blob_skips_oob() -> None:
    blob = os.urandom(10)
    mutated = _mutate_opaque_blob(blob, [5, 20])
    assert 5 in mutated
    assert 20 not in mutated


# ---------------------------------------------------------------------------
# Platform-independent mutation classification tests via monkeypatch
# ---------------------------------------------------------------------------


def _make_controlled_unprotect(
    original_key: bytes,
    mutation_results: list[DpapiResult],
) -> Any:
    """Return a callable that returns PASS+original_key for the original blob,
    then returns results from `mutation_results` in order for mutated blobs,
    then returns PASS+original_key for the final check.
    """
    call_index = 0

    def _mock(blob: bytes) -> DpapiResult:
        nonlocal call_index
        # First call is always original blob check
        if call_index == 0:
            call_index += 1
            return DpapiResult("PASS", original_key)
        # Last call is always final original check (after all mutations)
        if call_index > len(mutation_results):
            return DpapiResult("PASS", original_key)
        result = mutation_results[call_index - 1]
        call_index += 1
        return result

    return _mock


# Scenario A: one mutation PASS with same key, rest rejected -> PASS


def test_classify_mutations_one_same_key_rest_rejected_passes() -> None:
    """One mutation returns same key (non-semantic), others rejected -> PASS."""
    key = os.urandom(32)
    blob = os.urandom(200)
    results = [
        DpapiResult("PASS", key),  # accepted with same key — ok
        DpapiResult("ERR_DPAPI_UNPROTECT_FAILED"),
        DpapiResult("ERR_DPAPI_UNPROTECT_FAILED"),
    ]

    with patch(
        "spikes.windows_encryption.dpapi_probe.unprotect_current_user",
        _make_controlled_unprotect(key, results),
    ):
        status = classify_dpapi_mutations(blob, key)
    assert status == "PASS"


# Scenario B: all mutations PASS with same key -> ERR_DPAPI_NO_MUTATIONS_REJECTED


def test_classify_mutations_all_same_key_no_rejections() -> None:
    """All mutations return same key — no rejection evidence."""
    key = os.urandom(32)
    blob = os.urandom(200)
    results = [
        DpapiResult("PASS", key),
        DpapiResult("PASS", key),
        DpapiResult("PASS", key),
    ]

    with patch(
        "spikes.windows_encryption.dpapi_probe.unprotect_current_user",
        _make_controlled_unprotect(key, results),
    ):
        status = classify_dpapi_mutations(blob, key)
    assert status == "ERR_DPAPI_NO_MUTATIONS_REJECTED"


# Scenario C: mutation PASS with different key -> ERR_DPAPI_MUTATION_ACCEPTED_WITH_DIFFERENT_KEY


def test_classify_mutations_different_key_is_error() -> None:
    """Mutation accepted with a different 32-byte key."""
    key = os.urandom(32)
    other_key = os.urandom(32)
    assert other_key != key
    blob = os.urandom(200)
    results = [DpapiResult("PASS", other_key)]

    with patch(
        "spikes.windows_encryption.dpapi_probe.unprotect_current_user",
        _make_controlled_unprotect(key, results),
    ):
        status = classify_dpapi_mutations(blob, key)
    assert status == "ERR_DPAPI_MUTATION_ACCEPTED_WITH_DIFFERENT_KEY"


# Scenario D: all mutations rejected, final original valid -> PASS


def test_classify_mutations_all_rejected_final_ok() -> None:
    """All mutations rejected, final original valid -> PASS."""
    key = os.urandom(32)
    blob = os.urandom(200)
    results = [
        DpapiResult("ERR_DPAPI_UNPROTECT_FAILED"),
        DpapiResult("ERR_DPAPI_UNPROTECT_FAILED"),
        DpapiResult("ERR_DPAPI_UNPROTECT_FAILED"),
    ]

    with patch(
        "spikes.windows_encryption.dpapi_probe.unprotect_current_user",
        _make_controlled_unprotect(key, results),
    ):
        status = classify_dpapi_mutations(blob, key)
    assert status == "PASS"


# Scenario E: final original invalid -> ERR_DPAPI_ORIGINAL_CORRUPTED


def test_classify_mutations_final_original_corrupted() -> None:
    """Final original check fails after mutations."""
    key = os.urandom(32)
    blob = os.urandom(200)

    call_count = 0

    def _mock(blob_arg: bytes) -> DpapiResult:
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            return DpapiResult("PASS", key)
        # Reject mutations
        call_count += 1
        if call_count <= 4:
            return DpapiResult("ERR_DPAPI_UNPROTECT_FAILED")
        # Final original check fails
        return DpapiResult("ERR_DPAPI_UNPROTECT_FAILED")

    with patch(
        "spikes.windows_encryption.dpapi_probe.unprotect_current_user",
        _mock,
    ):
        status = classify_dpapi_mutations(blob, key)
    assert status == "ERR_DPAPI_ORIGINAL_CORRUPTED"
