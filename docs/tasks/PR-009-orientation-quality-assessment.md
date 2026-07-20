# PR-009 — Orientation and quality assessment contract

Status: AUTHORIZED FOR CONTRACT REVIEW; PRODUCTION IMPLEMENTATION NOT STARTED

## Implementation base rule

This documentation-only contract was prepared from PR #22 merge commit `063e4b5a981f8ef6914c055e9f50666bbf1be734`. The future PR-009 production implementation must branch from the exact merge commit of the PR that adds this contract, not from `063e4b5a981f8ef6914c055e9f50666bbf1be734`. Do not invent that future merge SHA.

## Goal and scope

PR-009 will implement deterministic whole-frame orientation and image-quality diagnostics for encrypted imported source files. Scope is limited to original EXIF orientation value, orientation-normalized analysis view, original encoded dimensions, orientation-normalized effective dimensions, minimum-resolution diagnostic, blur/sharpness metric, contrast metric, glare/highlight-clipping metric and exposure diagnostic.

PR-009 advances FR-04 but does not complete all of FR-04. FR-04 and `docs/image-pipeline.md` include overlapping broader quality items; this task stages region, boundary, geometry and document-presence work instead of silently expanding PR-009.

## Deferred scope

Deferred outside PR-009: cut-edge detection, perspective/skew assessment based on document boundaries, document presence detection, document count, segmentation, automatic crop, perspective correction and geometric transformation. PR-010 is staged for perspective and geometry tools. PR-012 is staged for document regions, document presence/count and multiple-document workflow. PR-010 and later remain unauthorized.

## Expected future implementation files

The future implementation may add or modify only after this contract is merged and accepted:

- `src/document_intake/domain/image_quality.py`;
- `src/document_intake/image_pipeline/quality_assessor.py`;
- `src/document_intake/application/dto/image_quality.py`;
- `src/document_intake/application/services/image_quality.py`;
- `src/document_intake/persistence/repositories/image_quality.py`;
- `src/document_intake/persistence/migrations/v0005_image_quality.py`;
- `scripts/verify_pr009_quality.py`.

Existing files expected to change in the implementation PR are `src/document_intake/application/ports/persistence.py`, `src/document_intake/application/ports/__init__.py`, persistence database registration/factory files, `src/document_intake/persistence/migrations/__init__.py`, `src/document_intake/persistence/serialization.py`, repository Unit of Work wiring, audit enum/serialization files if `IMAGE_QUALITY_ASSESSED` is added, and tests. This contract PR creates none of those production files.

## Exact domain, DTO and policy contracts

Domain contracts are immutable frozen/slotted types: `QualityAssessmentStatus`, `QualityIssueCode`, `QualityIssueSeverity`, `QualityMetricCode`, `QualityPolicyVersion`, `ImageQualityMetric`, `ImageQualityIssue`, `ImageQualityAssessment` and `ImageQualityPolicy`. Status values are `GOOD`, `REVIEW_REQUIRED`, `RETAKE_REQUIRED`. Issue codes are `LOW_RESOLUTION`, `BLUR_DETECTED`, `LOW_CONTRAST`, `GLARE_DETECTED`, `UNDEREXPOSED`, `OVEREXPOSED`. Deferred codes `CUT_EDGES`, `PERSPECTIVE`, `DOCUMENT_NOT_FOUND` and `MULTIPLE_DOCUMENTS` are not implemented. Severity values are `WARNING`, `BLOCKING`.

Metrics contain only `metric_code`, `algorithm_id`, `algorithm_version`, `numeric_value`, `unit`. Metric codes are `SHORT_SIDE_PIXELS`, `LONG_SIDE_PIXELS`, `LAPLACIAN_VARIANCE`, `LUMINANCE_STANDARD_DEVIATION`, `HIGHLIGHT_CLIPPED_FRACTION`, `SHADOW_CLIPPED_FRACTION`, `BRIGHT_CLIPPED_FRACTION`. DTOs must be PII-safe and include assessment ID, source file ID, status, encoded/effective dimensions, EXIF orientation, policy ID/version, metrics, issues and timestamps. DTOs must exclude basenames, paths, hashes, pixels, thumbnails, arbitrary metadata and raw exceptions.

`ImageQualityPolicy` contains `policy_id`, `policy_version`, `minimum_short_side_pixels`, `minimum_long_side_pixels`, `blur_minimum_laplacian_variance`, `contrast_minimum_luminance_stddev`, `glare_highlight_cutoff`, `glare_maximum_fraction`, `exposure_shadow_cutoff`, `exposure_maximum_shadow_fraction`, `exposure_bright_cutoff`, `exposure_maximum_bright_fraction` and an explicit severity mapping for every PR-009 issue code. Hidden global thresholds are prohibited.

## Algorithms and numeric determinism

Algorithms are exactly `RESOLUTION_V1`, `BLUR_LAPLACIAN_V1`, `CONTRAST_STDDEV_V1`, `GLARE_CLIPPED_FRACTION_V1` and `EXPOSURE_CLIPPED_FRACTION_V1`. The Laplacian kernel is `[0, 1, 0; 1, -4, 1; 0, 1, 0]`; border handling is valid-interior only. Grayscale is the decoder-provided 8-bit luminance plane after the one permitted EXIF analysis orientation; if RGB conversion is needed, use integer BT.601 `round_half_up((299*R + 587*G + 114*B) / 1000)`. Variance and standard deviation use population formulas. Variance and standard deviation are rounded half up to six fractional places; clipped fractions are rounded half up to eight fractional places. Dimensions and cutoffs are integers. Frozen vectors must match exactly on Ubuntu and Windows.

## Service, persistence and audit

The service contract is `assess_source_file_quality(command, dependencies) -> result`; command inputs are `source_file_id`, `actor`, `policy`, `correlation_id` and caller-provided assessment/audit IDs if consistent with existing service style. The service uses existing storage to load the encrypted original artifact by the stored artifact ID, verifies integrity, decodes using the accepted media decoder, applies orientation once for analysis only, computes metrics, evaluates policy, persists assessment/metrics/issues and one audit event atomically in the existing SQLCipher Unit of Work, and returns a sanitized DTO. It never accepts or persists a caller path and never modifies source rows or original artifacts.

Migration v0005 may create append-only `image_quality_assessments`, `image_quality_metrics` and `image_quality_issues`. One source file may have multiple assessments. Deterministic ordering is the metric-code and issue-code order from ADR-023. Update, delete and replace are forbidden. Existing v0001-v0004 migration checksums must remain unchanged. Tamper/projection-integrity checks follow current persistence conventions.

Audit action is proposed as `IMAGE_QUALITY_ASSESSED`; do not overload unrelated actions. Audit event data is controlled and contains subject ID, policy ID/version and correlation ID only. No paths, filenames, image hashes, raw metrics, free-text exceptions, SQL or key material are allowed.

## Failure codes

Future stable error codes are `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `QUALITY_POLICY_INVALID`, `QUALITY_ASSESSMENT_FAILED` and `PERSISTENCE_FAILED`. No third-party exception text may be exposed. Transaction rollback must remove assessment, metric, issue and audit rows together.

## Q-021 and activation boundary

Q-021 — PR-009 image-quality policy thresholds is OPEN and requires product-owner acceptance. PR-009 implementation may build deterministic metrics, typed policy handling, persistence and tests. Production activation of a default quality policy and final human acceptance of PR-009 remain blocked until Q-021 is accepted. Tests may use explicit synthetic policies. Production composition must fail closed if no accepted production policy is configured.

## Mandatory future tests

Unit tests use synthetic-only generated images. Orientation tests cover EXIF 1-8, effective dimension swaps, orientation applied once, original bytes unchanged and no transformed artifact. Resolution tests cover short/long side metrics, equality at threshold, one pixel below threshold and orientation-swapped dimensions. Blur tests cover uniform image, sharp checker/grid, deterministic blurred image, frozen Laplacian vectors and Ubuntu/Windows equality. Contrast tests cover uniform grayscale, two-tone image, deterministic gradient and frozen population-standard-deviation vectors. Glare tests cover no clipped pixels, exact cutoff boundary, fraction exactly at threshold and immediately above threshold. Exposure tests cover shadow fraction, bright fraction, exact boundaries, mixed image and independent under/overexposure.

Aggregation tests cover no issues to `GOOD`, warnings only to `REVIEW_REQUIRED`, any blocking issue to `RETAKE_REQUIRED` and deterministic issue ordering. Repository and migration tests cover append-only assessments, multiple policy versions, immutable metrics/issues, transaction rollback, tamper detection, migration v0004 to v0005 and unchanged v0001-v0004 checksums. Privacy tests cover safe `repr`, no basename/path/hash/pixels/SQL/key/exception leakage, verifier allowlist and synthetic data only. Application-service tests cover explicit policy injection, storage integrity verification, atomic audit emission and fail-closed missing production policy.

## Cross-platform verifier

`scripts/verify_pr009_quality.py` must use real production components, run on supported Windows SQLCipher CI, use deterministic synthetic images, validate schema v5, immutable original bytes, orientation semantics, frozen metric vectors, issue aggregation, rollback and privacy, print only allowlisted records and return `0` on pass, `1` on product failure and `2` only for a documented unsupported environment.

## Manual local calibration

Calibration for Q-021 must be local. Evidence may include synthetic calibration and anonymized/non-PII images where legally and operationally allowed. No real documents, document-derived images or PII may enter Git, Codex or CI. Evidence must compare false warnings and missed warnings and select explicit `policy_id` and `policy_version` before production activation.

## Acceptance criteria for the future implementation PR

PR-009 production code is acceptable only when ADR-023 is accepted or explicitly reaffirmed, Q-021 status is respected, whole-frame scope is maintained, algorithms and rounding match frozen vectors, policy is explicit/versioned, persistence/audit/privacy/failure contracts are met, all tests and verifier pass on supported platforms, no production default policy is activated without Q-021 acceptance, no real documents or PII are committed, PR-010+ remain unauthorized and Gate 2 remains not accepted.

## Non-goals

No image modification, correction, enhancement, crop, perspective correction, segmentation, document detection/count, OCR, UI, automatic rejection/deletion, prepared JPEG generation, PR-010+ work, final calibrated threshold claim or real-document fixtures.
