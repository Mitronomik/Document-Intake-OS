# ADR-025 — Deterministic prepared JPEG v1

**Status:** PROPOSED

## Decision status and authorization boundary

This ADR is a documentation-only proposal. It is not accepted and does not authorize PR-011 production implementation. The PR-011 contract is PROPOSED FOR HUMAN REVIEW; PR-011 production implementation is UNAUTHORIZED; PR-012 and later are UNAUTHORIZED; Gate 2 is NOT ACCEPTED; M3 is IN PROGRESS. A later explicit Product owner decision must accept this ADR and the PR-011 contract, authorize implementation, and name the merge commit of this documentation-contract PR as its exact base.

## Proposed decision

PR-011 will provide an offline, deterministic, reusable one-raster JPEG preparation primitive. Its input is exactly one accepted immutable PR-010 geometry-recipe version, replayed against immutable original bytes through the accepted PR-010 decoder and renderer. It accepts no caller bytes or paths, prior JPEG candidate, mutable UI state, unconfirmed coordinates, multiple regions or sides, or merged raster. It neither modifies geometry nor infers regions nor merges sides.

The identities are `pipeline_id = PILLOW_PREPARED_JPEG`, `pipeline_version = 1`, `output_contract_id = PREPARED_JPEG_SRGB_V1`, and `output_contract_version = 1`. The immutable prepared-artifact record persists both identities. A change to quality or resize sequences, resampling, subsampling, progressive/optimization mode, metadata or color interpretation, selection order, or technical readability floor requires a new pipeline version or ADR.

## Exact output contract

`MAX_PREPARED_JPEG_BYTES = 1_992_294`, the greatest whole-byte value not exceeding 1.90 × 1024 × 1024. Acceptance is `byte_size <= 1_992_294`; `1_992_295` fails. The output is a valid `.jpg` JPEG, RGB samples interpreted as sRGB, no alpha, and no embedded ICC profile in V1. It contains no EXIF/geolocation, XMP, IPTC, source ICC, comment, filename, local path, DPI metadata, or thumbnail. Required JPEG/JFIF structural headers are not source metadata. It is deterministic, baseline-compatible, non-progressive, and uses:

```text
format = JPEG
progressive = false
optimize = true
subsampling = 0
```

`subsampling = 0` is 4:4:4 for text and document-edge preservation. Callers have no encoder override.

## Original and candidate algorithm

The immutable original source bytes remain authoritative and unchanged. The accepted PR-010 recipe is reapplied to them to produce one fresh uncompressed RGB working raster. Every scale is derived from that raster and every quality candidate from the uncompressed raster at its scale; no JPEG candidate is decoded or reused.

```text
for scale in [100, 90, 80, 70, 60, 50]:
    derive the uncompressed raster for this scale from the original PR-010 working raster
    for quality in [95, 90, 85, 80, 75, 70, 65, 60]:
        encode a fresh JPEG candidate
        validate the complete output contract
        select and stop at the first valid candidate
```

Thus quality is reduced before resolution. There is no binary/adaptive/random search, caller quality, quality below 60, or continued search after the first valid candidate. Scaling never upscales, uses Pillow `LANCZOS`, preserves aspect ratio, skips duplicate dimension pairs, and calculates each dimension for percentage `p` as `max(1, floor((source_dimension * p + 50) / 100))`.

## Technical preparation guard

This is not semantic readability assessment and does not activate the deferred PR-009 policy. Q-021 remains DEFERRED; production PR-009 `policy_id` and `policy_version` remain unassigned; automatic blocking and production `RETAKE_REQUIRED` remain inactive. Quality is at least 60; neither dimension falls below 50% of the PR-010 render; when source short side is at least 1200 pixels the output short side remains at least 1200; when it is below 1200, resolution is not reduced. There is no sharpening, denoising, equalization, or generative restoration.

If no candidate fits, publish nothing, preserve originals and valid artifacts, return `SIZE_LIMIT_UNREACHABLE`, and direct the operator to `request a better source image`. `READABILITY_FAILED` is reserved for a separately accepted future policy or explicit workflow and is not emitted automatically in V1.

## Determinism

Identical immutable bytes/checksum, canonical recipe and PR-010 pipeline, PR-011 policy/pipeline, locked dependencies, OS and architecture produce byte-identical JPEGs. Windows 11 x64 reruns under the same packaged runtime must be byte-identical. Ubuntu/Windows outputs need structural equivalence—not unproved cross-libjpeg byte identity: successful JPEG/RGB decode, equal dimensions/scale/quality and metadata absence, exact boundary compliance, and byte-identical repeated runs on each platform.

## Model, application and persistence proposal

Immutable `PreparedImageArtifact` fields are: `id: EntityId`, `source_file_id: EntityId`, `geometry_recipe_version_id: EntityId`, `stored_artifact_id: EntityId`, `pipeline_id: str`, `pipeline_version: int`, `output_contract_id: str`, `output_contract_version: int`, `media_type: JPEG`, `color_space: SRGB`, `width: int`, `height: int`, `byte_size: int`, `sha256: Sha256Digest`, `jpeg_quality: int`, `resize_percent: int`, `created_at: datetime`, `created_by: ActorRef`. It contains no bytes, paths, filenames, coordinates, OCR/PII, or mutable status. Bytes belong in existing immutable encrypted storage; the database holds controlled metadata and immutable references.

`PrepareJpegCommand` fields are `prepared_artifact_id`, `stored_artifact_id`, `geometry_recipe_version_id`, `audit_event_id`, `prepared_at`, `actor`, `correlation_id`. IDs/timestamp are caller supplied; record IDs are pairwise distinct; time is aware UTC; there is no UUID/time generation, path, bytes, encoder/quality/resize override, or PR-009 policy identity. Results return controlled metadata and the persisted entity, never bytes or paths.

Future forward-only migration `v0007_prepared_jpeg` must not alter v0001-v0006 and receives no checksum until implemented/reviewed. It enforces immutable rows; positive dimensions/size; the exact byte ceiling; JPEG/SRGB; allowed quality/resize sequences; both identities; immutable source/recipe/stored-artifact references; canonical payload/projection consistency; update/delete/replacement rejection; and deterministic listing.

## Publication, transaction and reconciliation

The operation order is: (1) validate source-independent command invariants; (2) read immutable recipe/source/original metadata; (3) read encrypted original bytes; (4) reproduce the PR-010 RGB raster; (5) generate candidates in memory; (6) select first valid; (7) calculate SHA-256/metadata; (8) publish once to immutable encrypted storage; (9) open one metadata Unit of Work; (10) revalidate authoritative immutable references; (11) add stored-artifact record; (12) add `PreparedImageArtifact`; (13) add audit; (14) commit once; (15) return only after commit and Unit of Work exit. No intermediate candidate is persisted.

Filesystem and database writes are not one atomic transaction. A database failure after publication must preserve existing records, report the unreferenced encrypted object through the accepted read-only orphan-reconciliation mechanism, and must not silently adopt, overwrite, or delete it.

## Audit, errors and identity

Future enum values are `AuditAction.PREPARED_JPEG_CREATED` and `AuditSubjectType.PREPARED_IMAGE_ARTIFACT`. Audit uses action `PREPARED_JPEG_CREATED`, subject type `PREPARED_IMAGE_ARTIFACT`, prepared artifact ID, controlled after value `PREPARED_JPEG`, and caller correlation ID. It contains no filename/path/bytes, checksum, quality, dimensions, coordinates, document/OCR/PII, or exception text; size/dimensions remain in the entity record.

Controlled errors are `GEOMETRY_RECIPE_NOT_FOUND`, `SOURCE_FILE_NOT_FOUND`, `ORIGINAL_ARTIFACT_NOT_FOUND`, `ORIGINAL_BYTES_INVALID`, `SOURCE_DIMENSIONS_MISMATCH`, `GEOMETRY_RENDER_FAILED`, `JPEG_ENCODING_FAILED`, `SIZE_LIMIT_UNREACHABLE`, `STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_FAILED`, and `PERSISTED_DATA_INVALID`. String/repr expose only codes and never paths, filenames, bytes, checksums, coordinates, PII, or raw exceptions; internal chaining must not leak.

Deterministic bytes do not imply record identity. Duplicate IDs fail before publication; nothing is overwritten or updated in place; there is no mutable latest row. Immutable versioned records are preferred. Different caller IDs may create separate records only if the later accepted service contract explicitly permits it.

## Roadmap/pipeline ordering resolution

The product pipeline retains “merge before final compression.” PR-011 first creates the reusable one-recipe/one-raster primitive. PR-012 later supplies one confirmed recipe per region. PR-013 later composes working rasters/sides and reuses the same versioned primitive at the final composition boundary; it may add orchestration but cannot silently change PR-011 encoder semantics. Gate 2 remains blocked until PR-011, PR-012 and PR-013 are accepted and local real-photo evidence exists outside Git, Codex and CI.

