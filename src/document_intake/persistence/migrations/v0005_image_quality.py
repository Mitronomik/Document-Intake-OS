# ruff: noqa: E501
"""PR-009 image quality assessment tables."""

from document_intake.persistence.migrations.model import Migration

STATEMENTS: tuple[str, ...] = (
    """CREATE TABLE image_quality_assessments (id TEXT PRIMARY KEY, source_file_id TEXT NOT NULL REFERENCES source_files(source_file_id), assessed_at TEXT NOT NULL, policy_id TEXT NOT NULL CHECK(policy_id GLOB '[A-Z]*'), policy_version INTEGER NOT NULL CHECK(policy_version >= 1), status TEXT NOT NULL CHECK(status IN ('GOOD','REVIEW_REQUIRED','RETAKE_REQUIRED')), encoded_width INTEGER NOT NULL CHECK(encoded_width >= 1), encoded_height INTEGER NOT NULL CHECK(encoded_height >= 1), exif_orientation INTEGER CHECK(exif_orientation IS NULL OR exif_orientation BETWEEN 1 AND 8), effective_width INTEGER NOT NULL CHECK(effective_width >= 1), effective_height INTEGER NOT NULL CHECK(effective_height >= 1), canonical_payload TEXT NOT NULL)""",
    """CREATE TABLE image_quality_metrics (assessment_id TEXT NOT NULL REFERENCES image_quality_assessments(id) ON DELETE RESTRICT, ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 6), metric_code TEXT NOT NULL CHECK(metric_code IN ('SHORT_SIDE_PIXELS','LONG_SIDE_PIXELS','LAPLACIAN_VARIANCE','LUMINANCE_STANDARD_DEVIATION','HIGHLIGHT_CLIPPED_FRACTION','SHADOW_CLIPPED_FRACTION','BRIGHT_CLIPPED_FRACTION')), algorithm_id TEXT NOT NULL CHECK(algorithm_id IN ('RESOLUTION_V1','BLUR_LAPLACIAN_V1','CONTRAST_STDDEV_V1','GLARE_CLIPPED_FRACTION_V1','EXPOSURE_CLIPPED_FRACTION_V1')), algorithm_version INTEGER NOT NULL CHECK(algorithm_version = 1), numeric_value TEXT NOT NULL, unit TEXT NOT NULL CHECK(unit IN ('PIXELS','VARIANCE','LUMA_LEVEL','FRACTION')), canonical_payload TEXT NOT NULL, PRIMARY KEY(assessment_id, ordinal), UNIQUE(assessment_id, metric_code))""",
    """CREATE TABLE image_quality_issues (assessment_id TEXT NOT NULL REFERENCES image_quality_assessments(id) ON DELETE RESTRICT, ordinal INTEGER NOT NULL CHECK(ordinal >= 0), issue_code TEXT NOT NULL CHECK(issue_code IN ('LOW_RESOLUTION','BLUR_DETECTED','LOW_CONTRAST','GLARE_DETECTED','UNDEREXPOSED','OVEREXPOSED')), severity TEXT NOT NULL CHECK(severity IN ('WARNING','BLOCKING')), canonical_payload TEXT NOT NULL, PRIMARY KEY(assessment_id, ordinal), UNIQUE(assessment_id, issue_code))""",
    "CREATE TRIGGER image_quality_assessments_no_update BEFORE UPDATE ON image_quality_assessments BEGIN SELECT RAISE(ABORT, 'image_quality_assessments_append_only'); END",
    "CREATE TRIGGER image_quality_assessments_no_delete BEFORE DELETE ON image_quality_assessments BEGIN SELECT RAISE(ABORT, 'image_quality_assessments_append_only'); END",
    "CREATE TRIGGER image_quality_metrics_no_update BEFORE UPDATE ON image_quality_metrics BEGIN SELECT RAISE(ABORT, 'image_quality_metrics_append_only'); END",
    "CREATE TRIGGER image_quality_metrics_no_delete BEFORE DELETE ON image_quality_metrics BEGIN SELECT RAISE(ABORT, 'image_quality_metrics_append_only'); END",
    "CREATE TRIGGER image_quality_issues_no_update BEFORE UPDATE ON image_quality_issues BEGIN SELECT RAISE(ABORT, 'image_quality_issues_append_only'); END",
    "CREATE TRIGGER image_quality_issues_no_delete BEFORE DELETE ON image_quality_issues BEGIN SELECT RAISE(ABORT, 'image_quality_issues_append_only'); END",
    "PRAGMA user_version = 5",
)
CHECKSUM = "74f6376fbfd42ed4b9748cadd936daba3c26755a04ddc7cedee76ed2143d95f2"
MIGRATION = Migration(5, "image_quality_pr009", STATEMENTS, CHECKSUM)
