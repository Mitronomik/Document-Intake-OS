# ruff: noqa: E501
"""PR-011 immutable prepared JPEG artifacts."""

from document_intake.persistence.migrations.model import Migration, migration_checksum

STATEMENTS: tuple[str, ...] = (
    "CREATE TABLE prepared_image_artifacts (prepared_artifact_id TEXT PRIMARY KEY NOT NULL CHECK(length(prepared_artifact_id)=36), source_file_id TEXT NOT NULL REFERENCES source_files(id), geometry_recipe_version_id TEXT NOT NULL REFERENCES image_geometry_recipes(recipe_version_id), stored_artifact_id TEXT NOT NULL UNIQUE REFERENCES stored_artifacts(artifact_id), pipeline_id TEXT NOT NULL CHECK(pipeline_id='PILLOW_PREPARED_JPEG'), pipeline_version INTEGER NOT NULL CHECK(pipeline_version=1), output_contract_id TEXT NOT NULL CHECK(output_contract_id='PREPARED_JPEG_SRGB_V1'), output_contract_version INTEGER NOT NULL CHECK(output_contract_version=1), media_type TEXT NOT NULL CHECK(media_type='JPEG'), color_space TEXT NOT NULL CHECK(color_space='SRGB'), width INTEGER NOT NULL CHECK(width>0), height INTEGER NOT NULL CHECK(height>0), byte_size INTEGER NOT NULL CHECK(byte_size>0 AND byte_size<=1992294), sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'), jpeg_quality INTEGER NOT NULL CHECK(jpeg_quality IN (95,90,85,80,75,70,65,60)), resize_percent INTEGER NOT NULL CHECK(resize_percent IN (100,90,80,70,60,50)), created_at_utc TEXT NOT NULL CHECK(length(created_at_utc)>=20 AND substr(created_at_utc,-1)='Z'), created_by_id TEXT NOT NULL CHECK(length(created_by_id)=36), created_by_kind TEXT NOT NULL CHECK(created_by_kind IN ('OPERATOR','ADMIN','SYSTEM')), canonical_payload TEXT NOT NULL CHECK(length(canonical_payload)>0), UNIQUE(geometry_recipe_version_id,pipeline_id,pipeline_version,output_contract_id,output_contract_version))",
    "CREATE INDEX prepared_image_artifacts_source_order_idx ON prepared_image_artifacts(source_file_id,created_at_utc,prepared_artifact_id)",
    "CREATE INDEX prepared_image_artifacts_recipe_order_idx ON prepared_image_artifacts(geometry_recipe_version_id,created_at_utc,prepared_artifact_id)",
    "CREATE TRIGGER prepared_image_artifacts_no_update BEFORE UPDATE ON prepared_image_artifacts BEGIN SELECT RAISE(ABORT,'prepared_image_artifacts immutable'); END",
    "CREATE TRIGGER prepared_image_artifacts_no_delete BEFORE DELETE ON prepared_image_artifacts BEGIN SELECT RAISE(ABORT,'prepared_image_artifacts immutable'); END",
    "CREATE TRIGGER prepared_image_artifacts_no_replace BEFORE INSERT ON prepared_image_artifacts WHEN EXISTS(SELECT 1 FROM prepared_image_artifacts WHERE prepared_artifact_id=NEW.prepared_artifact_id) BEGIN SELECT RAISE(ABORT,'prepared_image_artifacts duplicate'); END",
    "PRAGMA user_version = 7",
)

MIGRATION = Migration(7, "prepared_jpeg_pr011", STATEMENTS, migration_checksum(STATEMENTS))
