# ADR-023 — Deterministic whole-frame image quality assessment v1

Status: ACCEPTED

Decision owner: Product owner

Date: 2026-07-21

## Context and source conflict

FR-04 in `docs/technical-specification.md` requires orientation, sharpness, glare, contrast, cropped edges, minimum resolution and document presence checks. `docs/image-pipeline.md` previously grouped blur, contrast, glare, exposure, resolution, cut edges, perspective and possible document count under quality assessment. The implementation plan stages PR-009 more narrowly around EXIF, dimensions, blur, glare and contrast diagnostics. This ADR records the conflict instead of resolving it silently.

PR-009 advances FR-04 but does not complete all of FR-04. PR-009 covers only deterministic whole-frame diagnostics that can be computed from the decoded source image without document segmentation, document boundaries or geometry inference: original EXIF orientation value, orientation-normalized analysis view, original encoded dimensions, orientation-normalized effective dimensions, minimum-resolution diagnostic, blur/sharpness metric, contrast metric, glare/highlight-clipping metric and exposure diagnostic. Deferred scope is cut-edge detection, perspective/skew assessment based on document boundaries, document presence detection, document count, segmentation, automatic crop, perspective correction and geometric transformation. Staging is: PR-010 for perspective and geometry tools; PR-012 for document regions, document presence/count and multiple-document workflow. PR-010 and later remain unauthorized by this ADR.

## Decision

### 1. Non-destructive analysis and decoder boundary

Original encrypted bytes remain immutable. PR-009 does not publish a modified image. Quality analysis uses an in-memory decoded representation. EXIF orientation may be applied once to the quality-analysis view. Applying EXIF orientation to the analysis view does not alter the stored original. Geometry and prepared-image recipes remain later work.

PR-009 preserves the existing PR-008 import decoder contract unchanged: `MediaDecoderPort.decode_for_import()`, `DecodedMedia`, `PillowMediaDecoder.decode_for_import()`, `DHASH64` 9×8 behavior and accepted frozen DHASH64 vectors remain unchanged. `decode_for_import()` continues to return the PR-008 DHASH64-oriented 9×8 grayscale raster and must not be used as the source for full-resolution blur, contrast, glare or exposure analysis.

PR-009 defines a separate quality-analysis decoder port:

```python
class QualityAnalysisDecoderPort(Protocol):
    def decode_for_quality(self, *, content: bytes) -> DecodedQualityMedia: ...
```

The exact immutable DTO is:

```python
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

Invariants are: `encoded_width >= 1`, `encoded_height >= 1`, `effective_width >= 1`, `effective_height >= 1`, `grayscale_width == effective_width`, `grayscale_height == effective_height`, `len(grayscale_pixels) == effective_width * effective_height`, grayscale contains one unsigned 8-bit luminance byte per pixel, `exif_orientation` is `None` or an integer from 1 through 8, and no image path or modified image bytes are included.

Orientation behavior is exact: absent EXIF yields `exif_orientation=None` and identity analysis orientation; invalid EXIF yields `exif_orientation=None` and identity analysis orientation; EXIF 1 is identity; EXIF 2–8 apply the corresponding EXIF transform exactly once to the quality-analysis image; EXIF 5, 6, 7 and 8 swap effective axes; EXIF 1, 2, 3 and 4 do not swap effective axes.

`PillowMediaDecoder` may implement both `MediaDecoderPort` and `QualityAnalysisDecoderPort`. `decode_for_quality()` uses the same accepted byte-based media detection, primary-frame selection, decompression-bomb protection, alpha compositing and controlled-error boundary; returns the full orientation-normalized grayscale plane; performs no resize; publishes no artifact; does not mutate original bytes; and must not call `decode_for_import()` to reconstruct quality pixels from the 9×8 DHASH64 raster. Shared private decode helpers are permitted only if all existing PR-008 decoder and DHASH64 tests remain unchanged and green.

The product owner accepts Pillow-detected `MPO` only as JPEG input compatibility. Both decoder methods explicitly seek frame `0`, apply its EXIF orientation exactly once and ignore all additional frames. They do not expose frame counts or secondary-frame data and do not create a flattened or converted artifact.

MPO detected as a JPEG container is accepted as JPEG.
Only primary frame 0 is decoded.
Original bytes remain immutable.
Secondary frames are ignored in MVP.

### 2. Analysis coordinate contract

Every assessment records `encoded_width`, `encoded_height`, `exif_orientation`, `effective_width` and `effective_height`. `effective_width` and `effective_height` describe the orientation-normalized analysis view. For EXIF orientations that swap axes, namely 5, 6, 7 and 8, effective dimensions are swapped deterministically. Orientations 1, 2, 3 and 4 preserve axes. No transformed image path or transformed image bytes are persisted by PR-009.

### 3. Exact domain types

PR-009 proposes these immutable frozen/slotted contracts:

```python
class QualityAssessmentStatus(StrEnum):
    GOOD = "GOOD"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    RETAKE_REQUIRED = "RETAKE_REQUIRED"

class QualityIssueCode(StrEnum):
    LOW_RESOLUTION = "LOW_RESOLUTION"
    BLUR_DETECTED = "BLUR_DETECTED"
    LOW_CONTRAST = "LOW_CONTRAST"
    GLARE_DETECTED = "GLARE_DETECTED"
    UNDEREXPOSED = "UNDEREXPOSED"
    OVEREXPOSED = "OVEREXPOSED"

class QualityIssueSeverity(StrEnum):
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"

class QualityMetricCode(StrEnum):
    SHORT_SIDE_PIXELS = "SHORT_SIDE_PIXELS"
    LONG_SIDE_PIXELS = "LONG_SIDE_PIXELS"
    LAPLACIAN_VARIANCE = "LAPLACIAN_VARIANCE"
    LUMINANCE_STANDARD_DEVIATION = "LUMINANCE_STANDARD_DEVIATION"
    HIGHLIGHT_CLIPPED_FRACTION = "HIGHLIGHT_CLIPPED_FRACTION"
    SHADOW_CLIPPED_FRACTION = "SHADOW_CLIPPED_FRACTION"
    BRIGHT_CLIPPED_FRACTION = "BRIGHT_CLIPPED_FRACTION"

class QualityMetricUnit(StrEnum):
    PIXELS = "PIXELS"
    VARIANCE = "VARIANCE"
    LUMA_LEVEL = "LUMA_LEVEL"
    FRACTION = "FRACTION"
```

Metric-unit mapping is exact: `SHORT_SIDE_PIXELS -> PIXELS`, `LONG_SIDE_PIXELS -> PIXELS`, `LAPLACIAN_VARIANCE -> VARIANCE`, `LUMINANCE_STANDARD_DEVIATION -> LUMA_LEVEL`, `HIGHLIGHT_CLIPPED_FRACTION -> FRACTION`, `SHADOW_CLIPPED_FRACTION -> FRACTION`, `BRIGHT_CLIPPED_FRACTION -> FRACTION`. Deferred issue codes are not part of PR-009: `CUT_EDGES`, `PERSPECTIVE`, `DOCUMENT_NOT_FOUND` and `MULTIPLE_DOCUMENTS`.

### 4. Exact value objects and entities

`QualityPolicyVersion` is `@dataclass(frozen=True, slots=True)` with `policy_id: str` and `version: int`. `policy_id` matches `[A-Z][A-Z0-9_]{0,63}`, contains no whitespace, path separators or punctuation outside underscore, `version >= 1`, and `repr` is safe.

`ImageQualityMetric` is `@dataclass(frozen=True, slots=True)` with `metric_code: QualityMetricCode`, `algorithm_id: str`, `algorithm_version: int`, `numeric_value: Decimal` and `unit: QualityMetricUnit`. `algorithm_id` is one of `RESOLUTION_V1`, `BLUR_LAPLACIAN_V1`, `CONTRAST_STDDEV_V1`, `GLARE_CLIPPED_FRACTION_V1`, `EXPOSURE_CLIPPED_FRACTION_V1`; `algorithm_version == 1`; `numeric_value` is finite Decimal with no NaN or infinity; dimensions are integral Decimal values `>= 1`; variance and standard deviation are `>= 0`; fractions are in `[0, 1]`; metric code, algorithm and unit combinations are exact; arbitrary metadata is prohibited. Canonical metric order is exactly `SHORT_SIDE_PIXELS`, `LONG_SIDE_PIXELS`, `LAPLACIAN_VARIANCE`, `LUMINANCE_STANDARD_DEVIATION`, `HIGHLIGHT_CLIPPED_FRACTION`, `SHADOW_CLIPPED_FRACTION`, `BRIGHT_CLIPPED_FRACTION`.

`ImageQualitySeverityRule` is `@dataclass(frozen=True, slots=True)` with `issue_code: QualityIssueCode` and `severity: QualityIssueSeverity`. A policy contains exactly six rules, every PR-009 issue code appears exactly once, there are no duplicates, no missing issue codes, no deferred issue codes, and canonical issue-code order is required.

`ImageQualityIssue` is `@dataclass(frozen=True, slots=True)` with `issue_code: QualityIssueCode` and `severity: QualityIssueSeverity`. It has no free-text message, path, filename, hash, raw observed value or threshold text. There is no duplicate issue code within one assessment, and canonical issue order is exactly the enum order listed above. Observed values remain available through typed metrics; thresholds remain available through the persisted policy snapshot.

`ImageQualityPolicy` is `@dataclass(frozen=True, slots=True)` with `version: QualityPolicyVersion`, `minimum_short_side_pixels: int`, `minimum_long_side_pixels: int`, `blur_minimum_laplacian_variance: Decimal`, `contrast_minimum_luminance_stddev: Decimal`, `glare_highlight_cutoff: int`, `glare_maximum_fraction: Decimal`, `exposure_shadow_cutoff: int`, `exposure_maximum_shadow_fraction: Decimal`, `exposure_bright_cutoff: int`, `exposure_maximum_bright_fraction: Decimal`, and `severity_rules: tuple[ImageQualitySeverityRule, ...]`. Validation requires minimum dimensions integers `>= 1`, `minimum_short_side_pixels <= minimum_long_side_pixels`, finite blur/contrast thresholds `>= 0`, grayscale cutoffs in `0..255`, `exposure_shadow_cutoff < exposure_bright_cutoff`, all maximum fractions finite Decimal values in `[0, 1]`, severity rules containing all six issue codes exactly once and no additional codes, no dictionary-based mapping, safe deterministic `repr`, and no hidden default values.

`ImageQualityAssessment` is `@dataclass(frozen=True, slots=True)` with `id: EntityId`, `source_file_id: EntityId`, `assessed_at: datetime`, `policy: ImageQualityPolicy`, `status: QualityAssessmentStatus`, `encoded_width: int`, `encoded_height: int`, `exif_orientation: int | None`, `effective_width: int`, `effective_height: int`, `metrics: tuple[ImageQualityMetric, ...]`, and `issues: tuple[ImageQualityIssue, ...]`. Invariants require valid IDs, timezone-aware UTC-normalized timestamp, positive dimensions, orientation `None` or 1–8, effective dimensions matching the orientation axis rule, exactly seven metrics with unique codes in canonical order, unique issues in canonical order, issue severity equal to the exact severity rule in `assessment.policy.severity_rules`, no issue code absent from policy severity rules, no additional policy issue codes, policy thresholds are the thresholds used to produce metrics and issues, database policy ID/version projections equal `assessment.policy.version`, canonical payload contains the complete policy, and rehydration reconstructs the complete `ImageQualityPolicy`, status derived exactly from issues and unable to disagree with issues, no arbitrary metadata, and no actor, username, filename, path, hash, pixel data or exception text.

### 5. Algorithm contracts and comparison boundaries

Algorithms are `RESOLUTION_V1`, `BLUR_LAPLACIAN_V1`, `CONTRAST_STDDEV_V1`, `GLARE_CLIPPED_FRACTION_V1` and `EXPOSURE_CLIPPED_FRACTION_V1`. The exact Laplacian kernel is the 3x3 integer kernel `[0, 1, 0; 1, -4, 1; 0, 1, 0]`. Border handling is valid-interior only. Grayscale source is the full-resolution `DecodedQualityMedia.grayscale_pixels` after the one permitted orientation normalization. If RGB conversion is needed, use integer BT.601 luma `Y = round_half_up((299*R + 587*G + 114*B) / 1000)` with R/G/B in 0..255.

Resolution metrics are `short_side = min(effective_width, effective_height)` and `long_side = max(effective_width, effective_height)`. `LOW_RESOLUTION` exists when `short_side < minimum_short_side_pixels OR long_side < minimum_long_side_pixels`; equality does not create an issue; only one `LOW_RESOLUTION` issue may exist even when both dimensions fail.

`BLUR_DETECTED` exists when `laplacian_variance < blur_minimum_laplacian_variance`; equality does not create an issue. `LOW_CONTRAST` exists when `luminance_standard_deviation < contrast_minimum_luminance_stddev`; equality does not create an issue. Highlight fraction is `count(pixel >= glare_highlight_cutoff) / total_pixel_count`; `GLARE_DETECTED` exists when `highlight_clipped_fraction > glare_maximum_fraction`; equality does not create an issue. Shadow fraction is `count(pixel <= exposure_shadow_cutoff) / total_pixel_count`; `UNDEREXPOSED` exists when `shadow_clipped_fraction > exposure_maximum_shadow_fraction`; equality does not create an issue. Bright fraction is `count(pixel >= exposure_bright_cutoff) / total_pixel_count`; `OVEREXPOSED` exists when `bright_clipped_fraction > exposure_maximum_bright_fraction`; equality does not create an issue. Glare and overexposure are independent evaluations, and both `GLARE_DETECTED` and `OVEREXPOSED` may be present in one assessment.

All seven metrics are calculated and persisted even when one or more issues are present. Dimensions are integer Decimal values. Variance and standard deviation are rounded half up to six decimal places. Fractions are rounded half up to eight decimal places. All comparison uses the exact rounded persisted Decimal value; no binary float threshold comparison is allowed. Population variance is computed from exact integer sums. Standard deviation computes the square root using `Decimal` with explicit local decimal context `precision = 28` and `rounding = ROUND_HALF_UP`; it must not depend on process-global decimal context and is then rounded half up to six decimal places. Frozen vectors must compare exact serialized values on Ubuntu and Windows.

### 6. Versioned policy and unresolved threshold decision

The assessment engine receives `ImageQualityPolicy` explicitly. There are no hidden process-global thresholds. Policy ID/version and the complete canonical policy snapshot are persisted with every assessment. Rerunning with a different policy creates a new immutable assessment. Existing assessments are not overwritten. Tests use explicit synthetic policies. Final production baseline threshold values are not silently selected by Codex.

Q-021 — PR-009 whole-frame diagnostic policy thresholds is `OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE`. It controls minimum source-image dimensions for PR-009 diagnostics, blur threshold, contrast threshold, glare cutoff/fraction, exposure cutoffs/fractions, severity mapping, production `policy_id`, production policy version, activation of the default PR-009 policy and final PR-009 human acceptance. Required evidence is local synthetic calibration, a local anonymized/non-PII image set where legally and operationally allowed, no real documents in Git, Codex or CI, comparison of false warning and missed warning rates, and explicit selected `policy_id` and `policy_version`.

Until Q-021 is accepted, algorithm and policy infrastructure may be implemented; production baseline threshold values must not be claimed final; PR-009 must not be described as pilot-calibrated; tests may use explicit test-only policies; application composition must fail closed if no accepted production policy is configured. PROPOSED recommendation for review: PR-009 implementation may build deterministic metrics, typed policy handling, persistence and tests. Production activation of a default quality policy and final human acceptance of PR-009 remain blocked until Q-021 is accepted.

### 7. Status aggregation rules

Aggregation is exact: `GOOD` means `issues` is empty; `REVIEW_REQUIRED` means at least one issue exists and all issues have severity `WARNING`; `RETAKE_REQUIRED` means at least one issue has severity `BLOCKING`. Status priority is `RETAKE_REQUIRED > REVIEW_REQUIRED > GOOD`. Issue ordering is canonical issue-code order, not discovery order. Default severity mapping is part of the policy and is not hardcoded inside algorithms. No issue automatically rejects, deletes, suppresses, modifies or replaces the source file. Operator workflow integration remains later work.

### 8. Persistence contract

PR-009 proposes immutable append-only persistence. The future implementation PR may add migration v0005; this documentation PR does not implement it. The same SQLCipher database and Unit of Work are used; no independent connection or commit is allowed.

`image_quality_assessments` logical columns are `id`, `source_file_id`, `assessed_at`, `policy_id`, `policy_version`, `status`, `encoded_width`, `encoded_height`, `exif_orientation`, `effective_width`, `effective_height` and `canonical_payload`. Constraints: primary key `id`, foreign key to `source_files`, timezone-normalized timestamp serialization, positive dimensions, EXIF orientation null or 1–8, accepted status values only, unique assessment ID, no update/delete/replace, canonical-payload/projection equality checks, deterministic source-file listing by `assessed_at`, then `id`.

`image_quality_metrics` logical columns are `assessment_id`, `ordinal`, `metric_code`, `algorithm_id`, `algorithm_version`, `numeric_value`, `unit` and `canonical_payload`. Constraints: foreign key to assessment, ordinal 0–6, unique `(assessment_id, ordinal)`, unique `(assessment_id, metric_code)`, exact controlled code values, canonical metric ordering and no update/delete/replace.

`image_quality_issues` logical columns are `assessment_id`, `ordinal`, `issue_code`, `severity` and `canonical_payload`. Constraints: foreign key to assessment, non-negative contiguous ordinal, unique `(assessment_id, ordinal)`, unique `(assessment_id, issue_code)`, exact controlled values, canonical issue ordering and no update/delete/replace.

PR-009 selects one exact policy-freezing approach: Persist the complete canonical policy snapshot inside the assessment canonical payload. No separate mutable policy table is part of PR-009. Persisting only policy ID/version while allowing thresholds to change elsewhere is prohibited. This guarantees historical reproducibility. Tamper/projection-integrity checks follow existing persistence conventions.



### 8a. Repository and Unit of Work contract

PR-009 adds exactly one future aggregate repository port:

```python
class ImageQualityAssessmentRepository(Protocol):
    def add(self, assessment: ImageQualityAssessment) -> None: ...

    def get(
        self,
        assessment_id: EntityId,
    ) -> ImageQualityAssessment | None: ...

    def list_by_source(
        self,
        source_file_id: EntityId,
    ) -> tuple[ImageQualityAssessment, ...]: ...
```

`ImageQualityAssessmentRepository` represents the complete immutable assessment aggregate. `add()` persists one complete `ImageQualityAssessment` aggregate, the assessment row, exactly seven metric rows, zero through six issue rows and the complete canonical policy snapshot; does not commit; uses the active Unit of Work connection; rejects duplicate assessment ID even when payload is equal; rejects invalid metric count, order or duplicates; rejects invalid issue order or duplicates; rejects policy snapshot mismatch; rejects projection/canonical-payload mismatch; and exposes only sanitized persistence errors.

`get()` returns the complete rehydrated aggregate; validates assessment projections, all seven metrics, issue ordinals and ordering, complete canonical policy snapshot and aggregate status against issues; fails closed on missing child rows, extra child rows, ordinal gaps, duplicates, controlled-value corruption or payload mismatch; and never silently returns a partial aggregate.

`list_by_source()` returns only complete validated aggregates in deterministic order `assessed_at` ascending then assessment ID ascending, performs validated reads before domain-level result construction, does not silently hide corrupted rows and returns an empty tuple when no assessments exist.

Public repositories for metrics or issues are forbidden. Public mutation methods `add_metric`, `add_issue`, `update`, `delete`, `replace`, `save` and `upsert` are forbidden. Metrics, issues and the policy snapshot are owned by the `ImageQualityAssessment` aggregate and persist only through `ImageQualityAssessmentRepository.add(assessment)`.

The future implementation extends the existing `UnitOfWork` Protocol with exactly `image_quality_assessments: ImageQualityAssessmentRepository`. The accepted Unit of Work shape remains the existing pattern and conceptually includes `source_files: SourceFileRepository`, `stored_artifacts: StoredArtifactRepository`, `audit_events: AuditEventRepository`, `image_quality_assessments: ImageQualityAssessmentRepository`, `__enter__`, `__exit__`, `commit()` and `rollback()`. The concrete repository is added to the existing SQLCipher Unit of Work. PR-009 must not create an independent assessment database, independent transaction, independent audit connection, second commit boundary or automatic repository commits.

### 8b. Canonical policy serialization

The canonical assessment payload contains the complete aggregate fields, complete policy snapshot, canonical metric references/order and canonical issue references/order. The policy snapshot logical structure is exactly `policy.policy_id`, `policy.policy_version`, `policy.minimum_short_side_pixels`, `policy.minimum_long_side_pixels`, `policy.blur_minimum_laplacian_variance`, `policy.contrast_minimum_luminance_stddev`, `policy.glare_highlight_cutoff`, `policy.glare_maximum_fraction`, `policy.exposure_shadow_cutoff`, `policy.exposure_maximum_shadow_fraction`, `policy.exposure_bright_cutoff`, `policy.exposure_maximum_bright_fraction` and `policy.severity_rules`.

`severity_rules` serialize in exact canonical issue-code order: `LOW_RESOLUTION`, `BLUR_DETECTED`, `LOW_CONTRAST`, `GLARE_DETECTED`, `UNDEREXPOSED`, `OVEREXPOSED`. Each rule contains exactly `issue_code` and `severity`. Decimal values use canonical fixed-point strings. Forbidden canonical Decimal forms are `NaN`, `Infinity`, `-Infinity`, scientific notation, locale-dependent decimal separators and binary-float-derived `repr`. Frozen canonical-payload tests are required.

### 9. Application-service contract and caller-supplied values

The exact command is:

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

Invariants: all four IDs are valid `EntityId` values; `assessment_id`, `audit_event_id`, `source_file_id` and `correlation_id` follow existing entity-ID validation; `assessment_id != audit_event_id`; `assessed_at` is timezone-aware and normalized to UTC; actor is caller-supplied; policy is caller-supplied and validated before storage access. The service must not generate UUIDs, read the system clock, infer actor, infer correlation ID or load a process-global default policy.

The service contract is:

```python
assess_source_file_quality(
    command: AssessSourceFileQualityCommand,
    *,
    decoder: QualityAnalysisDecoderPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> AssessSourceFileQualityResult
```

This `unit_of_work_factory: UnitOfWorkFactory` dependency is binding. The implementation must not rename or replace it with a nonexistent database port, a raw SQLCipher connection, a raw DB-API connection, a repository factory independent from the accepted Unit of Work, or separate connections for assessment and audit persistence. The service uses exactly one Unit of Work created by `unit_of_work_factory.unit_of_work()`. Assessment aggregate persistence and audit-event insertion use the same Unit of Work transaction. The service calls `commit()` exactly once after the source file is loaded, the stored artifact is verified, the source is decoded, metrics are computed, explicit policy is evaluated, the complete assessment aggregate is added and the exact audit event is added. Any failure before successful commit leaves no committed assessment, metric, issue or audit row. It must not reuse a caller-provided filesystem path, persist a source path, or modify the original artifact or source-file row.



The exact result DTO is:

```python
@dataclass(frozen=True, slots=True)
class AssessSourceFileQualityResult:
    assessment: ImageQualityAssessment
```

`AssessSourceFileQualityResult` invariants: `assessment` is an `ImageQualityAssessment`; there is no optional or partial success state; no path, basename, image bytes, pixel raster, SHA-256, perceptual hash, raw exception or arbitrary metadata; and `repr` is safe and deterministic. It must not define a result containing a separate policy object inconsistent with `assessment.policy`, and it must not return database rows or repository DTOs.



### 9a. Controlled application-service error boundary

The future implementation must add this exact enum to `src/document_intake/domain/enums.py`:

```python
class QualityAssessmentErrorCode(StrEnum):
    SOURCE_FILE_NOT_FOUND = "SOURCE_FILE_NOT_FOUND"
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
    ARTIFACT_INTEGRITY_FAILED = "ARTIFACT_INTEGRITY_FAILED"
    DECODE_FAILED = "DECODE_FAILED"
    QUALITY_POLICY_INVALID = "QUALITY_POLICY_INVALID"
    QUALITY_ASSESSMENT_FAILED = "QUALITY_ASSESSMENT_FAILED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
```

No additional PR-009 service error codes may be introduced without a separate decision. Do not reuse `SourceImportErrorCode`, `PersistenceErrorCode`, `StorageErrorCode`, arbitrary strings or third-party exception types. `QualityAssessmentErrorCode` is the stable external application-service failure vocabulary for PR-009.

The future implementation must define this exact public exception in `src/document_intake/application/services/image_quality.py`:

```python
class QualityAssessmentError(Exception):
    def __init__(self, code: QualityAssessmentErrorCode) -> None:
        if not isinstance(code, QualityAssessmentErrorCode):
            raise TypeError("quality_assessment_error.code: invalid_type")
        self.code = code
        super().__init__(code.value)

    def __repr__(self) -> str:
        return f"QualityAssessmentError(code={self.code.value})"
```

Binding behavior: `str(error) == error.code.value`. The exception contains only `code`. It must not contain a path, basename, artifact hash, image bytes, pixel data, SQL, database path, raw third-party exception text, original exception object, traceback text, key material or arbitrary metadata. All lower-level exception translations must use `raise QualityAssessmentError(code) from None`; raw exception chaining must not escape the application-service boundary.

Success returns exactly one `AssessSourceFileQualityResult`. Failure raises exactly one `QualityAssessmentError`. Forbidden failure mechanisms are returning `None`, returning a failure DTO, returning `QualityAssessmentError` as a value, returning `Result[Success, Failure]`, returning a success/error union, embedding `error_code` in `AssessSourceFileQualityResult`, returning a partial assessment, returning raw `StorageError`, returning raw `PersistenceError`, returning raw `InvalidValueError`, returning Pillow/pi-heif exceptions, or returning SQLite/SQLCipher exceptions.

`AssessSourceFileQualityResult` remains success-only. Do not add `error`, `error_code`, `success`, `failed`, `partial` or execution-failure warnings to this result DTO.

Domain/command construction validation remains separate: constructing invalid immutable domain objects or commands may raise existing controlled domain `InvalidValueError` for invalid `EntityId`, naive `assessed_at`, invalid `ImageQualityPolicy`, invalid Decimal, invalid severity mapping or invalid command field type. These happen before `assess_source_file_quality()` is invoked and are not translated by the service. Once a valid `AssessSourceFileQualityCommand` reaches the service, every execution failure is translated into `QualityAssessmentError`; the service must not return or expose `InvalidValueError`.


### 9b. Exact error mapping and encrypted artifact read

`QUALITY_POLICY_INVALID` is raised before opening the Unit of Work when an already constructed `ImageQualityPolicy` fails service preflight because its controlled policy ID/version is unsupported by the selected application composition, it cannot be serialized into the exact canonical policy snapshot, its severity rules are inconsistent with the fixed PR-009 issue-code contract, or it is incompatible with the PR-009 whole-frame policy schema. No repository or storage method may be called before this failure. Use `raise QualityAssessmentError(QualityAssessmentErrorCode.QUALITY_POLICY_INVALID) from None`.

Algorithm IDs and versions are fixed by the PR-009 implementation contract and are not fields of `ImageQualityPolicy`. The service must not add algorithm-selection fields to `ImageQualityPolicy`. No concrete production policy ID/version is accepted or activated while Q-021 remains open.

Policy/algorithm separation is exact: `ImageQualityPolicy` contains thresholds, controlled policy identity/version and severity mapping; the PR-009 implementation contract contains metric algorithms, algorithm IDs/versions, kernels, grayscale conversion, rounding and deterministic execution rules. Policy preflight may confirm compatibility with the fixed PR-009 whole-frame schema, but it must not expect algorithm identifiers supplied by policy.

`PERSISTENCE_FAILED` while opening or reading the Unit of Work: map failures from `unit_of_work_factory.unit_of_work()`, entering the Unit of Work, `uow.source_files.get(...)`, `uow.stored_artifacts.get(...)`, corrupted persistence data raised by a repository, and Unit of Work exit or rollback handling. Do not confuse repository failure with absent entity.

`SOURCE_FILE_NOT_FOUND`: raise only when `source_file = uow.source_files.get(command.source_file_id)` returns `None`; do not use it for repository exceptions.

`ARTIFACT_NOT_FOUND`: raise only when `stored_artifact = uow.stored_artifacts.get(source_file.original_artifact_id)` returns `None`. A missing stored-artifact database record is `ARTIFACT_NOT_FOUND`; a missing or invalid encrypted filesystem object for an existing stored record is `ARTIFACT_INTEGRITY_FAILED`.

`ARTIFACT_INTEGRITY_FAILED`: map every controlled or unexpected failure from `content = storage.read_bytes(expected=stored_artifact)` to `QualityAssessmentErrorCode.ARTIFACT_INTEGRITY_FAILED` without leaking lower-level storage codes. This includes encrypted object missing, expected-state mismatch, ciphertext hash mismatch, envelope context mismatch, key unavailable, key invalid, decrypt failure, invalid storage format, unsafe filesystem object and storage I/O failure.

`DECODE_FAILED`: map every controlled or unexpected failure from `decoder.decode_for_quality(content=content)` to `QualityAssessmentErrorCode.DECODE_FAILED`; do not expose `MediaDecodeError`, Pillow, pi-heif or decompression details.

`QUALITY_ASSESSMENT_FAILED`: map failures during seven-metric calculation, Laplacian computation, contrast computation, glare/exposure fraction computation, Decimal calculation, policy evaluation, issue construction, status aggregation and complete `ImageQualityAssessment` construction. This mapping does not apply to invalid policy caught by policy preflight.

`PERSISTENCE_FAILED` during write/commit: map every controlled or unexpected failure from `uow.image_quality_assessments.add(assessment)`, constructing or adding the audit event when caused by a persistence boundary, `uow.audit_events.add(event)`, `uow.commit()` and transaction exit after a failed write. The complete Unit of Work must be rolled back and no assessment, metric, issue or audit row may remain committed.

The exact encrypted artifact read is `content = storage.read_bytes(expected=stored_artifact)`, where `stored_artifact` is loaded from `uow.stored_artifacts.get(source_file.original_artifact_id)`. The service must not build or accept a filesystem path, read a file directly, call `Path.read_bytes()`, locate the encrypted object from a caller-provided path, call `storage.verify()` immediately before `storage.read_bytes()`, call both `verify()` and `read_bytes()` for the same assessment, call `read_bytes()` without an authoritative `StoredArtifactRecord`, or publish/rewrite an object. `StoragePort.read_bytes(expected=stored_artifact)` already performs accepted stored-object existence, expected-state, envelope-context, integrity and decryption checks required to return plaintext. Calling `verify()` first would perform a redundant second encrypted read and decrypt operation without increasing the accepted application guarantee. Exactly one `read_bytes()` call is expected on the successful service path. The returned plaintext exists in memory only for decoding and must not be persisted, logged, added to an error, placed in audit, included in a DTO or retained by the assessment aggregate.

Exact service workflow: validate command and complete policy; open one Unit of Work; load `SourceFile` through `uow.source_files.get(source_file_id)`; fail with `SOURCE_FILE_NOT_FOUND` when absent; resolve original stored artifact ID from the `SourceFile`; load expected stored-artifact state through `uow.stored_artifacts`; fail with `ARTIFACT_NOT_FOUND` when absent; read encrypted original exactly once through `content = storage.read_bytes(expected=stored_artifact)` using authoritative stored-artifact state; fail with `ARTIFACT_INTEGRITY_FAILED` on controlled integrity failure; decode bytes through `QualityAnalysisDecoderPort`; fail with `DECODE_FAILED` on controlled decode failure; calculate all seven deterministic metrics; evaluate the explicit command policy; construct one complete immutable `ImageQualityAssessment` containing the complete policy; add it through `uow.image_quality_assessments.add(assessment)`; construct the exact audit event; add it through `uow.audit_events.add(event)`; commit exactly once; return `AssessSourceFileQualityResult(assessment=assessment)`.



Implementation-equivalent flow, not production code for this documentation PR:

```python
def assess_source_file_quality(
    command: AssessSourceFileQualityCommand,
    *,
    decoder: QualityAnalysisDecoderPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> AssessSourceFileQualityResult:
    try:
        validate_policy_preflight(command.policy)
    except Exception:
        raise QualityAssessmentError(
            QualityAssessmentErrorCode.QUALITY_POLICY_INVALID
        ) from None

    try:
        with unit_of_work_factory.unit_of_work() as uow:
            source_file = uow.source_files.get(command.source_file_id)
            if source_file is None:
                raise QualityAssessmentError(
                    QualityAssessmentErrorCode.SOURCE_FILE_NOT_FOUND
                )

            stored_artifact = uow.stored_artifacts.get(
                source_file.original_artifact_id
            )
            if stored_artifact is None:
                raise QualityAssessmentError(
                    QualityAssessmentErrorCode.ARTIFACT_NOT_FOUND
                )

            try:
                content = storage.read_bytes(expected=stored_artifact)
            except Exception:
                raise QualityAssessmentError(
                    QualityAssessmentErrorCode.ARTIFACT_INTEGRITY_FAILED
                ) from None

            try:
                decoded = decoder.decode_for_quality(content=content)
            except Exception:
                raise QualityAssessmentError(
                    QualityAssessmentErrorCode.DECODE_FAILED
                ) from None

            try:
                assessment = build_complete_assessment(
                    command=command,
                    decoded=decoded,
                )
            except Exception:
                raise QualityAssessmentError(
                    QualityAssessmentErrorCode.QUALITY_ASSESSMENT_FAILED
                ) from None

            try:
                uow.image_quality_assessments.add(assessment)
                uow.audit_events.add(
                    build_quality_assessment_audit_event(
                        command=command,
                    )
                )
                uow.commit()
            except Exception:
                raise QualityAssessmentError(
                    QualityAssessmentErrorCode.PERSISTENCE_FAILED
                ) from None

    except QualityAssessmentError:
        raise
    except Exception:
        raise QualityAssessmentError(
            QualityAssessmentErrorCode.PERSISTENCE_FAILED
        ) from None

    return AssessSourceFileQualityResult(assessment=assessment)
```

The future implementation may extract private helpers but must preserve this exact public behavior and error mapping.

No database row may be persisted before the complete aggregate is constructed. No audit event may be committed without the assessment. No assessment may be committed without its audit event. No object-storage write occurs in PR-009. The original artifact remains unchanged.

Transaction and failure semantics are exact. Invalid immutable domain-object or command construction validation occurs before the service is invoked and may raise the existing controlled `InvalidValueError`. Once a valid `AssessSourceFileQualityCommand` enters the service, policy preflight failure maps to `QUALITY_POLICY_INVALID` before Unit of Work creation. `QUALITY_ASSESSMENT_FAILED` applies only to failures during metric calculation, Decimal calculation, policy evaluation, issue construction, status aggregation, or complete `ImageQualityAssessment` construction. Inside the Unit of Work before persistence, `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED` and `QUALITY_ASSESSMENT_FAILED` leave no new rows. Any failure while adding assessment, metrics, issues, policy snapshot, audit event or commit rolls back the complete Unit of Work, leaves no partial PR-009 rows, leaves no audit event, leaves original source and artifact unchanged, returns only a controlled `PERSISTENCE_FAILED` boundary and exposes no raw DB-API, SQLCipher or SQLite exception. No orphan filesystem artifact is possible because PR-009 performs no storage publication.

Error-boundary summary: before service invocation, `InvalidValueError` covers invalid immutable domain/command construction. Inside the service before Unit of Work creation, `QualityAssessmentError(QUALITY_POLICY_INVALID)` covers policy preflight failure. Inside the service after decoding, `QualityAssessmentError(QUALITY_ASSESSMENT_FAILED)` covers calculation, evaluation, issue/status, or aggregate-construction failure. Pre-service construction errors must not be translated into `QualityAssessmentError`, and a valid command reaching the service must not expose `InvalidValueError`.


Rollback requirements: `SOURCE_FILE_NOT_FOUND` and `ARTIFACT_NOT_FOUND` create no rows; `ARTIFACT_INTEGRITY_FAILED` creates no rows; `DECODE_FAILED` creates no rows; `QUALITY_ASSESSMENT_FAILED` creates no rows; `PERSISTENCE_FAILED` rolls back assessment, metrics, issues and audit; no error changes the `SourceFile`; no error changes the stored-artifact record; no error changes encrypted object bytes; no error publishes an object; and no error produces a partial success result. The Unit of Work context rolls back automatically or explicitly according to the accepted UoW implementation. PR-009 must not introduce a second Unit of Work for reads or audit.


### 10. Audit contract

The future PR-009 service emits one immutable audit event only after successful persistence. The implementation must add exactly `AuditAction.IMAGE_QUALITY_ASSESSED`, `AuditSubjectType.IMAGE_QUALITY_ASSESSMENT` and `AuditReasonCode("IMAGE_QUALITY_ASSESSMENT")`. It must not reuse `ARTIFACT_REGISTERED`, `ENTITY_CREATED` or another unrelated action.

Event shape is exact: `event_id=command.audit_event_id`, `action_code=AuditAction.IMAGE_QUALITY_ASSESSED`, `subject_type=AuditSubjectType.IMAGE_QUALITY_ASSESSMENT`, `subject_id=command.assessment_id`, `field_key=None`, `before.classification=ABSENT`, `before.display_value=None`, `before.was_present=False`, `after.classification=NON_SENSITIVE`, `after.display_value="QUALITY_ASSESSMENT"`, `after.was_present=True`, `reason_code=AuditReasonCode("IMAGE_QUALITY_ASSESSMENT")`, `correlation_id=command.correlation_id`, `actor=command.actor` and `occurred_at=command.assessed_at`.

The implementation task must require enum serialization tests, migration compatibility tests, audit canonical-payload tests, exact event-field application-service tests, rollback tests, verifier assertions for the complete event, and unchanged historical audit values and behavior. Policy ID/version and raw metrics must not be placed in arbitrary audit metadata. The audit event contains only the controlled display value above and the correlation ID.

### 11. Privacy

Quality results may contain controlled codes, algorithm IDs and versions, numeric metrics, dimensions, policy ID/version, timestamps and opaque entity IDs. They must not contain original basename, source path, storage path, database path, SHA-256, perceptual hash, image bytes, pixel dumps, thumbnails, EXIF metadata other than orientation, GPS, camera manufacturer/model, operator username, raw exception, SQL or key material. All representations and errors remain sanitized.

### 12. Failure model

Stable controlled error codes for the future task include `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `QUALITY_POLICY_INVALID`, `QUALITY_ASSESSMENT_FAILED` and `PERSISTENCE_FAILED`. Third-party exception text must not escape. Policy validation fails before storage access. Validation and decode failures do not persist partial assessment rows. Database persistence and audit insertion occur in one Unit of Work transaction; any failure rolls back assessment, metrics, issues and audit event together.

### 13. Non-goals

Non-goals are image modification, correction or enhancement, crop, perspective correction, segmentation, document detection/count, OCR, UI, automatic rejection or deletion, prepared JPEG, PR-010+ work, claims of final calibrated thresholds and real-document fixtures.
