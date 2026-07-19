from __future__ import annotations

from pathlib import Path

import pytest

from document_intake.persistence.database import (
    EncryptedDatabase,
    _apply_raw_hex_key,
    _validate_key,
)
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


class Provider:
    def __init__(self, value: object) -> None:
        self.value = value
        self.calls = 0

    def get_database_key(self) -> object:
        self.calls += 1
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value


class Conn:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)


def test_key_provider_requires_exact_bytes_and_is_called_once() -> None:
    provider = Provider(b"a" * 32)
    assert _validate_key(provider) == b"a" * 32
    assert provider.calls == 1
    for value in ("a" * 32, b"short", b"b" * 33, RuntimeError("unsafe raw")):
        with pytest.raises(PersistenceError) as excinfo:
            _validate_key(Provider(value))  # type: ignore[arg-type]
        assert excinfo.value.code == PersistenceErrorCode.DB_KEY_INVALID
        assert "unsafe raw" not in str(excinfo.value)


def test_raw_key_helper_is_private_and_does_not_return_key_material() -> None:
    conn = Conn()
    assert _apply_raw_hex_key(conn, b"k" * 32) is None
    assert len(conn.statements) == 1
    assert conn.statements[0].startswith("PRAGMA key")
    with pytest.raises(PersistenceError) as excinfo:
        _apply_raw_hex_key(conn, b"short")
    assert excinfo.value.code == PersistenceErrorCode.DB_KEY_INVALID


def test_parent_missing_fails_without_path_leak(tmp_path: Path) -> None:
    db = EncryptedDatabase(tmp_path / "missing" / "db.sqlite", Provider(b"k" * 32))
    with pytest.raises(PersistenceError) as excinfo:
        db.initialize()
    assert excinfo.value.code == PersistenceErrorCode.DB_PARENT_MISSING
    assert str(tmp_path) not in str(excinfo.value)
    assert str(tmp_path) not in repr(db)


class ClosingConn:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.closed = False
        path.write_text("new-db")
        Path(str(path) + "-wal").write_text("wal")
        Path(str(path) + "-shm").write_text("shm")
        Path(str(path) + "-journal").write_text("journal")

    def close(self) -> None:
        self.closed = True


def test_failed_new_database_cleanup_closes_and_removes_only_sidecars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index in range(3):
        db_path = tmp_path / f"new-{index}.db"
        unrelated = tmp_path / f"new-{index}.db-unrelated"
        unrelated.write_text("keep")
        directory_marker = tmp_path / f"marker-{index}.txt"
        directory_marker.write_text("keep-dir")
        made: list[ClosingConn] = []

        def open_conn(
            path: Path, provider: Provider, made_connections: list[ClosingConn] = made
        ) -> ClosingConn:
            _ = provider
            conn = ClosingConn(path)
            made_connections.append(conn)
            return conn

        def fail_migration(conn: ClosingConn) -> None:
            _ = conn
            raise PersistenceError(PersistenceErrorCode.MIGRATION_FAILED)

        monkeypatch.setattr("document_intake.persistence.database._open_connection", open_conn)
        monkeypatch.setattr(
            "document_intake.persistence.database._apply_migrations", fail_migration
        )
        with pytest.raises(PersistenceError) as excinfo:
            EncryptedDatabase(db_path, Provider(b"k" * 32)).initialize()
        assert excinfo.value.code == PersistenceErrorCode.MIGRATION_FAILED
        assert made and made[0].closed
        assert not db_path.exists()
        assert not Path(str(db_path) + "-wal").exists()
        assert not Path(str(db_path) + "-shm").exists()
        assert not Path(str(db_path) + "-journal").exists()
        assert unrelated.read_text() == "keep"
        assert directory_marker.read_text() == "keep-dir"
        assert str(db_path) not in str(excinfo.value)


def test_existing_database_is_never_deleted_after_initialize_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "existing.db"
    db_path.write_text("existing")
    Path(str(db_path) + "-wal").write_text("existing-wal")

    def open_conn(path: Path, provider: Provider) -> ClosingConn:
        _ = provider
        conn = ClosingConn(path)
        path.write_text("existing")
        return conn

    def fail_migration(conn: ClosingConn) -> None:
        _ = conn
        raise PersistenceError(PersistenceErrorCode.MIGRATION_FAILED)

    monkeypatch.setattr("document_intake.persistence.database._open_connection", open_conn)
    monkeypatch.setattr("document_intake.persistence.database._apply_migrations", fail_migration)
    with pytest.raises(PersistenceError):
        EncryptedDatabase(db_path, Provider(b"k" * 32)).initialize()
    assert db_path.read_text() == "existing"
    assert Path(str(db_path) + "-wal").exists()
    assert tmp_path.exists()
