# PR-011 — Deterministic JPEG Preparation Under 1.90 MiB

**Status:** CONTRACT PROPOSED FOR HUMAN REVIEW; PRODUCTION IMPLEMENTATION UNAUTHORIZED

## Authorization and implementation base

This is a documentation-only contract proposal governed by proposed [ADR-025](../decisions/ADR-025-prepared-jpeg-v1.md). Merging it does not authorize production implementation. The future exact implementation base is **the merge commit of this documentation-contract PR, after separate Product owner acceptance and authorization**. That decision must accept ADR-025 and this contract. PR-012 and later remain UNAUTHORIZED; Gate 2 is NOT ACCEPTED; M3 is IN PROGRESS.

## Complete V1 contract

ADR-025's exact input, original-raster, output, candidate ordering, determinism, technical guard, immutable model, DTO, future v0007, publication/UoW/reconciliation, audit, controlled-error, idempotency, privacy, and PR-012/PR-013 orchestration rules are normative and incorporated here without caller overrides.

Fixed identities and boundary:

```text
MAX_PREPARED_JPEG_BYTES = 1_992_294
byte_size <= 1_992_294
pipeline_id = PILLOW_PREPARED_JPEG
pipeline_version = 1
output_contract_id = PREPARED_JPEG_SRGB_V1
output_contract_version = 1
format = JPEG
progressive = false
optimize = true
subsampling = 0
quality = [95, 90, 85, 80, 75, 70, 65, 60]
scale = [100, 90, 80, 70, 60, 50]
```

`1_992_295` fails. `subsampling = 0` means 4:4:4. Output is `.jpg`, valid JPEG, RGB/sRGB without alpha or embedded source ICC, non-progressive and baseline-compatible, with no EXIF/geolocation, XMP, IPTC, source comment/name/path/DPI/thumbnail. Every scale comes from the fresh uncompressed PR-010 raster; every quality attempt from its uncompressed scale raster; no prior JPEG is reused. Quality is exhausted before reducing resolution. Dimension half-up formula is `max(1, floor((source_dimension * p + 50) / 100))`; use `LANCZOS`, never upscale, and skip duplicate pairs.

The technical guard is quality ≥60, scale ≥50%, output short side ≥1200 when source short side ≥1200, and no downscale when source short side <1200. It is separate from PR-009: Q-021 remains deferred, no production policy identity/activation or automatic `RETAKE_REQUIRED` exists, and V1 does not emit automatic `READABILITY_FAILED`. No sharpening, denoising, equalization, or generative restoration occurs. Failure returns `SIZE_LIMIT_UNREACHABLE`, publishes nothing, preserves existing data, and requests a better source image.

`PreparedImageArtifact` has `id`, `source_file_id`, `geometry_recipe_version_id`, `stored_artifact_id`, `pipeline_id`, `pipeline_version`, `output_contract_id`, `output_contract_version`, `media_type`, `color_space`, `width`, `height`, `byte_size`, `sha256`, `jpeg_quality`, `resize_percent`, `created_at`, and `created_by` with the types and exclusions in ADR-025. `PrepareJpegCommand` has `prepared_artifact_id`, `stored_artifact_id`, `geometry_recipe_version_id`, `audit_event_id`, `prepared_at`, `actor`, and `correlation_id`, all caller-controlled as specified there.

Audit values are `AuditAction.PREPARED_JPEG_CREATED`, `AuditSubjectType.PREPARED_IMAGE_ARTIFACT`, and controlled after value `PREPARED_JPEG`. Errors are `GEOMETRY_RECIPE_NOT_FOUND`, `SOURCE_FILE_NOT_FOUND`, `ORIGINAL_ARTIFACT_NOT_FOUND`, `ORIGINAL_BYTES_INVALID`, `SOURCE_DIMENSIONS_MISMATCH`, `GEOMETRY_RENDER_FAILED`, `JPEG_ENCODING_FAILED`, `SIZE_LIMIT_UNREACHABLE`, `IDENTITY_CONFLICT`, `PREPARATION_ALREADY_EXISTS`, `STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_CONFLICT`, `PERSISTENCE_FAILED`, and `PERSISTED_DATA_INVALID`, with privacy-safe string/repr. `IDENTITY_CONFLICT` means that a caller-supplied record ID already exists during preflight before publication. `PREPARATION_ALREADY_EXISTS` means that the exact natural preparation key already exists before publication. `PERSISTENCE_CONFLICT` means that a late uniqueness or race conflict occurs after publication and before successful database commit.

The selected JPEG is published exactly once only after the write Unit of Work is open, has revalidated the authoritative references, and has verified that the prepared-artifact ID, stored-artifact ID, audit-event ID and natural preparation key are absent. No intermediate JPEG candidate is published. Publication occurs before inserting the prepared stored-artifact metadata, `PreparedImageArtifact` and audit event in that same write Unit of Work. Filesystem publication and the database transaction are not claimed to be atomic; a late database uniqueness race follows the controlled `PERSISTENCE_CONFLICT` and read-only orphan-reconciliation contract defined below.

PR-011 consumes one accepted recipe and implements no multi-region or side merge. PR-012 supplies recipes per region; PR-013 preserves merge-before-final-compression by composing working rasters/sides and reusing the versioned primitive without silently changing encoder semantics.

## Future implementation files (not created by this PR)

`src/document_intake/domain/prepared_jpeg.py`; `src/document_intake/application/dto/prepared_jpeg.py`; `src/document_intake/application/services/prepared_jpeg.py`; `src/document_intake/application/ports/jpeg_preparation.py`; `src/document_intake/image_pipeline/jpeg_preparer.py`; `src/document_intake/persistence/migrations/v0007_prepared_jpeg.py`; `src/document_intake/persistence/repositories/prepared_jpeg.py`; `src/document_intake/persistence/serialization.py`; `src/document_intake/persistence/database.py`; `src/document_intake/application/ports/persistence.py`; `scripts/verify_pr011_jpeg.py`; `tests/domain/test_prepared_jpeg.py`; `tests/image_pipeline/test_jpeg_preparer.py`; `tests/application/test_prepared_jpeg_service.py`; `tests/persistence/test_prepared_jpeg_repository.py`; `tests/persistence/test_migrations.py`; `tests/persistence/test_static_contracts.py`; `tests/test_verify_pr011_jpeg.py`; `.github/workflows/ci.yml`.

## Future tests

Synthetic-only tests must cover: exact accepted/rejected byte boundaries; JPEG decode; RGB/sRGB/no alpha; empty EXIF and absent ICC/XMP/IPTC/comment/source metadata; exact quality and resolution ordering; quality before resolution; every attempt from uncompressed raster and never prior JPEG; 4:4:4; non-progressive; repeated determinism; immutable original and recipe; no intermediate publication; selected publication once; failure publishes nothing; database failure preserves valid records and meets orphan reconciliation; canonical payload/projection validation; update/delete/replace rejection; audit insertion/rollback; privacy-safe errors/repr/verifier; no paths or bytes in DTOs; full Ubuntu/Windows pytest; `uv build`; Windows production SQLCipher verification; and no real documents or PII.

## Future verifier

Future `scripts/verify_pr011_jpeg.py` uses synthetic data only and proves immutable original, accepted geometry replay, candidate order, boundary, JPEG/RGB/metadata, selected quality/scale, deterministic rerun, encrypted immutable storage, persistence, audit, rollback, allowlisted privacy output, migration chain, and production SQLCipher on Windows. It is not added to CI by this documentation PR. Sanitized output contract:

```text
PR011_VERIFY schema_version=7
PR011_VERIFY byte_limit=1992294
PR011_VERIFY original_immutable=PASS
PR011_VERIFY geometry_replay=PASS
PR011_VERIFY candidate_order=PASS
PR011_VERIFY jpeg_valid=PASS
PR011_VERIFY rgb=PASS
PR011_VERIFY metadata_removed=PASS
PR011_VERIFY size_limit=PASS
PR011_VERIFY deterministic=PASS
PR011_VERIFY persistence=PASS
PR011_VERIFY audit=PASS
PR011_VERIFY rollback=PASS
PR011_VERIFY privacy=PASS
PR011_VERIFY result=PASS
```

## Non-goals

No production code, migration/checksum, dependency/lock/workflow change, encoding, resizing, metadata stripping, persistence, audit enum, verifier, region orchestration, side merge, UI, OCR, Excel, terminal adapter, PR-009 policy activation, Q-021 resolution, installer, network/cloud/telemetry, fixture/binary, real document, or personal data is included.

## Recipe application service and reusable encoder

The future use case `prepare_geometry_recipe_as_jpeg` accepts one immutable `geometry_recipe_version_id` plus caller `prepared_artifact_id`, `stored_artifact_id`, `audit_event_id`, `prepared_at`, `actor` and `correlation_id`. It loads and replays PR-010 geometry, constructs a fresh `UncompressedRgbRaster`, calls `PreparedJpegEncoderPort`, then publishes and persists. It rejects caller bytes/paths/settings, unconfirmed geometry, multiple recipes/sides, and composed rasters. PR-013 never calls this recipe service with composition output.

```python
@dataclass(frozen=True, slots=True)
class UncompressedRgbRaster:
    width: int
    height: int
    rgb_pixels: bytes

class PreparedJpegEncoderPort(Protocol):
    def encode_prepared_jpeg(
        self,
        raster: UncompressedRgbRaster,
        *,
        pipeline: PreparedJpegPipelineVersion,
    ) -> EncodedPreparedJpeg: ...

@dataclass(frozen=True, slots=True)
class EncodedPreparedJpeg:
    jpeg_bytes: bytes
    width: int
    height: int
    byte_size: int
    sha256: Sha256Digest
    jpeg_quality: int
    resize_percent: int
    pipeline_id: str
    pipeline_version: int
    output_contract_id: str
    output_contract_version: int
```

Raster dimensions are positive, `len(rgb_pixels) == width * height * 3`, and mode is exactly RGB. It contains no encoded JPEG, path, filename, document/source ID, OCR or PII. The encoder has no database, filesystem publication or audit access and returns one in-memory selected candidate with controlled metadata. `EncodedPreparedJpeg` is internal, not an application DTO; raw bytes never enter UI, logs, audit or repository interfaces. PR-013 can compose confirmed uncompressed rasters into this type and call the same port directly, but cannot change any fixed V1 setting, sequence, metadata rule or byte limit.

## Create-once persistence and exact operation order

Exactly one artifact exists for natural key `(geometry_recipe_version_id, pipeline_id, pipeline_version, output_contract_id, output_contract_version)`, enforced by the exact future unique constraint:

```text
UNIQUE (
    geometry_recipe_version_id,
    pipeline_id,
    pipeline_version,
    output_contract_id,
    output_contract_version
)
```

There is no latest row, update-in-place or revision chain. Another artifact requires a changed versioned identity. Encoding is replayable, while creation is create-once: an existing key fails with `PREPARATION_ALREADY_EXISTS`, without returning the existing entity, ignoring IDs or creating duplicates.

Exact application order:

1. validate source-independent command invariants;
2. validate caller record IDs are pairwise distinct;
3. open a read Unit of Work;
4. load and validate recipe, source file and original stored-artifact metadata;
5. close the read Unit of Work without commit;
6. read and verify immutable original bytes;
7. replay accepted PR-010 geometry;
8. construct one fresh `UncompressedRgbRaster`;
9. call `PreparedJpegEncoderPort`;
10. calculate and validate selected-candidate metadata;
11. open one write Unit of Work;
12. re-read and revalidate authoritative references;
13. verify `prepared_artifact_id` does not exist;
14. verify `stored_artifact_id` does not exist;
15. verify `audit_event_id` does not exist;
16. verify the natural preparation key does not exist;
17. publish the JPEG exactly once to encrypted immutable storage;
18. add stored-artifact metadata;
19. add `PreparedImageArtifact`;
20. add the audit event;
21. commit exactly once;
22. exit the Unit of Work;
23. construct and return the application result.

Nothing is published before steps 13-16 pass and no intermediate candidate is published. Primary keys, stored/audit IDs and natural key remain database-enforced. A late uniqueness race rolls back database changes, preserves valid records, leaves the new encrypted object unreferenced for read-only orphan reconciliation, performs no adoption/deletion, and returns privacy-safe `PERSISTENCE_CONFLICT`.

`IDENTITY_CONFLICT` means a caller record ID already exists before publication. `PREPARATION_ALREADY_EXISTS` means the natural key exists before publication. `PERSISTENCE_CONFLICT` means a late uniqueness race after publication and before commit. Raw SQL is never exposed.

## Exact audit event

Future enums are `AuditAction.PREPARED_JPEG_CREATED`, `AuditSubjectType.PREPARED_IMAGE_ARTIFACT`, and `AuditReasonCode.PREPARED_JPEG_CREATED`.

```text
event_id = command.audit_event_id
action = PREPARED_JPEG_CREATED
subject_type = PREPARED_IMAGE_ARTIFACT
subject_id = command.prepared_artifact_id
actor = command.actor
occurred_at = command.prepared_at
field_key = None
before.classification = ABSENT
before.display_value = None
before.was_present = false
after.classification = NON_SENSITIVE
after.display_value = PREPARED_JPEG
after.was_present = true
reason_code = PREPARED_JPEG_CREATED
correlation_id = command.correlation_id
```

Audit, stored-artifact metadata and prepared artifact commit atomically in the write Unit of Work; none commits without the others. Audit excludes filename, path, bytes, source/output checksum, quality, resize, dimensions, byte size, coordinates, document identifiers, OCR, PII and raw exceptions. Controlled metrics remain on the immutable artifact.

## Future v0007 persistence correction

The proposal transitions schema 6 to 7 without modifying v0001–v0006 or assigning a checksum here. It enforces immutable rows; UPDATE/DELETE/REPLACE rejection; positive dimensions/size; `byte_size <= 1_992_294`; allowed quality/resize sequences; fixed JPEG/SRGB and pipeline/output identities; foreign keys; canonical payload/projection equality; deterministic ordering; and the unique natural key above. Reads validate every canonical payload and projection before filtering or returning.

## Additional future tests

Tests must prove recipe service rejection of caller raster bytes; valid-only RGB raster input; PR-013-compatible encoder reuse; no persistence/storage/audit in the encoder; create-once natural key; duplicate-ID and existing-key preflight before publication; late-race controlled orphan reconciliation; exact audit fields; and artifact/audit atomicity.
