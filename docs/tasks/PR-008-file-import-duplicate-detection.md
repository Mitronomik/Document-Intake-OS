# PR-008 — File import and duplicate detection

Status: `AUTHORIZED, NOT STARTED`

Exact verified base SHA: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`

Authorization source: PR-007 was completed and human accepted through GitHub PR `#19`; final reviewed head `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`; merge commit `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`; exact-head CI `CI #92` successful; migration v0003 checksum `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`. This task may not be implemented until the lifecycle PR that creates this task and ADR-022 is merged into `main`. PR-009 and later remain `UNAUTHORIZED`.

## Goal

Implement the non-UI application and persistence foundation for creating an `UploadBatch`, importing one or more JPG/JPEG, PNG or HEIC/HEIF source files into a batch, preserving each original byte-for-byte through the accepted encrypted managed object store, persisting source-file metadata in encrypted SQLCipher, computing exact SHA-256 and advisory perceptual duplicate evidence, and returning controlled duplicate warnings.

## Exact production-file allowlist

PR-008 may create or modify only files required for the contracts below under:

- `src/document_intake/domain/`
- `src/document_intake/application/`
- `src/document_intake/persistence/`
- `src/document_intake/storage/` only to reuse existing PR-006 ports/adapters, not to create a second original storage implementation
- `src/document_intake/image_pipeline/` only for local media validation/perceptual hashing adapters if the dependency boundary is satisfied
- `docs/` only for PR-008 documentation updates

Do not modify UI, recognition, terminal adapters, export implementation, scripts, workflows, lockfiles or dependency files except a normal dependency and lockfile update that is explicitly justified by the selected offline decoder/perceptual-hash dependency evidence.

## Exact test-file allowlist

PR-008 may create or modify only tests required for these contracts under:

- `tests/` source-code tests
- `tests/fixtures/synthetic/` for any committed tiny synthetic image fixture, if runtime generation is insufficient

No real document, real personal data, terminal template, template-derived binary, production database, log or private acceptance fixture may be added.

## Domain contracts

Introduce explicit immutable domain/application contracts for `UploadBatch`, `SourceFile`, import results and duplicate warnings. The task must specify exact fields, enums, invariants, repository methods and service inputs/outputs before implementation. `UploadBatch` and `SourceFile` start from the documented business concepts of batch import and immutable originals. Public APIs require type annotations and safe `repr()` output.

## Application-service contract

The non-UI service creates an upload batch and imports one or more source files into that batch. It returns an import result containing safe immutable IDs and zero or more controlled duplicate warnings. It must clearly distinguish exact duplicate evidence from successful storage-integrity validation. It must not call UI, OCR, MRZ, barcode, Excel or terminal-adapter code.

## Storage reuse contract

PR-008 must reuse the accepted PR-006 managed object store: encrypted managed objects only, AES-256-GCM envelope v1, `DIOSOBJ1` magic, immutable UUID-derived managed paths, object-first/database-second publication, SQLCipher authoritative expected-state records, no plaintext managed originals, no update or delete operation, no automatic orphan adoption and no automatic orphan deletion. Do not create human-readable managed object paths or a second original-file storage implementation. Do not place filenames, names, passport numbers, VINs, registrations or other PII in managed paths.

## Persistence and v0004 migration contract

Add forward-only migration `v0004_source_file_import.py` with version `4` and name `source_file_import_pr008`. Migration ordering is append-only; v0001, v0002 and v0003 remain byte-for-byte unchanged; the v0004 checksum is independently asserted in tests; canonical payload and projection-integrity validation remain mandatory; all new tables remain in encrypted SQLCipher; no destructive migration, down migration or plaintext SQLite support is authorized.

## Duplicate-warning contract

Warnings may contain only warning code, new source-file ID, prior source-file ID, exact/perceptual classification, perceptual distance where applicable, algorithm identifier and algorithm version. Warnings must not contain original filename, full path, document image bytes, OCR text, MRZ, passport numbers, VINs, registrations, raw exception text, SQL, database path, storage path or key material.

## Exact/perceptual distinction

Compute SHA-256 over unchanged original bytes. SHA-256 is exact-content identity evidence only and is not a cryptographic storage-integrity substitute in the application result. An exact duplicate warns only; it does not overwrite, mutate, delete, merge batches, silently suppress the new import or automatically resolve operator review. It does not automatically delete any source file and does not automatically merge any source file or batch.

Perceptual hashing is advisory only. It must never be used as a security hash, integrity checksum or proof that files are identical, and must never overwrite, merge, delete, reject or bypass operator review. Persisted perceptual hashes must include an explicit algorithm identifier and algorithm version. PR-008 must define deterministic canonical in-memory image preparation used only for hashing, hash bit width, distance function, configured warning threshold, compatible algorithm/version comparison and deterministic tie ordering.

## Media validation contract

Do not trust only filename extension. Validate supported format from file content and successful local decoding. Extension/content disagreement must produce a controlled warning or error defined by PR-008. No cloud decoder, remote service, runtime download or network fallback is allowed. The decoder must fail closed when unavailable.

## Filename/privacy contract

Only the input file basename may be retained as encrypted SQLCipher source metadata. Do not persist full source filesystem paths. The basename must never be used in the managed storage path and must not appear in logs, errors, audit summaries, verifier output or test reports. It must be excluded from unsafe `repr()` output, reject path separators, control characters and invalid empty values, and have an explicit documented length boundary.

## Transaction and orphan behavior

A successful import requires: read and validate source bytes; compute SHA-256 and perceptual evidence; publish an immutable encrypted original object; open one SQLCipher Unit of Work; insert authoritative stored-artifact metadata; insert `UploadBatch`/`SourceFile` metadata as applicable; insert explicitly created PII-safe audit event or events when required by the final task contract; explicitly commit; return result and warnings. If database publication fails after object creation, no false successful import result may be returned; database changes and audit events roll back together; the encrypted object may remain an orphan; existing read-only reconciliation reports the orphan; no automatic orphan adoption or deletion is added.

## Audit boundary

The implementation task must explicitly decide and document whether successful original registration emits existing controlled action `ARTIFACT_REGISTERED`. Low-level repositories must not infer or automatically emit audit events. Any audit events are created explicitly by the application service using the same Unit of Work. No raw value, filename, path, media bytes, checksum, perceptual hash or duplicate distance may be stored in audit before/after summaries. Do not add free-text audit messages or change the accepted PR-007 audit privacy model without a separate product-owner decision.

## Dependency boundary

Any image-decoder/perceptual-hash dependency must work fully offline after installation, support Windows 11 x64 and Python 3.12, have installable Windows AMD64 wheels or an explicitly verified packaging path, have documented license and redistribution obligations, be pinned through the normal dependency and lockfile process, introduce no runtime downloads, telemetry or cloud service, and fail closed when unavailable. Do not select a dependency silently; PR-008 must document selected dependency, exact pinned version, Windows evidence and license evidence before acceptance.

## Acceptance criteria

- Imports preserve original bytes byte-for-byte in encrypted managed storage.
- Metadata is persisted only in encrypted SQLCipher.
- Exact SHA-256 and versioned advisory perceptual-hash evidence are deterministic.
- Duplicate warnings are controlled, privacy-safe and advisory.
- No automatic merge, overwrite, delete, adoption, suppression or rejection occurs for duplicates.
- v0004 migration is append-only and independently checksummed.
- Transaction failures do not report false success and leave only reconcilable encrypted orphans when object publication succeeded first.
- PR-009 and later remain unauthorized.

## Mandatory automated tests

Tests must cover immutable original preservation, encrypted-storage reuse, no plaintext managed originals, safe basename validation and `repr()`, extension/content disagreement, unsupported/corrupt media fail-closed behavior, exact SHA-256 duplicate warning, versioned perceptual hash warning and incompatible-version exclusion, deterministic tie ordering, no auto-merge/delete/overwrite/suppress behavior, Unit of Work rollback with audit rollback, orphan reconciliation after database failure, v0004 checksum and unchanged v0001/v0002/v0003 checksums, repository-policy compliance and synthetic-fixture boundaries.

## Windows verification requirements

Before PR-008 acceptance, verify on Windows 11 x64 with Python 3.12 that SQLCipher remains active, encrypted managed storage works offline, the selected decoder/perceptual-hash dependency imports without runtime downloads, supported formats decode locally, unavailable decoders fail closed, and no filenames, paths, checksums, hashes, OCR/MRZ text, SQL, storage paths, database paths, keys, real documents or PII appear in reports, logs or console output.

## Manual verification procedure

Use only generated synthetic non-document images. Create a batch, import multiple supported files, repeat an exact file, import a visually similar generated image, inspect safe warnings, verify stored encrypted object bytes decrypt to the exact source bytes through the storage API, verify no plaintext managed original exists, simulate database failure after object publication and run read-only reconciliation, and confirm no source basename appears outside encrypted SQLCipher metadata.

## Non-goals

PR-008 must not implement PySide upload UI, drag and drop, background job UI, quality scoring, blur/glare/contrast diagnostics, final EXIF orientation diagnostics, crop, perspective correction, segmentation, multiple-document regions, JPEG preparation or compression, OCR, MRZ, barcode, document classification, field candidates, operator verification, Excel, terminal adapters, export, backup/restore, retention/deletion, users/authentication, telemetry, cloud services, browser automation or PR-009-or-later behavior.

## Hard prohibitions

Do not add real documents, transformed real documents, real personal data, original filenames in paths/logs/errors/audits/reports, plaintext SQLite support, plaintext managed originals, human-readable managed object paths, cloud services, telemetry, runtime downloads, automatic duplicate merge/delete/overwrite/reject/suppress behavior, automatic orphan adoption/deletion, repository-emitted audit events or free-text audit messages.

## Exact-head CI completion gate

PR-008 cannot be accepted until the exact GitHub head SHA has successful CI, v0004 checksum evidence, Windows verification evidence, dependency/license evidence, repository-policy success and confirmation that no PR-009 or later behavior was implemented.
