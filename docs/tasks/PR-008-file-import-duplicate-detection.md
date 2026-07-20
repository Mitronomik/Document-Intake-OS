# PR-008 — File import and duplicate detection

Status: `AUTHORIZED, NOT STARTED`

Lifecycle preparation base: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`.

PR-008 implementation base: the eventual exact merge commit of GitHub PR #20. Do not invent the future merge SHA. PR-008 must not branch from `71dfd7fa31bd67c9f9fa54cc9057684486e842ad` after PR #20 is merged. The PR-008 implementation prompt must use the actual PR #20 merge commit as its exact base, and PR-008 may not start from an earlier commit.

Authorization source: PR-007 was completed and human accepted through GitHub PR `#19`; final reviewed head `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`; merge commit `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`; exact-head CI `CI #92` successful; migration v0003 checksum `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`. This task may not be implemented until the lifecycle PR that creates this task and ADR-022 is merged into `main`. PR-009 and later remain `UNAUTHORIZED`.

## Goal

Implement the non-UI application and persistence foundation for creating an `UploadBatch`, importing one or more JPG/JPEG, PNG or HEIC/HEIF source files into a batch, preserving each original byte-for-byte through the accepted encrypted managed object store, persisting source-file metadata in encrypted SQLCipher, computing exact SHA-256 and advisory deterministic DHASH64 duplicate evidence, and returning controlled duplicate warnings.

## Exact production-file allowlist

PR-008 may create or modify these exact expected production files:

- `src/document_intake/domain/enums.py`
- `src/document_intake/domain/entities/imports.py`
- `src/document_intake/domain/entities/__init__.py`
- `src/document_intake/domain/value_objects/imports.py`
- `src/document_intake/domain/value_objects/__init__.py`
- `src/document_intake/domain/__init__.py`
- `src/document_intake/application/dto/imports.py`
- `src/document_intake/application/ports/media.py`
- `src/document_intake/application/ports/persistence.py`
- `src/document_intake/application/services/imports.py`
- `src/document_intake/persistence/database.py`
- `src/document_intake/persistence/serialization.py`
- `src/document_intake/persistence/migrations/__init__.py`
- `src/document_intake/persistence/migrations/v0004_source_file_import.py`
- `src/document_intake/image_pipeline/media_decoder.py`
- `scripts/verify_pr008_import.py`
- `pyproject.toml`
- `uv.lock`
- PR-008 documentation files.

Any additional production file requires an explicit explanation in the PR description and must remain inside PR-008 scope. Do not modify existing PR-006 storage implementation unless a demonstrated bug prevents reuse. Such a bug requires a regression test and explicit report.

## Exact test-file allowlist

PR-008 may create or modify these exact expected test files:

- `tests/domain/test_import_contracts.py`
- `tests/application/test_import_service.py`
- `tests/persistence/test_source_file_import_repository.py`
- `tests/persistence/test_migrations.py`
- `tests/image_pipeline/test_media_decoder.py`
- `tests/test_documentation_baseline.py`
- `tests/fixtures/synthetic/` for any committed tiny synthetic image fixture only if runtime generation is insufficient.

Any additional test file requires an explicit explanation in the PR description and must remain inside PR-008 scope. No real document, real personal data, terminal template, template-derived binary, production database, log or private acceptance fixture may be added.

## Exact enums

`UploadBatchStatus` contains exactly `NEW`, `PROCESSING`, `NEEDS_REVIEW`, `READY`, `ARCHIVED`. PR-008 creates batches only in `NEW`. It does not implement later workflow transitions.

`SourceMediaType` contains exactly `JPEG`, `PNG`, `HEIF`.

`ImportWarningCode` contains exactly `EXACT_DUPLICATE`, `PERCEPTUAL_SIMILARITY`, `EXTENSION_CONTENT_MISMATCH`.

`SourceImportErrorCode` contains exactly `BATCH_NOT_FOUND`, `SOURCE_READ_FAILED`, `SOURCE_BASENAME_INVALID`, `UNSUPPORTED_EXTENSION`, `UNSUPPORTED_FORMAT`, `DECODE_FAILED`, `STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_FAILED`. Errors must remain sanitized and must not contain source names, paths, image bytes, hashes, SQL, database paths, storage paths, keys or raw exceptions.

## Exact value objects

`BatchNumber` is immutable, frozen and slotted: canonical string; length 1-64; regex `^[A-Z0-9][A-Z0-9_-]{0,63}$`; no free text; safe `repr()`.

`SourceBasename` is immutable, frozen and slotted: exact basename only; length 1-255 Unicode code points; reject `/` and `\`; reject NUL, U+0000-U+001F and U+007F; reject `.` and `..`; do not trim, truncate or silently normalize; never include the parent path; `repr()` must show only `<redacted>`.

`Sha256Digest` is immutable, frozen and slotted: exactly 64 lowercase hexadecimal characters; computed over unchanged original bytes; no unsafe `repr()`.

`PerceptualHash` is immutable, frozen and slotted with exact fields `algorithm_id`, `algorithm_version`, `bit_width`, `hex_value`. Exact PR-008 values are `algorithm_id = "DHASH64"`, `algorithm_version = 1`, `bit_width = 64`, and `hex_value` exactly 16 lowercase hexadecimal characters. The hash value must not appear in logs, errors, audit events, verifier output or duplicate warnings.

## Exact domain entities

`UploadBatch` is immutable, frozen and slotted with exactly:

- `id: EntityId`
- `number: BatchNumber`
- `created_at: datetime`
- `created_by: ActorRef`
- `status: UploadBatchStatus`
- `source_file_ids: tuple[EntityId, ...]`

Invariants: `created_at` must be timezone-aware and normalized to UTC; `created_by` must be explicit; `source_file_ids` preserves successful import order; duplicate source-file IDs are rejected; PR-008 adds IDs only by returning a new immutable batch instance; notes are not part of PR-008; `repr()` exposes only ID, number, status and source count.

`SourceFile` is immutable, frozen and slotted with exactly:

- `id: EntityId`
- `batch_id: EntityId`
- `original_artifact_id: EntityId`
- `original_basename: SourceBasename`
- `detected_media_type: SourceMediaType`
- `byte_size: int`
- `sha256: Sha256Digest`
- `perceptual_hash: PerceptualHash`
- `width: int`
- `height: int`
- `exif_orientation: int | None`
- `imported_at: datetime`
- `imported_by: ActorRef`

Invariants: `byte_size > 0`; width and height are positive; width and height describe the primary decoded frame before EXIF orientation; only EXIF orientation integer 1-8 may be retained; no other EXIF field, GPS data or metadata is persisted; `imported_at` is timezone-aware and normalized to UTC; basename, SHA-256 and perceptual hash must be redacted from `repr()`. Do not add `quality_assessment` in PR-008. Quality assessment remains PR-009.

`ImportWarning` is immutable, frozen and slotted with exactly:

- `code: ImportWarningCode`
- `source_file_id: EntityId`
- `related_source_file_id: EntityId | None`
- `perceptual_distance: int | None`
- `algorithm_id: str | None`
- `algorithm_version: int | None`

Invariants: `EXACT_DUPLICATE` requires a related source ID and forbids distance and algorithm fields; `PERCEPTUAL_SIMILARITY` requires related source ID, distance, algorithm ID and algorithm version; `EXTENSION_CONTENT_MISMATCH` forbids related source ID, distance and algorithm fields; no warning may contain filenames, paths, bytes, hashes or PII.

## Exact application DTOs

Define exact immutable DTOs:

- `CreateUploadBatchCommand`: `batch_id`, `number`, `created_at`, `actor`.
- `SourceFileImportInput`: `source_file_id`, `artifact_id`, `source_path`, `imported_at`.
- `ImportSourceFilesCommand`: `batch_id`, `actor`, `items: tuple[SourceFileImportInput, ...]`.
- `ImportedSourceFileResult`: `source_file`, `warnings`.
- `FailedSourceFileResult`: `source_file_id`, `error_code`.
- `ImportSourceFilesResult`: `batch_id`, `imported`, `failed`.

The path is an ephemeral input only. Command and DTO `repr()` must redact it. No result contains a basename or path.

## Exact repository API

`UploadBatchRepository` exposes exactly `add(batch)`, `get(batch_id)`, `update(batch)`.

`SourceFileRepository` exposes exactly `add(source_file)`, `get(source_file_id)`, `list_by_batch(batch_id)`, `list_by_sha256(sha256)`, `list_compatible_perceptual_hashes(algorithm_id, algorithm_version, bit_width)`.

Rules: Source files expose no update or delete method; list ordering is deterministic ascending by `imported_at`, then ID; compatible perceptual lookup returns only equal algorithm ID, version and bit width; canonical payload/projection validation occurs before returning rows; no arbitrary filter, caller-supplied sorting or pagination is authorized.

## Storage reuse contract

PR-008 must reuse the accepted PR-006 managed object store: encrypted managed objects only, AES-256-GCM envelope v1, `DIOSOBJ1` magic, immutable UUID-derived managed paths, object-first/database-second publication, SQLCipher authoritative expected-state records, no plaintext managed originals, no update or delete operation, no automatic orphan adoption and no automatic orphan deletion. Do not create human-readable managed object paths or a second original-file storage implementation. Do not place filenames, names, passport numbers, VINs, registrations or other PII in managed paths.

The bytes registered as the original must be byte-for-byte identical to the bytes read from the selected input file. PR-008 may decode a separate in-memory representation only for media validation and perceptual hashing. Decoded or normalized bytes must never replace the stored original. No EXIF rewrite, orientation rewrite, metadata stripping, image correction, crop, compression or format conversion is authorized in PR-008.

## Persistence and v0004 migration contract

Add forward-only migration `v0004_source_file_import.py` with version `4` and name `source_file_import_pr008`. Migration ordering is append-only; v0001, v0002 and v0003 remain byte-for-byte unchanged; the v0004 checksum is independently asserted in tests; canonical payload and projection-integrity validation remain mandatory; all new tables remain in encrypted SQLCipher; no destructive migration, down migration or plaintext SQLite support is authorized.

## Multi-file transaction semantics

Document and test this deliberate behavior:

1. `CreateUploadBatch` is a separate committed operation.
2. Before processing files, the import service verifies that the batch exists. A missing batch fails the whole command before reading or publishing files.
3. Input files are processed sequentially in the supplied order.
4. Each source file has its own object-first/database-second transaction boundary.
5. A successful prior source import is not rolled back because a later source fails.
6. A failed source produces a sanitized `FailedSourceFileResult`.
7. Processing continues after a per-file failure.
8. For each successful file, one SQLCipher Unit of Work atomically inserts the `StoredArtifactRecord`, inserts the immutable `SourceFile`, updates the immutable `UploadBatch` with the appended source ID, inserts the required audit event, and commits.
9. If the SQLCipher transaction fails, `SourceFile`, batch update and audit event roll back together, no success result is returned, and the encrypted object may remain a reconcilable orphan.
10. No whole-batch filesystem transaction is claimed.

Duplicate evidence is a warning and does not create a failure result.

## Exact media validation behavior

The extension map is exact:

- `.jpg`, `.jpeg` -> `JPEG`
- `.png` -> `PNG`
- `.heic`, `.heif` -> `HEIF`

Rules: unsupported extension produces `UNSUPPORTED_EXTENSION`; supported extension plus corrupt or undecodable content produces `DECODE_FAILED`; content that decodes to no supported media type produces `UNSUPPORTED_FORMAT`; supported extension whose decoded supported type differs from the extension imports successfully with `EXTENSION_CONTENT_MISMATCH`; detected content type is authoritative for `SourceFile.detected_media_type`; validation occurs before encrypted object publication; no failed validation publishes an object. Do not trust extension alone.

## Exact duplicate and perceptual-hash contract

Compute SHA-256 over unchanged original bytes. SHA-256 is exact-content identity evidence only and is not a cryptographic storage-integrity substitute in the application result. An exact duplicate warns only; it does not overwrite, mutate, delete, merge batches, silently suppress the new import or automatically resolve operator review. It does not automatically delete any source file and does not automatically merge any source file or batch.

Use the deterministic PR-008 perceptual-hash algorithm: algorithm ID `DHASH64`; version `1`; bit width `64`; use the primary decoded image/frame only; apply EXIF orientation in memory for hashing only; convert alpha images by compositing onto an opaque white background; convert to 8-bit grayscale; resize to exactly `9x8` using a fixed `LANCZOS` resampler; compare each pixel with the pixel immediately to its right; bit is 1 when left luminance is greater than right luminance, otherwise 0; bits are stored row-major as a 64-bit value; persist exactly 16 lowercase hexadecimal characters; distance is Hamming distance using XOR and population count; warning threshold is distance <= 8; final real-photo threshold validation remains local pilot evidence; a later threshold or preparation change requires a new algorithm version.

Comparison scope: compare against all persisted compatible `SourceFile` records, not only the current batch; incompatible algorithm/version/bit-width records are excluded; exact same SHA-256 pair produces `EXACT_DUPLICATE`; do not also produce a perceptual warning for the same exact pair; deterministic warning order is exact warnings by related source-file ID, then perceptual warnings by distance and related source-file ID, then extension/content warning last.

Warnings may contain only warning code, new source-file ID, prior source-file ID, exact/perceptual classification, perceptual distance where applicable, algorithm identifier and version. Warnings must not contain original filename, full path, document image bytes, OCR text, MRZ, passport numbers, VINs, registrations, raw exception text, SQL, database path, storage path, key material or hash values.

## Filename/privacy contract

Only the input file basename may be retained as encrypted SQLCipher source metadata. Do not persist full source filesystem paths. The basename must never be used in the managed storage path and must not appear in logs, errors, audit summaries, verifier output or test reports. It must be excluded from unsafe `repr()` output, reject path separators, control characters, invalid empty values, `.` and `..`, and have the exact length boundary 1-255 Unicode code points. Do not trim, truncate or silently normalize.

## Exact audit event contract

Successful original registration must emit exactly one audit event using the same SQLCipher Unit of Work:

- action: `ARTIFACT_REGISTERED`
- subject type: `STORED_ARTIFACT`
- subject ID: the original artifact ID
- actor: the import command actor
- occurred time: the source imported time
- field key: absent
- before: `ABSENT`
- after: `NON_SENSITIVE` with controlled display value `ORIGINAL`
- reason code: `SOURCE_FILE_IMPORT`
- correlation ID: upload batch ID

Do not emit audit events for failed imports, duplicate warnings, extension mismatch warnings or `UploadBatch` creation. `UploadBatch` is not added to `AuditSubjectType` in PR-008. Do not change existing audit enums or the PR-007 privacy model. Low-level repositories must not infer or automatically emit audit events.

## Dependency boundary

The domain and application contracts must depend on a local `MediaDecoderPort`, not directly on a third-party package. The port returns only detected media type, primary-frame dimensions, optional orientation integer and an in-memory pixel representation sufficient for deterministic dHash. No external perceptual-hash library is required. The algorithm must be implemented against the selected local decoder adapter.

The implementation PR may select decoder dependencies only after documenting exact pinned versions, Python 3.12 support, Windows AMD64 wheel availability or verified packaging, JPEG, PNG and HEIF decoding evidence, offline import and execution, license and redistribution obligations, and no runtime downloads or telemetry. If the evidence is not available, PR-008 must stop as blocked rather than silently dropping HEIF support or selecting another architecture. Runtime codec downloads are not authorized.

## Acceptance criteria

- Imports preserve original bytes byte-for-byte in encrypted managed storage.
- Metadata is persisted only in encrypted SQLCipher.
- Exact SHA-256 and DHASH64 version 1 advisory perceptual-hash evidence are deterministic.
- Duplicate warnings are controlled, privacy-safe and advisory.
- Extension/content mismatch is a warning and successful import.
- Unsupported extension is an error and publishes no object.
- No automatic merge, overwrite, delete, adoption, suppression or rejection occurs for duplicates.
- v0004 migration is append-only and independently checksummed.
- Per-file transaction failures do not report false success and leave only reconcilable encrypted orphans when object publication succeeded first.
- PR-009 and later remain unauthorized.

## Mandatory automated tests

Tests must cover immutable original preservation, encrypted-storage reuse, no plaintext managed originals, exact enum values, exact domain fields, safe basename validation length 1-255 and redacted `repr()`, path redaction in command/DTO `repr()`, exact repository method names and absence of source-file update/delete, media extension mapping, extension/content mismatch warning with successful import, unsupported extension error, corrupt decode failure, unsupported decoded format failure, validation-before-publication, exact SHA-256 duplicate warning, DHASH64 algorithm ID, version 1, 64 bits, threshold 8, deterministic preparation and warning ordering, compatible perceptual lookup only, no perceptual warning for exact pairs, no auto-merge/delete/overwrite/suppress behavior, per-file partial-success transaction semantics, Unit of Work rollback with audit rollback, orphan reconciliation after database failure, exact audit event contract, v0004 checksum and unchanged v0001/v0002/v0003 checksums, no `quality_assessment` scope, repository-policy compliance and synthetic-fixture boundaries.

## Windows verification requirements

Before PR-008 acceptance, verify on Windows 11 x64 with Python 3.12 that SQLCipher remains active, encrypted managed storage works offline, the selected decoder dependency imports without runtime downloads, supported JPEG/PNG/HEIF formats decode locally, unavailable decoders fail closed, DHASH64 is deterministic, and no filenames, paths, checksums, hashes, OCR/MRZ text, SQL, storage paths, database paths, keys, real documents or PII appear in reports, logs or console output.

## Manual verification procedure

Use only generated synthetic non-document images. Create a batch, import multiple supported files, repeat an exact file, import a visually similar generated image, import a supported extension with different supported content to confirm `EXTENSION_CONTENT_MISMATCH` and success, import an unsupported extension to confirm error and no object, inspect safe warnings, verify stored encrypted object bytes decrypt to the exact source bytes through the storage API, verify no plaintext managed original exists, simulate database failure after object publication and run read-only reconciliation, and confirm no source basename appears outside encrypted SQLCipher metadata.

## Non-goals

PR-008 must not implement PySide upload UI, drag and drop, background job UI, quality scoring, blur/glare/contrast diagnostics, final EXIF orientation diagnostics, crop, perspective correction, segmentation, multiple-document regions, JPEG preparation or compression, OCR, MRZ, barcode, document classification, field candidates, operator verification, Excel, terminal adapters, export, backup/restore, retention/deletion, users/authentication, telemetry, cloud services, browser automation, `quality_assessment` or PR-009-or-later behavior.

## Hard prohibitions

Do not add real documents, transformed real documents, real personal data, original filenames in paths/logs/errors/audits/reports, plaintext SQLite support, plaintext managed originals, human-readable managed object paths, cloud services, telemetry, runtime downloads, automatic duplicate merge/delete/overwrite/reject/suppress behavior, automatic orphan adoption/deletion, repository-emitted audit events, free-text audit messages, UploadBatch audit subject type, quality assessment or PR-009 behavior.

## Exact-head CI completion gate

PR-008 cannot be accepted until the exact GitHub head SHA has successful CI, v0004 checksum evidence, Windows verification evidence, dependency/license evidence, repository-policy success and confirmation that no PR-009 or later behavior was implemented.
