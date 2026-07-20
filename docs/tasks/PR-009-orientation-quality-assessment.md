# PR-009 — Orientation and quality assessment contract

Status: AUTHORIZED FOR CONTRACT REVIEW; PRODUCTION IMPLEMENTATION NOT STARTED

## Implementation base rule

This documentation-only contract was prepared from PR #22 merge commit `063e4b5a981f8ef6914c055e9f50666bbf1be734`. The future PR-009 production implementation must branch from the exact merge commit of the PR that adds this contract, not from `063e4b5a981f8ef6914c055e9f50666bbf1be734`. Do not invent that future merge SHA.

## Goal and scope

PR-009 will implement deterministic whole-frame orientation and image-quality diagnostics for encrypted imported source files. Scope is limited to original EXIF orientation value, orientation-normalized analysis view, original encoded dimensions, orientation-normalized effective dimensions, minimum-resolution diagnostic, blur/sharpness metric, contrast metric, glare/highlight-clipping metric and exposure diagnostic.

PR-009 advances FR-04 but does not complete all of FR-04. FR-04 and `docs/image-pipeline.md` include overlapping broader quality items; this task stages region, boundary, geometry and document-presence work instead of silently expanding PR-009.

## Deferred scope

Deferred outside PR-009: cut-edge detection, perspective/skew assessment based on document boundaries, document presence detection, document count, segmentation, automatic crop, perspective correction and geometric transformation. PR-010 is staged for perspective and geometry tools. PR-012 is staged for document regions, document presence/count and multiple-document workflow. PR-010 and later remain unauthorized.

## Decoder boundary

The future implementation must preserve `MediaDecoderPort.decode_for_import()`, `DecodedMedia`, `PillowMediaDecoder.decode_for_import()`, DHASH64 9×8 behavior and accepted frozen DHASH64 vectors unchanged. PR-009 must not change the semantics or output of `decode_for_import()` and must not calculate full-resolution quality metrics from the 9×8 DHASH64 raster.

PR-009 adds a separate full-resolution quality-analysis decoder contract:

```python
class QualityAnalysisDecoderPort(Protocol):
    def decode_for_quality(self, *, content: bytes) -> DecodedQualityMedia: ...

@dataclass(frozen=True, slots=True)
class DecodedQualityMedia:
    media_type: SourceMediaType
    encoded_width: int
    encoded_height: int
    exif_orientation: int | None
    effective_width: int
    effective_height: int
    grayscale_pixels: bytes
    grayscale_width: int
    grayscale_height: int
```

`DecodedQualityMedia` invariants: all encoded/effective dimensions are `>= 1`; `grayscale_width == effective_width`; `grayscale_height == effective_height`; `len(grayscale_pixels) == effective_width * effective_height`; grayscale contains one unsigned 8-bit luminance byte per pixel; `exif_orientation` is `None` or 1–8; no path or modified image bytes are included. EXIF absent or invalid means `exif_orientation=None` with identity analysis orientation; EXIF 1 is identity; EXIF 2–8 apply the corresponding EXIF transform exactly once; EXIF 5/6/7/8 swap axes; EXIF 1/2/3/4 do not swap axes.

`PillowMediaDecoder` may implement both ports. `decode_for_quality()` uses the same accepted byte-based media detection, primary-frame selection, decompression-bomb protection, alpha compositing and controlled-error boundary; returns the full orientation-normalized grayscale plane; performs no resize; publishes no artifact; does not mutate original bytes; and must not call `decode_for_import()` to reconstruct quality pixels from the 9×8 raster. Shared helpers are allowed only if all PR-008 decoder and DHASH64 tests remain unchanged and green.

## Expected future implementation files

The future implementation may add or modify only after this contract is merged and accepted:

- `src/document_intake/domain/image_quality.py`;
- `src/document_intake/image_pipeline/quality_assessor.py`;
- `src/document_intake/application/dto/image_quality.py`;
- `src/document_intake/application/services/image_quality.py`;
- `src/document_intake/persistence/repositories/image_quality.py`;
- `src/document_intake/persistence/migrations/v0005_image_quality.py`;
- `scripts/verify_pr009_quality.py`.

Existing files expected to change in the implementation PR are `src/document_intake/application/ports/media.py`, `src/document_intake/application/ports/persistence.py`, `src/document_intake/application/ports/__init__.py`, persistence database registration/factory files, `src/document_intake/persistence/migrations/__init__.py`, `src/document_intake/persistence/serialization.py`, repository Unit of Work wiring, audit enum/serialization files and tests. This contract PR creates none of those production files.

## Exact domain, DTO and policy contracts

Future domain contracts are immutable frozen/slotted types: `QualityAssessmentStatus`, `QualityIssueCode`, `QualityIssueSeverity`, `QualityMetricCode`, `QualityMetricUnit`, `QualityPolicyVersion`, `ImageQualityMetric`, `ImageQualitySeverityRule`, `ImageQualityIssue`, `ImageQualityAssessment` and `ImageQualityPolicy`.

Enums are exact `StrEnum` values: `QualityAssessmentStatus` has `GOOD`, `REVIEW_REQUIRED`, `RETAKE_REQUIRED`; `QualityIssueCode` has `LOW_RESOLUTION`, `BLUR_DETECTED`, `LOW_CONTRAST`, `GLARE_DETECTED`, `UNDEREXPOSED`, `OVEREXPOSED`; `QualityIssueSeverity` has `WARNING`, `BLOCKING`; `QualityMetricCode` has `SHORT_SIDE_PIXELS`, `LONG_SIDE_PIXELS`, `LAPLACIAN_VARIANCE`, `LUMINANCE_STANDARD_DEVIATION`, `HIGHLIGHT_CLIPPED_FRACTION`, `SHADOW_CLIPPED_FRACTION`, `BRIGHT_CLIPPED_FRACTION`; `QualityMetricUnit` has `PIXELS`, `VARIANCE`, `LUMA_LEVEL`, `FRACTION`. Unit mapping is exact: short/long side to `PIXELS`, Laplacian to `VARIANCE`, luminance standard deviation to `LUMA_LEVEL`, and all clipped fractions to `FRACTION`.

`QualityPolicyVersion(policy_id: str, version: int)` validates `policy_id` against `[A-Z][A-Z0-9_]{0,63}`, forbids whitespace/path separators/punctuation outside underscore, requires `version >= 1`, and has safe `repr`.

`ImageQualityMetric(metric_code, algorithm_id, algorithm_version, numeric_value: Decimal, unit)` validates algorithm ID in `RESOLUTION_V1`, `BLUR_LAPLACIAN_V1`, `CONTRAST_STDDEV_V1`, `GLARE_CLIPPED_FRACTION_V1`, `EXPOSURE_CLIPPED_FRACTION_V1`; `algorithm_version == 1`; finite Decimal numeric values; no NaN/infinity; dimensions integral Decimal `>= 1`; variance/stddev `>= 0`; fractions in `[0, 1]`; exact code/algorithm/unit combinations; no arbitrary metadata. Canonical metric order is `SHORT_SIDE_PIXELS`, `LONG_SIDE_PIXELS`, `LAPLACIAN_VARIANCE`, `LUMINANCE_STANDARD_DEVIATION`, `HIGHLIGHT_CLIPPED_FRACTION`, `SHADOW_CLIPPED_FRACTION`, `BRIGHT_CLIPPED_FRACTION`.

`ImageQualitySeverityRule(issue_code, severity)` appears in policy exactly six times: every PR-009 issue code exactly once, no duplicates, no missing issue code, no deferred issue code and canonical issue-code order.

`ImageQualityIssue(issue_code, severity)` contains no free-text message, path, filename, hash, raw observed value or threshold text. Duplicate issue codes within one assessment are forbidden. Issue ordering is canonical enum order. Observed values are typed metrics; thresholds are in the persisted policy snapshot.

`ImageQualityPolicy` fields are exactly `version: QualityPolicyVersion`, `minimum_short_side_pixels: int`, `minimum_long_side_pixels: int`, `blur_minimum_laplacian_variance: Decimal`, `contrast_minimum_luminance_stddev: Decimal`, `glare_highlight_cutoff: int`, `glare_maximum_fraction: Decimal`, `exposure_shadow_cutoff: int`, `exposure_maximum_shadow_fraction: Decimal`, `exposure_bright_cutoff: int`, `exposure_maximum_bright_fraction: Decimal`, `severity_rules: tuple[ImageQualitySeverityRule, ...]`. Validation: minimum dimensions integers `>= 1`; short side minimum `<=` long side minimum; blur/contrast thresholds finite and `>= 0`; grayscale cutoffs integers `0..255`; `exposure_shadow_cutoff < exposure_bright_cutoff`; all maximum fractions finite Decimal in `[0, 1]`; severity rules contain all six issue codes exactly once; no additional issue codes; no dictionary mapping; safe deterministic `repr`; no hidden defaults.

`ImageQualityAssessment` fields are exactly `id: EntityId`, `source_file_id: EntityId`, `assessed_at: datetime`, `policy_version: QualityPolicyVersion`, `status: QualityAssessmentStatus`, `encoded_width: int`, `encoded_height: int`, `exif_orientation: int | None`, `effective_width: int`, `effective_height: int`, `metrics: tuple[ImageQualityMetric, ...]`, `issues: tuple[ImageQualityIssue, ...]`. Invariants: valid IDs; timezone-aware UTC-normalized timestamp; positive dimensions; orientation `None` or 1–8; effective dimensions match orientation axis rule; exactly seven metrics with unique codes in canonical order; issues unique and canonical; issue severity equals policy severity rule; status derived from issues and cannot disagree; no arbitrary metadata, actor, username, filename, path, hash, pixel data or exception text.

DTOs must be PII-safe and include assessment ID, source file ID, status, encoded/effective dimensions, EXIF orientation, policy ID/version, metrics, issues and timestamps. DTOs must exclude basenames, paths, hashes, pixels, thumbnails, arbitrary metadata and raw exceptions.

## Exact command and service contract

The command is exact:

```python
@dataclass(frozen=True, slots=True)
class AssessSourceFileQualityCommand:
    source_file_id: EntityId
    assessment_id: EntityId
    audit_event_id: EntityId
    assessed_at: datetime
    actor: ActorRef
    policy: ImageQualityPolicy
    correlation_id: EntityId
```

All four IDs are valid `EntityId` values; `assessment_id`, `audit_event_id`, `source_file_id` and `correlation_id` follow existing entity-ID validation; `assessment_id != audit_event_id`; `assessed_at` is timezone-aware and normalized to UTC; actor is caller-supplied; policy is caller-supplied and validated before storage access. The service must not generate UUIDs, read the system clock, infer actor, infer correlation ID or load a process-global default policy.

The exact service contract is:

```python
assess_source_file_quality(
    command: AssessSourceFileQualityCommand,
    *,
    decoder: QualityAnalysisDecoderPort,
    storage: StoragePort,
    database: DatabasePort,
) -> AssessSourceFileQualityResult
```

The implementation may use the repository's actual Unit of Work dependency naming convention, but ID and timestamp generation are not open. The service loads immutable `SourceFile` and encrypted original artifact, verifies storage integrity, decodes through `QualityAnalysisDecoderPort`, computes metrics, evaluates policy, persists assessment/metrics/issues and one audit event atomically, and returns a sanitized DTO.

## Algorithms, comparisons and aggregation

Algorithms are exactly `RESOLUTION_V1`, `BLUR_LAPLACIAN_V1`, `CONTRAST_STDDEV_V1`, `GLARE_CLIPPED_FRACTION_V1` and `EXPOSURE_CLIPPED_FRACTION_V1`. The Laplacian kernel is `[0, 1, 0; 1, -4, 1; 0, 1, 0]`; border handling is valid-interior only; grayscale is full-resolution quality-analysis luminance after one EXIF analysis orientation. RGB conversion, if needed, uses `round_half_up((299*R + 587*G + 114*B) / 1000)`.

Comparison rules are exact. `LOW_RESOLUTION` exists when `short_side < minimum_short_side_pixels OR long_side < minimum_long_side_pixels`; equality produces no issue and only one resolution issue may exist. `BLUR_DETECTED` exists when `laplacian_variance < blur_minimum_laplacian_variance`; equality produces no issue. `LOW_CONTRAST` exists when `luminance_standard_deviation < contrast_minimum_luminance_stddev`; equality produces no issue. `GLARE_DETECTED` uses `count(pixel >= glare_highlight_cutoff) / total_pixel_count` and exists when `highlight_clipped_fraction > glare_maximum_fraction`; equality produces no issue. `UNDEREXPOSED` uses `count(pixel <= exposure_shadow_cutoff) / total_pixel_count` and exists when `shadow_clipped_fraction > exposure_maximum_shadow_fraction`; equality produces no issue. `OVEREXPOSED` uses `count(pixel >= exposure_bright_cutoff) / total_pixel_count` and exists when `bright_clipped_fraction > exposure_maximum_bright_fraction`; equality produces no issue. Glare and overexposure are independent; both `GLARE_DETECTED` and `OVEREXPOSED` may coexist. All seven metrics are calculated and persisted even when issues exist.

Rounding is exact: dimensions are integer Decimal values; variance and standard deviation round half up to six decimal places; fractions round half up to eight decimal places; comparisons use exact rounded persisted Decimal values; no binary float threshold comparison. Population variance uses exact integer sums. Standard deviation uses Decimal square root with local decimal context `precision = 28` and `rounding = ROUND_HALF_UP`, never process-global context, then rounds half up to six decimal places.

Status aggregation is exact: `GOOD` when issues are empty; `REVIEW_REQUIRED` when at least one issue exists and all severities are `WARNING`; `RETAKE_REQUIRED` when at least one issue is `BLOCKING`. Priority is `RETAKE_REQUIRED > REVIEW_REQUIRED > GOOD`. Issue ordering is canonical issue-code order, not discovery order. No issue automatically rejects, deletes, suppresses, modifies or replaces the source file.

## Service, persistence and audit

Migration v0005 may create append-only `image_quality_assessments`, `image_quality_metrics` and `image_quality_issues`. `image_quality_assessments` columns are `id`, `source_file_id`, `assessed_at`, `policy_id`, `policy_version`, `status`, `encoded_width`, `encoded_height`, `exif_orientation`, `effective_width`, `effective_height`, `canonical_payload`. Constraints include primary key, foreign key to `source_files`, timezone-normalized timestamp, positive dimensions, EXIF null or 1–8, accepted status values, unique assessment ID, no update/delete/replace, canonical-payload/projection equality, deterministic listing by `assessed_at` then `id`.

`image_quality_metrics` columns are `assessment_id`, `ordinal`, `metric_code`, `algorithm_id`, `algorithm_version`, `numeric_value`, `unit`, `canonical_payload`; constraints include assessment foreign key, ordinal 0–6, unique `(assessment_id, ordinal)`, unique `(assessment_id, metric_code)`, exact controlled values, canonical metric ordering and no update/delete/replace.

`image_quality_issues` columns are `assessment_id`, `ordinal`, `issue_code`, `severity`, `canonical_payload`; constraints include assessment foreign key, non-negative contiguous ordinal, unique `(assessment_id, ordinal)`, unique `(assessment_id, issue_code)`, exact controlled values, canonical issue ordering and no update/delete/replace.

PR-009 selects one exact policy-freezing approach: Persist the complete canonical policy snapshot inside the assessment canonical payload. No separate mutable policy table is part of PR-009. Persisting only policy ID/version while allowing thresholds to change elsewhere is prohibited.

The future implementation must add exactly `AuditAction.IMAGE_QUALITY_ASSESSED`, `AuditSubjectType.IMAGE_QUALITY_ASSESSMENT` and `AuditReasonCode("IMAGE_QUALITY_ASSESSMENT")`; it must not reuse `ARTIFACT_REGISTERED`, `ENTITY_CREATED` or another unrelated action. Exact audit event: `event_id=command.audit_event_id`, `action_code=AuditAction.IMAGE_QUALITY_ASSESSED`, `subject_type=AuditSubjectType.IMAGE_QUALITY_ASSESSMENT`, `subject_id=command.assessment_id`, `field_key=None`, `before.classification=ABSENT`, `before.display_value=None`, `before.was_present=False`, `after.classification=NON_SENSITIVE`, `after.display_value="QUALITY_ASSESSMENT"`, `after.was_present=True`, `reason_code=AuditReasonCode("IMAGE_QUALITY_ASSESSMENT")`, `correlation_id=command.correlation_id`, `actor=command.actor`, `occurred_at=command.assessed_at`. Required tests include enum serialization, migration compatibility, audit canonical payload, exact event fields, rollback, verifier assertions and unchanged historical audit values/behavior.

## Failure codes and privacy

Future stable error codes are `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `QUALITY_POLICY_INVALID`, `QUALITY_ASSESSMENT_FAILED` and `PERSISTENCE_FAILED`. Policy validation fails before storage access. No third-party exception text may be exposed. Transaction rollback must remove assessment, metric, issue and audit rows together.

Privacy restrictions prohibit basenames, paths, hashes, image bytes, pixel dumps, thumbnails, arbitrary EXIF beyond orientation, GPS, camera make/model, username, raw exception, SQL and key material in domain objects, DTOs, audit event, errors, verifier output and logs.

## Q-021 and activation boundary

Q-021 — PR-009 whole-frame diagnostic policy thresholds is OPEN and requires product-owner acceptance. It controls minimum source-image dimensions, blur threshold, contrast threshold, glare cutoff/fraction, exposure cutoffs/fractions, severity mapping, production `policy_id`, production policy version, activation of default PR-009 policy and final PR-009 human acceptance. PR-009 implementation may build deterministic metrics, typed policy handling, persistence and tests. Production activation of a default quality policy and final human acceptance remain blocked until Q-021 is accepted. Tests may use explicit synthetic policies. Production composition must fail closed if no accepted production policy is configured.

Q-007 remains separate and deferred for PR-011 prepared-JPEG readability and post-compression resolution thresholds. The PR-009 whole-frame source-quality threshold portion is separated into Q-021. Q-007 no longer blocks PR-009 algorithm or persistence implementation.

## Mandatory future tests

Unit tests use synthetic-only generated images. Orientation tests cover EXIF 1-8, effective dimension swaps, orientation applied once, original bytes unchanged and no transformed artifact. Decoder tests prove `decode_for_import()` output remains unchanged while `decode_for_quality()` returns full-resolution pixels. Resolution tests cover short/long side metrics, equality at threshold, one pixel below threshold and orientation-swapped dimensions. Blur tests cover uniform image, sharp checker/grid, deterministic blurred image, frozen Laplacian vectors and Ubuntu/Windows equality. Contrast tests cover uniform grayscale, two-tone image, deterministic gradient and frozen population-standard-deviation vectors. Glare tests cover no clipped pixels, exact cutoff boundary, fraction exactly at threshold and immediately above threshold. Exposure tests cover shadow fraction, bright fraction, exact boundaries, mixed image and independent under/overexposure.

Aggregation tests cover no issues to `GOOD`, warnings only to `REVIEW_REQUIRED`, any blocking issue to `RETAKE_REQUIRED` and deterministic issue ordering. Repository and migration tests cover append-only assessments, multiple policy versions, immutable metrics/issues, transaction rollback, tamper detection, migration v0004 to v0005, full canonical policy snapshot persistence and unchanged v0001-v0004 checksums. Privacy tests cover safe `repr`, no basename/path/hash/pixels/SQL/key/exception leakage, verifier allowlist and synthetic data only. Application-service tests cover explicit policy injection, caller-supplied IDs/timestamp, storage integrity verification, exact audit event, atomic audit emission and fail-closed missing production policy.

## Cross-platform verifier

`scripts/verify_pr009_quality.py` must use real production components, run on supported Windows SQLCipher CI, use deterministic synthetic images, validate schema v5, immutable original bytes, import decoder compatibility, quality decoder full-resolution semantics, orientation semantics, frozen metric vectors, issue aggregation, full policy snapshot, complete audit event, rollback and privacy, print only allowlisted records and return `0` on pass, `1` on product failure and `2` only for a documented unsupported environment.

## Manual local calibration

Calibration for Q-021 must be local. Evidence may include synthetic calibration and anonymized/non-PII images where legally and operationally allowed. No real documents, document-derived images or PII may enter Git, Codex or CI. Evidence must compare false warnings and missed warnings and select explicit `policy_id` and `policy_version` before production activation.

## Acceptance criteria for the future implementation PR

PR-009 production code is acceptable only when ADR-023 is accepted or explicitly reaffirmed, Q-021 status is respected, whole-frame scope is maintained, import decoder DHASH64 behavior is preserved, quality decoder is full-resolution and separate, command IDs/timestamp are caller-supplied, audit event is exact, algorithms/comparisons/rounding match frozen vectors, policy is explicit/versioned/snapshotted, persistence/privacy/failure contracts are met, all tests and verifier pass on supported platforms, no production default policy is activated without Q-021 acceptance, no real documents or PII are committed, PR-010+ remain unauthorized and Gate 2 remains not accepted.

## Non-goals

No image modification, correction, enhancement, crop, perspective correction, segmentation, document detection/count, OCR, UI, automatic rejection/deletion, prepared JPEG generation, PR-010+ work, final calibrated threshold claim or real-document fixtures.
