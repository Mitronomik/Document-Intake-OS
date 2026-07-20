# ruff: noqa: E501, F405, F403, SIM105
"""Encrypted SQLCipher database facade."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import Enum, auto
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self, TypeVar

from document_intake.application.dto.storage import StoredArtifactRecord
from document_intake.application.ports.persistence import DatabaseKeyProvider
from document_intake.domain import *
from document_intake.persistence import serialization as ser
from document_intake.persistence.errors import (
    PersistenceError,
    PersistenceErrorCode,
    translate_driver_error,
)
from document_intake.persistence.migrations import (
    APPLICATION_ID,
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
)

Connection = Any
RepositoryT = TypeVar("RepositoryT")


def _load_sqlcipher3() -> Any:
    try:
        return importlib.import_module("sqlcipher3")
    except ImportError:
        raise PersistenceError(PersistenceErrorCode.SQLCIPHER_UNAVAILABLE) from None


def _apply_raw_hex_key(connection: Connection, key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) != 32:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_INVALID)
    key_sql = "PRAGMA key = \"x'" + key.hex() + "'\""
    try:
        connection.execute(key_sql)
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_REJECTED) from None
    finally:
        key_sql = ""


def _fetch_one(connection: Connection, sql: str) -> Any:
    row = connection.execute(sql).fetchone()
    return None if row is None else row[0]


def _cipher_status_is_active(value: Any) -> bool:
    if isinstance(value, int) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        return value == "1"
    if isinstance(value, bytes):
        return value == b"1"
    return False


def _validate_key(provider: DatabaseKeyProvider) -> bytes:
    try:
        key = provider.get_database_key()
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_INVALID) from None
    if not isinstance(key, bytes) or len(key) != 32:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_INVALID)
    return key


def _open_connection(path: Path, provider: DatabaseKeyProvider) -> Connection:
    module = _load_sqlcipher3()
    key = _validate_key(provider)
    try:
        conn = module.connect(str(path), timeout=5.0, isolation_level=None)
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_OPEN_FAILED) from None
    try:
        _apply_raw_hex_key(conn, key)
        _harden_connection(conn)
    except PersistenceError:
        try:
            conn.close()
        finally:
            raise
    except Exception:
        try:
            conn.close()
        finally:
            raise PersistenceError(PersistenceErrorCode.DB_OPEN_FAILED) from None
    return conn


def _harden_connection(conn: Connection) -> None:
    try:
        cipher_version = _fetch_one(conn, "PRAGMA cipher_version")
        if not isinstance(cipher_version, str) or not cipher_version.strip():
            raise PersistenceError(PersistenceErrorCode.DB_ENCRYPTION_INACTIVE)

        status = _fetch_one(conn, "PRAGMA cipher_status")
        if not _cipher_status_is_active(status):
            raise PersistenceError(PersistenceErrorCode.DB_ENCRYPTION_INACTIVE)
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_REJECTED) from None

    try:
        # Wrong keys and corruption of the first/schema page are indistinguishable here.
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_KEY_REJECTED) from None

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA temp_store = MEMORY")
        journal = _fetch_one(conn, "PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        conn.execute("PRAGMA trusted_schema = OFF")
        if int(_fetch_one(conn, "PRAGMA foreign_keys")) != 1:
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        if int(_fetch_one(conn, "PRAGMA temp_store")) != 2:
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        if str(journal).lower() != "wal":
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        if int(_fetch_one(conn, "PRAGMA synchronous")) != 2:
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
        if int(_fetch_one(conn, "PRAGMA trusted_schema")) != 0:
            raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION)
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_PRAGMA_CONFIGURATION) from None

    try:
        rows = conn.execute("PRAGMA cipher_integrity_check").fetchall()
        if rows:
            raise PersistenceError(PersistenceErrorCode.DB_INTEGRITY_FAILED)
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.DB_INTEGRITY_FAILED) from None


def _table_count(conn: Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0])


def _validate_schema(conn: Connection) -> None:
    try:
        user_version = int(_fetch_one(conn, "PRAGMA user_version"))
        if user_version > CURRENT_SCHEMA_VERSION:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_VERSION_UNSUPPORTED)
        app_id = int(_fetch_one(conn, "PRAGMA application_id"))
        if user_version and app_id != APPLICATION_ID:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
        if user_version == 0:
            if _table_count(conn) != 0:
                raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
            return
        rows = tuple(
            conn.execute(
                "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
            ).fetchall()
        )
        if len(rows) != user_version:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
        expected_versions = tuple(range(1, user_version + 1))
        if tuple(int(row[0]) for row in rows) != expected_versions:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
        applied_migrations = MIGRATIONS[:user_version]
        if len(applied_migrations) != user_version:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
        for row, migration in zip(rows, applied_migrations, strict=True):
            if row[1] != migration.name:
                raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
            if row[2] != migration.checksum:
                raise PersistenceError(PersistenceErrorCode.SCHEMA_CHECKSUM_MISMATCH)
    except PersistenceError:
        raise
    except Exception:
        raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID) from None


def _apply_migrations(conn: Connection) -> None:
    _validate_schema(conn)
    current = int(_fetch_one(conn, "PRAGMA user_version"))
    for migration in MIGRATIONS[current:]:
        if migration.version != current + 1:
            raise PersistenceError(PersistenceErrorCode.SCHEMA_HISTORY_INVALID)
        try:
            conn.execute("BEGIN IMMEDIATE")
            if migration.version == 1:
                conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at_utc) VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                (migration.version, migration.name, migration.checksum),
            )
            conn.execute(f"PRAGMA user_version = {migration.version}")
            conn.execute("COMMIT")
            current = migration.version
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise PersistenceError(PersistenceErrorCode.MIGRATION_FAILED) from None
    _validate_schema(conn)


class EncryptedDatabase:
    def __init__(self, path: Path, key_provider: DatabaseKeyProvider) -> None:
        self._path = Path(path)
        self._key_provider = key_provider

    def __repr__(self) -> str:
        return "EncryptedDatabase(<redacted>)"

    def initialize(self) -> None:
        if not self._path.parent.exists():
            raise PersistenceError(PersistenceErrorCode.DB_PARENT_MISSING)
        existed = self._path.exists()
        conn: Connection | None = None
        try:
            conn = _open_connection(self._path, self._key_provider)
            _apply_migrations(conn)
        except PersistenceError:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None
            if not existed:
                self._cleanup_new_database()
            raise
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED) from None

    def _cleanup_new_database(self) -> None:
        for suffix in ("", "-wal", "-shm", "-journal"):
            target = Path(str(self._path) + suffix)
            try:
                if target.exists():
                    target.unlink()
            except OSError:
                pass

    def unit_of_work(self) -> SqlCipherUnitOfWork:
        return SqlCipherUnitOfWork(self._path, self._key_provider)


class _Repo:
    def __init__(
        self,
        uow: SqlCipherUnitOfWork,
        table: str,
        to_json: Callable[[Any], str],
        from_json: Callable[..., Any],
        payload_key: Callable[[Any], str],
    ) -> None:
        self._uow = uow
        self._table = table
        self._to_json = to_json
        self._from_json = from_json
        self._payload_key = payload_key

    def __repr__(self) -> str:
        return f"Repository({self._table})"

    @property
    def c(self) -> Connection:
        return self._uow._connection()

    def _execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
        *,
        duplicate_is_already_exists: bool = False,
    ) -> Any:
        try:
            return self.c.execute(sql, parameters)
        except PersistenceError:
            raise
        except Exception as error:
            transaction_check = getattr(self._uow, "_invalidate_if_transaction_lost", None)
            if callable(transaction_check):
                transaction_check()
            raise translate_driver_error(
                error, duplicate_is_already_exists=duplicate_is_already_exists
            ) from None

    def _fetchall(self, sql: str, parameters: tuple[Any, ...] = ()) -> tuple[Any, ...]:
        try:
            return tuple(self._execute(sql, parameters).fetchall())
        except PersistenceError:
            raise
        except Exception as error:
            raise translate_driver_error(error) from None

    def _deserialize(self, payload: str) -> Any:
        try:
            return self._from_json(payload)
        except PersistenceError:
            raise
        except Exception:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID) from None

    def _entity_from_payload_row(self, key: Any, payload: str) -> Any:
        entity = self._deserialize(payload)
        if self._payload_key(entity) != str(key):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity

    @contextmanager
    def _atomic_write(self) -> Iterator[None]:
        try:
            self._execute("SAVEPOINT repository_write")
        except PersistenceError as error:
            if error.code not in {
                PersistenceErrorCode.UOW_CLOSED,
                PersistenceErrorCode.UOW_STATE,
            }:
                self._uow._invalidate()
            raise
        try:
            yield
            self._execute("RELEASE SAVEPOINT repository_write")
        except BaseException:
            try:
                self._execute("ROLLBACK TO SAVEPOINT repository_write")
                self._execute("RELEASE SAVEPOINT repository_write")
            except PersistenceError:
                self._uow._invalidate()
                raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED) from None
            raise

    def _add(self, key: str, payload: str, extra: tuple[Any, ...] = ()) -> None:
        placeholders = ", ".join("?" for _ in (key, *extra, payload))
        cols = {
            "persons": "id, payload",
            "vehicles": "id, payload",
            "terminals": "code, is_active, payload",
            "identity_documents": "id, person_id, payload",
            "migration_documents": "id, person_id, related_passport_id, payload",
            "documents": "id, owner_kind, owner_id, payload",
            "field_candidates": "id, field_entity_id, field_key, confidence, payload",
        }[self._table]
        self._execute(
            f"INSERT INTO {self._table} ({cols}) VALUES ({placeholders})",
            (key, *extra, payload),
            duplicate_is_already_exists=True,
        )

    def _update(
        self,
        key: str,
        payload: str,
        where_col: str = "id",
        extra_set: str = "",
        params: tuple[Any, ...] = (),
    ) -> None:
        cur = self._execute(
            f"UPDATE {self._table} SET payload=?{extra_set} WHERE {where_col}=?",
            (payload, *params, key),
        )
        if cur.rowcount != 1:
            raise PersistenceError(PersistenceErrorCode.ENTITY_NOT_FOUND)

    def _get(self, key: Any, where_col: str = "id") -> Any | None:
        rows = self._fetchall(
            f"SELECT {where_col}, payload FROM {self._table} WHERE {where_col}=?", (key,)
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return self._entity_from_payload_row(rows[0][0], rows[0][1])


class PersonRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow, "persons", ser.person_to_json, ser.person_from_json, lambda x: str(x.id)
        )

    def add(self, person: Person) -> None:
        self._add(str(person.id), self._to_json(person))

    def get(self, entity_id: EntityId) -> Person | None:
        return self._get(str(entity_id))

    def update(self, person: Person) -> None:
        self._update(str(person.id), self._to_json(person))

    def list_all(self) -> tuple[Person, ...]:
        return tuple(
            self._entity_from_payload_row(r[0], r[1])
            for r in self._fetchall("SELECT id, payload FROM persons ORDER BY id")
        )


class IdentityRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "identity_documents",
            ser.identity_to_json,
            ser.identity_from_json,
            lambda x: str(x.id),
        )

    def add(self, document: IdentityDocument) -> None:
        self._add(str(document.id), self._to_json(document), (str(document.person_id),))

    def get(self, entity_id: EntityId) -> IdentityDocument | None:
        rows = self._fetchall(
            "SELECT id, person_id, payload FROM identity_documents WHERE id=?",
            (str(entity_id),),
        )
        return None if not rows else self._from_projection(rows[0])

    def update(self, document: IdentityDocument) -> None:
        self._update(
            str(document.id),
            self._to_json(document),
            extra_set=", person_id=?",
            params=(str(document.person_id),),
        )

    def list_by_person(self, person_id: EntityId) -> tuple[IdentityDocument, ...]:
        entities = tuple(
            self._from_projection(r)
            for r in self._fetchall(
                "SELECT id, person_id, payload FROM identity_documents ORDER BY id"
            )
        )
        return tuple(entity for entity in entities if entity.person_id == person_id)

    def _from_projection(self, row: tuple[str, str, str]) -> IdentityDocument:
        entity = self._entity_from_payload_row(row[0], row[2])
        if not isinstance(entity, IdentityDocument) or str(entity.person_id) != row[1]:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity


class MigrationRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "migration_documents",
            ser.migration_to_json,
            ser.migration_from_json,
            lambda x: str(x.id),
        )

    def add(self, document: MigrationDocument) -> None:
        self._add(
            str(document.id),
            self._to_json(document),
            (
                str(document.person_id),
                None if document.related_passport_id is None else str(document.related_passport_id),
            ),
        )

    def get(self, entity_id: EntityId) -> MigrationDocument | None:
        rows = self._fetchall(
            "SELECT id, person_id, related_passport_id, payload FROM migration_documents WHERE id=?",
            (str(entity_id),),
        )
        return None if not rows else self._from_projection(rows[0])

    def update(self, document: MigrationDocument) -> None:
        self._update(
            str(document.id),
            self._to_json(document),
            extra_set=", person_id=?, related_passport_id=?",
            params=(
                str(document.person_id),
                None if document.related_passport_id is None else str(document.related_passport_id),
            ),
        )

    def list_by_person(self, person_id: EntityId) -> tuple[MigrationDocument, ...]:
        entities = tuple(
            self._from_projection(r)
            for r in self._fetchall(
                "SELECT id, person_id, related_passport_id, payload "
                "FROM migration_documents ORDER BY id"
            )
        )
        return tuple(entity for entity in entities if entity.person_id == person_id)

    def _from_projection(self, row: tuple[str, str, str | None, str]) -> MigrationDocument:
        entity = self._entity_from_payload_row(row[0], row[3])
        if not isinstance(entity, MigrationDocument):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        related = None if entity.related_passport_id is None else str(entity.related_passport_id)
        if str(entity.person_id) != row[1] or related != row[2]:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity


class VehicleRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow, "vehicles", ser.vehicle_to_json, ser.vehicle_from_json, lambda x: str(x.id)
        )

    def add(self, vehicle: Vehicle) -> None:
        self._add(str(vehicle.id), self._to_json(vehicle))

    def get(self, entity_id: EntityId) -> Vehicle | None:
        return self._get(str(entity_id))

    def update(self, vehicle: Vehicle) -> None:
        self._update(str(vehicle.id), self._to_json(vehicle))

    def list_all(self) -> tuple[Vehicle, ...]:
        return tuple(
            self._entity_from_payload_row(r[0], r[1])
            for r in self._fetchall("SELECT id, payload FROM vehicles ORDER BY id")
        )


class TerminalRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "terminals",
            ser.terminal_to_json,
            ser.terminal_from_json,
            lambda x: x.code.value,
        )

    def add(self, terminal: Terminal) -> None:
        self._add(terminal.code.value, self._to_json(terminal), (1 if terminal.is_active else 0,))

    def get(self, code: TerminalCode) -> Terminal | None:
        rows = self._fetchall(
            "SELECT code, is_active, payload FROM terminals WHERE code=?", (code.value,)
        )
        return None if not rows else self._from_projection(rows[0])

    def update(self, terminal: Terminal) -> None:
        self._update(
            terminal.code.value,
            self._to_json(terminal),
            "code",
            ", is_active=?",
            (1 if terminal.is_active else 0,),
        )

    def list_active(self) -> tuple[Terminal, ...]:
        entities = tuple(
            self._from_projection(r)
            for r in self._fetchall("SELECT code, is_active, payload FROM terminals ORDER BY code")
        )
        return tuple(entity for entity in entities if entity.is_active)

    def _from_projection(self, row: tuple[str, int, str]) -> Terminal:
        entity = self._entity_from_payload_row(row[0], row[2])
        if not isinstance(entity, Terminal) or int(entity.is_active) != row[1]:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity


class DocumentRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow, "documents", ser.document_to_json, ser.document_from_json, lambda x: str(x.id)
        )

    def add(self, document: Document) -> None:
        owner = document.owner_ref
        with self._atomic_write():
            self._add(
                str(document.id),
                self._to_json(document),
                (
                    None if owner is None else owner.owner_kind.value,
                    None if owner is None else str(owner.owner_id),
                ),
            )
            self._replace_sides(document)

    def get(self, entity_id: EntityId) -> Document | None:
        return self._get_document(str(entity_id))

    def update(self, document: Document) -> None:
        owner = document.owner_ref
        with self._atomic_write():
            self._update(
                str(document.id),
                self._to_json(document),
                extra_set=", owner_kind=?, owner_id=?",
                params=(
                    None if owner is None else owner.owner_kind.value,
                    None if owner is None else str(owner.owner_id),
                ),
            )
            self._execute("DELETE FROM document_sides WHERE document_id=?", (str(document.id),))
            self._replace_sides(document)

    def _replace_sides(self, document: Document) -> None:
        for i, side_id in enumerate(document.side_ids):
            self._execute(
                "INSERT INTO document_sides(document_id, order_index, side_id) VALUES (?,?,?)",
                (str(document.id), i, str(side_id)),
            )

    def _get_document(self, document_id: str) -> Document | None:
        rows = self._fetchall(
            "SELECT id, owner_kind, owner_id, payload FROM documents WHERE id=?",
            (document_id,),
        )
        if not rows:
            return None
        row = rows[0]
        entity = self._entity_from_payload_row(row[0], row[3])
        if not isinstance(entity, Document):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        owner = entity.owner_ref
        expected_owner = (
            None if owner is None else owner.owner_kind.value,
            None if owner is None else str(owner.owner_id),
        )
        if expected_owner != (row[1], row[2]):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        side_rows = self._fetchall(
            "SELECT order_index, side_id FROM document_sides WHERE document_id=? ORDER BY order_index",
            (document_id,),
        )
        expected_sides = tuple(
            (index, str(side_id)) for index, side_id in enumerate(entity.side_ids)
        )
        if side_rows != expected_sides:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity

    def list_by_owner(self, owner_ref: OwnerRef) -> tuple[Document, ...]:
        ids = tuple(row[0] for row in self._fetchall("SELECT id FROM documents ORDER BY id"))
        result: list[Document] = []
        for document_id in ids:
            entity = self._get_document(document_id)
            if entity is None:
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
            if entity.owner_ref == owner_ref:
                result.append(entity)
        return tuple(result)


class CandidateRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "field_candidates",
            ser.candidate_to_json,
            ser.candidate_from_json,
            lambda x: str(x.id),
        )

    def add(self, candidate: FieldCandidate) -> None:
        with self._atomic_write():
            self._add(
                str(candidate.id),
                self._to_json(candidate),
                (
                    str(candidate.field_ref.entity_id),
                    candidate.field_ref.field_key.value,
                    str(candidate.confidence.value),
                ),
            )
            self._replace_validation_results(candidate)

    def get(self, entity_id: EntityId) -> FieldCandidate | None:
        return self._get_candidate(str(entity_id))

    def update(self, candidate: FieldCandidate) -> None:
        with self._atomic_write():
            self._update(
                str(candidate.id),
                self._to_json(candidate),
                extra_set=", field_entity_id=?, field_key=?, confidence=?",
                params=(
                    str(candidate.field_ref.entity_id),
                    candidate.field_ref.field_key.value,
                    str(candidate.confidence.value),
                ),
            )
            self._execute(
                "DELETE FROM field_candidate_validation_results WHERE candidate_id=?",
                (str(candidate.id),),
            )
            self._replace_validation_results(candidate)

    def _replace_validation_results(self, candidate: FieldCandidate) -> None:
        for index, result in enumerate(candidate.validation_results):
            self._execute(
                "INSERT INTO field_candidate_validation_results(candidate_id, order_index, result) VALUES (?,?,?)",
                (str(candidate.id), index, result.value),
            )

    def _get_candidate(self, candidate_id: str) -> FieldCandidate | None:
        rows = self._fetchall(
            "SELECT id, field_entity_id, field_key, confidence, payload FROM field_candidates WHERE id=?",
            (candidate_id,),
        )
        if not rows:
            return None
        row = rows[0]
        entity = self._entity_from_payload_row(row[0], row[4])
        if not isinstance(entity, FieldCandidate):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        field_ref = entity.field_ref
        if (
            str(field_ref.entity_id) != row[1]
            or field_ref.field_key.value != row[2]
            or str(entity.confidence.value) != row[3]
        ):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        validation_rows = self._fetchall(
            "SELECT order_index, result FROM field_candidate_validation_results WHERE candidate_id=? ORDER BY order_index",
            (candidate_id,),
        )
        expected = tuple(
            (index, result.value) for index, result in enumerate(entity.validation_results)
        )
        if validation_rows != expected:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity

    def list_for_field(self, field_ref: FieldRef) -> tuple[FieldCandidate, ...]:
        ids = tuple(row[0] for row in self._fetchall("SELECT id FROM field_candidates ORDER BY id"))
        result: list[FieldCandidate] = []
        for candidate_id in ids:
            entity = self._get_candidate(candidate_id)
            if entity is None:
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
            if entity.field_ref == field_ref:
                result.append(entity)
        return tuple(result)


class ApplicationRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "applications",
            ser.application_to_json,
            ser.application_from_json,
            lambda x: str(x.id),
        )

    def add(self, application: Application) -> None:
        with self._atomic_write():
            self._execute(
                "INSERT INTO applications(id, batch_id, terminal_code, status, created_by_actor_id, created_by_actor_kind, created_at_utc, updated_at_utc, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*ser.application_columns(application), self._to_json(application)),
                duplicate_is_already_exists=True,
            )
            self._children(application)

    def get(self, entity_id: EntityId) -> Application | None:
        return self._get_application(str(entity_id))

    def _get_application(self, application_id: str) -> Application | None:
        rows = self._fetchall(
            "SELECT id, batch_id, terminal_code, status, created_by_actor_id, created_by_actor_kind, created_at_utc, updated_at_utc, payload FROM applications WHERE id=?",
            (application_id,),
        )
        if not rows:
            return None
        row = rows[0]
        entity = self._entity_from_payload_row(row[0], row[8])
        if not isinstance(entity, Application) or tuple(row[:8]) != ser.application_columns(entity):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        self._validate_assignments(
            entity,
            self._fetchall(
                "SELECT order_index, person_id, tractor_id, trailer_id, payload FROM application_assignments WHERE application_id=? ORDER BY order_index",
                (application_id,),
            ),
        )
        self._validate_verified_fields(
            entity,
            self._fetchall(
                "SELECT order_index, field_entity_id, field_key, source_candidate_id, payload FROM application_verified_fields WHERE application_id=? ORDER BY order_index",
                (application_id,),
            ),
        )
        self._validate_issues(
            entity,
            self._fetchall(
                "SELECT order_index, payload FROM application_validation_issues WHERE application_id=? ORDER BY order_index",
                (application_id,),
            ),
        )
        return entity

    def update(self, application: Application) -> None:
        application_id = str(application.id)
        with self._atomic_write():
            cur = self._execute(
                "UPDATE applications SET batch_id=?, terminal_code=?, status=?, created_by_actor_id=?, created_by_actor_kind=?, created_at_utc=?, updated_at_utc=?, payload=? WHERE id=?",
                (
                    *ser.application_columns(application)[1:],
                    self._to_json(application),
                    application_id,
                ),
            )
            if cur.rowcount != 1:
                raise PersistenceError(PersistenceErrorCode.ENTITY_NOT_FOUND)
            self._execute(
                "DELETE FROM application_assignments WHERE application_id=?", (application_id,)
            )
            self._execute(
                "DELETE FROM application_verified_fields WHERE application_id=?",
                (application_id,),
            )
            self._execute(
                "DELETE FROM application_validation_issues WHERE application_id=?",
                (application_id,),
            )
            self._children(application)

    def _children(self, a: Application) -> None:
        for i, x in enumerate(a.assignments):
            self._execute(
                "INSERT INTO application_assignments(application_id, order_index, person_id, tractor_id, trailer_id, payload) VALUES (?,?,?,?,?,?)",
                (
                    str(a.id),
                    i,
                    str(x.person_id),
                    str(x.tractor_id),
                    None if x.trailer_id is None else str(x.trailer_id),
                    ser.dumps(ser._assignment_to_dict(x)),
                ),
            )
        for index, verified_field in enumerate(a.verified_fields):
            self._execute(
                "INSERT INTO application_verified_fields(application_id, order_index, field_entity_id, field_key, source_candidate_id, payload) VALUES (?,?,?,?,?,?)",
                (
                    str(a.id),
                    index,
                    str(verified_field.field_ref.entity_id),
                    verified_field.field_ref.field_key.value,
                    None
                    if verified_field.source_candidate_id is None
                    else str(verified_field.source_candidate_id),
                    ser.dumps(ser._verified_to_dict(verified_field)),
                ),
            )
        for issue_index, issue in enumerate(a.validation_report.issues):
            self._execute(
                "INSERT INTO application_validation_issues(application_id, order_index, payload) VALUES (?,?,?)",
                (str(a.id), issue_index, ser.dumps(ser._issue_to_dict(issue))),
            )

    def _validate_assignments(self, application: Application, rows: tuple[Any, ...]) -> None:
        if len(rows) != len(application.assignments):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        for index, (expected, row) in enumerate(zip(application.assignments, rows, strict=True)):
            actual = ser.assignment_from_json(row[4])
            expected_projection = (
                index,
                str(expected.person_id),
                str(expected.tractor_id),
                None if expected.trailer_id is None else str(expected.trailer_id),
            )
            if actual != expected or tuple(row[:4]) != expected_projection:
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)

    def _validate_verified_fields(self, application: Application, rows: tuple[Any, ...]) -> None:
        if len(rows) != len(application.verified_fields):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        for index, (expected, row) in enumerate(
            zip(application.verified_fields, rows, strict=True)
        ):
            actual = ser.verified_field_from_json(row[4])
            expected_projection = (
                index,
                str(expected.field_ref.entity_id),
                expected.field_ref.field_key.value,
                None if expected.source_candidate_id is None else str(expected.source_candidate_id),
            )
            if actual != expected or tuple(row[:4]) != expected_projection:
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)

    def _validate_issues(self, application: Application, rows: tuple[Any, ...]) -> None:
        issues = application.validation_report.issues
        if len(rows) != len(issues):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        for index, (expected, row) in enumerate(zip(issues, rows, strict=True)):
            actual = ser.validation_issue_from_json(row[1])
            if actual != expected or row[0] != index:
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)


class SnapshotRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "application_snapshots",
            ser.snapshot_to_json,
            ser.snapshot_from_json,
            lambda x: str(x.id),
        )

    def add(self, snapshot: ApplicationSnapshot) -> None:
        with self._atomic_write():
            self._execute(
                "INSERT INTO application_snapshots(id, application_id, terminal_code, template_version, rules_version, created_by_actor_id, created_by_actor_kind, created_at_utc, payload_json, sha256, expected_artifact_ref_count, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    *ser.snapshot_columns(snapshot),
                    len(snapshot.document_artifact_refs),
                    self._to_json(snapshot),
                ),
                duplicate_is_already_exists=True,
            )
            for index, artifact_ref in enumerate(snapshot.document_artifact_refs):
                self._execute(
                    "INSERT INTO application_snapshot_artifact_refs(snapshot_id, order_index, artifact_ref) VALUES (?,?,?)",
                    (str(snapshot.id), index, str(artifact_ref)),
                )

    def get(self, entity_id: EntityId) -> ApplicationSnapshot | None:
        return self._get_snapshot(str(entity_id))

    def _get_snapshot(self, snapshot_id: str) -> ApplicationSnapshot | None:
        rows = self._fetchall(
            "SELECT id, application_id, terminal_code, template_version, rules_version, created_by_actor_id, created_by_actor_kind, created_at_utc, payload_json, sha256, expected_artifact_ref_count, payload FROM application_snapshots WHERE id=?",
            (snapshot_id,),
        )
        if not rows:
            return None
        row = rows[0]
        entity = self._entity_from_payload_row(row[0], row[11])
        if not isinstance(entity, ApplicationSnapshot):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        if tuple(row[:10]) != ser.snapshot_columns(entity):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        artifact_rows = self._fetchall(
            "SELECT order_index, artifact_ref FROM application_snapshot_artifact_refs WHERE snapshot_id=? ORDER BY order_index",
            (snapshot_id,),
        )
        expected_count = len(entity.document_artifact_refs)
        expected_rows = tuple(
            (index, str(artifact_ref))
            for index, artifact_ref in enumerate(entity.document_artifact_refs)
        )
        if row[10] != expected_count or artifact_rows != expected_rows:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity

    def list_by_application(self, application_id: EntityId) -> tuple[ApplicationSnapshot, ...]:
        ids = tuple(
            r[0]
            for r in self._fetchall(
                "SELECT id FROM application_snapshots ORDER BY created_at_utc, id"
            )
        )
        snapshots: list[ApplicationSnapshot] = []
        for stored_snapshot_id in ids:
            stored = self._get_snapshot(stored_snapshot_id)
            if stored is None:
                raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
            if stored.application_id == application_id:
                snapshots.append(stored)
        return tuple(snapshots)


class StoredArtifactRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "stored_artifacts",
            ser.stored_artifact_to_json,
            ser.stored_artifact_from_json,
            lambda x: str(x.artifact_id),
        )

    def add(self, record: StoredArtifactRecord) -> None:
        payload = self._to_json(record)
        self._execute(
            "INSERT INTO stored_artifacts("
            "artifact_id, artifact_kind, object_generation, plaintext_length, "
            "plaintext_sha256, ciphertext_sha256, key_version, storage_format_version, "
            "created_at, canonical_payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (*ser.stored_artifact_columns(record), payload),
            duplicate_is_already_exists=True,
        )

    def get(self, artifact_id: EntityId) -> StoredArtifactRecord | None:
        rows = self._fetchall(
            "SELECT artifact_id, artifact_kind, object_generation, plaintext_length, "
            "plaintext_sha256, ciphertext_sha256, key_version, storage_format_version, "
            "created_at, canonical_payload FROM stored_artifacts WHERE artifact_id=?",
            (str(artifact_id),),
        )
        return None if not rows else self._from_projection(rows[0])

    def list_all(self) -> tuple[StoredArtifactRecord, ...]:
        return tuple(
            self._from_projection(row)
            for row in self._fetchall(
                "SELECT artifact_id, artifact_kind, object_generation, plaintext_length, "
                "plaintext_sha256, ciphertext_sha256, key_version, storage_format_version, "
                "created_at, canonical_payload FROM stored_artifacts ORDER BY artifact_id"
            )
        )

    def _from_projection(self, row: tuple[Any, ...]) -> StoredArtifactRecord:
        entity = self._entity_from_payload_row(row[0], row[9])
        if not isinstance(entity, StoredArtifactRecord):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        if tuple(row[:9]) != ser.stored_artifact_columns(entity):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity


class AuditEventRepo(_Repo):
    def __init__(self, uow: SqlCipherUnitOfWork) -> None:
        super().__init__(
            uow,
            "audit_events",
            ser.audit_event_to_json,
            ser.audit_event_from_json,
            lambda x: str(x.event_id),
        )

    def add(self, event: AuditEvent) -> None:
        if self.get(event.event_id) is not None:
            raise PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        with self._atomic_write():
            self._execute(
                "INSERT INTO audit_events(event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type, subject_id, field_key, before_classification, before_was_present, before_display_value, after_classification, after_was_present, after_display_value, reason_code, correlation_id, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*ser.audit_event_columns(event), self._to_json(event)),
                duplicate_is_already_exists=True,
            )

    def get(self, event_id: EntityId) -> AuditEvent | None:
        rows = self._fetchall(
            "SELECT event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type, subject_id, field_key, before_classification, before_was_present, before_display_value, after_classification, after_was_present, after_display_value, reason_code, correlation_id, payload FROM audit_events WHERE event_id=?",
            (str(event_id),),
        )
        return None if not rows else self._from_projection(rows[0])

    def list_for_subject(
        self, subject_type: AuditSubjectType, subject_id: EntityId
    ) -> tuple[AuditEvent, ...]:
        if not isinstance(subject_type, AuditSubjectType) or not isinstance(subject_id, EntityId):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return tuple(
            event
            for event in self._list_validated_ordered()
            if event.subject_type is subject_type and event.subject_id == subject_id
        )

    def list_by_correlation(self, correlation_id: EntityId) -> tuple[AuditEvent, ...]:
        if not isinstance(correlation_id, EntityId):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return tuple(
            event
            for event in self._list_validated_ordered()
            if event.correlation_id == correlation_id
        )

    def _list_validated_ordered(self) -> tuple[AuditEvent, ...]:
        return tuple(
            self._from_projection(row)
            for row in self._fetchall(
                "SELECT event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type, subject_id, field_key, before_classification, before_was_present, before_display_value, after_classification, after_was_present, after_display_value, reason_code, correlation_id, payload FROM audit_events ORDER BY occurred_at_utc, event_id"
            )
        )

    def _from_projection(self, row: tuple[Any, ...]) -> AuditEvent:
        entity = self._deserialize(row[16])
        if not isinstance(entity, AuditEvent) or ser.audit_event_columns(entity) != tuple(row[:16]):
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        if ser.audit_event_to_json(entity) != row[16]:
            raise PersistenceError(PersistenceErrorCode.PERSISTED_DATA_INVALID)
        return entity


class _UowState(Enum):
    NEW = auto()
    ACTIVE = auto()
    COMMITTED = auto()
    ROLLED_BACK = auto()
    CLOSED = auto()


class SqlCipherUnitOfWork:
    def __init__(self, path: Path, key_provider: DatabaseKeyProvider) -> None:
        self._path = path
        self._key_provider = key_provider
        self._conn: Connection | None = None
        self._state = _UowState.NEW
        self._persons: PersonRepo | None = None
        self._identity_documents: IdentityRepo | None = None
        self._migration_documents: MigrationRepo | None = None
        self._vehicles: VehicleRepo | None = None
        self._terminals: TerminalRepo | None = None
        self._documents: DocumentRepo | None = None
        self._field_candidates: CandidateRepo | None = None
        self._applications: ApplicationRepo | None = None
        self._application_snapshots: SnapshotRepo | None = None
        self._stored_artifacts: StoredArtifactRepo | None = None
        self._audit_events: AuditEventRepo | None = None

    def __repr__(self) -> str:
        return "SqlCipherUnitOfWork(<redacted>)"

    def _connection(self) -> Connection:
        if self._state is _UowState.CLOSED:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        if self._state is not _UowState.ACTIVE or self._conn is None:
            raise PersistenceError(PersistenceErrorCode.UOW_STATE)
        return self._conn

    def _repository(self, repository: RepositoryT | None) -> RepositoryT:
        if self._state is _UowState.CLOSED:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        if self._state is not _UowState.ACTIVE or repository is None:
            raise PersistenceError(PersistenceErrorCode.UOW_STATE)
        return repository

    @property
    def persons(self) -> PersonRepo:
        return self._repository(self._persons)

    @property
    def identity_documents(self) -> IdentityRepo:
        return self._repository(self._identity_documents)

    @property
    def migration_documents(self) -> MigrationRepo:
        return self._repository(self._migration_documents)

    @property
    def vehicles(self) -> VehicleRepo:
        return self._repository(self._vehicles)

    @property
    def terminals(self) -> TerminalRepo:
        return self._repository(self._terminals)

    @property
    def documents(self) -> DocumentRepo:
        return self._repository(self._documents)

    @property
    def field_candidates(self) -> CandidateRepo:
        return self._repository(self._field_candidates)

    @property
    def applications(self) -> ApplicationRepo:
        return self._repository(self._applications)

    @property
    def application_snapshots(self) -> SnapshotRepo:
        return self._repository(self._application_snapshots)

    @property
    def stored_artifacts(self) -> StoredArtifactRepo:
        return self._repository(self._stored_artifacts)

    @property
    def audit_events(self) -> AuditEventRepo:
        return self._repository(self._audit_events)

    def _construct_repositories(self) -> None:
        self._persons = PersonRepo(self)
        self._identity_documents = IdentityRepo(self)
        self._migration_documents = MigrationRepo(self)
        self._vehicles = VehicleRepo(self)
        self._terminals = TerminalRepo(self)
        self._documents = DocumentRepo(self)
        self._field_candidates = CandidateRepo(self)
        self._applications = ApplicationRepo(self)
        self._application_snapshots = SnapshotRepo(self)
        self._stored_artifacts = StoredArtifactRepo(self)
        self._audit_events = AuditEventRepo(self)

    def _invalidate(self) -> None:
        connection = self._conn
        self._conn = None
        self._state = _UowState.CLOSED
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def _invalidate_if_transaction_lost(self) -> None:
        if self._state is not _UowState.ACTIVE or self._conn is None:
            return
        try:
            transaction_active = bool(self._conn.in_transaction)
        except Exception:
            self._invalidate()
            return
        if not transaction_active:
            self._invalidate()

    def _close_after_failed_entry(self, *, transaction_started: bool) -> None:
        if self._conn is not None:
            if transaction_started:
                try:
                    self._conn.execute("ROLLBACK")
                except Exception:
                    pass
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self._state = _UowState.CLOSED

    def __enter__(self) -> Self:
        if self._state is _UowState.CLOSED:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        if self._state is not _UowState.NEW:
            raise PersistenceError(PersistenceErrorCode.UOW_STATE)
        transaction_started = False
        try:
            self._conn = _open_connection(self._path, self._key_provider)
            _validate_schema(self._conn)
            if int(_fetch_one(self._conn, "PRAGMA user_version")) != CURRENT_SCHEMA_VERSION:
                raise PersistenceError(PersistenceErrorCode.SCHEMA_VERSION_UNSUPPORTED)
            self._conn.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._construct_repositories()
        except PersistenceError:
            self._close_after_failed_entry(transaction_started=transaction_started)
            raise
        except Exception:
            self._close_after_failed_entry(transaction_started=transaction_started)
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED) from None
        self._state = _UowState.ACTIVE
        return self

    def commit(self) -> None:
        if self._state is _UowState.CLOSED:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        if self._state is not _UowState.ACTIVE or self._conn is None:
            raise PersistenceError(PersistenceErrorCode.UOW_STATE)
        try:
            self._conn.execute("COMMIT")
        except Exception:
            self._invalidate()
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED) from None
        self._state = _UowState.COMMITTED

    def rollback(self) -> None:
        if self._state is _UowState.CLOSED:
            raise PersistenceError(PersistenceErrorCode.UOW_CLOSED)
        if self._state is not _UowState.ACTIVE or self._conn is None:
            raise PersistenceError(PersistenceErrorCode.UOW_STATE)
        try:
            self._conn.execute("ROLLBACK")
        except Exception:
            self._invalidate()
            raise PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED) from None
        self._state = _UowState.ROLLED_BACK

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            if self._conn is not None and self._state is _UowState.ACTIVE:
                try:
                    self._conn.execute("ROLLBACK")
                except Exception:
                    pass
                self._state = _UowState.ROLLED_BACK
        finally:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
            self._conn = None
            self._state = _UowState.CLOSED
        return False
