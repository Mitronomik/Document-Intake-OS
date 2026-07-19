"""Safe persistence exceptions."""

from __future__ import annotations

from enum import StrEnum


class PersistenceErrorCode(StrEnum):
    SQLCIPHER_UNAVAILABLE = "ERR_SQLCIPHER_UNAVAILABLE"
    DB_KEY_INVALID = "ERR_DB_KEY_INVALID"
    DB_PARENT_MISSING = "ERR_DB_PARENT_MISSING"
    DB_OPEN_FAILED = "ERR_DB_OPEN_FAILED"
    DB_KEY_REJECTED = "ERR_DB_KEY_REJECTED"
    DB_ENCRYPTION_INACTIVE = "ERR_DB_ENCRYPTION_INACTIVE"
    DB_INTEGRITY_FAILED = "ERR_DB_INTEGRITY_FAILED"
    DB_PRAGMA_CONFIGURATION = "ERR_DB_PRAGMA_CONFIGURATION"
    SCHEMA_VERSION_UNSUPPORTED = "ERR_SCHEMA_VERSION_UNSUPPORTED"
    SCHEMA_HISTORY_INVALID = "ERR_SCHEMA_HISTORY_INVALID"
    SCHEMA_CHECKSUM_MISMATCH = "ERR_SCHEMA_CHECKSUM_MISMATCH"
    MIGRATION_FAILED = "ERR_MIGRATION_FAILED"
    UOW_CLOSED = "ERR_UOW_CLOSED"
    UOW_STATE = "ERR_UOW_STATE"
    ENTITY_ALREADY_EXISTS = "ERR_ENTITY_ALREADY_EXISTS"
    ENTITY_NOT_FOUND = "ERR_ENTITY_NOT_FOUND"
    PERSISTENCE_CONSTRAINT = "ERR_PERSISTENCE_CONSTRAINT"
    PERSISTED_DATA_INVALID = "ERR_PERSISTED_DATA_INVALID"
    PERSISTENCE_UNEXPECTED = "ERR_PERSISTENCE_UNEXPECTED"


class PersistenceError(Exception):
    """Fail-closed persistence exception with stable non-sensitive text."""

    def __init__(self, code: PersistenceErrorCode) -> None:
        self.code = code
        super().__init__(code.value)

    def __repr__(self) -> str:
        return f"PersistenceError(code={self.code.value})"


_DUPLICATE_CONSTRAINT_CODES = frozenset({1555, 2067})
_INTEGRITY_CONSTRAINT_BASE_CODE = 19


def translate_driver_error(
    error: BaseException, *, duplicate_is_already_exists: bool = False
) -> PersistenceError:
    """Translate a DB-API failure without exposing its message or parameters."""

    code = getattr(error, "sqlite_errorcode", None)
    class_name = type(error).__name__
    is_integrity = class_name == "IntegrityError" or (
        isinstance(code, int) and code & 0xFF == _INTEGRITY_CONSTRAINT_BASE_CODE
    )
    if is_integrity:
        is_duplicate = code in _DUPLICATE_CONSTRAINT_CODES
        if not is_duplicate and duplicate_is_already_exists:
            normalized = str(error).casefold()
            is_duplicate = "unique constraint" in normalized or "primary key" in normalized
        if is_duplicate and duplicate_is_already_exists:
            return PersistenceError(PersistenceErrorCode.ENTITY_ALREADY_EXISTS)
        return PersistenceError(PersistenceErrorCode.PERSISTENCE_CONSTRAINT)
    return PersistenceError(PersistenceErrorCode.PERSISTENCE_UNEXPECTED)
