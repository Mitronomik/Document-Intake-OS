# PR-013 — Merge confirmed document sides

**Status:** CONTRACT ACCEPTED
**Production implementation:** AUTHORIZED AND IN REVIEW
**Human acceptance:** NOT GRANTED
**Merge:** NOT AUTHORIZED
**ADR:** [ADR-027](../decisions/ADR-027-document-side-composition-v1.md) (ACCEPTED)

The Product owner directly accepted ADR-027 and this contract and authorized
implementation on 2026-08-02 without a separate lifecycle-only pull request.
The implementation base is `bb25421b4b1630a45359a0b82f949e2b044eaafa`.
Earlier proposal and unauthorized statements remain historical evidence only.

## 1. Lifecycle, base, and authorization

PR-012 is completed and human accepted through PR #32 at reviewed head
`9a6af1b72a064c47c66989b1e7dbc78d72768957` and merge commit
`6a0f0df1e2d43e67395d4dee9415b6703181ab41`. Schema version 8 is current;
migrations v0001 through v0008 are frozen. This contract correction implements
no production code and creates no migration.

A future implementation may start only after a separate Product-owner decision
accepts ADR-027, accepts this contract, explicitly authorizes PR-013, and names
the documentation PR's actual merge commit as its exact base. M3 is IN PROGRESS;
Gate 2 is NOT ACCEPTED; PR-014 and later are UNAUTHORIZED; Q-021 remains
DEFERRED.

## 2. Objective and accepted upstream boundaries

Create one immutable prepared JPEG from exactly two explicitly ordered,
operator-confirmed sides. Layout is explicit `VERTICAL` or `HORIZONTAL`, and
margin and gap are explicit. Originals, PR-010 recipes, PR-012 region sets, and
all historical selections remain unchanged.

PR-013 V1 is create-once and one-to-one. One `DocumentSideComposition` has
exactly one `DocumentSideCompositionVersion`, and one
`DocumentSideCompositionVersion` has exactly one
`PreparedCompositionArtifact`. The version name is retained as an immutable
persistence and possible future compatibility boundary, but it has no
revision-chain semantics in V1.

The future service reuses these accepted production boundaries exactly:

- `UnitOfWorkFactory`
- `StoragePort`
- `GeometryDecoderPort`
- `GeometryRendererPort`
- `PreparedJpegEncoderPort`

The existing PR-011 encoder operation remains:

```python
encode_prepared_jpeg(
    raster: UncompressedRgbRaster,
    *,
    pipeline: PreparedJpegPipelineVersion,
) -> EncodedPreparedJpeg
```

PR-013 passes the final composed `UncompressedRgbRaster` to that operation
exactly once. No prepared JPEG is composition input. No intermediate JPEG is created.
The accepted encoder contract is unchanged, no additional JPEG encoder is
introduced, and the composition component never performs final JPEG encoding.

PR-013 changes none of the accepted PR-011 constants, quality sequence, resize
sequence, metadata rules, or the 1,992,294-byte limit.

## 3. Exact side reference and authoritative validation

```python
@dataclass(frozen=True, slots=True)
class DocumentSideReference:
    region_set_version_id: EntityId
    source_file_id: EntityId
    region_id: EntityId
    geometry_recipe_version_id: EntityId
```

The exact validation for each side is:

1. `region_set_version_id` exists.
2. The region set belongs to `source_file_id`.
3. The region set is an immutable operator-confirmed PR-012 version.
4. The set contains `region_id`.
5. That member references exactly `geometry_recipe_version_id`.
6. The geometry recipe version exists.
7. The recipe belongs to the same `source_file_id`.
8. The recipe belongs to the same `region_id`.
9. The original encrypted artifact exists.
10. Original artifact integrity validation succeeds.

The sides may use different source files; the same source file through different
confirmed regions; or the same region-set version when both selected regions
are members. Duplicate lineage is equality of `(source_file_id, region_id)` and
is rejected.

Only explicit `side_1` and `side_2` define order. Region-set order, filename,
import order, database order, classifier output, and identifier sorting never
define composition order.

## 4. Exact command and result

```python
@dataclass(frozen=True, slots=True)
class CreateDocumentSideCompositionCommand:
    composition_id: EntityId
    composition_version_id: EntityId
    side_1: DocumentSideReference
    side_2: DocumentSideReference
    layout: DocumentSideCompositionLayout
    outer_margin_px: int
    inter_side_gap_px: int
    prepared_artifact_id: EntityId
    stored_artifact_id: EntityId
    audit_event_id: EntityId
    created_at: datetime
    actor: ActorRef
    correlation_id: EntityId


@dataclass(frozen=True, slots=True)
class CreateDocumentSideCompositionResult:
    composition_version: DocumentSideCompositionVersion
    artifact: PreparedCompositionArtifact
```

`created_at` is required timezone-aware UTC. `correlation_id` and `layout` are
required. `outer_margin_px` and `inter_side_gap_px` are integer but not boolean,
with inclusive bounds `0..256`. The following record identifiers are pairwise
distinct: `composition_id`, `composition_version_id`, `prepared_artifact_id`,
`stored_artifact_id`, and `audit_event_id`.

The command does not accept caller-selected pipeline identities, caller-selected
output-contract identities, raster bytes, JPEG bytes, source paths, storage
paths, filenames, hashes, dimensions, JPEG quality, or resize percentage.

The result contains only the two persisted immutable domain records. It contains
no image or source bytes, filename, filesystem or managed storage path, or
encryption material.

## 5. Exact fixed pipeline identities

The four boundaries remain distinct:

1. Each side is replayed through the accepted PR-010 geometry pipeline.
2. Normalization/canvas work uses the PR-013 composition pipeline.
3. Final encoding uses the accepted PR-011 JPEG pipeline.
4. The result satisfies the accepted PR-011 output contract.

```text
DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID =
PILLOW_DOCUMENT_SIDE_COMPOSITION_BICUBIC

DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION = 1
```

```python
@dataclass(frozen=True, slots=True)
class DocumentSideCompositionPipelineVersion:
    pipeline_id: str = DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID
    version: int = DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION
```

Composition normalization uses exactly `Image.Resampling.BICUBIC`; there is no
implicit or platform-dependent default. Composition identity belongs to the
immutable composition version. Final JPEG pipeline and output-contract identity
belong to the prepared composition artifact. The caller chooses none of them.

Any Pillow or implementation change that changes deterministic output requires
compatibility analysis, synthetic golden-file comparison, an explicit
pipeline-version decision, and a version bump when compatibility is not
preserved.

## 6. Pure composition port

PR-013 proposes exactly one new port:

```python
class DocumentSideComposerPort(Protocol):
    def compose(
        self,
        *,
        side_1: UncompressedRgbRaster,
        side_2: UncompressedRgbRaster,
        layout: DocumentSideCompositionLayout,
        outer_margin_px: int,
        inter_side_gap_px: int,
        pipeline: DocumentSideCompositionPipelineVersion,
    ) -> UncompressedRgbRaster: ...
```

The composer accepts uncompressed RGB rasters only and performs normalization
and fresh canvas composition. It never reads storage, opens a Unit of Work,
encodes JPEG, publishes an artifact, writes an audit event, or accesses a
network.

No second geometry decoder, geometry renderer, storage port, JPEG encoder, Unit
of Work, or audit abstraction is permitted.

## 7. Exact deterministic normalization

- `VERTICAL`: side 1 is above side 2.
- `HORIZONTAL`: side 1 is left of side 2.

There is no inferred layout and no hidden production default.

Integer half-up is exactly:

```text
(2 * numerator + denominator) // (2 * denominator)
```

Floating-point rounding is forbidden.

For `VERTICAL`:

```text
target_width = min(side_1.width, side_2.width)
calculated_height =
    half_up(original_height * target_width / original_width)
```

Only a wider side is downscaled; the other is unchanged. No side is upscaled.

For `HORIZONTAL`:

```text
target_height = min(side_1.height, side_2.height)
calculated_width =
    half_up(original_width * target_height / original_height)
```

Only a taller side is downscaled; the other is unchanged. No side is upscaled.

If any calculated normalized width or height is less than one pixel, return
`COMPOSITION_RENDER_FAILED`. Zero is not clamped to one.

All normalization uses exactly `Image.Resampling.BICUBIC`. The canvas is a
fresh opaque-white RGB raster. For vertical composition:

```text
canvas_width = target_width + 2 * outer_margin_px
canvas_height = normalized_side_1_height + normalized_side_2_height
                + inter_side_gap_px + 2 * outer_margin_px
side_1_origin = (outer_margin_px, outer_margin_px)
side_2_origin = (
    outer_margin_px,
    outer_margin_px + normalized_side_1_height + inter_side_gap_px,
)
```

For horizontal composition:

```text
canvas_width = normalized_side_1_width + normalized_side_2_width
               + inter_side_gap_px + 2 * outer_margin_px
canvas_height = target_height + 2 * outer_margin_px
side_1_origin = (outer_margin_px, outer_margin_px)
side_2_origin = (
    outer_margin_px + normalized_side_1_width + inter_side_gap_px,
    outer_margin_px,
)
```

## 8. Margin, gap, and final JPEG semantics

`outer_margin_px` and `inter_side_gap_px` apply exactly to the fresh
uncompressed composition raster before final JPEG encoding.

1. The composer creates the requested margin and gap exactly.
2. The existing PR-011 encoder may resize the entire raster below 100%.
3. Side content, margins, and gap are scaled together.
4. Final width and height come from `EncodedPreparedJpeg`.
5. Final `resize_percent` records the PR-011 encoder decision.
6. Pure composer tests assert exact pre-encoder margin and gap pixels.
7. End-to-end JPEG tests assert proportional whole-image resizing.
8. Final JPEG margins need not equal requested pixels when
   `resize_percent < 100`.

Final dimensions, byte size, SHA-256, `jpeg_quality`, and `resize_percent` are
persisted on `PreparedCompositionArtifact` consistently with PR-011. They are
never placed in logs, audit events, or verifier stdout.

## 9. Exact immutable domain records

```python
@dataclass(frozen=True, slots=True)
class DocumentSideComposition:
    id: EntityId


@dataclass(frozen=True, slots=True)
class DocumentSideCompositionVersion:
    id: EntityId
    composition_id: EntityId

    side_1_region_set_version_id: EntityId
    side_1_source_file_id: EntityId
    side_1_region_id: EntityId
    side_1_geometry_recipe_version_id: EntityId

    side_2_region_set_version_id: EntityId
    side_2_source_file_id: EntityId
    side_2_region_id: EntityId
    side_2_geometry_recipe_version_id: EntityId

    layout: DocumentSideCompositionLayout
    outer_margin_px: int
    inter_side_gap_px: int

    composition_pipeline_id: str
    composition_pipeline_version: int

    jpeg_pipeline_id: str
    jpeg_pipeline_version: int

    output_contract_id: str
    output_contract_version: int

    created_at: datetime
    created_by: ActorRef
    correlation_id: EntityId


@dataclass(frozen=True, slots=True)
class PreparedCompositionArtifact:
    id: EntityId
    composition_version_id: EntityId
    stored_artifact_id: EntityId

    pipeline_id: str
    pipeline_version: int
    output_contract_id: str
    output_contract_version: int

    media_type: PreparedMediaType
    color_space: ColorSpace

    width: int
    height: int
    byte_size: int
    sha256: Sha256Digest
    jpeg_quality: int
    resize_percent: int

    created_at: datetime
    created_by: ActorRef
```

The aggregate has no mutable current-version pointer. The immutable composition
version uses exactly:

```text
composition_pipeline_id = DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID
composition_pipeline_version = DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION
jpeg_pipeline_id = PREPARED_JPEG_PIPELINE_ID
jpeg_pipeline_version = PREPARED_JPEG_PIPELINE_VERSION
output_contract_id = PREPARED_JPEG_OUTPUT_CONTRACT_ID
output_contract_version = PREPARED_JPEG_OUTPUT_CONTRACT_VERSION
```

The prepared artifact uses exactly:

```text
pipeline_id = PREPARED_JPEG_PIPELINE_ID
pipeline_version = PREPARED_JPEG_PIPELINE_VERSION
output_contract_id = PREPARED_JPEG_OUTPUT_CONTRACT_ID
output_contract_version = PREPARED_JPEG_OUTPUT_CONTRACT_VERSION
media_type = PreparedMediaType.JPEG
color_space = ColorSpace.SRGB
```

`PreparedCompositionArtifact` is a self-contained immutable projection and must
agree with both `DocumentSideCompositionVersion` and `EncodedPreparedJpeg`:

```text
artifact.pipeline_id
    == composition_version.jpeg_pipeline_id
    == encoded.pipeline_id
    == PREPARED_JPEG_PIPELINE_ID
artifact.pipeline_version
    == composition_version.jpeg_pipeline_version
    == encoded.pipeline_version
    == PREPARED_JPEG_PIPELINE_VERSION
artifact.output_contract_id
    == composition_version.output_contract_id
    == encoded.output_contract_id
    == PREPARED_JPEG_OUTPUT_CONTRACT_ID
artifact.output_contract_version
    == composition_version.output_contract_version
    == encoded.output_contract_version
    == PREPARED_JPEG_OUTPUT_CONTRACT_VERSION
```

Any disagreement before persistence returns `JPEG_ENCODING_FAILED`; a
disagreement found while loading persisted records returns
`PERSISTED_DATA_INVALID`.

Changing side 1 identity, side 2 identity, side order, layout, outer margin,
inter-side gap, composition pipeline identity, JPEG pipeline identity, or
output-contract identity creates a completely new composition aggregate, new
composition version, and new prepared artifact. The operation always requires
new `composition_id`, `composition_version_id`, `prepared_artifact_id`,
`stored_artifact_id`, and `audit_event_id`; it never reuses an existing
`composition_id`.

The V1 model contains no `revision`, `superseded_composition_version_id`,
`latest_composition_version_id`, or `current_composition_version_id`. The V1
repository exposes no `get_latest`, `set_latest`, `replace`, `update`,
`supersede`, or `delete`. There is no revision sequence or latest-version query
in V1.

Future schema constraints are exact:

```text
DocumentSideComposition.id: PRIMARY KEY
DocumentSideCompositionVersion.id: PRIMARY KEY
DocumentSideCompositionVersion.composition_id:
    FOREIGN KEY to DocumentSideComposition.id, UNIQUE, NOT NULL
PreparedCompositionArtifact.id: PRIMARY KEY
PreparedCompositionArtifact.composition_version_id:
    FOREIGN KEY to DocumentSideCompositionVersion.id, UNIQUE, NOT NULL
```

They enforce one aggregate to exactly one version and one version to exactly
one prepared artifact.

## 10. Exact ordered natural key and persistence port

```text
side_1.region_set_version_id
side_1.source_file_id
side_1.region_id
side_1.geometry_recipe_version_id

side_2.region_set_version_id
side_2.source_file_id
side_2.region_id
side_2.geometry_recipe_version_id

layout
outer_margin_px
inter_side_gap_px

DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID
DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION

PREPARED_JPEG_PIPELINE_ID
PREPARED_JPEG_PIPELINE_VERSION

PREPARED_JPEG_OUTPUT_CONTRACT_ID
PREPARED_JPEG_OUTPUT_CONTRACT_VERSION
```

This key is ordered. Swapping the sides creates a different key. An exact
existing key returns `COMPOSITION_ALREADY_EXISTS` before encrypted publication,
and no additional encrypted object is published.

Before publication, all five supplied IDs and the complete key are checked. An
existing `composition_id`, `composition_version_id`, `prepared_artifact_id`,
`stored_artifact_id`, or `audit_event_id` returns `IDENTITY_CONFLICT`. Different
supplied IDs with an existing ordered natural key return
`COMPOSITION_ALREADY_EXISTS`. The preflight does not replace database unique
constraints.

The future `UnitOfWork` may gain exactly one repository named
`document_side_compositions`. It supports create, read, and exact-natural-key
lookup only. It supports no `get_latest`, `set_latest`, `replace`, `update`,
`supersede`, `delete`, or mutable-current operation. Canonical payload and
projected fields must agree; in-scope corruption fails closed.

A future implementation may propose a forward-only
`v0009_document_side_composition` migration from schema 8 to 9. This contract
correction creates no migration and does not modify frozen migrations v0001
through v0008.

## 11. Exact typed audit

Future production enums would add:

```python
AuditAction.DOCUMENT_SIDE_COMPOSITION_CREATED
AuditSubjectType.DOCUMENT_SIDE_COMPOSITION
```

The future event is exactly:

```python
AuditEvent(
    event_id=command.audit_event_id,
    occurred_at=command.created_at,
    actor=command.actor,
    action_code=AuditAction.DOCUMENT_SIDE_COMPOSITION_CREATED,
    subject_type=AuditSubjectType.DOCUMENT_SIDE_COMPOSITION,
    subject_id=command.composition_id,
    field_key=None,
    before=None,
    after=None,
    reason_code=None,
    correlation_id=command.correlation_id,
)
```

No alternate audit model, arbitrary dictionary, string action code, or string
subject type is permitted. Layout, dimensions, margins, gaps, hashes, quality,
resize percentage, paths, and image data are absent from the event.

## 12. Exact transaction and publication order

### Read-phase snapshot and authoritative revalidation

Before rendering, each side retains an immutable snapshot of its exact
`DocumentRegionSetVersion`, selected `DocumentRegionSetMember`,
`ImageGeometryRecipe`, `SourceFile`, and original `StoredArtifactRecord`. It
preserves and validates:

```text
region_set_version.region_set_version_id == side.region_set_version_id
region_set_version.source_file_id == side.source_file_id
member.region_id == side.region_id
member.geometry_recipe_version_id == side.geometry_recipe_version_id
recipe.recipe_version_id == side.geometry_recipe_version_id
recipe.source_file_id == side.source_file_id
recipe.region_id == side.region_id
source.id == side.source_file_id
original.artifact_id == source.original_artifact_id
original.artifact_kind is ArtifactKind.ORIGINAL
original.plaintext_length == source.byte_size
original.plaintext_sha256 == source.sha256.value
```

Shared sources, sets, or originals may deduplicate physical reads, but two
explicit side-specific references are retained and validated; one side is never
inferred from the other.

After encoding, the write Unit of Work re-reads by exact identifier, for each
side, the `DocumentRegionSetVersion`, exact selected
`DocumentRegionSetMember`, `ImageGeometryRecipe`, `SourceFile`, and original
`StoredArtifactRecord`. It compares every record with its read-phase snapshot,
repeats every ownership and identity relationship, and repeats all original
stored-metadata validation. A missing, changed, inconsistent, corrupt, or
differently related record returns `PERSISTED_DATA_INVALID`; a repository
access exception returns `PERSISTENCE_FAILED`. No second decode, geometry
replay, composition, or JPEG encoding occurs in the write phase.

### Exact storage publication

The accepted `StoragePort` is called exactly as follows:

```python
record = storage.publish_bytes(
    artifact_id=command.stored_artifact_id,
    artifact_kind=ArtifactKind.PREPARED_JPEG,
    plaintext=encoded.jpeg_bytes,
    created_at=command.created_at,
)
```

No new composition-specific kind is introduced, and the composition JPEG does
not use `ArtifactKind.PREPARED_DOCUMENT` or `ArtifactKind.EXPORT_ARTIFACT`.
Before any database row is added, validate:

```python
record.artifact_id == command.stored_artifact_id
record.artifact_kind is ArtifactKind.PREPARED_JPEG
record.object_generation == 1
record.plaintext_length == encoded.byte_size
record.plaintext_sha256 == encoded.sha256.value
record.created_at == command.created_at
```

The returned `StoredArtifactRecord` constructor remains authoritative for
`ciphertext_sha256`, `key_version`, `storage_format_version`, and timezone-aware
`created_at`; PR-013 does not duplicate those checks. A publication exception
or returned-record mismatch returns `STORAGE_PUBLICATION_FAILED`. The exact
validated returned record is inserted directly with
`uow.stored_artifacts.add(record)` and is not reconstructed or replaced with
independently derived metadata.

### Final authoritative order

1. Validate command types, ranges, required values and pairwise record-ID distinctness.
2. Open the read Unit of Work.
3. Load the exact region-set version, selected member, geometry recipe, source file and original `StoredArtifactRecord` for each side.
4. Validate every side relationship and original stored-metadata invariant.
5. Close the read Unit of Work and retain immutable read snapshots only.
6. Read and integrity-check the original encrypted bytes through `StoragePort`.
7. Decode each required original independently.
8. Replay each selected geometry recipe independently through the accepted PR-010 pipeline.
9. Create two fresh `UncompressedRgbRaster` values.
10. Compose the rasters through `DocumentSideComposerPort`.
11. Encode the final composed raster exactly once through `PreparedJpegEncoderPort`.
12. Validate `EncodedPreparedJpeg` identities and metadata.
13. Open the write Unit of Work.
14. Re-read both complete persisted side contexts by exact identifiers.
15. Compare both write-phase contexts with the read-phase snapshots and repeat every relationship and stored-metadata invariant.
16. Check all five supplied record identities for conflicts.
17. Check the complete ordered natural key, including composition pipeline, JPEG pipeline and output-contract identities.
18. Publish `encoded.jpeg_bytes` exactly once through `StoragePort.publish_bytes` using `ArtifactKind.PREPARED_JPEG`.
19. Validate the returned `StoredArtifactRecord` against the command and encoded result.
20. Construct the new `DocumentSideComposition` exactly once.
21. Construct the one and only `DocumentSideCompositionVersion` for that aggregate.
22. Construct the one and only `PreparedCompositionArtifact` for that version and validate cross-record pipeline/output identities.
23. Construct the typed `AuditEvent`.
24. Add the validated returned `StoredArtifactRecord`.
25. Add the new composition aggregate.
26. Add the immutable composition version.
27. Add the prepared composition artifact.
28. Add the typed audit event.
29. Commit exactly once.
30. Exit the write Unit of Work successfully.
31. Return `CreateDocumentSideCompositionResult` only after successful Unit of Work exit.

Failures before step 18 publish no output object. Any failure after physical
publication succeeds but before SQLCipher commit completes may leave one
unreferenced encrypted object, including returned-record mismatch, any insert
failure, a natural-key race, or commit failure. The Unit of Work rolls back and
leaves no partial rows; the service never adopts or deletes the object
automatically; existing read-only orphan reconciliation may report it; and no
path, hash, size, or image data is exposed. The appropriate result remains
`STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_CONFLICT`, `PERSISTENCE_FAILED`, or
`COMMIT_FAILED`, rather than a single generic code.

## 13. Controlled failure contract

The future service uses the exact controlled codes below and privacy-safe
generic messages:

```text
COMPOSITION_INPUT_COUNT_INVALID
COMPOSITION_INPUT_DUPLICATE
COMPOSITION_ORDER_INVALID
COMPOSITION_LAYOUT_INVALID
COMPOSITION_MARGIN_INVALID
COMPOSITION_GAP_INVALID
REGION_NOT_FOUND
REGION_SET_NOT_FOUND
REGION_SELECTION_INVALID
GEOMETRY_RECIPE_NOT_FOUND
GEOMETRY_RECIPE_INVALID
SOURCE_FILE_NOT_FOUND
ORIGINAL_ARTIFACT_NOT_FOUND
ORIGINAL_BYTES_INVALID
SOURCE_DIMENSIONS_MISMATCH
GEOMETRY_RENDER_FAILED
COMPOSITION_RENDER_FAILED
JPEG_ENCODING_FAILED
SIZE_LIMIT_UNREACHABLE
IDENTITY_CONFLICT
COMPOSITION_ALREADY_EXISTS
STORAGE_PUBLICATION_FAILED
PERSISTENCE_CONFLICT
PERSISTENCE_FAILED
COMMIT_FAILED
PERSISTED_DATA_INVALID
```

No failure leaks bytes, paths, filenames, hashes, coordinates, dimensions,
quality, resize percentage, OCR/MRZ, personal data, keys, SQL, or raw exception
text.

## 14. Required future tests

Synthetic-only tests must prove:

- exact command and result fields and byte/path-free application DTOs;
- each side's region-set/member/recipe/source/original validation;
- two-source, same-source/two-region, and same-set/two-region cases;
- duplicate `(source_file_id, region_id)` rejection and explicit side order;
- both layouts, exact integer half-up calculation, no upscaling, and exact
  `Image.Resampling.BICUBIC` normalization;
- `COMPOSITION_RENDER_FAILED` when a calculated dimension is below one, without
  clamping;
- exact pre-encoder margin/gap pixels and proportional whole-raster resizing;
- one `PreparedJpegEncoderPort.encode_prepared_jpeg` call and no prepared or
  intermediate JPEG input;
- final metadata copied from `EncodedPreparedJpeg`, including `jpeg_quality` and
  `resize_percent`;
- exact typed `AuditEvent` and absence of forbidden audit data;
- exact immutable persistence fields, ordered natural-key uniqueness, and
  create/read/exact-key-only repository behavior;
- the 31-step operation order, publication exactly once, rollback, and
  read-only orphan reconciliation;
- no migration exists in this documentation PR and no production source file
  differs from the initial PR #33 head;
- full accepted PR-010, PR-011, and PR-012 regression coverage remains intact.

Pure composer tests inspect the uncompressed raster. End-to-end JPEG tests
inspect `EncodedPreparedJpeg` metadata and prove whole-image scaling when
`resize_percent < 100`.

## 15. Non-goals and privacy

This proposal does not implement domain classes, DTOs, ports, application
services, a composer, persistence, schema version 9, audit enum values, UI,
OCR/MRZ/barcode, side detection, document classification, terminal defaults,
snapshot/export/Excel work, installer, backup/restore, Konversta/browser
automation, cloud processing, telemetry, analytics, Q-021, or PR-014 and later.

Real documents, personal data, terminal templates, private reports, local paths,
keys, and private databases remain prohibited in Git, Codex, CI, logs, and
reports. Runtime composition remains offline and originals/history remain
immutable.

## Authoritative lifecycle boundary

```text
ADR-026: ACCEPTED
PR-012: COMPLETED AND HUMAN ACCEPTED
CURRENT SCHEMA VERSION: 8
MIGRATIONS V0001 THROUGH V0008: FROZEN
ADR-027: PROPOSED
PR-013 CONTRACT: PROPOSED FOR HUMAN REVIEW
PR-013 PRODUCTION IMPLEMENTATION: UNAUTHORIZED
PR-014 AND LATER: UNAUTHORIZED
M3: IN PROGRESS
GATE 2: NOT ACCEPTED
Q-021: DEFERRED
PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE
PRODUCTION POLICY_ID: NOT ASSIGNED
PRODUCTION POLICY_VERSION: NOT ASSIGNED
AUTOMATIC QUALITY-BASED DOCUMENT BLOCKING: NOT ACTIVE
AUTOMATIC PRODUCTION RETAKE_REQUIRED: NOT ACTIVE
```

The preceding proposal/authorization statements are historical evidence.

Current state: ADR-027 is ACCEPTED; this contract is ACCEPTED; production
implementation is AUTHORIZED AND IN REVIEW. Human acceptance is not granted,
merge is not authorized, and PR-014 and later remain unauthorized.
