# ADR-023 — Deterministic whole-frame image quality assessment v1

Status: PROPOSED

Decision owner: Product owner

Date: 2026-07-21

## Context and source conflict

FR-04 in `docs/technical-specification.md` requires orientation, sharpness, glare, contrast, cropped edges, minimum resolution and document presence checks. `docs/image-pipeline.md` previously grouped blur, contrast, glare, exposure, resolution, cut edges, perspective and possible document count under quality assessment. The implementation plan stages PR-009 more narrowly around EXIF, dimensions, blur, glare and contrast diagnostics. This ADR records the conflict instead of resolving it silently.

PR-009 advances FR-04 but does not complete all of FR-04. PR-009 covers only deterministic whole-frame diagnostics that can be computed from the decoded source image without document segmentation, document boundaries or geometry inference: original EXIF orientation value, orientation-normalized analysis view, original encoded dimensions, orientation-normalized effective dimensions, minimum-resolution diagnostic, blur/sharpness metric, contrast metric, glare/highlight-clipping metric and exposure diagnostic. Cut-edge detection (cut-edge detection), perspective/skew assessment based on document boundaries, document presence detection, document count, segmentation, automatic crop, perspective correction and geometric transformation are deferred. Staging is: PR-010 for perspective and geometry tools; PR-012 for document regions, document presence/count and multiple-document workflow. PR-010 and later remain unauthorized by this ADR.

## Decision

### 1. Non-destructive analysis

Original encrypted bytes remain immutable. PR-009 does not publish a modified image. Quality analysis uses an in-memory decoded representation. EXIF orientation may be applied once to the analysis view. Applying EXIF orientation to the analysis view does not alter the stored original. PR-009 must not reapply orientation already applied by the decoder contract. Geometry and prepared-image recipes remain later work.

### 2. Analysis coordinate contract

Every assessment records `encoded_width`, `encoded_height`, `exif_orientation`, `effective_width` and `effective_height`. `effective_width` and `effective_height` describe the orientation-normalized analysis view. For EXIF orientations that swap axes, namely 5, 6, 7 and 8, effective dimensions are swapped deterministically. Orientations 1, 2, 3 and 4 preserve axes. No transformed image path or transformed image bytes are persisted by PR-009.

### 3. Exact domain types

PR-009 proposes immutable frozen/slotted contracts for `QualityAssessmentStatus`, `QualityIssueCode`, `QualityIssueSeverity`, `QualityMetricCode`, `QualityPolicyVersion`, `ImageQualityMetric`, `ImageQualityIssue` and `ImageQualityAssessment`.

Status values are exactly `GOOD`, `REVIEW_REQUIRED` and `RETAKE_REQUIRED`. PR-009 issue codes are exactly `LOW_RESOLUTION`, `BLUR_DETECTED`, `LOW_CONTRAST`, `GLARE_DETECTED`, `UNDEREXPOSED` and `OVEREXPOSED`. Deferred issue codes are not part of PR-009: `CUT_EDGES`, `PERSPECTIVE`, `DOCUMENT_NOT_FOUND` and `MULTIPLE_DOCUMENTS`. Severity values are exactly `WARNING` and `BLOCKING`.

### 4. Typed metric contract

Each metric includes only typed, non-sensitive diagnostic data: `metric_code`, `algorithm_id`, `algorithm_version`, `numeric_value` and `unit`. PR-009 metric codes are exactly `SHORT_SIDE_PIXELS`, `LONG_SIDE_PIXELS`, `LAPLACIAN_VARIANCE`, `LUMINANCE_STANDARD_DEVIATION`, `HIGHLIGHT_CLIPPED_FRACTION`, `SHADOW_CLIPPED_FRACTION` and `BRIGHT_CLIPPED_FRACTION`. Arbitrary metadata dictionaries are prohibited. Assessments must not persist histograms, thumbnails, pixels, filenames, paths or hashes.

### 5. Algorithm contracts

PR-009 defines deterministic versioned algorithms but does not approve final numeric production thresholds.

- `RESOLUTION_V1`: orientation-normalized short and long side in pixels, integer units, computed after the EXIF one-time analysis-view rule.
- `BLUR_LAPLACIAN_V1`: variance of a fixed discrete Laplacian over an 8-bit grayscale analysis image.
- `CONTRAST_STDDEV_V1`: population standard deviation of 8-bit grayscale luminance.
- `GLARE_CLIPPED_FRACTION_V1`: fraction of grayscale pixels at or above a policy-provided highlight cutoff.
- `EXPOSURE_CLIPPED_FRACTION_V1`: fractions of grayscale pixels at or below a shadow cutoff and at or above a bright cutoff.

The exact Laplacian kernel is the 3x3 integer kernel `[0, 1, 0; 1, -4, 1; 0, 1, 0]`. Border handling is valid-interior only: compute Laplacian responses only for pixels whose four direct neighbors exist; images smaller than 3x3 fail with `QUALITY_ASSESSMENT_FAILED` unless already blocked by policy validation. Grayscale source is the decoder-provided 8-bit luminance analysis plane after the accepted import decoder's color/alpha handling and after the one permitted orientation normalization. If the decoder returns only RGB for PR-009, luminance must be computed as integer BT.601 luma `Y = round_half_up((299*R + 587*G + 114*B) / 1000)` with R/G/B in 0..255; this is a behavior-changing algorithm input and must be frozen in tests. Population variance and standard deviation use exact integer sums. `LAPLACIAN_VARIANCE` and luminance standard deviation numeric values are decimal strings rounded half up to six fractional places. Fraction metrics are decimal strings rounded half up to eight fractional places. Pixel counts, dimensions and thresholds remain integers. Frozen vectors must compare exact serialized values on Ubuntu and Windows.

### 6. Versioned policy

`ImageQualityPolicy` is immutable and includes `policy_id`, `policy_version`, `minimum_short_side_pixels`, `minimum_long_side_pixels`, `blur_minimum_laplacian_variance`, `contrast_minimum_luminance_stddev`, `glare_highlight_cutoff`, `glare_maximum_fraction`, `exposure_shadow_cutoff`, `exposure_maximum_shadow_fraction`, `exposure_bright_cutoff` and `exposure_maximum_bright_fraction`. The policy also explicitly maps every PR-009 issue code to `WARNING` or `BLOCKING` severity.

The assessment engine receives the policy explicitly. There are no hidden process-global thresholds. Policy ID and version are persisted with every assessment. Rerunning with a different policy creates a new immutable assessment. Existing assessments are not overwritten. Tests use explicit synthetic policies. Final production baseline threshold values are not silently selected by Codex.

### 7. Unresolved threshold decision

Q-021 — PR-009 image-quality policy thresholds is `OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE`. Required evidence is local synthetic calibration, a local anonymized/non-PII image set where legally and operationally allowed, no real documents in Git, Codex or CI, comparison of false warning and missed warning rates, and explicit selected `policy_id` and `policy_version`.

Until Q-021 is accepted, algorithm and policy infrastructure may be implemented; production baseline threshold values must not be claimed final; PR-009 must not be described as pilot-calibrated; tests may use explicit test-only policies; application composition must fail closed if no accepted production policy is configured. PROPOSED recommendation for review: PR-009 implementation may build deterministic metrics, typed policy handling, persistence and tests. Production activation of a default quality policy and final human acceptance of PR-009 remain blocked until Q-021 is accepted.

### 8. Status aggregation rules

Aggregation is exact and independent of numeric threshold values: `GOOD` means no issues; `REVIEW_REQUIRED` means one or more `WARNING` issues and no `BLOCKING` issues; `RETAKE_REQUIRED` means one or more `BLOCKING` issues. Default severity mapping is part of the policy and is not hardcoded inside algorithms. No diagnostic automatically deletes, rejects or overwrites a source file. Operator workflow integration remains later work.

### 9. Persistence contract

PR-009 proposes immutable append-only persistence. The future implementation PR may add migration v0005; this documentation PR does not implement it. Repository concepts are `image_quality_assessments`, `image_quality_metrics` and `image_quality_issues`. Assessment references `SourceFile`; one source file may have multiple assessment versions; assessment ID, policy ID/version and algorithm IDs/versions are immutable; metrics and issues are append-only. Deterministic ordering is metric code order listed in this ADR and issue code order listed in this ADR. Update/delete/replace operations are forbidden. Tamper/projection-integrity checks follow existing persistence conventions. The same SQLCipher database and Unit of Work are used; no independent connection or commit is allowed.

### 10. Application-service contract

The future service is equivalent to `assess_source_file_quality(command, dependencies) -> result`. Inputs include `source_file_id`, `actor`, `policy` and `correlation_id`. The service loads the immutable source file and encrypted original artifact; verifies stored-artifact integrity through existing storage; decodes using the accepted media decoder; obtains orientation-normalized analysis pixels; calculates deterministic metrics; evaluates the explicit policy; persists assessment, metrics, issues and one audit event atomically; and returns a PII-safe DTO. It must not reuse a caller-provided filesystem path, persist a source path, or modify the original artifact or source-file row.

### 11. Audit contract

The future PR-009 service emits one immutable audit event only after successful persistence. ADR-023 proposes the new controlled action code `IMAGE_QUALITY_ASSESSED` with subject type `SOURCE_FILE` or a newly specified `IMAGE_QUALITY_ASSESSMENT` if the PR-009 task adds that enum with migration/serialization compatibility tests. The implementation must not overload an unrelated action silently. Audit data contains the source-file subject ID or assessment subject ID, policy identifier/version in non-sensitive controlled form and correlation ID. Audit data contains no paths, filenames, image hashes, raw metric collection or free-text exception.

### 12. Privacy

Quality results may contain controlled codes, algorithm IDs and versions, numeric metrics, dimensions, policy ID/version, timestamps and opaque entity IDs. They must not contain original basename, source path, storage path, database path, SHA-256, perceptual hash, image bytes, pixel dumps, thumbnails, EXIF metadata other than orientation, GPS, camera manufacturer/model, operator username, raw exception, SQL or key material. All representations and errors remain sanitized.

### 13. Failure model

Stable controlled error codes for the future task include `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `QUALITY_POLICY_INVALID`, `QUALITY_ASSESSMENT_FAILED` and `PERSISTENCE_FAILED`. Third-party exception text must not escape. Validation and decode failures do not persist partial assessment rows. Database persistence and audit insertion occur in one Unit of Work transaction; any failure rolls back assessment, metrics, issues and audit event together.

### 14. Non-goals

Non-goals are image modification, correction or enhancement, crop, perspective correction, segmentation, document detection/count, OCR, UI, automatic rejection or deletion, prepared JPEG, PR-010+ work, claims of final calibrated thresholds and real-document fixtures.
