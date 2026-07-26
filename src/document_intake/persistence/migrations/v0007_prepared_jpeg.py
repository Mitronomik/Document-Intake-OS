# ruff: noqa: E501
"""PR-011 audit extension and immutable prepared JPEG artifacts."""

from document_intake.persistence.migrations.model import Migration, migration_checksum
from document_intake.persistence.migrations.v0006_image_geometry import STATEMENTS as V0006

_AUDIT_CREATE = (
    V0006[1]
    .replace(
        "'IMAGE_GEOMETRY_RECIPE_CREATED'",
        "'IMAGE_GEOMETRY_RECIPE_CREATED','PREPARED_JPEG_CREATED'",
    )
    .replace(
        "'IMAGE_GEOMETRY_RECIPE'",
        "'IMAGE_GEOMETRY_RECIPE','PREPARED_IMAGE_ARTIFACT'",
    )
)

STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE audit_events RENAME TO audit_events_v0006",
    _AUDIT_CREATE,
    "INSERT INTO audit_events SELECT * FROM audit_events_v0006",
    "DROP TABLE audit_events_v0006",
    "CREATE INDEX audit_events_subject_order_idx ON audit_events(subject_type, subject_id, occurred_at_utc, event_id)",
    "CREATE INDEX audit_events_correlation_order_idx ON audit_events(correlation_id, occurred_at_utc, event_id) WHERE correlation_id IS NOT NULL",
    "CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit_events immutable'); END",
    "CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit_events immutable'); END",
    "CREATE TRIGGER audit_events_no_replace BEFORE INSERT ON audit_events WHEN EXISTS (SELECT 1 FROM audit_events WHERE event_id = NEW.event_id) BEGIN SELECT RAISE(ABORT, 'audit_events duplicate'); END",
    "CREATE TABLE stored_artifacts_v0007_new (artifact_id TEXT PRIMARY KEY, artifact_kind TEXT NOT NULL CHECK (artifact_kind IN ('ORIGINAL','PREPARED_DOCUMENT','EXPORT_ARTIFACT','PREPARED_JPEG')), object_generation INTEGER NOT NULL CHECK (object_generation = 1), plaintext_length INTEGER NOT NULL CHECK (plaintext_length >= 0), plaintext_sha256 TEXT NOT NULL CHECK (length(plaintext_sha256) = 64 AND plaintext_sha256 NOT GLOB '*[^0-9a-f]*'), ciphertext_sha256 TEXT NOT NULL CHECK (length(ciphertext_sha256) = 64 AND ciphertext_sha256 NOT GLOB '*[^0-9a-f]*'), key_version INTEGER NOT NULL CHECK (key_version > 0), storage_format_version INTEGER NOT NULL CHECK (storage_format_version = 1), created_at TEXT NOT NULL, canonical_payload TEXT NOT NULL)",
    "INSERT INTO stored_artifacts_v0007_new (artifact_id, artifact_kind, object_generation, plaintext_length, plaintext_sha256, ciphertext_sha256, key_version, storage_format_version, created_at, canonical_payload) SELECT artifact_id, artifact_kind, object_generation, plaintext_length, plaintext_sha256, ciphertext_sha256, key_version, storage_format_version, created_at, canonical_payload FROM stored_artifacts",
    "DROP TABLE stored_artifacts",
    "ALTER TABLE stored_artifacts_v0007_new RENAME TO stored_artifacts",
    "CREATE TRIGGER stored_artifacts_no_update BEFORE UPDATE ON stored_artifacts BEGIN SELECT RAISE(ABORT, 'ERR_STORED_ARTIFACT_IMMUTABLE'); END",
    "CREATE TRIGGER stored_artifacts_no_delete BEFORE DELETE ON stored_artifacts BEGIN SELECT RAISE(ABORT, 'ERR_STORED_ARTIFACT_IMMUTABLE'); END",
    "CREATE TABLE prepared_image_artifacts (prepared_artifact_id TEXT PRIMARY KEY NOT NULL CHECK(length(prepared_artifact_id)=36), source_file_id TEXT NOT NULL REFERENCES source_files(id), geometry_recipe_version_id TEXT NOT NULL REFERENCES image_geometry_recipes(recipe_version_id), stored_artifact_id TEXT NOT NULL UNIQUE REFERENCES stored_artifacts(artifact_id), pipeline_id TEXT NOT NULL CHECK(pipeline_id='PILLOW_PREPARED_JPEG'), pipeline_version INTEGER NOT NULL CHECK(pipeline_version=1), output_contract_id TEXT NOT NULL CHECK(output_contract_id='PREPARED_JPEG_SRGB_V1'), output_contract_version INTEGER NOT NULL CHECK(output_contract_version=1), media_type TEXT NOT NULL CHECK(media_type='JPEG'), color_space TEXT NOT NULL CHECK(color_space='SRGB'), width INTEGER NOT NULL CHECK(width>0), height INTEGER NOT NULL CHECK(height>0), byte_size INTEGER NOT NULL CHECK(byte_size BETWEEN 1 AND 1992294), sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'), jpeg_quality INTEGER NOT NULL CHECK(jpeg_quality IN (95,90,85,80,75,70,65,60)), resize_percent INTEGER NOT NULL CHECK(resize_percent IN (100,90,80,70,60,50)), created_at_utc TEXT NOT NULL CHECK(length(created_at_utc)>=20 AND substr(created_at_utc,-1)='Z'), created_by_id TEXT NOT NULL CHECK(length(created_by_id)=36), created_by_kind TEXT NOT NULL CHECK(created_by_kind IN ('OPERATOR','ADMIN','SYSTEM')), canonical_payload TEXT NOT NULL CHECK(length(canonical_payload)>0), UNIQUE(geometry_recipe_version_id,pipeline_id,pipeline_version,output_contract_id,output_contract_version))",
    "CREATE INDEX prepared_image_artifacts_source_order_idx ON prepared_image_artifacts(source_file_id,created_at_utc,prepared_artifact_id)",
    "CREATE INDEX prepared_image_artifacts_recipe_order_idx ON prepared_image_artifacts(geometry_recipe_version_id,created_at_utc,prepared_artifact_id)",
    "CREATE TRIGGER prepared_image_artifacts_no_update BEFORE UPDATE ON prepared_image_artifacts BEGIN SELECT RAISE(ABORT,'prepared_image_artifacts immutable'); END",
    "CREATE TRIGGER prepared_image_artifacts_no_delete BEFORE DELETE ON prepared_image_artifacts BEGIN SELECT RAISE(ABORT,'prepared_image_artifacts immutable'); END",
    "CREATE TRIGGER prepared_image_artifacts_no_replace BEFORE INSERT ON prepared_image_artifacts WHEN EXISTS(SELECT 1 FROM prepared_image_artifacts WHERE prepared_artifact_id=NEW.prepared_artifact_id) BEGIN SELECT RAISE(ABORT,'prepared_image_artifacts duplicate'); END",
)
MIGRATION = Migration(
    7,
    "prepared_jpeg_pr011",
    STATEMENTS,
    migration_checksum(STATEMENTS, foreign_key_mode="DISABLED_DURING_TABLE_REBUILD"),
    foreign_key_mode="DISABLED_DURING_TABLE_REBUILD",
)
