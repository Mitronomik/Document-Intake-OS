# ruff: noqa: E501
"""Initial encrypted persistence schema."""

from document_intake.persistence.migrations.model import Migration

VERSION = 1
NAME = "initial_pr004_domain_persistence"
STATEMENTS = (
    "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at_utc TEXT NOT NULL)",
    "CREATE TABLE persons (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    "CREATE TABLE identity_documents (id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE RESTRICT, payload TEXT NOT NULL)",
    "CREATE TABLE migration_documents (id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE RESTRICT, related_passport_id TEXT REFERENCES identity_documents(id) ON DELETE RESTRICT, payload TEXT NOT NULL)",
    "CREATE TABLE documents (id TEXT PRIMARY KEY, owner_kind TEXT, owner_id TEXT, payload TEXT NOT NULL, CHECK ((owner_kind IS NULL AND owner_id IS NULL) OR (owner_kind IS NOT NULL AND owner_id IS NOT NULL)))",
    "CREATE TABLE document_sides (document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT, order_index INTEGER NOT NULL CHECK (order_index >= 0), side_id TEXT NOT NULL, PRIMARY KEY(document_id, order_index))",
    "CREATE TABLE vehicles (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    "CREATE TABLE terminals (code TEXT PRIMARY KEY, is_active INTEGER NOT NULL CHECK (is_active IN (0,1)), payload TEXT NOT NULL)",
    "CREATE TABLE field_candidates (id TEXT PRIMARY KEY, field_entity_id TEXT NOT NULL, field_key TEXT NOT NULL, confidence TEXT NOT NULL, payload TEXT NOT NULL)",
    "CREATE TABLE field_candidate_validation_results (candidate_id TEXT NOT NULL REFERENCES field_candidates(id) ON DELETE RESTRICT, order_index INTEGER NOT NULL CHECK (order_index >= 0), result TEXT NOT NULL, PRIMARY KEY(candidate_id, order_index))",
    "CREATE TABLE applications (id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, terminal_code TEXT REFERENCES terminals(code) ON DELETE RESTRICT, status TEXT NOT NULL, created_by_actor_id TEXT NOT NULL, created_by_actor_kind TEXT NOT NULL, created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL, payload TEXT NOT NULL)",
    "CREATE TABLE application_assignments (application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE RESTRICT, order_index INTEGER NOT NULL CHECK (order_index >= 0), person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE RESTRICT, tractor_id TEXT NOT NULL REFERENCES vehicles(id) ON DELETE RESTRICT, trailer_id TEXT REFERENCES vehicles(id) ON DELETE RESTRICT, payload TEXT NOT NULL, PRIMARY KEY(application_id, order_index))",
    "CREATE TABLE application_verified_fields (application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE RESTRICT, order_index INTEGER NOT NULL CHECK (order_index >= 0), field_entity_id TEXT NOT NULL, field_key TEXT NOT NULL, source_candidate_id TEXT REFERENCES field_candidates(id) ON DELETE RESTRICT, payload TEXT NOT NULL, PRIMARY KEY(application_id, field_entity_id, field_key), UNIQUE(application_id, order_index))",
    "CREATE TABLE application_validation_issues (application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE RESTRICT, order_index INTEGER NOT NULL CHECK (order_index >= 0), payload TEXT NOT NULL, PRIMARY KEY(application_id, order_index))",
    "CREATE TABLE application_snapshots (id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id) ON DELETE RESTRICT, terminal_code TEXT NOT NULL REFERENCES terminals(code) ON DELETE RESTRICT, template_version TEXT NOT NULL, rules_version TEXT NOT NULL, created_by_actor_id TEXT NOT NULL, created_by_actor_kind TEXT NOT NULL, created_at_utc TEXT NOT NULL, payload_json TEXT NOT NULL, sha256 TEXT NOT NULL, expected_artifact_ref_count INTEGER NOT NULL CHECK (expected_artifact_ref_count >= 0), payload TEXT NOT NULL)",
    "CREATE TABLE application_snapshot_artifact_refs (snapshot_id TEXT NOT NULL REFERENCES application_snapshots(id) ON DELETE RESTRICT, order_index INTEGER NOT NULL CHECK (order_index >= 0), artifact_ref TEXT NOT NULL, PRIMARY KEY(snapshot_id, order_index))",
    "CREATE TRIGGER application_snapshots_no_replace BEFORE INSERT ON application_snapshots WHEN EXISTS (SELECT 1 FROM application_snapshots WHERE id = NEW.id) BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: application_snapshots.id'); END",
    "CREATE TRIGGER application_snapshots_no_update BEFORE UPDATE ON application_snapshots BEGIN SELECT RAISE(ABORT, 'ERR_SNAPSHOT_IMMUTABLE'); END",
    "CREATE TRIGGER application_snapshots_no_delete BEFORE DELETE ON application_snapshots BEGIN SELECT RAISE(ABORT, 'ERR_SNAPSHOT_IMMUTABLE'); END",
    "CREATE TRIGGER application_snapshot_artifact_refs_no_replace BEFORE INSERT ON application_snapshot_artifact_refs WHEN EXISTS (SELECT 1 FROM application_snapshot_artifact_refs WHERE snapshot_id = NEW.snapshot_id AND order_index = NEW.order_index) BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: application_snapshot_artifact_refs.snapshot_id, application_snapshot_artifact_refs.order_index'); END",
    "CREATE TRIGGER application_snapshot_artifact_refs_no_update BEFORE UPDATE ON application_snapshot_artifact_refs BEGIN SELECT RAISE(ABORT, 'ERR_SNAPSHOT_ARTIFACT_IMMUTABLE'); END",
    "CREATE TRIGGER application_snapshot_artifact_refs_no_delete BEFORE DELETE ON application_snapshot_artifact_refs BEGIN SELECT RAISE(ABORT, 'ERR_SNAPSHOT_ARTIFACT_IMMUTABLE'); END",
    "CREATE TRIGGER application_snapshot_artifact_refs_bounded BEFORE INSERT ON application_snapshot_artifact_refs WHEN NEW.order_index >= COALESCE((SELECT expected_artifact_ref_count FROM application_snapshots WHERE id = NEW.snapshot_id), 0) BEGIN SELECT RAISE(ABORT, 'ERR_SNAPSHOT_ARTIFACT_ORDINAL'); END",
)
CHECKSUM = "e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500"
MIGRATION = Migration(VERSION, NAME, STATEMENTS, CHECKSUM)
