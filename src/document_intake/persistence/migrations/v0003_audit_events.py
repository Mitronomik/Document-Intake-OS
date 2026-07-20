"""PR-007 immutable PII-safe audit events migration."""
# ruff: noqa: E501

from document_intake.persistence.migrations.model import Migration, migration_checksum

STATEMENTS = (
    """
    CREATE TABLE audit_events(
        event_id TEXT PRIMARY KEY NOT NULL CHECK(length(event_id)=36),
        occurred_at_utc TEXT NOT NULL CHECK(length(occurred_at_utc)>=20 AND substr(occurred_at_utc,-1)='Z'),
        actor_id TEXT NOT NULL CHECK(length(actor_id)=36),
        actor_kind TEXT NOT NULL CHECK(actor_kind IN ('OPERATOR','ADMIN','SYSTEM')),
        action_code TEXT NOT NULL CHECK(action_code IN ('ENTITY_CREATED','ENTITY_UPDATED','FIELD_CORRECTED','FIELD_VERIFIED','SNAPSHOT_CREATED','ARTIFACT_REGISTERED','EXPORT_CREATED')),
        subject_type TEXT NOT NULL CHECK(subject_type IN ('PERSON','IDENTITY_DOCUMENT','MIGRATION_DOCUMENT','VEHICLE','DOCUMENT','FIELD_CANDIDATE','APPLICATION','APPLICATION_SNAPSHOT','STORED_ARTIFACT')),
        subject_id TEXT NOT NULL CHECK(length(subject_id)=36),
        field_key TEXT NULL CHECK(field_key IS NULL OR (length(field_key) BETWEEN 1 AND 128 AND substr(field_key,1,1) GLOB '[a-z0-9]' AND field_key NOT GLOB '*[^a-z0-9_.]*')),
        before_classification TEXT NULL CHECK(before_classification IS NULL OR before_classification IN ('ABSENT','NON_SENSITIVE','SENSITIVE_REDACTED')),
        before_was_present INTEGER NULL CHECK(before_was_present IS NULL OR before_was_present IN (0,1)),
        before_display_value TEXT NULL CHECK(before_display_value IS NULL OR (length(before_display_value) BETWEEN 1 AND 64 AND substr(before_display_value,1,1) GLOB '[A-Z0-9]' AND before_display_value NOT GLOB '*[^A-Z0-9_.:-]*')),
        after_classification TEXT NULL CHECK(after_classification IS NULL OR after_classification IN ('ABSENT','NON_SENSITIVE','SENSITIVE_REDACTED')),
        after_was_present INTEGER NULL CHECK(after_was_present IS NULL OR after_was_present IN (0,1)),
        after_display_value TEXT NULL CHECK(after_display_value IS NULL OR (length(after_display_value) BETWEEN 1 AND 64 AND substr(after_display_value,1,1) GLOB '[A-Z0-9]' AND after_display_value NOT GLOB '*[^A-Z0-9_.:-]*')),
        reason_code TEXT NULL CHECK(reason_code IS NULL OR (length(reason_code) BETWEEN 1 AND 64 AND substr(reason_code,1,1) GLOB '[A-Z]' AND reason_code NOT GLOB '*[^A-Z0-9_]*')),
        correlation_id TEXT NULL CHECK(correlation_id IS NULL OR length(correlation_id)=36),
        payload TEXT NOT NULL,
        CHECK((before_classification IS NULL AND before_was_present IS NULL AND before_display_value IS NULL) OR (before_classification='ABSENT' AND before_was_present=0 AND before_display_value IS NULL) OR (before_classification='NON_SENSITIVE' AND before_was_present=1 AND before_display_value IS NOT NULL) OR (before_classification='SENSITIVE_REDACTED' AND before_was_present=1 AND before_display_value IS NULL)),
        CHECK((after_classification IS NULL AND after_was_present IS NULL AND after_display_value IS NULL) OR (after_classification='ABSENT' AND after_was_present=0 AND after_display_value IS NULL) OR (after_classification='NON_SENSITIVE' AND after_was_present=1 AND after_display_value IS NOT NULL) OR (after_classification='SENSITIVE_REDACTED' AND after_was_present=1 AND after_display_value IS NULL))
    )
    """,
    """
    CREATE INDEX audit_events_subject_order_idx
    ON audit_events(subject_type, subject_id, occurred_at_utc, event_id)
    """,
    """
    CREATE INDEX audit_events_correlation_order_idx
    ON audit_events(correlation_id, occurred_at_utc, event_id)
    WHERE correlation_id IS NOT NULL
    """,
    """
    CREATE TRIGGER audit_events_no_update
    BEFORE UPDATE ON audit_events
    BEGIN
        SELECT RAISE(ABORT, 'audit_events immutable');
    END
    """,
    """
    CREATE TRIGGER audit_events_no_delete
    BEFORE DELETE ON audit_events
    BEGIN
        SELECT RAISE(ABORT, 'audit_events immutable');
    END
    """,
    """
    CREATE TRIGGER audit_events_no_replace
    BEFORE INSERT ON audit_events
    WHEN EXISTS (SELECT 1 FROM audit_events WHERE event_id = NEW.event_id)
    BEGIN
        SELECT RAISE(ABORT, 'audit_events duplicate');
    END
    """,
)

MIGRATION = Migration(3, "audit_events_pr007", STATEMENTS, migration_checksum(STATEMENTS))
