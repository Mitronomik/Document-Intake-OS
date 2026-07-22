# PR-009 — Orientation and quality assessment contract

Status: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION

The requirements below originated as the pre-implementation contract and remain authoritative for reviewing the implementation. The lifecycle status is now completed and human accepted with `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY`. GitHub PR #24 merged on 2026-07-22 from reviewed head `72c01662031f73985f8715d6c3c87abf7aa5c4db` at merge commit `b491226878cabfc87c484f6a4d41bc2969851273`. Q-021 is deferred after accepted negative calibration evidence; no production default quality policy is active.

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

`ImageQualityAssessment` fields are exactly `id: EntityId`, `source_file_id: EntityId`, `assessed_at: datetime`, `policy: ImageQualityPolicy`, `status: QualityAssessmentStatus`, `encoded_width: int`, `encoded_height: int`, `exif_orientation: int | None`, `effective_width: int`, `effective_height: int`, `metrics: tuple[ImageQualityMetric, ...]`, `issues: tuple[ImageQualityIssue, ...]`. Invariants: valid IDs; timezone-aware UTC-normalized timestamp; positive dimensions; orientation `None` or 1–8; effective dimensions match orientation axis rule; exactly seven metrics with unique codes in canonical order; issues unique and canonical; issue severity equals exact severity rule in `assessment.policy.severity_rules`; no issue code is absent from policy severity rules; no policy contains additional issue codes; policy thresholds are the thresholds used to produce metrics and issues; database policy ID/version projections equal `assessment.policy.version`; canonical payload contains the complete policy including policy ID, policy version, thresholds and all six severity rules in canonical order; rehydration reconstructs the complete `ImageQualityPolicy`; status derived from issues and cannot disagree; no arbitrary metadata, actor, username, filename, path, hash, pixel data or exception text.

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
    unit_of_work_factory: UnitOfWorkFactory,
) -> AssessSourceFileQualityResult
```

This `unit_of_work_factory: UnitOfWorkFactory` dependency is binding. The implementation must not rename or replace it with a nonexistent database port, a raw SQLCipher connection, a raw DB-API connection, a repository factory independent from the accepted Unit of Work, or separate connections for assessment and audit persistence. The service uses exactly one Unit of Work created by `unit_of_work_factory.unit_of_work()`. Assessment aggregate persistence and audit-event insertion use the same Unit of Work transaction. The service calls `commit()` exactly once after the source file is loaded, the stored artifact is verified, the source is decoded, metrics are computed, explicit policy is evaluated, the complete assessment aggregate is added and the exact audit event is added. Any failure before successful commit leaves no committed assessment, metric, issue or audit row.

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

Algorithm IDs and versions are fixed by the PR-009 implementation contract and are not fields of `ImageQualityPolicy`. The service must not add algorithm-selection fields to `ImageQualityPolicy`. No concrete production policy ID/version is accepted or activated while Q-021 remains deferred without a selected policy.

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


The future implementation must add exactly `AuditAction.IMAGE_QUALITY_ASSESSED`, `AuditSubjectType.IMAGE_QUALITY_ASSESSMENT` and `AuditReasonCode("IMAGE_QUALITY_ASSESSMENT")`; it must not reuse `ARTIFACT_REGISTERED`, `ENTITY_CREATED` or another unrelated action. Exact audit event: `event_id=command.audit_event_id`, `action_code=AuditAction.IMAGE_QUALITY_ASSESSED`, `subject_type=AuditSubjectType.IMAGE_QUALITY_ASSESSMENT`, `subject_id=command.assessment_id`, `field_key=None`, `before.classification=ABSENT`, `before.display_value=None`, `before.was_present=False`, `after.classification=NON_SENSITIVE`, `after.display_value="QUALITY_ASSESSMENT"`, `after.was_present=True`, `reason_code=AuditReasonCode("IMAGE_QUALITY_ASSESSMENT")`, `correlation_id=command.correlation_id`, `actor=command.actor`, `occurred_at=command.assessed_at`. Required tests include enum serialization, migration compatibility, audit canonical payload, exact event fields, rollback, verifier assertions and unchanged historical audit values/behavior.



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

## Failure codes and privacy

Future stable error codes are `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `QUALITY_POLICY_INVALID`, `QUALITY_ASSESSMENT_FAILED` and `PERSISTENCE_FAILED`. Policy validation fails before storage access. No third-party exception text may be exposed. Transaction rollback must remove assessment, metric, issue and audit rows together.

Privacy restrictions prohibit basenames, paths, hashes, image bytes, pixel dumps, thumbnails, arbitrary EXIF beyond orientation, GPS, camera make/model, username, raw exception, SQL and key material in domain objects, DTOs, audit event, errors, verifier output and logs.

## Q-021 and activation boundary

Q-021 — PR-009 whole-frame diagnostic policy thresholds is DEFERRED after the product owner accepted the completed local calibration as valid negative evidence. No production `policy_id`, `policy_version`, threshold set or severity mapping was accepted, and no default policy is active.

PR-009 infrastructure is ready for human acceptance with `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY`. Q-021 is deferred and continues to block only:

- selection of a production default policy;
- activation of production quality decisions;
- claims that PR-009 thresholds are calibrated for production.

The deterministic V1 metrics, explicit policy domain model, persistence, audit, controlled errors and synthetic verification are accepted as infrastructure. The completed local calibration did not identify an acceptable production threshold and severity policy. No process-global, hidden or default production policy may be configured. Production composition must fail closed when an accepted policy is absent. No document may be automatically rejected, deleted, suppressed or blocked using an unaccepted PR-009 policy. Explicit synthetic policies remain allowed in tests and verifiers. Any future production policy requires a separate versioned metric-separability task, local recalibration and explicit product-owner acceptance.

Q-007 remains separate and deferred for PR-011 prepared-JPEG readability and post-compression resolution thresholds. The PR-009 whole-frame source-quality threshold portion is separated into Q-021. Q-007 no longer blocks PR-009 algorithm or persistence implementation.

## Mandatory future tests

Unit tests use synthetic-only generated images. Orientation tests cover EXIF 1-8, effective dimension swaps, orientation applied once, original bytes unchanged and no transformed artifact. Decoder tests prove `decode_for_import()` output remains unchanged while `decode_for_quality()` returns full-resolution pixels. Resolution tests cover short/long side metrics, equality at threshold, one pixel below threshold and orientation-swapped dimensions. Blur tests cover uniform image, sharp checker/grid, deterministic blurred image, frozen Laplacian vectors and Ubuntu/Windows equality. Contrast tests cover uniform grayscale, two-tone image, deterministic gradient and frozen population-standard-deviation vectors. Glare tests cover no clipped pixels, exact cutoff boundary, fraction exactly at threshold and immediately above threshold. Exposure tests cover shadow fraction, bright fraction, exact boundaries, mixed image and independent under/overexposure.

Aggregation tests cover no issues to `GOOD`, warnings only to `REVIEW_REQUIRED`, any blocking issue to `RETAKE_REQUIRED` and deterministic issue ordering. Repository and migration tests cover append-only assessments, multiple policy versions, immutable metrics/issues, transaction rollback, tamper detection, migration v0004 to v0005, full canonical policy snapshot persistence and unchanged v0001-v0004 checksums. Privacy tests cover safe `repr`, no basename/path/hash/pixels/SQL/key/exception leakage, verifier allowlist and synthetic data only. Application-service tests cover explicit policy injection, caller-supplied IDs/timestamp, storage integrity verification, exact audit event, atomic audit emission and fail-closed missing production policy.



## Exact repository, Unit of Work and service tests

Future repository tests must cover: add/get complete assessment, empty issue list, all six issue codes, exactly seven metrics, multiple assessments for one source, deterministic `list_by_source`, duplicate assessment ID, missing metric row, extra metric row, duplicate metric code, metric ordinal gap, issue ordinal gap, duplicate issue code, policy snapshot corruption, policy projection mismatch, severity-rule mismatch, status/issues mismatch, canonical payload mismatch, update rejection, delete rejection, replace rejection, rollback and no partial aggregate return.

Future Unit of Work tests must prove `image_quality_assessments` repository exists, shares the same SQLCipher connection, does not auto-commit, assessment and audit commit together, assessment failure prevents audit insertion, audit failure rolls back assessment/metrics/issues and commit failure rolls back the complete transaction.

Future application-service tests must cover exact successful result DTO, complete `assessment.policy`, source missing, artifact missing, storage-integrity failure, decode failure, invalid policy fails before storage access, exact seven metrics, exact audit event, assessment and audit atomicity, no UUID generation, no system-clock access, no process-global policy, no source mutation, no artifact mutation and privacy-safe errors and `repr`.

Future serialization tests must cover complete policy canonical snapshot, fixed-point Decimal strings, severity-rule canonical order, deterministic round trip, no scientific notation and tamper detection.

The future verifier must additionally verify schema v5, repository round trip of the complete aggregate, complete policy snapshot round trip, exact seven metrics, issue/status aggregation, exact audit event, transaction rollback, policy corruption rejection, metric/issue corruption rejection, unchanged source artifact bytes, privacy allowlist and deterministic output through real production components.



## Controlled error and artifact-read tests

Future controlled exception tests must cover every `QualityAssessmentErrorCode`: `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `QUALITY_POLICY_INVALID`, `QUALITY_ASSESSMENT_FAILED` and `PERSISTENCE_FAILED`. For every error assert `type(error) is QualityAssessmentError`, `error.code is expected_code`, `str(error) == expected_code.value`, `repr(error) == f"QualityAssessmentError(code={expected_code.value})"` and `error.__cause__ is None`. Error `str` and `repr` must not contain source basename, source path, storage path, database path, artifact hash, image bytes, SQL, key or lower-level exception text.

Future mapping tests must cover policy preflight failure before Unit of Work creation, Unit of Work creation failure to `PERSISTENCE_FAILED`, source repository exception to `PERSISTENCE_FAILED`, missing source to `SOURCE_FILE_NOT_FOUND`, artifact repository exception to `PERSISTENCE_FAILED`, missing stored-artifact database record to `ARTIFACT_NOT_FOUND`, encrypted object missing to `ARTIFACT_INTEGRITY_FAILED`, envelope mismatch to `ARTIFACT_INTEGRITY_FAILED`, decrypt/key failure to `ARTIFACT_INTEGRITY_FAILED`, decoder controlled failure to `DECODE_FAILED`, decoder unexpected failure to `DECODE_FAILED`, metric calculation failure to `QUALITY_ASSESSMENT_FAILED`, policy evaluation failure to `QUALITY_ASSESSMENT_FAILED`, aggregate construction failure to `QUALITY_ASSESSMENT_FAILED`, assessment repository add failure to `PERSISTENCE_FAILED`, audit add failure to `PERSISTENCE_FAILED` and commit failure to `PERSISTENCE_FAILED`.

Future success-path storage tests must assert `storage.read_bytes` is called exactly once, `storage.verify` is not called, `storage.publish_bytes` is not called, the `expected` argument is the `StoredArtifactRecord` loaded from the Unit of Work, and plaintext is passed only to `decoder.decode_for_quality`. Result tests must assert success returns `AssessSourceFileQualityResult`, failure never returns a result, result has exactly one field `assessment`, no failure code is embedded in the result and no partial assessment exists.

## Cross-platform verifier

`scripts/verify_pr009_quality.py` must use real production components, run on supported Windows SQLCipher CI, use deterministic synthetic images, validate schema v5, immutable original bytes, import decoder compatibility, quality decoder full-resolution semantics, orientation semantics, frozen metric vectors, issue aggregation, full policy snapshot, complete audit event, rollback and privacy, print only allowlisted records and return `0` on pass, `1` on product failure and `2` only for a documented unsupported environment.

## Manual local calibration

The private local Q-021 calibration contour completed with 60 samples processed, 60 metric sets calculated, zero failures, 43 calibration samples, 17 held-out validation samples and 54 Pareto candidates in a `CALIBRATION_ONLY` search. No candidate or production policy was accepted. Only these aggregate results are recorded; private inputs and exported calibration artifacts remain outside Git, Codex and CI.

The accepted narrow conclusion is that the current PR-009 V1 whole-frame metrics, current candidate search space and tested severity combinations did not produce an acceptable production quality policy on the completed local Q-021 calibration and validation set. This does not prove universal failure of the algorithms. Future metric changes must be versioned; V1 formulas and persisted algorithm identities must not be silently changed.

The previously accepted sanitized MPO/JPEG compatibility result remains:

```text
Q021-0017 result=PASS media_type=JPEG
Q021-0018 result=PASS media_type=JPEG
Q021-0019 result=PASS media_type=JPEG

summary total=22 passed=20 failed=0 duplicates=2
```

This controlled output contains no private input identity or calibration artifact and selects no quality policy.

## Accepted MPO/JPEG input correction

MPO detected as a JPEG container is accepted as JPEG.
Only primary frame 0 is decoded.
Original bytes remain immutable.
Secondary frames are ignored in MVP.

Synthetic tests and both production-component verifiers must prove Pillow detection as `MPO`, mapping to `SourceMediaType.JPEG`, explicit frame-0 import and quality decoding, one-time EXIF orientation, secondary-frame independence, primary-frame sensitivity, byte immutability and unchanged JPEG/PNG/HEIF/unsupported behavior. No real MPO input, path, filename, hash, thumbnail, EXIF payload, manifest or label enters Git, Codex, CI, logs or reports.

## Acceptance criteria for the future implementation PR

PR-009 production code is acceptable only when ADR-023 is accepted or explicitly reaffirmed, Q-021 status is respected, whole-frame scope is maintained, import decoder DHASH64 behavior is preserved, quality decoder is full-resolution and separate, command IDs/timestamp are caller-supplied, audit event is exact, algorithms/comparisons/rounding match frozen vectors, policy is explicit/versioned/snapshotted, persistence/privacy/failure contracts are met, all tests and verifier pass on supported platforms, no production default policy is activated without a separate explicit product-owner acceptance, no real documents or PII are committed, PR-010+ remain unauthorized and Gate 2 remains not accepted.

## Non-goals

No image modification, correction, enhancement, crop, perspective correction, segmentation, document detection/count, OCR, UI, automatic rejection/deletion, prepared JPEG generation, PR-010+ work, final calibrated threshold claim or real-document fixtures.


## PR-009 calibration lifecycle update — 2026-07-22

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE MERGE BOUNDARY.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

PR-009 implements deterministic whole-frame metrics, explicit caller-provided typed policy handling, full-resolution orientation-normalized decoding, append-only persistence, audit integration, controlled service errors, synthetic tests and a cross-platform verifier. The residual limitation blocks production activation of PR-009 quality decisions, not human acceptance or merge of the explicit-policy infrastructure. Human acceptance and merge are still pending; PR-010 and later require a separate post-merge product-owner decision.

Review correction verification uses literal synthetic import-grayscale, DHASH64, full-resolution grayscale, orientation/dimension and seven-metric vectors. On supported Windows SQLCipher it creates and imports through production services, assesses through `assess_source_file_quality()`, reads the complete aggregate and exact audit event through production repositories, proves source/artifact/encrypted-object immutability, proves deterministic `list_by_source()`, proves failing-audit rollback through a wrapper around the real Unit of Work, and proves repository rejection after controlled corruption through the isolated real SQLCipher connection. The PR-008 verifier independently freezes the exact migration chain through v0005 while preserving its accepted `migration_v0004` output field.
## PR-009 human acceptance lifecycle state — 2026-07-22

PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
Production policy_id: NOT ASSIGNED.
Production policy_version: NOT ASSIGNED.
Automatic PR-009 quality-based document blocking: NOT ACTIVE.
Automatic PR-009 production RETAKE_REQUIRED enforcement: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.
PR-010 CONTRACT DEFINITION: AUTHORIZED, NOT STARTED.
PR-010 PRODUCTION IMPLEMENTATION: UNAUTHORIZED.
PR-011 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

GitHub PR: #24.
Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`.
Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.
Merge date: 2026-07-22.

This later lifecycle decision does not alter accepted PR-009 algorithms, comparisons, rounding, DTOs, domain model, policy snapshot contract, persistence contract, audit contract, migration contract, verifier contract, tests or acceptance vectors. It authorizes preparation of the exact PR-010 documentation contract only and does not authorize PR-010 runtime behavior.
