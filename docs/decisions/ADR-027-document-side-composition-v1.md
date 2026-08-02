# ADR-027 — Document-side composition V1

**Status:** ACCEPTED
**Scope:** PR-013 accepted contract and production implementation review
**Authorization:** PRODUCTION IMPLEMENTATION AUTHORIZED AND IN REVIEW

The Product owner directly accepted ADR-027 and the PR-013 contract and
authorized production implementation on 2026-08-02 without a separate
lifecycle-only pull request. PR-013 human acceptance is not granted and merge
is not authorized. Statements below describing this ADR as proposed or
implementation as unauthorized are preserved historical evidence from PR #33.

## Context and decision

A two-sided logical document must produce one prepared JPEG without changing the
accepted PR-010 geometry replay, PR-012 confirmed-region, or PR-011 JPEG
preparation contracts. V1 proposes an immutable
`DocumentSideComposition` aggregate, an immutable
`DocumentSideCompositionVersion`, and one immutable
`PreparedCompositionArtifact`. Single-sided documents continue to use the
accepted PR-011/PR-012 path and do not receive a synthetic composition.

PR-013 V1 is create-once and one-to-one. One `DocumentSideComposition` has
exactly one `DocumentSideCompositionVersion`, and one
`DocumentSideCompositionVersion` has exactly one
`PreparedCompositionArtifact`. The version name is retained as an immutable
persistence and possible future compatibility boundary, but it has no
revision-chain semantics in V1.

The future PR-013 service reuses the existing `UnitOfWorkFactory`, `StoragePort`,
`GeometryDecoderPort`, `GeometryRendererPort`, and `PreparedJpegEncoderPort`.
It introduces exactly one new pure composition port. It does not introduce a
second decoder, renderer, storage port, JPEG encoder, Unit of Work, or audit
abstraction.

Historical PR #33 state: this ADR was proposed, defined no production
implementation, and created no migration. The current authorized implementation
creates candidate migration v0009 without changing the accepted contract.

## Exact side identity and validation

```python
@dataclass(frozen=True, slots=True)
class DocumentSideReference:
    region_set_version_id: EntityId
    source_file_id: EntityId
    region_id: EntityId
    geometry_recipe_version_id: EntityId
```

These are the exact four fields. A side does not carry a separate recipe-family
identity or a caller-supplied numeric recipe revision.

For each side, the service must validate all of the following against accepted
PR-012 and PR-010 persistence:

1. `region_set_version_id` exists.
2. The region set belongs to `source_file_id`.
3. The region set is an immutable operator-confirmed PR-012 version.
4. The region set contains the supplied `region_id`.
5. That member references exactly the supplied `geometry_recipe_version_id`.
6. The geometry recipe version exists.
7. The recipe belongs to the same `source_file_id`.
8. The recipe belongs to the same `region_id`.
9. The original encrypted artifact exists.
10. Original artifact integrity validation succeeds.

The sides may reference different source files, the same source file through
different confirmed regions, or the same region-set version when it contains
both selected regions. The same region lineage must not be used twice.
Duplicate lineage is equality of the ordered pair `(source_file_id, region_id)`.

Order is defined only by explicit `side_1` and `side_2`. It is never inferred
from region-set order, filename, import order, database order, source/region/
recipe identifier sorting, or any classifier.

## Exact command and result

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

`created_at` must be timezone-aware UTC and `correlation_id` is required.
`layout` is explicit. Margin and gap must each be an integer but not a boolean,
with inclusive bounds `0..256`. The record identifiers
`composition_id`, `composition_version_id`, `prepared_artifact_id`,
`stored_artifact_id`, and `audit_event_id` are pairwise distinct.

The command accepts no raster bytes, JPEG bytes, source or storage paths,
filenames, hashes, dimensions, JPEG quality, resize percentage, or pipeline and
output-contract identity choices. Those identities are fixed domain constants.

The result contains no image bytes, source bytes, filenames, filesystem paths,
managed storage paths, or encryption material. Persisted artifact metadata may
contain the final dimensions, byte size, SHA-256, JPEG quality, and resize
percentage consistent with PR-011. Those values remain prohibited in logs,
audit events, and verifier stdout.

## Four distinct versioned boundaries

The contract distinguishes these four identities:

1. PR-010 geometry replay: each selected recipe's accepted
   `PILLOW_QUAD_BICUBIC`, version `1` pipeline.
2. PR-013 composition: normalization and canvas creation under the fixed
   composition pipeline below.
3. PR-011 final JPEG encoding: the unchanged
   `PREPARED_JPEG_PIPELINE_ID` and `PREPARED_JPEG_PIPELINE_VERSION`.
4. PR-011 output: the unchanged `PREPARED_JPEG_OUTPUT_CONTRACT_ID` and
   `PREPARED_JPEG_OUTPUT_CONTRACT_VERSION`.

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

Normalization uses exactly `Image.Resampling.BICUBIC`; implicit
platform-dependent resampling defaults are forbidden. The composition pipeline
identity belongs to the immutable composition version. The final JPEG pipeline
and output-contract identity belong to the prepared composition artifact. The
caller chooses none of these identities.

A Pillow or implementation change that changes deterministic output requires
compatibility analysis, synthetic golden-file comparison, an explicit
pipeline-version decision, and a version bump when compatibility is not
preserved.

PR-013 does not change `PREPARED_JPEG_PIPELINE_ID`,
`PREPARED_JPEG_PIPELINE_VERSION`, `PREPARED_JPEG_OUTPUT_CONTRACT_ID`, or
`PREPARED_JPEG_OUTPUT_CONTRACT_VERSION`. It does not change the accepted PR-011
quality sequence, resize sequence, or 1,992,294-byte limit.

## Pure composition port and final encoding

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

The composer accepts uncompressed RGB rasters only. It performs normalization
and fresh opaque-white canvas composition. It never reads storage, opens a Unit
of Work, encodes JPEG, publishes an artifact, writes an audit event, or accesses
a network.

PR-013 reuses the existing `PreparedJpegEncoderPort` and its exact accepted
operation:

```python
encode_prepared_jpeg(
    raster: UncompressedRgbRaster,
    *,
    pipeline: PreparedJpegPipelineVersion,
) -> EncodedPreparedJpeg
```

The final composed `UncompressedRgbRaster` is passed to
`encode_prepared_jpeg` exactly once. No prepared JPEG is used as composition
input and no intermediate JPEG is created. The existing PR-011 encoder contract
remains unchanged. PR-013 must not introduce another JPEG encoder, and the
composition component must not perform final JPEG encoding.

## Exact normalization and canvas mechanics

`DocumentSideCompositionLayout` contains exactly `VERTICAL` and `HORIZONTAL`:

- `VERTICAL`: side 1 is above side 2.
- `HORIZONTAL`: side 1 is left of side 2.

Q-006 remains unresolved; there is no hidden production default.

All half-up dimension calculations use positive integer arithmetic only:

```text
(2 * numerator + denominator) // (2 * denominator)
```

Floating-point rounding is forbidden.

For `VERTICAL`:

```text
target_width = min(side_1.width, side_2.width)
normalized_height =
    half_up(original_height * target_width / original_width)
```

Only a wider side is downscaled. A side already at `target_width` is unchanged.
No side is upscaled. If a calculated normalized width or height is less than
one pixel, return `COMPOSITION_RENDER_FAILED`; do not clamp zero to one.

The fresh opaque-white RGB canvas has:

```text
width = target_width + 2 * outer_margin_px
height = side_1_normalized_height + side_2_normalized_height
         + inter_side_gap_px + 2 * outer_margin_px
side_1_origin = (outer_margin_px, outer_margin_px)
side_2_origin = (
    outer_margin_px,
    outer_margin_px + side_1_normalized_height + inter_side_gap_px,
)
```

For `HORIZONTAL`:

```text
target_height = min(side_1.height, side_2.height)
normalized_width =
    half_up(original_width * target_height / original_height)
```

Only a taller side is downscaled. A side already at `target_height` is
unchanged. No side is upscaled. If a calculated normalized width or height is
less than one pixel, return `COMPOSITION_RENDER_FAILED`; do not clamp zero to
one.

The fresh opaque-white RGB canvas has:

```text
width = side_1_normalized_width + side_2_normalized_width
        + inter_side_gap_px + 2 * outer_margin_px
height = target_height + 2 * outer_margin_px
side_1_origin = (outer_margin_px, outer_margin_px)
side_2_origin = (
    outer_margin_px + side_1_normalized_width + inter_side_gap_px,
    outer_margin_px,
)
```

## Margin and gap semantics

`outer_margin_px` and `inter_side_gap_px` apply exactly to the fresh
uncompressed composition raster before final JPEG encoding.

1. The composer creates the requested margin and gap exactly.
2. The final encoder may resize the complete composition raster below 100%.
3. Side content, margins, and gap are scaled together.
4. Final width and height come from `EncodedPreparedJpeg`.
5. Final `resize_percent` records the PR-011 encoder decision.
6. Pure composer tests assert exact pre-encoder margin and gap pixels.
7. End-to-end JPEG tests assert proportional whole-image resizing.
8. Final JPEG margins are not guaranteed to equal the requested pixel count
   when `resize_percent < 100`.

## Exact immutable records

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

`DocumentSideComposition` has no mutable current-version pointer. The immutable
composition version has these fixed identities:

```text
composition_pipeline_id = DOCUMENT_SIDE_COMPOSITION_PIPELINE_ID
composition_pipeline_version = DOCUMENT_SIDE_COMPOSITION_PIPELINE_VERSION
jpeg_pipeline_id = PREPARED_JPEG_PIPELINE_ID
jpeg_pipeline_version = PREPARED_JPEG_PIPELINE_VERSION
output_contract_id = PREPARED_JPEG_OUTPUT_CONTRACT_ID
output_contract_version = PREPARED_JPEG_OUTPUT_CONTRACT_VERSION
```

`PreparedCompositionArtifact` has exactly these fixed identities:

```text
pipeline_id = PREPARED_JPEG_PIPELINE_ID
pipeline_version = PREPARED_JPEG_PIPELINE_VERSION
output_contract_id = PREPARED_JPEG_OUTPUT_CONTRACT_ID
output_contract_version = PREPARED_JPEG_OUTPUT_CONTRACT_VERSION
media_type = PreparedMediaType.JPEG
color_space = ColorSpace.SRGB
```

`PreparedCompositionArtifact` is a self-contained immutable artifact projection.
Before persistence, the following equalities must hold:

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

Any pre-persistence disagreement returns `JPEG_ENCODING_FAILED`; disagreement
found when loading persisted records returns `PERSISTED_DATA_INVALID`.

Changing either side identity, side order, layout, outer margin, inter-side
gap, composition pipeline identity, JPEG pipeline identity, or output-contract
identity creates a new composition aggregate, new composition version, and new
prepared artifact. Every such operation requires new `composition_id`,
`composition_version_id`, `prepared_artifact_id`, `stored_artifact_id`, and
`audit_event_id`; an existing `composition_id` must never be reused.

The V1 model contains no `revision`, `superseded_composition_version_id`,
`latest_composition_version_id`, or `current_composition_version_id`. The V1
repository exposes no `get_latest`, `set_latest`, `replace`, `update`,
`supersede`, or `delete` operation. There is no revision sequence and no latest
version query in V1.

Future schema constraints enforce the cardinality exactly:

```text
DocumentSideComposition.id: PRIMARY KEY
DocumentSideCompositionVersion.id: PRIMARY KEY
DocumentSideCompositionVersion.composition_id:
    FOREIGN KEY to DocumentSideComposition.id, UNIQUE, NOT NULL
PreparedCompositionArtifact.id: PRIMARY KEY
PreparedCompositionArtifact.composition_version_id:
    FOREIGN KEY to DocumentSideCompositionVersion.id, UNIQUE, NOT NULL
```

These constraints enforce one aggregate to exactly one version and one version
to exactly one prepared artifact.

## Ordered natural key and repository

The exact ordered natural key is:

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

Order is significant. Swapping side 1 and side 2 produces a different natural
key. An exact existing natural key returns `COMPOSITION_ALREADY_EXISTS` before
encrypted object publication. Another encrypted object must not be published
for an existing key.

Before publication, all five supplied record IDs are checked. An existing
`composition_id`, `composition_version_id`, `prepared_artifact_id`,
`stored_artifact_id`, or `audit_event_id` returns `IDENTITY_CONFLICT`. A
different set of supplied IDs with an existing complete ordered natural key
returns `COMPOSITION_ALREADY_EXISTS`. Database uniqueness constraints remain
authoritative against concurrent races.

The future Unit of Work may be extended with exactly one repository named
`document_side_compositions`. It exposes create, read, and exact-natural-key
lookup operations only. It exposes no `get_latest`, `set_latest`, `replace`,
`update`, `supersede`, `delete`, or mutable-current operation.

## Typed audit event

PR-013 proposes the future enum additions:

```python
AuditAction.DOCUMENT_SIDE_COMPOSITION_CREATED
AuditSubjectType.DOCUMENT_SIDE_COMPOSITION
```

The exact future event is:

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

No other audit model, arbitrary audit dictionary, string action code, or string
subject type is introduced. Layout, dimensions, margins, gaps, hashes, quality,
resize percentage, paths, and image data are absent from the audit event.

## Exact read snapshot and write-phase revalidation

Before rendering, the service loads and retains an immutable read snapshot for
each side containing the exact `DocumentRegionSetVersion`, selected
`DocumentRegionSetMember`, `ImageGeometryRecipe`, `SourceFile`, and original
`StoredArtifactRecord`. Each snapshot preserves and validates:

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

Physical repository reads may be deduplicated when both sides share a source,
region set, or original artifact, but the service retains and validates two
explicit side-specific references and never infers one side from the other.

After encoding, the write Unit of Work re-reads, by exact identifier, each
side's `DocumentRegionSetVersion`, selected `DocumentRegionSetMember`,
`ImageGeometryRecipe`, `SourceFile`, and original `StoredArtifactRecord`. For
each side it locates the exact member, compares every re-read record with the
corresponding read-phase snapshot, repeats every ownership and identity
relationship, and repeats original stored-metadata validation. A missing,
changed, inconsistent, corrupt, or differently related record returns
`PERSISTED_DATA_INVALID`; a repository access exception returns
`PERSISTENCE_FAILED`. The write phase does not decode, replay geometry, compose,
or encode again; it validates persisted authority, not the produced raster.

After this revalidation and before publication, the service checks all five
supplied record identities and the complete ordered natural key. This preflight
does not replace database uniqueness constraints; a concurrent constraint
failure after publication returns `PERSISTENCE_CONFLICT`.

## Exact storage publication contract

The future service publishes exactly once through the accepted port:

```python
record = storage.publish_bytes(
    artifact_id=command.stored_artifact_id,
    artifact_kind=ArtifactKind.PREPARED_JPEG,
    plaintext=encoded.jpeg_bytes,
    created_at=command.created_at,
)
```

The composition JPEG uses exactly `ArtifactKind.PREPARED_JPEG`; it introduces
no composition-specific kind and never uses `ArtifactKind.PREPARED_DOCUMENT` or
`ArtifactKind.EXPORT_ARTIFACT`. Before adding any database row, validate:

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
`created_at`; the service does not duplicate that validation. A publication
exception or returned-record mismatch returns `STORAGE_PUBLICATION_FAILED`.
The exact validated returned record is inserted directly with
`uow.stored_artifacts.add(record)`; it is not reconstructed, and no storage
metadata is independently derived for persistence.

## Exact operation and publication order

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
unreferenced encrypted object, including a returned-record mismatch, any row
insertion failure, a natural-key constraint race, or commit failure. The Unit of
Work rolls back so no partial rows remain; the service neither adopts nor
deletes the object automatically; existing read-only orphan reconciliation may
report it; and no path, hash, size, or image data is exposed. The appropriate
controlled code remains `STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_CONFLICT`,
`PERSISTENCE_FAILED`, or `COMMIT_FAILED`, rather than one generic code.

## Controlled failures

The proposed controlled codes are:

- `COMPOSITION_INPUT_COUNT_INVALID`
- `COMPOSITION_INPUT_DUPLICATE`
- `COMPOSITION_ORDER_INVALID`
- `COMPOSITION_LAYOUT_INVALID`
- `COMPOSITION_MARGIN_INVALID`
- `COMPOSITION_GAP_INVALID`
- `REGION_NOT_FOUND`
- `REGION_SET_NOT_FOUND`
- `REGION_SELECTION_INVALID`
- `GEOMETRY_RECIPE_NOT_FOUND`
- `GEOMETRY_RECIPE_INVALID`
- `SOURCE_FILE_NOT_FOUND`
- `ORIGINAL_ARTIFACT_NOT_FOUND`
- `ORIGINAL_BYTES_INVALID`
- `SOURCE_DIMENSIONS_MISMATCH`
- `GEOMETRY_RENDER_FAILED`
- `COMPOSITION_RENDER_FAILED`
- `JPEG_ENCODING_FAILED`
- `SIZE_LIMIT_UNREACHABLE`
- `IDENTITY_CONFLICT`
- `COMPOSITION_ALREADY_EXISTS`
- `STORAGE_PUBLICATION_FAILED`
- `PERSISTENCE_CONFLICT`
- `PERSISTENCE_FAILED`
- `COMMIT_FAILED`
- `PERSISTED_DATA_INVALID`

Errors, logs, audit records, and verifier output expose no raw bytes, paths,
filenames, hashes, coordinates, dimensions, quality, resize percentage, OCR,
MRZ, personal data, encryption material, SQL, or raw exception text.

## Persistence and compatibility boundary

A future implementation may propose a forward-only schema 8-to-9 migration for
these immutable records. This documentation correction does not create
`v0009_document_side_composition` or any other migration. Migrations v0001
through v0008 remain frozen and unchanged.

Canonical payloads and projected columns must agree. Foreign keys bind the
composition to accepted PR-012 and stored-artifact records. Database constraints
must enforce the ordered natural key and immutable create-only behavior.

## Non-goals and authorization boundary

Non-goals include OCR, MRZ, barcode processing, side detection, front/back
classification, inferred order or layout, terminal defaults, final UI,
person/vehicle cards, snapshot/export/Excel work, installer, backup/restore,
Konversta, browser automation, cloud processing, telemetry, analytics, PR-009
quality-policy activation, Q-021 resolution, and PR-014 or later work.

Real documents and personal data remain prohibited in Git, Codex, CI, logs,
and reports. All runtime work remains local/offline. Originals and historical
records remain immutable.

The preceding proposal/authorization statements are historical evidence.

Current state: ADR-027 is ACCEPTED; the PR-013 contract is ACCEPTED; PR-013
production implementation is AUTHORIZED AND IN REVIEW. Human acceptance is not
granted and merge is not authorized. PR-014 and later remain unauthorized.
