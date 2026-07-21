# ruff: noqa: E501
"""PR-009 image quality assessment tables."""

from document_intake.persistence.migrations.model import Migration, migration_checksum

_NUMERIC_CHECK = "length(numeric_value) >= 1 AND numeric_value NOT GLOB '*[eE,+ -]*' AND numeric_value NOT GLOB '*,*' AND numeric_value NOT GLOB '*[^0-9.]*'"
STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE audit_events RENAME TO audit_events_v0003",
    """CREATE TABLE audit_events(
        event_id TEXT PRIMARY KEY NOT NULL CHECK(length(event_id)=36),
        occurred_at_utc TEXT NOT NULL CHECK(length(occurred_at_utc)>=20 AND substr(occurred_at_utc,-1)='Z'),
        actor_id TEXT NOT NULL CHECK(length(actor_id)=36),
        actor_kind TEXT NOT NULL CHECK(actor_kind IN ('OPERATOR','ADMIN','SYSTEM')),
        action_code TEXT NOT NULL CHECK(action_code IN ('ENTITY_CREATED','ENTITY_UPDATED','FIELD_CORRECTED','FIELD_VERIFIED','SNAPSHOT_CREATED','ARTIFACT_REGISTERED','EXPORT_CREATED','IMAGE_QUALITY_ASSESSED')),
        subject_type TEXT NOT NULL CHECK(subject_type IN ('PERSON','IDENTITY_DOCUMENT','MIGRATION_DOCUMENT','VEHICLE','DOCUMENT','FIELD_CANDIDATE','APPLICATION','APPLICATION_SNAPSHOT','STORED_ARTIFACT','IMAGE_QUALITY_ASSESSMENT')),
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
    )""",
    """INSERT INTO audit_events(
        event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type,
        subject_id, field_key, before_classification, before_was_present,
        before_display_value, after_classification, after_was_present,
        after_display_value, reason_code, correlation_id, payload
    ) SELECT
        event_id, occurred_at_utc, actor_id, actor_kind, action_code, subject_type,
        subject_id, field_key, before_classification, before_was_present,
        before_display_value, after_classification, after_was_present,
        after_display_value, reason_code, correlation_id, payload
    FROM audit_events_v0003""",
    "DROP TABLE audit_events_v0003",
    "CREATE INDEX audit_events_subject_order_idx ON audit_events(subject_type, subject_id, occurred_at_utc, event_id)",
    "CREATE INDEX audit_events_correlation_order_idx ON audit_events(correlation_id, occurred_at_utc, event_id) WHERE correlation_id IS NOT NULL",
    "CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit_events immutable'); END",
    "CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit_events immutable'); END",
    "CREATE TRIGGER audit_events_no_replace BEFORE INSERT ON audit_events WHEN EXISTS (SELECT 1 FROM audit_events WHERE event_id = NEW.event_id) BEGIN SELECT RAISE(ABORT, 'audit_events duplicate'); END",
    """CREATE TABLE image_quality_assessments (id TEXT PRIMARY KEY, source_file_id TEXT NOT NULL REFERENCES source_files(id), assessed_at TEXT NOT NULL, policy_id TEXT NOT NULL CHECK(length(policy_id) BETWEEN 1 AND 64) CHECK(substr(policy_id, 1, 1) GLOB '[A-Z]') CHECK(policy_id NOT GLOB '*[^A-Z0-9_]*'), policy_version INTEGER NOT NULL CHECK(policy_version >= 1), status TEXT NOT NULL CHECK(status IN ('GOOD','REVIEW_REQUIRED','RETAKE_REQUIRED')), encoded_width INTEGER NOT NULL CHECK(encoded_width >= 1), encoded_height INTEGER NOT NULL CHECK(encoded_height >= 1), exif_orientation INTEGER CHECK(exif_orientation IS NULL OR exif_orientation BETWEEN 1 AND 8), effective_width INTEGER NOT NULL CHECK(effective_width >= 1), effective_height INTEGER NOT NULL CHECK(effective_height >= 1), canonical_payload TEXT NOT NULL CHECK(length(canonical_payload) >= 1))""",
    f"""CREATE TABLE image_quality_metrics (assessment_id TEXT NOT NULL REFERENCES image_quality_assessments(id) ON DELETE RESTRICT, ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 6), metric_code TEXT NOT NULL CHECK(metric_code IN ('SHORT_SIDE_PIXELS','LONG_SIDE_PIXELS','LAPLACIAN_VARIANCE','LUMINANCE_STANDARD_DEVIATION','HIGHLIGHT_CLIPPED_FRACTION','SHADOW_CLIPPED_FRACTION','BRIGHT_CLIPPED_FRACTION')), algorithm_id TEXT NOT NULL CHECK(algorithm_id IN ('RESOLUTION_V1','BLUR_LAPLACIAN_V1','CONTRAST_STDDEV_V1','GLARE_CLIPPED_FRACTION_V1','EXPOSURE_CLIPPED_FRACTION_V1')), algorithm_version INTEGER NOT NULL CHECK(algorithm_version = 1), numeric_value TEXT NOT NULL CHECK({_NUMERIC_CHECK}) CHECK((unit = 'PIXELS' AND numeric_value NOT GLOB '*.*') OR (unit IN ('VARIANCE','LUMA_LEVEL') AND numeric_value GLOB '*.[0-9][0-9][0-9][0-9][0-9][0-9]' AND numeric_value NOT GLOB '*.[0-9][0-9][0-9][0-9][0-9][0-9][0-9]*') OR (unit = 'FRACTION' AND numeric_value GLOB '*.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]' AND numeric_value NOT GLOB '*.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*')), unit TEXT NOT NULL CHECK(unit IN ('PIXELS','VARIANCE','LUMA_LEVEL','FRACTION')), canonical_payload TEXT NOT NULL CHECK(length(canonical_payload) >= 1), PRIMARY KEY(assessment_id, ordinal), UNIQUE(assessment_id, metric_code))""",
    """CREATE TABLE image_quality_issues (assessment_id TEXT NOT NULL REFERENCES image_quality_assessments(id) ON DELETE RESTRICT, ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 5), issue_code TEXT NOT NULL CHECK(issue_code IN ('LOW_RESOLUTION','BLUR_DETECTED','LOW_CONTRAST','GLARE_DETECTED','UNDEREXPOSED','OVEREXPOSED')), severity TEXT NOT NULL CHECK(severity IN ('WARNING','BLOCKING')), canonical_payload TEXT NOT NULL CHECK(length(canonical_payload) >= 1), PRIMARY KEY(assessment_id, ordinal), UNIQUE(assessment_id, issue_code))""",
    "CREATE TRIGGER image_quality_assessments_no_update BEFORE UPDATE ON image_quality_assessments BEGIN SELECT RAISE(ABORT, 'image_quality_assessments_append_only'); END",
    "CREATE TRIGGER image_quality_assessments_no_delete BEFORE DELETE ON image_quality_assessments BEGIN SELECT RAISE(ABORT, 'image_quality_assessments_append_only'); END",
    "CREATE TRIGGER image_quality_metrics_no_update BEFORE UPDATE ON image_quality_metrics BEGIN SELECT RAISE(ABORT, 'image_quality_metrics_append_only'); END",
    "CREATE TRIGGER image_quality_metrics_no_delete BEFORE DELETE ON image_quality_metrics BEGIN SELECT RAISE(ABORT, 'image_quality_metrics_append_only'); END",
    "CREATE TRIGGER image_quality_issues_no_update BEFORE UPDATE ON image_quality_issues BEGIN SELECT RAISE(ABORT, 'image_quality_issues_append_only'); END",
    "CREATE TRIGGER image_quality_issues_no_delete BEFORE DELETE ON image_quality_issues BEGIN SELECT RAISE(ABORT, 'image_quality_issues_append_only'); END",
    "PRAGMA user_version = 5",
)
MIGRATION = Migration(5, "image_quality_pr009", STATEMENTS, migration_checksum(STATEMENTS))
