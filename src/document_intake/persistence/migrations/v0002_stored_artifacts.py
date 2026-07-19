"""Stored artifacts schema."""

from document_intake.persistence.migrations.model import Migration

VERSION = 2
NAME = "stored_artifacts_pr006"
STATEMENTS = (
    "CREATE TABLE stored_artifacts ("
    "artifact_id TEXT PRIMARY KEY, "
    "artifact_kind TEXT NOT NULL CHECK (artifact_kind IN "
    "('ORIGINAL','PREPARED_DOCUMENT','EXPORT_ARTIFACT')), "
    "object_generation INTEGER NOT NULL CHECK (object_generation = 1), "
    "plaintext_length INTEGER NOT NULL CHECK (plaintext_length >= 0), "
    "plaintext_sha256 TEXT NOT NULL CHECK "
    "(length(plaintext_sha256) = 64 AND plaintext_sha256 NOT GLOB '*[^0-9a-f]*'), "
    "ciphertext_sha256 TEXT NOT NULL CHECK "
    "(length(ciphertext_sha256) = 64 AND ciphertext_sha256 NOT GLOB '*[^0-9a-f]*'), "
    "key_version INTEGER NOT NULL CHECK (key_version > 0), "
    "storage_format_version INTEGER NOT NULL CHECK (storage_format_version = 1), "
    "created_at TEXT NOT NULL, "
    "canonical_payload TEXT NOT NULL)",
    "CREATE TRIGGER stored_artifacts_no_update "
    "BEFORE UPDATE ON stored_artifacts "
    "BEGIN SELECT RAISE(ABORT, 'ERR_STORED_ARTIFACT_IMMUTABLE'); END",
    "CREATE TRIGGER stored_artifacts_no_delete "
    "BEFORE DELETE ON stored_artifacts "
    "BEGIN SELECT RAISE(ABORT, 'ERR_STORED_ARTIFACT_IMMUTABLE'); END",
)
CHECKSUM = "fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d"
MIGRATION = Migration(VERSION, NAME, STATEMENTS, CHECKSUM)
