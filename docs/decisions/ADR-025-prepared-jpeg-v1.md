# ADR-025 — Deterministic prepared JPEG v1

**Status:** ACCEPTED

## Decision status and authorization boundary

This ADR and the PR-011 contract were accepted by the Product owner on 2026-07-26. The exact accepted implementation base is `f007fb5a04a5c69c70a37faf7ba12fa6775ae819`. PR-011 production implementation is in review and not human accepted; PR-012 and later remain unauthorized; Gate 2 is not accepted; M3 remains in progress.

## Proposed decision

PR-011 separates the recipe-specific application use case from a reusable pure encoder. `prepare_geometry_recipe_as_jpeg` consumes one accepted immutable `geometry_recipe_version_id` plus caller-supplied persistence/audit IDs, actor, timestamp and correlation ID. It loads the recipe, replays it against immutable original bytes, obtains a fresh uncompressed RGB raster, calls the pure encoder, then publishes and persists the selected artifact. It rejects caller bytes, paths, unconfirmed geometry, multiple recipes/sides, composed rasters and caller encoder settings. PR-013 does not call this service for composition output.

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

Future forward-only migration `v0007_prepared_jpeg` transitions schema 6 to 7, must not alter v0001-v0006, and receives no checksum until implemented/reviewed. It enforces immutable rows; positive dimensions/size; the exact byte ceiling; JPEG/SRGB; allowed quality/resize sequences; fixed identities; foreign keys; canonical payload/projection equality; update/delete/replacement rejection; deterministic ordering; and `UNIQUE (geometry_recipe_version_id, pipeline_id, pipeline_version, output_contract_id, output_contract_version)`. Repository reads validate every canonical payload and projection before filtering or returning.

## Publication, transaction and reconciliation

The exact application order is: (1) validate source-independent invariants; (2) validate separate record IDs are pairwise distinct; (3) open a read Unit of Work; (4) load and validate recipe, source and original-artifact metadata; (5) close it without commit; (6) read and verify original bytes; (7) replay PR-010 geometry; (8) construct `UncompressedRgbRaster`; (9) call `PreparedJpegEncoderPort`; (10) validate selected metadata; (11) open one write Unit of Work; (12) re-read and revalidate authoritative references; (13) verify `prepared_artifact_id` is absent; (14) verify `stored_artifact_id` is absent; (15) verify `audit_event_id` is absent; (16) verify the natural preparation key is absent; (17) publish exactly once; (18) add stored-artifact metadata; (19) add `PreparedImageArtifact`; (20) add audit; (21) commit exactly once; (22) exit; (23) construct and return the result. Nothing is published before steps 13-16 pass; no intermediate candidate is published.

Filesystem and database writes are not one atomic transaction. A late uniqueness race after publication rolls back all database changes, preserves valid records, neither overwrites nor adopts a record, leaves the encrypted object unreferenced for accepted read-only orphan-reconciliation, performs no automatic deletion, and returns `PERSISTENCE_CONFLICT` without path, filename, checksum or bytes.

## Audit, errors and identity

Future enum values are `AuditAction.PREPARED_JPEG_CREATED`, `AuditSubjectType.PREPARED_IMAGE_ARTIFACT`, and `AuditReasonCode.PREPARED_JPEG_CREATED`. Exact fields are: `event_id = command.audit_event_id`; action `PREPARED_JPEG_CREATED`; subject type `PREPARED_IMAGE_ARTIFACT`; `subject_id = command.prepared_artifact_id`; `actor = command.actor`; `occurred_at = command.prepared_at`; `field_key = None`; before classification `ABSENT`, display value `None`, was-present `false`; after classification `NON_SENSITIVE`, display value `PREPARED_JPEG`, was-present `true`; reason `PREPARED_JPEG_CREATED`; and `correlation_id = command.correlation_id`. Audit, stored-artifact metadata and prepared artifact commit in the same write Unit of Work: none may commit without the others. Audit contains no filename/path/bytes, source/output checksum, quality, resize, dimensions, byte size, coordinates, document identifiers, OCR/PII or raw exception; controlled metrics remain in the artifact record.

Controlled errors are `GEOMETRY_RECIPE_NOT_FOUND`, `SOURCE_FILE_NOT_FOUND`, `ORIGINAL_ARTIFACT_NOT_FOUND`, `ORIGINAL_BYTES_INVALID`, `SOURCE_DIMENSIONS_MISMATCH`, `GEOMETRY_RENDER_FAILED`, `JPEG_ENCODING_FAILED`, `SIZE_LIMIT_UNREACHABLE`, `IDENTITY_CONFLICT`, `PREPARATION_ALREADY_EXISTS`, `STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_CONFLICT`, `PERSISTENCE_FAILED`, and `PERSISTED_DATA_INVALID`. `IDENTITY_CONFLICT` means a caller record ID exists at preflight; `PREPARATION_ALREADY_EXISTS` means the natural key exists at preflight; `PERSISTENCE_CONFLICT` means a late uniqueness race after publication. String/repr expose only codes and never paths, filenames, bytes, checksums, coordinates, PII, raw SQL or raw exceptions.

The encoder is deterministic and replayable; application creation is create-once. Exactly one artifact exists for `(geometry_recipe_version_id, pipeline_id, pipeline_version, output_contract_id, output_contract_version)`. There is no mutable latest row, update-in-place or PR-011 revision chain. Another artifact for the recipe requires a changed pipeline or output-contract identity. Repeated test encoding reproduces bytes; repeated persistence creation returns `PREPARATION_ALREADY_EXISTS`, never an existing entity or duplicate record, and never ignores caller IDs.

## Reusable pure encoder contract

`PreparedJpegEncoderPort.encode_prepared_jpeg(raster: UncompressedRgbRaster, *, pipeline: PreparedJpegPipelineVersion) -> EncodedPreparedJpeg` is pure with respect to persistence/storage: no database, publication or audit. Frozen `UncompressedRgbRaster` contains positive `width`, positive `height`, and `rgb_pixels: bytes` of exact length `width * height * 3`; mode is RGB and it contains no encoded JPEG, path, filename, document/source ID, OCR or PII. Frozen internal `EncodedPreparedJpeg` contains `jpeg_bytes`, `width`, `height`, `byte_size`, `sha256`, `jpeg_quality`, `resize_percent`, and both pipeline/output-contract IDs and versions. It returns one selected in-memory candidate using fixed V1 settings. Raw bytes never cross application DTO, UI, log, audit or repository interfaces.

## Roadmap/pipeline ordering resolution

The product pipeline retains “merge before final compression.” PR-012 supplies confirmed recipes per region. PR-013 composes confirmed uncompressed RGB rasters into one controlled `UncompressedRgbRaster`, then calls `PreparedJpegEncoderPort` directly—not the recipe service. It cannot bypass or change settings, sequences, metadata rules or byte limit. Gate 2 remains blocked until PR-011, PR-012 and PR-013 are accepted and local real-photo evidence exists outside Git, Codex and CI.

## Current lifecycle state — 2026-07-26


Product owner authorization date: 2026-07-26. Accepted contract and implementation base: `f007fb5a04a5c69c70a37faf7ba12fa6775ae819`. Current schema version: `7`. Final v0007 checksum: `62c38c1a64fa620a04d6bb0536ad7ed5ffede376b8293b555330611ca45c84ca`. ADR-025: ACCEPTED. PR-011 CONTRACT: ACCEPTED. PR-011 PRODUCTION IMPLEMENTATION: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-012 AND LATER: UNAUTHORIZED. Q-021: DEFERRED. PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE. PRODUCTION `policy_id`: NOT ASSIGNED. PRODUCTION `policy_version`: NOT ASSIGNED. AUTOMATIC PR-009 QUALITY BLOCKING: NOT ACTIVE. AUTOMATIC PRODUCTION `RETAKE_REQUIRED`: NOT ACTIVE. GATE 2: NOT ACCEPTED. M3: IN PROGRESS. Real documents and personal data remain prohibited in Git, Codex and CI.
