from __future__ import annotations

from spikes.windows_encryption.crash_consistency_probe import (
    FailurePoint,
    ReconcileStatus,
    reconcile,
    run_staged_sequence,
    windows_directory_fsync_limitation,
)


def test_reconciliation_statuses_are_bounded(tmp_path) -> None:
    allowed = {ReconcileStatus.ACTIVE, ReconcileStatus.SAFE_TO_RETRY, ReconcileStatus.QUARANTINED}
    for failure in FailurePoint:
        record, temp_path, final_path = run_staged_sequence(tmp_path / failure.value, failure)
        assert reconcile(record, final_path, temp_path) in allowed
    assert (
        windows_directory_fsync_limitation()
        == "WINDOWS_DIRECTORY_FSYNC_NOT_PORTABLE_IN_PYTHON_SPIKE"
    )


def test_object_without_expected_state_is_not_silently_accepted(tmp_path) -> None:
    final_path = tmp_path / "orphan.bin"
    final_path.write_bytes(b"encrypted-orphan")
    assert reconcile(None, final_path, tmp_path / "missing.tmp") is ReconcileStatus.QUARANTINED
