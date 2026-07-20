# PR-008 — File import and duplicate detection

Status: `IMPLEMENTED AND IN REVIEW, NOT ACCEPTED`

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

PR-008 must define exactly these immutable, frozen and slotted DTOs.

```python
@dataclass(frozen=True, slots=True)
class CreateUploadBatchCommand:
    batch_id: EntityId
    number: BatchNumber
    created_at: datetime
    actor: ActorRef
```

Invariants: `created_at` must be timezone-aware; construction normalizes it to UTC; `actor` must be explicit; the command creates the batch only with `UploadBatchStatus.NEW`; UUIDs and timestamps are caller-supplied; `repr()` must be safe.

```python
@dataclass(frozen=True, slots=True)
class SourceFileImportInput:
    source_file_id: EntityId
    artifact_id: EntityId
    audit_event_id: EntityId
    source_path: Path
    imported_at: datetime
```

Invariants: `source_file_id`, `artifact_id` and `audit_event_id` must be distinct; `source_path` is an ephemeral local input only; it is never persisted; it is never included in application results; it must be redacted from `repr()`; `imported_at` must be timezone-aware and normalized to UTC; IDs and timestamps are caller-supplied; no service-generated UUIDs or implicit current-time calls are authorized. The explicit `audit_event_id` is mandatory because the existing immutable `AuditEvent` contract requires an `event_id`.

```python
@dataclass(frozen=True, slots=True)
class ImportSourceFilesCommand:
    batch_id: EntityId
    actor: ActorRef
    items: tuple[SourceFileImportInput, ...]
```

Invariants: `items` must be a non-empty tuple; duplicate `source_file_id` values are rejected before any file is read; duplicate `artifact_id` values are rejected before any file is read; duplicate `audit_event_id` values are rejected before any file is read; command `repr()` must not reveal any source path.

```python
@dataclass(frozen=True, slots=True)
class ImportedSourceFileResult:
    source_file: SourceFile
    warnings: tuple[ImportWarning, ...]
```

```python
@dataclass(frozen=True, slots=True)
class FailedSourceFileResult:
    source_file_id: EntityId
    error_code: SourceImportErrorCode
```

```python
@dataclass(frozen=True, slots=True)
class ImportSourceFilesResult:
    batch_id: EntityId
    imported: tuple[ImportedSourceFileResult, ...]
    failed: tuple[FailedSourceFileResult, ...]
```

Result invariants: `imported` preserves successful input order; `failed` preserves failed input order; a source ID must not appear in both collections; No result contains a basename or path. No result contains basename, source path, hash value, storage path or raw exception.

## Exact application-service API

PR-008 defines exactly two public application operations:

```python
def create_upload_batch(
    command: CreateUploadBatchCommand,
    *,
    unit_of_work_factory: UnitOfWorkFactory,
) -> UploadBatch:
    ...
```

Required behavior: construct an immutable `UploadBatch`; force status to `UploadBatchStatus.NEW`; start one SQLCipher Unit of Work; call `upload_batches.add(batch)`; explicitly commit; return the persisted batch; create no audit event; expose no source path or PII in failures. Duplicate batch IDs or numbers must fail with a sanitized persistence/application error. Do not silently replace an existing batch.

```python
def import_source_files(
    command: ImportSourceFilesCommand,
    *,
    storage: StoragePort,
    media_decoder: MediaDecoderPort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> ImportSourceFilesResult:
    ...
```

No additional public PR-008 application service operations are authorized. Internal private helpers are permitted only when they preserve this contract.

## Exact repository API

```python
class UploadBatchRepository(Protocol):
    def add(self, batch: UploadBatch) -> None: ...

    def get(self, batch_id: EntityId) -> UploadBatch | None: ...

    def update(self, batch: UploadBatch) -> None: ...

    def get_by_number(self, number: BatchNumber) -> UploadBatch | None: ...
```

`get_by_number` is required to enforce unique batch numbers without exposing an arbitrary filter API. Rules: no delete method; no raw SQL; no caller-defined sorting; no pagination; `update` must validate canonical payload and projections; an update may only replace the immutable batch row with a new valid batch instance whose ID, number, created time and creator are unchanged; PR-008 may only append one successfully imported source ID; status transitions remain outside PR-008.

```python
class SourceFileRepository(Protocol):
    def add(self, source_file: SourceFile) -> None: ...

    def get(self, source_file_id: EntityId) -> SourceFile | None: ...

    def list_by_batch(
        self,
        batch_id: EntityId,
    ) -> tuple[SourceFile, ...]: ...

    def list_by_sha256(
        self,
        sha256: Sha256Digest,
    ) -> tuple[SourceFile, ...]: ...

    def list_compatible_perceptual_hashes(
        self,
        algorithm_id: str,
        algorithm_version: int,
        bit_width: int,
    ) -> tuple[SourceFile, ...]: ...
```

Rules: no update method; no delete method; ordering is ascending by `imported_at`, then `id`; canonical payload/projection validation occurs before returning rows; canonical payload and projection integrity must be validated before rows are returned; no `list_all`; no arbitrary filters; no caller-defined sorting; no pagination.

The existing `UnitOfWork` contract must gain exactly:

```python
upload_batches: UploadBatchRepository
source_files: SourceFileRepository
```

They must use the same SQLCipher connection and transaction as `stored_artifacts` and `audit_events`. No repository may open an independent connection or commit independently. If the implementation needs a factory port, define exactly:

```python
class UnitOfWorkFactory(Protocol):
    def unit_of_work(self) -> UnitOfWork: ...
```

The task must align this signature with the existing database adapter entry point rather than inventing a conflicting abstraction.

## Storage reuse contract

PR-008 must reuse the accepted PR-006 managed object store: encrypted managed objects only, AES-256-GCM envelope v1, `DIOSOBJ1` magic, immutable UUID-derived managed paths, object-first/database-second publication, SQLCipher authoritative expected-state records, no plaintext managed originals, no update or delete operation, no automatic orphan adoption and no automatic orphan deletion. Do not create human-readable managed object paths or a second original-file storage implementation. Do not place filenames, names, passport numbers, VINs, registrations or other PII in managed paths.

Every successfully validated original is published through the existing PR-006 port exactly as:

```python
stored_artifact = storage.publish_bytes(
    artifact_id=item.artifact_id,
    artifact_kind=ArtifactKind.ORIGINAL,
    plaintext=original_bytes,
    created_at=item.imported_at,
)
```

Binding rules: `ArtifactKind.ORIGINAL` is mandatory; the plaintext argument is the exact byte sequence read from `source_path`; no decoded, oriented, normalized, converted or recompressed bytes may be passed; `created_at` is exactly `item.imported_at`; the returned `StoredArtifactRecord` is inserted through `uow.stored_artifacts.add(stored_artifact)`; the returned artifact ID must equal `item.artifact_id`; any mismatch fails closed before inserting `SourceFile`; do not create a second storage port or a special original-file storage implementation.

The bytes registered as the original must be byte-for-byte identical to the bytes read from the selected input file. PR-008 may decode a separate in-memory representation only for media validation and perceptual hashing. Decoded or normalized bytes must never replace the stored original. No EXIF rewrite, orientation rewrite, metadata stripping, image correction, crop, compression or format conversion is authorized in PR-008.

## Persistence and v0004 migration contract

Add forward-only migration `v0004_source_file_import.py` with version `4` and name `source_file_import_pr008`. Migration ordering is append-only; v0001, v0002 and v0003 remain byte-for-byte unchanged; the v0004 checksum is independently asserted in tests; canonical payload and projection-integrity validation remain mandatory; all new tables remain in encrypted SQLCipher; no destructive migration, down migration or plaintext SQLite support is authorized.

Migration v0004 must create persistence for upload batches, ordered upload-batch source-file membership, source files, and required unique and lookup indexes. Upload batch constraints: unique batch ID; unique canonical batch number; status projection; UTC timestamp projection; canonical payload; projection-integrity validation. Source file constraints: unique source-file ID; unique `original_artifact_id`; foreign key to upload batch; foreign key to stored artifact; positive byte size; positive dimensions; allowed media type; allowed EXIF orientation; lowercase SHA-256 shape validation; perceptual algorithm/version/bit-width/hash projections; canonical payload; projection-integrity validation. Indexes at minimum: batch membership ordering lookup; SHA-256 lookup; compatible perceptual algorithm/version/bit-width lookup; imported-time deterministic ordering. Do not authorize database-level fuzzy-distance computation. Hamming distance is computed in application code over compatible candidate rows. Migration v0004 remains forward-only and append-only.


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

## Exact file-reading and basename behavior

1. `source_path` is accepted as `pathlib.Path`.
2. The service derives the basename only as `source_path.name`.
3. The complete path is never persisted.
4. The path is never included in logs, errors, audit events, verifier output or test reports.
5. File bytes are read once into memory for the PR-008 import operation.
6. `SOURCE_READ_FAILED` covers file not found, permission denied, path is not a regular file, read failure, and file changes or disappears during the read boundary where detectable.
7. Raw operating-system exceptions are never exposed.
8. Empty files fail before decoding.
9. Basename validation occurs before reading image bytes where possible.
10. Basename validation failure produces `SOURCE_BASENAME_INVALID` and publishes no object.

## Exact media validation behavior

The extension map is exact:

- `.jpg`, `.jpeg` -> `JPEG`
- `.png` -> `PNG`
- `.heic`, `.heif` -> `HEIF`

Rules: the suffix used for validation is `source_path.suffix.lower()`; only ASCII extension tokens are recognized; the stored `SourceBasename` preserves the original basename exactly; no filename case normalization is persisted; `.jpg`, `.JPG`, `.JpG` map to `JPEG`; `.jpeg` variants map to `JPEG`; `.png` variants map to `PNG`; `.heic` and `.heif` variants map to `HEIF`; a file with no suffix produces `UNSUPPORTED_EXTENSION`; a basename ending only with `.` produces `UNSUPPORTED_EXTENSION`; multiple suffixes use only the final suffix; unsupported extension fails before decoding and before storage publication; unsupported extension produces `UNSUPPORTED_EXTENSION`; supported extension plus corrupt or undecodable content produces `DECODE_FAILED`; content that decodes to no supported media type produces `UNSUPPORTED_FORMAT`; supported extension whose decoded supported type differs from the extension imports successfully with `EXTENSION_CONTENT_MISMATCH`; detected content type is authoritative for `SourceFile.detected_media_type`; validation occurs before encrypted object publication; no failed validation publishes an object. Do not trust extension alone.

## Exact duplicate and perceptual-hash contract

Compute SHA-256 over unchanged original bytes. SHA-256 is exact-content identity evidence only and is not a cryptographic storage-integrity substitute in the application result. An exact duplicate warns only; it does not overwrite, mutate, delete, merge batches, silently suppress the new import or automatically resolve operator review. It does not automatically delete any source file and does not automatically merge any source file or batch.

Use the deterministic PR-008 perceptual-hash algorithm: algorithm ID `DHASH64`; version `1`; bit width `64`; use the primary decoded image/frame only; apply EXIF orientation in memory for hashing only; convert alpha images by compositing onto an opaque white background; convert to 8-bit grayscale; resize to exactly `9x8` using a fixed `LANCZOS` resampler; compare each pixel with the pixel immediately to its right; bit is 1 when left luminance is greater than right luminance, otherwise 0; bits are stored row-major as a 64-bit value; persist exactly 16 lowercase hexadecimal characters; distance is Hamming distance using XOR and population count; warning threshold is distance <= 8; final real-photo threshold validation remains local pilot evidence; a later threshold or preparation change requires a new algorithm version.



The persistent algorithm version must not depend on unspecified decoder or resampler behavior. ADR-022 and this task require canonical synthetic golden vectors generated at test runtime. Vector A horizontal ascending gradient has logical image size before hashing `9 x 8`, 8-bit grayscale rows `0, 16, 32, 48, 64, 80, 96, 112, 128`, no EXIF orientation and no alpha; expected DHASH64 is `0000000000000000` because no left pixel is greater than its right neighbor. Vector B horizontal descending gradient has logical image size `9 x 8`, every row `128, 112, 96, 80, 64, 48, 32, 16, 0`; expected DHASH64 is `ffffffffffffffff`. Vector C alternating rows uses even rows from Vector A and odd rows from Vector B; expected DHASH64 is `00ff00ff00ff00ff`.

Tests must prove the vectors produce the exact lowercase values above; Ubuntu and Windows produce identical values; serialization preserves leading zeroes; Hamming distance between A and B is `64`; Hamming distance between A and C is `32`; threshold `8` does not classify those pairs as perceptually similar; a generated one-bit-different hash has distance `1` and does produce a perceptual warning; changing decoder, grayscale conversion, EXIF behavior, alpha compositing or resampler behavior in a way that changes these vectors requires `algorithm_version = 2`. For test vectors already exactly `9 x 8`, the implementation must not introduce platform-dependent resizing differences. At least one generated larger synthetic image must exercise the fixed LANCZOS resize path, and its expected hash is frozen after the dependency is selected and verified on Ubuntu and Windows. Do not commit real or document-like images.
Comparison scope: compare against all persisted compatible `SourceFile` records, not only the current batch; incompatible algorithm/version/bit-width records are excluded; exact same SHA-256 pair produces `EXACT_DUPLICATE`; do not also produce a perceptual warning for the same exact pair; deterministic warning order is exact warnings by related source-file ID, then perceptual warnings by distance and related source-file ID, then extension/content warning last.

For every source item, the service uses this exact duplicate lookup order: validate basename and extension; read exact original bytes; decode and validate supported content; compute SHA-256 and DHASH64; open a read-only or uncommitted SQLCipher Unit of Work to load prior duplicate candidates; query exact candidates by SHA-256; query perceptual candidates only by compatible algorithm/version/bit width; exclude every row whose `id == item.source_file_id`; exclude every row whose `original_artifact_id == item.artifact_id`; close or roll back the lookup Unit of Work without writing; construct deterministic warnings; publish encrypted object; open the write Unit of Work; re-check that no `SourceFile` with the same source ID or artifact ID now exists; insert storage record, source file, batch update and audit event; commit. Because the first MVP permits only one active application session, PR-008 does not implement a multi-writer conflict-resolution protocol. Nevertheless, the write transaction must reject duplicate IDs and must never classify the new row as its own duplicate. A lookup must consider only rows that existed before the current `SourceFile` insertion. Do not insert the current `SourceFile` before duplicate warnings are calculated.

Warning deduplication for one imported source: emit at most one `EXACT_DUPLICATE` warning per related source ID; emit at most one `PERCEPTUAL_SIMILARITY` warning per related source ID; when a related source is an exact SHA-256 duplicate, do not emit a perceptual warning for the same related source; do not collapse different related source IDs into one warning; extension mismatch produces at most one warning; warning ordering remains exact duplicate warnings by related source ID, perceptual warnings by distance then related source ID, and extension mismatch last.

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

Exact construction requirement:

```python
audit_event = AuditEvent(
    event_id=item.audit_event_id,
    occurred_at=item.imported_at,
    actor=command.actor,
    action_code=AuditAction.ARTIFACT_REGISTERED,
    subject_type=AuditSubjectType.STORED_ARTIFACT,
    subject_id=item.artifact_id,
    field_key=None,
    before=AuditValueSummary(
        classification=AuditValueClassification.ABSENT,
        display_value=None,
        was_present=False,
    ),
    after=AuditValueSummary(
        classification=AuditValueClassification.NON_SENSITIVE,
        display_value="ORIGINAL",
        was_present=True,
    ),
    reason_code=AuditReasonCode("SOURCE_FILE_IMPORT"),
    correlation_id=command.batch_id,
)
```

Use the accepted existing types `AuditAction`, `AuditSubjectType`, `AuditValueClassification`, `AuditEvent`, `AuditReasonCode` and `AuditValueSummary`. Use the actual existing constructors of the accepted PR-007 domain implementation. The implementation must not add alternative audit value-object APIs, new audit factories, new class methods, new audit enum values or free-text audit fields merely to match this pseudocode. Binding rules: `event_id` is exactly `item.audit_event_id`; one successful source import creates exactly one event; the event is added through `uow.audit_events.add(audit_event)`; it shares the same write transaction as stored artifact, SourceFile and batch update; audit add failure rolls back all database writes; failed storage publication creates no audit event; failed media validation creates no audit event; duplicate warnings create no extra audit events; extension mismatch creates no extra audit event; event `repr()` and failures remain PII-safe.

Do not emit audit events for failed imports, duplicate warnings, extension mismatch warnings or `UploadBatch` creation. `UploadBatch` is not added to `AuditSubjectType` in PR-008. Do not change existing audit enums or the PR-007 privacy model. Low-level repositories must not infer or automatically emit audit events.

## Dependency boundary

The domain and application contracts must depend on a local `MediaDecoderPort`, not directly on a third-party package. The immutable decoded result contract is exact:

```python
@dataclass(frozen=True, slots=True)
class DecodedMedia:
    media_type: SourceMediaType
    width: int
    height: int
    exif_orientation: int | None
    grayscale_pixels: bytes
    grayscale_width: int
    grayscale_height: int
```

The decoder must not return arbitrary original metadata. The exact port is:

```python
class MediaDecoderPort(Protocol):
    def decode_for_import(
        self,
        *,
        content: bytes,
    ) -> DecodedMedia:
        ...
```

Rules: receives bytes, not a filesystem path; makes no network call; performs no runtime download; returns the primary frame only; returns the detected content media type; retains only EXIF orientation 1-8; returns no GPS, filename, source path, camera metadata or arbitrary metadata mapping; returns sufficient deterministic pixels for PR-008 dHash only; failures map to controlled import errors; no raw decoder exception escapes. If the final implementation uses a different internal pixel representation, the public port must remain semantically equivalent and this exact task must be updated before implementation. Do not leave an unrestricted `Any`, third-party image object or arbitrary metadata dictionary in the public application port.

No external perceptual-hash library is required. The algorithm must be implemented against the selected local decoder adapter. The PR-008 description must include an explicit dependency decision section containing package name, exact pinned version, direct/transitive role, Python 3.12 support, Windows AMD64 wheel or packaging evidence, JPEG support, PNG support, HEIF/HEIC support, offline installation evidence, offline runtime evidence, license, redistribution obligations, native binary components, security/update considerations, confirmation of no telemetry and confirmation of no runtime downloads. If HEIF requires a second package or native codec, list and pin it explicitly. If the evidence is not available, PR-008 must stop as blocked. If no compliant HEIF solution is available, PR-008 must report itself blocked and must not silently omit HEIF, must not treat HEIF as a future enhancement, must not add runtime downloads, must not call an external service and must not change the accepted media scope. Runtime codec downloads are not authorized.

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

## Exact PR-008 verifier contract

The future file `scripts/verify_pr008_import.py` must use generated synthetic non-document images only; accept no real-document paths; make no network calls; create its own temporary encrypted storage and SQLCipher database; print no source basename, full path, SHA-256, perceptual hash, database path, storage path, key material, synthetic pixel contents or raw exceptions.

Required command:

```bash
uv run python scripts/verify_pr008_import.py
```

Exit codes: `0` means every required check passed; `1` means product verification failure; `2` means unsupported or inconclusive runner environment. Exit code `2` must not be used for deterministic product failures. Required safe output lines are exactly allowlisted records in this shape: `PR008_VERIFY schema_version=4`, `PR008_VERIFY migration_v0004=PASS`, `PR008_VERIFY encrypted_storage=PASS`, `PR008_VERIFY byte_identity=PASS`, `PR008_VERIFY media_jpeg=PASS`, `PR008_VERIFY media_png=PASS`, `PR008_VERIFY media_heif=PASS`, `PR008_VERIFY extension_casefold=PASS`, `PR008_VERIFY extension_mismatch_warning=PASS`, `PR008_VERIFY unsupported_extension=PASS`, `PR008_VERIFY exact_duplicate=PASS`, `PR008_VERIFY perceptual_duplicate=PASS`, `PR008_VERIFY no_self_match=PASS`, `PR008_VERIFY warning_order=PASS`, `PR008_VERIFY partial_success=PASS`, `PR008_VERIFY audit_atomicity=PASS`, `PR008_VERIFY orphan_reconciliation=PASS`, `PR008_VERIFY privacy=PASS`, `PR008_VERIFY result=PASS`. For an unsupported environment, the final line may be `PR008_VERIFY result=INCONCLUSIVE code=<CONTROLLED_CODE>`. Allowed environment-inconclusive codes are exactly `WINDOWS_SQLCIPHER_UNAVAILABLE`, `HEIF_DECODER_UNAVAILABLE`, `UNSUPPORTED_PLATFORM`. No uncontrolled message is allowed.

Mandatory verifier checks: schema version exactly 4; migration v0004 checksum matches the implementation constant; v0001/v0002/v0003 checksums remain unchanged; ordinary SQLite cannot read the production database; originals decrypt byte-for-byte; no plaintext managed original exists; JPEG, PNG and HEIF content validation; extension case folding; extension/content mismatch warning and successful import; unsupported extension fails before storage publication; corrupt content fails before storage publication; exact duplicate warning; perceptual warning at distance `<= 8`; no perceptual warning above threshold; no self-match; deterministic warning order; per-file partial success; previous successful imports survive a later failed item; audit event is exactly the accepted event; audit event and database records roll back together; object-first database-failure orphan is reported by read-only reconciliation; no automatic orphan adoption or deletion; no forbidden value appears in output. The verifier must not claim acceptance of real documents or real-photo perceptual quality.

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

## Implementation evidence (Codex PR-008 branch)

Status: IMPLEMENTED AND IN REVIEW, NOT ACCEPTED.

Implementation base: `67d2233d2f907bd65eeedcb287a50e00db3d2e6f`.
Implementation branch: `codex-uj32ni`.

Selected decoder dependencies are `Pillow==12.3.0` and `pi-heif==1.4.0`. Pillow is used for JPEG/PNG decoding, in-memory EXIF orientation handling, alpha compositing, grayscale conversion and fixed LANCZOS resizing. pi-heif is used only for decode-side HEIF/HEIC opener registration at the adapter boundary. No OpenCV, NumPy, imagehash, cloud image libraries, runtime codec installers, telemetry or runtime downloads are introduced by PR-008 code.

Licensing evidence recorded for review: Pillow uses the MIT-CMU license. pi-heif includes Python/package code and native binary wheel components; bundled libheif components are LGPL-covered and have redistribution obligations. PR-033 Windows packaging must ship required third-party license notices, keep LGPL components replaceable as separately distributed native components, avoid statically merging LGPL binary code into proprietary application code, and handle corresponding source/notice obligations for any LGPL component modifications. PR-008 does not modify third-party native libraries.

Gate 2 remains not accepted. PR-009 and later remain UNAUTHORIZED. No OCR is authorized or implemented by PR-008.
