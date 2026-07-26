from document_intake.persistence import serialization as ser
from tests.domain.test_prepared_jpeg import artifact


def test_prepared_artifact_canonical_round_trip_has_no_bytes_or_paths() -> None:
    value = artifact()
    payload = ser.prepared_image_artifact_to_json(value)
    assert ser.prepared_image_artifact_from_json(payload) == value
    assert "jpeg_bytes" not in payload and "path" not in payload and "filename" not in payload


def test_real_repository_uow_round_trip_and_corruption_boundary(monkeypatch, tmp_path):  # type: ignore[no-untyped-def]
    import sqlite3

    from scripts import verify_pr011_jpeg as verifier

    from document_intake.persistence import database

    def open_sqlite(path, provider):  # type: ignore[no-untyped-def]
        del provider
        connection = sqlite3.connect(path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    monkeypatch.setattr(database, "_open_connection", open_sqlite)
    statuses = verifier._run_production(tmp_path)
    assert statuses[-4:] == ("audit=PASS", "rollback=PASS", "privacy=PASS", "result=PASS")
