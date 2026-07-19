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
