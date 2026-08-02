"""PR-013 immutable deterministic document-side compositions."""

from document_intake.persistence.migrations.model import Migration, migration_checksum
from document_intake.persistence.migrations.v0008_document_regions import (
    _AUDIT_CREATE as V8_AUDIT_CREATE,
)

_AUDIT_CREATE = V8_AUDIT_CREATE.replace(
    "'DOCUMENT_REGION_SET_CONFIRMED'",
    "'DOCUMENT_REGION_SET_CONFIRMED','DOCUMENT_SIDE_COMPOSITION_CREATED'",
).replace(
    "'DOCUMENT_REGION_SET'",
    "'DOCUMENT_REGION_SET','DOCUMENT_SIDE_COMPOSITION'",
)

STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE audit_events RENAME TO audit_events_v0008",
    _AUDIT_CREATE,
    "INSERT INTO audit_events SELECT * FROM audit_events_v0008",
    "DROP TABLE audit_events_v0008",
    "CREATE INDEX audit_events_subject_order_idx ON audit_events(subject_type,subject_id,occurred_at_utc,event_id)",  # noqa: E501
    "CREATE INDEX audit_events_correlation_order_idx ON audit_events(correlation_id,occurred_at_utc,event_id) WHERE correlation_id IS NOT NULL",  # noqa: E501
    "CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_events immutable'); END",  # noqa: E501
    "CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_events immutable'); END",  # noqa: E501
    "CREATE TRIGGER audit_events_no_replace BEFORE INSERT ON audit_events WHEN EXISTS(SELECT 1 FROM audit_events WHERE event_id=NEW.event_id) BEGIN SELECT RAISE(ABORT,'audit_events duplicate'); END",  # noqa: E501
    "CREATE TABLE document_side_compositions(id TEXT PRIMARY KEY NOT NULL CHECK(length(id)=36))",
    "CREATE TABLE document_side_composition_versions(id TEXT PRIMARY KEY NOT NULL CHECK(length(id)=36),composition_id TEXT NOT NULL UNIQUE REFERENCES document_side_compositions(id),side_1_region_set_version_id TEXT NOT NULL REFERENCES document_region_set_versions(region_set_version_id),side_1_source_file_id TEXT NOT NULL REFERENCES source_files(id),side_1_region_id TEXT NOT NULL CHECK(length(side_1_region_id)=36),side_1_geometry_recipe_version_id TEXT NOT NULL REFERENCES image_geometry_recipes(recipe_version_id),side_2_region_set_version_id TEXT NOT NULL REFERENCES document_region_set_versions(region_set_version_id),side_2_source_file_id TEXT NOT NULL REFERENCES source_files(id),side_2_region_id TEXT NOT NULL CHECK(length(side_2_region_id)=36),side_2_geometry_recipe_version_id TEXT NOT NULL REFERENCES image_geometry_recipes(recipe_version_id),layout TEXT NOT NULL CHECK(layout IN ('VERTICAL','HORIZONTAL')),outer_margin_px INTEGER NOT NULL CHECK(outer_margin_px BETWEEN 0 AND 256),inter_side_gap_px INTEGER NOT NULL CHECK(inter_side_gap_px BETWEEN 0 AND 256),composition_pipeline_id TEXT NOT NULL CHECK(composition_pipeline_id='PILLOW_DOCUMENT_SIDE_COMPOSITION_BICUBIC'),composition_pipeline_version INTEGER NOT NULL CHECK(composition_pipeline_version=1),jpeg_pipeline_id TEXT NOT NULL CHECK(jpeg_pipeline_id='PILLOW_PREPARED_JPEG'),jpeg_pipeline_version INTEGER NOT NULL CHECK(jpeg_pipeline_version=1),output_contract_id TEXT NOT NULL CHECK(output_contract_id='PREPARED_JPEG_SRGB_V1'),output_contract_version INTEGER NOT NULL CHECK(output_contract_version=1),created_at_utc TEXT NOT NULL CHECK(length(created_at_utc)>=20 AND substr(created_at_utc,-1)='Z'),created_by_id TEXT NOT NULL CHECK(length(created_by_id)=36),created_by_kind TEXT NOT NULL CHECK(created_by_kind IN ('OPERATOR','ADMIN','SYSTEM')),correlation_id TEXT NOT NULL CHECK(length(correlation_id)=36),canonical_payload TEXT NOT NULL CHECK(length(canonical_payload)>0),CHECK(side_1_source_file_id<>side_2_source_file_id OR side_1_region_id<>side_2_region_id),UNIQUE(side_1_region_set_version_id,side_1_source_file_id,side_1_region_id,side_1_geometry_recipe_version_id,side_2_region_set_version_id,side_2_source_file_id,side_2_region_id,side_2_geometry_recipe_version_id,layout,outer_margin_px,inter_side_gap_px,composition_pipeline_id,composition_pipeline_version,jpeg_pipeline_id,jpeg_pipeline_version,output_contract_id,output_contract_version))",  # noqa: E501
    "CREATE TABLE prepared_composition_artifacts(id TEXT PRIMARY KEY NOT NULL CHECK(length(id)=36),composition_version_id TEXT NOT NULL UNIQUE REFERENCES document_side_composition_versions(id),stored_artifact_id TEXT NOT NULL UNIQUE REFERENCES stored_artifacts(artifact_id),pipeline_id TEXT NOT NULL CHECK(pipeline_id='PILLOW_PREPARED_JPEG'),pipeline_version INTEGER NOT NULL CHECK(pipeline_version=1),output_contract_id TEXT NOT NULL CHECK(output_contract_id='PREPARED_JPEG_SRGB_V1'),output_contract_version INTEGER NOT NULL CHECK(output_contract_version=1),media_type TEXT NOT NULL CHECK(media_type='JPEG'),color_space TEXT NOT NULL CHECK(color_space='SRGB'),width INTEGER NOT NULL CHECK(width>0),height INTEGER NOT NULL CHECK(height>0),byte_size INTEGER NOT NULL CHECK(byte_size BETWEEN 1 AND 1992294),sha256 TEXT NOT NULL CHECK(length(sha256)=64 AND sha256 NOT GLOB '*[^0-9a-f]*'),jpeg_quality INTEGER NOT NULL CHECK(jpeg_quality IN (95,90,85,80,75,70,65,60)),resize_percent INTEGER NOT NULL CHECK(resize_percent IN (100,90,80,70,60,50)),created_at_utc TEXT NOT NULL CHECK(length(created_at_utc)>=20 AND substr(created_at_utc,-1)='Z'),created_by_id TEXT NOT NULL CHECK(length(created_by_id)=36),created_by_kind TEXT NOT NULL CHECK(created_by_kind IN ('OPERATOR','ADMIN','SYSTEM')),canonical_payload TEXT NOT NULL CHECK(length(canonical_payload)>0))",  # noqa: E501
    "CREATE TRIGGER document_side_compositions_no_update BEFORE UPDATE ON document_side_compositions BEGIN SELECT RAISE(ABORT,'document_side_compositions immutable'); END",  # noqa: E501
    "CREATE TRIGGER document_side_compositions_no_delete BEFORE DELETE ON document_side_compositions BEGIN SELECT RAISE(ABORT,'document_side_compositions immutable'); END",  # noqa: E501
    "CREATE TRIGGER document_side_compositions_no_replace BEFORE INSERT ON document_side_compositions WHEN EXISTS(SELECT 1 FROM document_side_compositions WHERE id=NEW.id) BEGIN SELECT RAISE(ABORT,'document_side_compositions duplicate'); END",  # noqa: E501
    "CREATE TRIGGER document_side_composition_versions_no_update BEFORE UPDATE ON document_side_composition_versions BEGIN SELECT RAISE(ABORT,'document_side_composition_versions immutable'); END",  # noqa: E501
    "CREATE TRIGGER document_side_composition_versions_no_delete BEFORE DELETE ON document_side_composition_versions BEGIN SELECT RAISE(ABORT,'document_side_composition_versions immutable'); END",  # noqa: E501
    "CREATE TRIGGER document_side_composition_versions_no_replace BEFORE INSERT ON document_side_composition_versions WHEN EXISTS(SELECT 1 FROM document_side_composition_versions WHERE id=NEW.id OR composition_id=NEW.composition_id) BEGIN SELECT RAISE(ABORT,'document_side_composition_versions duplicate'); END",  # noqa: E501
    "CREATE TRIGGER prepared_composition_artifacts_no_update BEFORE UPDATE ON prepared_composition_artifacts BEGIN SELECT RAISE(ABORT,'prepared_composition_artifacts immutable'); END",  # noqa: E501
    "CREATE TRIGGER prepared_composition_artifacts_no_delete BEFORE DELETE ON prepared_composition_artifacts BEGIN SELECT RAISE(ABORT,'prepared_composition_artifacts immutable'); END",  # noqa: E501
    "CREATE TRIGGER prepared_composition_artifacts_no_replace BEFORE INSERT ON prepared_composition_artifacts WHEN EXISTS(SELECT 1 FROM prepared_composition_artifacts WHERE id=NEW.id OR composition_version_id=NEW.composition_version_id OR stored_artifact_id=NEW.stored_artifact_id) BEGIN SELECT RAISE(ABORT,'prepared_composition_artifacts duplicate'); END",  # noqa: E501
)

MIGRATION = Migration(
    9,
    "document_side_composition_pr013",
    STATEMENTS,
    migration_checksum(STATEMENTS, foreign_key_mode="DISABLED_DURING_TABLE_REBUILD"),
    foreign_key_mode="DISABLED_DURING_TABLE_REBUILD",
)
