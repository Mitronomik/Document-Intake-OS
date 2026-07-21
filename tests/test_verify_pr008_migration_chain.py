from __future__ import annotations

from dataclasses import replace

import scripts.verify_pr008_import as verifier


def test_pr008_verifier_requires_exact_current_v0001_to_v0005_chain() -> None:
    assert verifier.CURRENT_SCHEMA_VERSION == 5
    assert (
        tuple(migration.checksum for migration in verifier.MIGRATIONS)
        == verifier._EXPECTED_MIGRATION_CHECKSUMS
    )
    assert (
        verifier.V0001,
        verifier.V0002,
        verifier.V0003,
        verifier.V0004,
        verifier.V0005,
    ) == verifier.MIGRATIONS
    assert verifier._migration_chain_is_current()


def test_pr008_migration_chain_rejects_v0005_omitted(monkeypatch) -> None:
    monkeypatch.setattr(verifier, "MIGRATIONS", verifier.MIGRATIONS[:4])
    assert not verifier._migration_chain_is_current()


def test_pr008_migration_chain_rejects_order_change(monkeypatch) -> None:
    monkeypatch.setattr(
        verifier,
        "MIGRATIONS",
        (verifier.V0001, verifier.V0003, verifier.V0002, verifier.V0004, verifier.V0005),
    )
    assert not verifier._migration_chain_is_current()


def test_pr008_migration_chain_rejects_v0004_checksum_change(monkeypatch) -> None:
    bad = replace(verifier.V0004, checksum="bad")
    monkeypatch.setattr(verifier, "V0004", bad)
    monkeypatch.setattr(
        verifier,
        "MIGRATIONS",
        (verifier.V0001, verifier.V0002, verifier.V0003, bad, verifier.V0005),
    )
    assert not verifier._migration_chain_is_current()


def test_pr008_migration_chain_rejects_v0005_checksum_change(monkeypatch) -> None:
    bad = replace(verifier.V0005, checksum="bad")
    monkeypatch.setattr(verifier, "V0005", bad)
    monkeypatch.setattr(
        verifier,
        "MIGRATIONS",
        (verifier.V0001, verifier.V0002, verifier.V0003, verifier.V0004, bad),
    )
    assert not verifier._migration_chain_is_current()


def test_pr008_migration_chain_rejects_middle_insert(monkeypatch) -> None:
    extra = replace(verifier.V0005, version=5, name="extra_middle")
    monkeypatch.setattr(
        verifier,
        "MIGRATIONS",
        (verifier.V0001, verifier.V0002, verifier.V0003, extra, verifier.V0004, verifier.V0005),
    )
    assert not verifier._migration_chain_is_current()
