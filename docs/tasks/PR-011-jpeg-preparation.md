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

Audit values are `AuditAction.PREPARED_JPEG_CREATED`, `AuditSubjectType.PREPARED_IMAGE_ARTIFACT`, and controlled after value `PREPARED_JPEG`. Errors are `GEOMETRY_RECIPE_NOT_FOUND`, `SOURCE_FILE_NOT_FOUND`, `ORIGINAL_ARTIFACT_NOT_FOUND`, `ORIGINAL_BYTES_INVALID`, `SOURCE_DIMENSIONS_MISMATCH`, `GEOMETRY_RENDER_FAILED`, `JPEG_ENCODING_FAILED`, `SIZE_LIMIT_UNREACHABLE`, `STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_FAILED`, and `PERSISTED_DATA_INVALID`, with privacy-safe string/repr.

Storage publication occurs once after in-memory selection and before one metadata Unit of Work; reference revalidation, stored-artifact metadata, prepared entity, and audit commit together. Database failure leaves an encrypted unreferenced object for the existing read-only orphan reconciliation; filesystem/database atomicity is not claimed.

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
