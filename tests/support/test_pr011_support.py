import sqlite3

import pytest

from tests.support import pr011


def test_deterministic_ids_timestamps_and_domain_entity() -> None:
    assert pr011.entity_id(1) == pr011.entity_id(1)
    assert pr011.STAMP.utcoffset().total_seconds() == 0
    assert pr011.prepared_artifact().created_at == pr011.STAMP


def test_schema_v6_builder_enables_and_preserves_foreign_keys() -> None:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    snapshot = pr011.build_schema_v6(connection)
    assert connection.execute("PRAGMA user_version").fetchone() == (6,)
    pr011.assert_foreign_keys(connection)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert len(snapshot.rows_by_table["schema_migrations"]) == 6


def test_commit_failure_occurs_before_delegated_commit() -> None:
    class Delegated:
        committed = False

        def commit(self) -> None:
            self.committed = True

    delegated = Delegated()
    with pytest.raises(RuntimeError, match="SYNTHETIC_COMMIT_FAILURE"):
        pr011.CommitFailureUow(delegated).commit()
    assert not delegated.committed


def test_call_recorder_preserves_order() -> None:
    recorder = pr011.CallRecorder([])
    recorder.record("first")
    recorder.record("second")
    assert recorder.calls == ["first", "second"]
