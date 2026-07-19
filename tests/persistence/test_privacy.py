from __future__ import annotations

import logging
from pathlib import Path

import pytest
from tests.persistence.test_repositories import FakeUow, migrated_connection, person

from document_intake.persistence.database import EncryptedDatabase, SqlCipherUnitOfWork
from document_intake.persistence.errors import PersistenceError, PersistenceErrorCode


class Provider:
    def get_database_key(self) -> bytes:
        return b"z" * 32


def test_safe_repr_errors_and_logs_do_not_leak_sensitive_values(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level(logging.DEBUG)
    db_path = tmp_path / "fictional-secret-name.db"
    key_hex = (b"z" * 32).hex()
    passport = "PX000012345"
    vin = "VIN00000000000001"
    phone = "000123456789"
    address = "Synthetic Address, Apt Quote"
    payload = "payload-secret-content"

    db = EncryptedDatabase(db_path, Provider())
    uow = SqlCipherUnitOfWork(db_path, Provider())
    repo = FakeUow(migrated_connection())
    error = PersistenceError(PersistenceErrorCode.DB_KEY_REJECTED)
    print("safe output only")
    logging.getLogger("document_intake_test").debug("safe log only")

    combined = "\n".join(
        [
            str(error),
            repr(error),
            repr(db),
            repr(uow),
            repr(repo),
            capsys.readouterr().out,
            capsys.readouterr().err,
            caplog.text,
        ]
    )
    for forbidden in (
        key_hex,
        "PRAGMA key",
        str(db_path),
        passport,
        vin,
        phone,
        address,
        payload,
        person().registration_address.value,
    ):
        assert forbidden not in combined
