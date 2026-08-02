# ADR-027 — Document-side composition V1

**Status:** PROPOSED
**Scope:** PR-013 contract proposal only
**Authorization:** PRODUCTION IMPLEMENTATION UNAUTHORIZED

## Context and decision

A two-sided logical document must produce one prepared JPEG. V1 proposes an
immutable `DocumentSideComposition` aggregate whose immutable
`DocumentSideCompositionVersion` records an explicit ordered pair of confirmed
PR-012 region lineages and their accepted immutable PR-010 geometry-recipe
versions. Inputs may be two sources or two confirmed regions of one source.
Single-sided documents remain on the PR-011/PR-012 prepared-artifact path and
do not receive a synthetic one-side composition.

The command and result carry identifiers and controlled metadata only: no
raster/JPEG bytes, paths, or filenames. Exactly two confirmed inputs are
required. Caller-supplied raster bytes, JPEG bytes, filesystem paths,
unconfirmed selections, missing recipes, duplicate region lineage, fewer or
more than two sides, inferred order, front/back classification, and inferred
layout are rejected.

## Explicit order and layout

The command supplies `side_1` then `side_2`; order is never inferred from a
filename, import order, source/region/recipe identifier, classifier, or row
order. `DocumentSideCompositionLayout` contains exactly `VERTICAL` and
`HORIZONTAL`:

- `VERTICAL`: side 1 is above side 2.
- `HORIZONTAL`: side 1 is left of side 2.

Q-006 remains unresolved. Layout has no hidden production default and must be
explicit. Terminal or UI defaults require a separate accepted decision; V1 has
no terminal-specific layout policy. Background is opaque white RGB; transparent
output is forbidden. `outer_margin_px` and `inter_side_gap_px` are explicit
integers with no defaults and each must satisfy `0 <= value <= 256`.

## Deterministic raster mechanics

Each selected recipe is independently replayed from verified immutable original
bytes into a fresh uncompressed RGB raster. An existing prepared JPEG is never
decoded as input; two compressed JPEGs are never composed; no intermediate JPEG
is encoded. Aspect ratio is preserved and neither side is upscaled.

For `VERTICAL`, target width is `min(w1, w2)`. Only an input wider than target
is downscaled. Its height is `round_half_up(original_height * target_width /
original_width)`, with exact integer arithmetic `(2*numerator + denominator) //
(2*denominator)` for positive dimensions; the already-target-width raster is
unchanged. Resulting widths are equal. Canvas width is `target_width +
2*outer_margin_px`; height is `h1' + h2' + inter_side_gap_px +
2*outer_margin_px`. Side 1 begins at `(margin, margin)` and side 2 at `(margin,
margin + h1' + gap)`.

For `HORIZONTAL`, target height is `min(h1, h2)`. Only an input taller than
target is downscaled. Its width uses the same accepted PR-011 half-up rule:
`round_half_up(original_width * target_height / original_height)`. Resulting
heights are equal. Canvas width is `w1' + w2' + inter_side_gap_px +
2*outer_margin_px`; height is `target_height + 2*outer_margin_px`. Side 1 begins
at `(margin, margin)` and side 2 at `(margin + w1' + gap, margin)`. All canvas
pixels are initialized opaque white RGB; there is no additional alignment
choice or padding between normalized sides beyond the explicit gap and margin.

One fresh composition raster is passed exactly once to the accepted reusable
PR-011 `PreparedJpegEncoder`. The selected candidate is validated exactly once.
The output remains deterministic non-progressive RGB/sRGB-interpreted JPEG,
4:4:4, without alpha, EXIF, ICC, XMP, IPTC, comment, filename, path, or source
metadata and is at most **1,992,294 bytes**. Accepted PR-011 encoder settings and
rounding are unchanged; composition occurs before final JPEG compression.

## Immutable persistence and idempotency

The aggregate records composition and version identities; ordered side region
and recipe-version identities; layout, margin, gap, fixed white background;
composition pipeline identity/version; output contract identity/version;
encrypted stored-artifact reference; immutable `PreparedCompositionArtifact`;
actor; timezone-aware creation time; and correlation identifier. It is
append-only: no update, delete, replace, or mutable “latest” row.

The create-once natural key is the ordered side-1 region and recipe version,
ordered side-2 region and recipe version, layout, margin, gap, composition
pipeline identity/version, and output contract identity/version. Order is
significant; swapping sides is a different key. An exact existing key returns
`COMPOSITION_ALREADY_EXISTS` before publication and publishes nothing.

A future forward-only `v0009_document_side_composition` migration would advance
schema 8 to 9. This documentation PR creates no migration. V0001 through v0008
remain byte-for-byte frozen; a v0009 checksum is frozen only after future
implementation acceptance.

## Reused boundaries and operation order

PR-013 must reuse immutable original storage, deterministic PR-010 replay,
PR-012 region identity/validation, the PR-011 uncompressed-RGB encoder,
encrypted immutable filesystem publication, SQLCipher Unit of Work,
privacy-safe audit, and read-only orphan reconciliation. It must not change
those semantics, the size limit, or region identity; introduce parallel or
plaintext storage; or use cloud/network processing.

The exact order is: (1) source-independent validation; (2) pairwise caller-ID
validation; (3) open read-only UoW; (4) load/validate regions; (5) load/validate
recipes; (6) load sources/original artifacts; (7) close read UoW without commit;
(8) read/verify originals; (9) replay both recipes independently; (10) obtain
fresh RGB rasters; (11) scale; (12) compose; (13) call final encoder once; (14)
validate selected candidate; (15) open one write UoW; (16) re-read/revalidate
all references; (17) recheck caller identities; (18) preflight natural key;
(19) publish encrypted JPEG once; (20) insert stored-artifact metadata; (21)
insert immutable composition records; (22) insert audit; (23) commit once; (24)
exit UoW successfully and return a byte-free result.

Validation/render/encoding failure occurs before publication. Storage failure
creates no rows. Database failure before publication creates no object. Any
post-publication persistence/commit failure rolls back rows. Filesystem and
SQLCipher are not one atomic transaction: a late database conflict leaves only
an unreferenced encrypted orphan, visible solely to read-only reconciliation,
with no automatic adoption or deletion, and returns `PERSISTENCE_CONFLICT`.

## Controlled errors

All errors expose only the code and controlled generic message:

| Code | Exact meaning |
|---|---|
| `COMPOSITION_INPUT_COUNT_INVALID` | input count is not exactly two |
| `COMPOSITION_INPUT_DUPLICATE` | both sides use one region lineage |
| `COMPOSITION_ORDER_INVALID` | ordered side fields are absent/invalid |
| `COMPOSITION_LAYOUT_INVALID` | layout is not an enum member |
| `COMPOSITION_MARGIN_INVALID` | margin is not an integer in 0..256 |
| `COMPOSITION_GAP_INVALID` | gap is not an integer in 0..256 |
| `REGION_NOT_FOUND` / `REGION_SET_NOT_FOUND` | authoritative region/reference is absent |
| `REGION_SELECTION_INVALID` | region is unconfirmed, inconsistent, or invalid |
| `GEOMETRY_RECIPE_NOT_FOUND` | referenced recipe version is absent |
| `GEOMETRY_RECIPE_INVALID` | recipe does not belong to/qualify for its region |
| `SOURCE_FILE_NOT_FOUND` / `ORIGINAL_ARTIFACT_NOT_FOUND` | authoritative source/reference is absent |
| `ORIGINAL_BYTES_INVALID` | immutable bytes fail integrity/decode validation |
| `SOURCE_DIMENSIONS_MISMATCH` | verified dimensions disagree with authority |
| `GEOMETRY_RENDER_FAILED` | accepted replay cannot produce one side raster |
| `COMPOSITION_RENDER_FAILED` | scaling/canvas/paste cannot satisfy this contract |
| `JPEG_ENCODING_FAILED` | accepted encoder fails generically |
| `SIZE_LIMIT_UNREACHABLE` | no accepted final candidate is within the limit |
| `IDENTITY_CONFLICT` | pairwise/caller identity conflicts with authority |
| `COMPOSITION_ALREADY_EXISTS` | exact natural key already exists |
| `STORAGE_PUBLICATION_FAILED` | encrypted publication failed |
| `PERSISTENCE_CONFLICT` | concurrent/late create-once conflict |
| `PERSISTENCE_FAILED` | controlled database operation failure |
| `COMMIT_FAILED` | sole write commit failed |
| `PERSISTED_DATA_INVALID` | persisted canonical payload/projection is invalid |

Existing names are reused only where their current meaning is exact (notably
PR-010/011 render, encoding and size codes and shared persistence concepts);
composition-specific codes do not redefine them.

## Audit, privacy, and non-goals

Future creation emits action `document_side_composition.created`, object type
`document_side_composition`, and outcome `success` through the existing
`AuditEvent` constructor. Controlled details may contain layout enum,
side-count=2, and pipeline/output-contract identifiers only. Composition rows
and audit commit in the same UoW. Audit/errors/logs/verifier/tests expose no
bytes, paths, filenames, hashes, coordinates, dimensions, byte size, quality,
resize percentage, layout pixel dimensions, OCR/document/personal values,
keys, SQL, or raw exceptions.

Non-goals: OCR, MRZ, barcode, side/front/back detection, automatic layout,
terminal defaults, final UI, upload UI, person/vehicle cards, verification,
snapshots, Excel/template/export work, installer, backup/restore, Konversta,
browser automation, cloud, telemetry, analytics, PR-009 quality blocking,
Q-021 resolution, and PR-014 or later.

Real documents and personal data remain prohibited in Git, Codex, CI, logs,
and reports. All work is local/offline and originals/history remain immutable.
This PROPOSED ADR does not authorize implementation.
