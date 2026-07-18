from __future__ import annotations

from pathlib import Path

from spikes.windows_encryption.crash_consistency_probe import (
    FailurePoint,
    ReconcileStatus,
    reconcile,
    run_staged_sequence,
    windows_directory_fsync_limitation,
)


def test_staged_sequence_exact_results(tmp_path: Path) -> None:
    """Each FailurePoint must produce an exact expected ReconcileStatus."""
    expected_map = {
        FailurePoint.NONE: ReconcileStatus.ACTIVE,
        FailurePoint.BEFORE_TEMP_WRITE: ReconcileStatus.SAFE_TO_RETRY,
        FailurePoint.DURING_TEMP_WRITE: ReconcileStatus.SAFE_TO_RETRY,
        FailurePoint.AFTER_TEMP_WRITE: ReconcileStatus.SAFE_TO_RETRY,
        FailurePoint.AFTER_REPLACE: ReconcileStatus.QUARANTINED,
        FailurePoint.BEFORE_ACTIVE_FINALIZATION: ReconcileStatus.QUARANTINED,
        FailurePoint.AFTER_ACTIVE_FINALIZATION: ReconcileStatus.ACTIVE,
    }
    for failure, expected in expected_map.items():
        record, temp_path, final_path = run_staged_sequence(tmp_path / failure.value, failure)
        result = reconcile(record, final_path, temp_path)
        assert result is expected, f"{failure.value}: expected {expected}, got {result}"


def test_active_with_matching_object_is_active(tmp_path: Path) -> None:
    record, temp_path, final_path = run_staged_sequence(
        tmp_path / "happy", FailurePoint.AFTER_ACTIVE_FINALIZATION
    )
    assert reconcile(record, final_path, temp_path) is ReconcileStatus.ACTIVE


def test_active_with_modified_object_is_quarantined(tmp_path: Path) -> None:
    record, temp_path, final_path = run_staged_sequence(
        tmp_path / "mod", FailurePoint.AFTER_ACTIVE_FINALIZATION
    )
    # Corrupt the final object
    data = bytearray(final_path.read_bytes())
    data[0] ^= 0xFF
    final_path.write_bytes(bytes(data))
    assert reconcile(record, final_path, temp_path) is ReconcileStatus.QUARANTINED


def test_active_with_missing_object_is_quarantined(tmp_path: Path) -> None:
    record, temp_path, final_path = run_staged_sequence(
        tmp_path / "missing", FailurePoint.AFTER_ACTIVE_FINALIZATION
    )
    final_path.unlink()
    assert reconcile(record, final_path, temp_path) is ReconcileStatus.QUARANTINED


def test_pending_and_unpublished_is_safe_to_retry(tmp_path: Path) -> None:
    record, temp_path, final_path = run_staged_sequence(
        tmp_path / "pending", FailurePoint.BEFORE_TEMP_WRITE
    )
    assert reconcile(record, final_path, temp_path) is ReconcileStatus.SAFE_TO_RETRY


def test_pending_partial_temp_is_safe_to_retry(tmp_path: Path) -> None:
    record, temp_path, final_path = run_staged_sequence(
        tmp_path / "partial", FailurePoint.DURING_TEMP_WRITE
    )
    assert reconcile(record, final_path, temp_path) is ReconcileStatus.SAFE_TO_RETRY


def test_pending_with_published_final_is_quarantined(tmp_path: Path) -> None:
    record, temp_path, final_path = run_staged_sequence(
        tmp_path / "pub", FailurePoint.AFTER_REPLACE
    )
    assert reconcile(record, final_path, temp_path) is ReconcileStatus.QUARANTINED


def test_object_without_expected_state_is_not_silently_accepted(tmp_path: Path) -> None:
    final_path = tmp_path / "orphan.bin"
    final_path.write_bytes(b"opaque synthetic bytes for crash consistency test")
    assert reconcile(None, final_path, tmp_path / "missing.tmp") is ReconcileStatus.QUARANTINED


def test_object_without_expected_state_and_no_object_is_safe_to_retry(tmp_path: Path) -> None:
    assert (
        reconcile(None, tmp_path / "absent.bin", tmp_path / "also-absent.tmp")
        is ReconcileStatus.SAFE_TO_RETRY
    )


def test_directory_fsync_limitation_constant() -> None:
    assert (
        windows_directory_fsync_limitation()
        == "WINDOWS_DIRECTORY_FSYNC_NOT_PORTABLE_IN_PYTHON_SPIKE"
    )
