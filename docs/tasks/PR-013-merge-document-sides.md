# PR-013 — Merge confirmed document sides

**Status:** CONTRACT PROPOSED FOR HUMAN REVIEW
**Production implementation:** UNAUTHORIZED
**ADR:** [ADR-027](../decisions/ADR-027-document-side-composition-v1.md) (PROPOSED)

## 1. Lifecycle, base, and authorization

PR-012 is completed and human accepted through PR #32 at merge commit
`6a0f0df1e2d43e67395d4dee9415b6703181ab41`; schema 8 and migrations v0001
through v0008 are frozen. This contract PR does not authorize production code.
A future implementation may start only after a separate Product-owner decision
accepts ADR-027, accepts this contract, explicitly authorizes PR-013, and names
this documentation PR's actual merge commit as the exact implementation base.
That commit must be fetched and verified identical immediately before branching;
movement or a dirty tree requires stopping rather than rebasing.

M3 is IN PROGRESS; Gate 2 is NOT ACCEPTED; PR-014 and later are UNAUTHORIZED.

## 2. Objective, scope, upstream contracts

Create exactly one immutable prepared JPEG for exactly two explicitly ordered,
confirmed sides, using explicit `VERTICAL` or `HORIZONTAL` layout and explicit
margin/gap. Reuse immutable original storage, PR-010 geometry replay, PR-012
region identity and validation, PR-011 `PreparedJpegEncoder`, encrypted immutable
publication, SQLCipher UoW, `AuditEvent`, and read-only orphan reconciliation.
Originals, recipes, region sets, and selections remain unchanged.

Accepted upstream semantics—including `SOURCE_EFFECTIVE_PIXELS_V1`, geometry
replay, `PreparedJpegPipelineVersion.V1`, RGB output, non-progressive 4:4:4,
metadata removal, and `1_992_294` bytes—must not change.

## 3. Exact domain and application API

Future identifiers extend current conventions without renaming accepted APIs:

- `DocumentSideCompositionId`, `DocumentSideCompositionVersionId` value objects;
- `DocumentSideCompositionLayout(str, Enum)` with exactly `VERTICAL`, `HORIZONTAL`;
- immutable `DocumentSideReference(region_id, geometry_recipe_id,
  geometry_recipe_version)`;
- immutable `DocumentSideComposition`, `DocumentSideCompositionVersion`, and
  `PreparedCompositionArtifact` entities;
- `DocumentSideCompositionErrorCode` and `DocumentSideCompositionError`;
- frozen `CreateDocumentSideCompositionCommand(composition_id,
  composition_version_id, side_1, side_2, layout, outer_margin_px,
  inter_side_gap_px, composition_pipeline_id, composition_pipeline_version,
  output_contract_id, output_contract_version, prepared_artifact_id,
  stored_artifact_id, actor, created_at, correlation_id)`;
- frozen `CreateDocumentSideCompositionResult(composition_id,
  composition_version_id, prepared_artifact_id, stored_artifact_id, layout,
  created_at, correlation_id)` containing no bytes, hashes, filenames, or paths;
- `CreateDocumentSideCompositionService.create(command:
  CreateDocumentSideCompositionCommand) -> CreateDocumentSideCompositionResult`.

All public APIs are typed. IDs use existing UUID-backed conventions and are
pairwise distinct where their roles require it. `created_at` is timezone-aware
UTC. Commands are identifier-only and cannot accept raster/JPEG bytes or paths.

Required ports: existing `UnitOfWorkFactory`, source/stored-artifact, geometry,
region-set/selection, and audit repositories; new
`DocumentSideCompositionRepository`; existing immutable encrypted artifact
reader/publisher; existing geometry transformer; a `DocumentSideComposer` that
accepts only two `UncompressedRgbRaster` values and controlled layout settings;
and existing `PreparedJpegEncoder` called once.

## 4. Validation and exact deterministic algorithm

Validation occurs in this order: command type; exactly two sides; required
ordered roles; pairwise ID types/distinctness; duplicate lineage; enum type;
integer (not boolean) margin and gap in inclusive range 0..256; timezone-aware
timestamp; controlled actor/correlation/pipeline/output identities. No values
are inferred. Missing/invalid/unconfirmed authoritative data fails closed.

Order is significant and never derived from filename, import order, source,
region, recipe, classifier, or row order. `VERTICAL` means side 1 above side 2;
`HORIZONTAL` means side 1 left of side 2. Q-006 remains unresolved: there is no
hidden default and no terminal policy.

Decode each verified original and replay each selected accepted recipe
independently to a fresh uncompressed RGB raster. Never decode a prepared JPEG,
compose compressed JPEGs, create intermediate JPEGs, or use a prior candidate.
Preserve aspect ratio and never upscale.

For vertical, `tw=min(w1,w2)`. A wider raster alone is resized to
`(tw, half_up(h*tw/w))`; equal-width input is unchanged. Canvas is opaque white
RGB `(tw+2m, h1'+h2'+g+2m)`. Paste side 1 at `(m,m)` and side 2 at
`(m,m+h1'+g)`. For horizontal, `th=min(h1,h2)`; a taller raster alone becomes
`(half_up(w*th/h),th)`. Canvas is `(w1'+w2'+g+2m, th+2m)`; paste side 1 at
`(m,m)` and side 2 at `(m+w1'+g,m)`.

For positive integer numerator `n` and denominator `d`, half-up is exactly
`(2*n+d)//(2*d)`. It is the accepted PR-011 rule; no float rounding or second
convention is allowed. Dimensions, white margins, gap, alignment, pixel
positions, resampling configuration, and iteration order are fixed. Pass the
one composed raster to the accepted encoder exactly once and validate its exact
selected candidate. Output is RGB/sRGB-interpreted JPEG, no alpha/EXIF/ICC/XMP/
IPTC/comment/name/path, non-progressive 4:4:4, and `<=1_992_294`; `1_992_295`
is rejected. Unreachable size returns `SIZE_LIMIT_UNREACHABLE` and publishes
nothing.

## 5. Exact operation, transaction, and failure order

1. Source-independent command validation.
2. Pairwise caller-supplied identity validation.
3. Open read-only UoW.
4. Load and validate both confirmed region selections and region sets.
5. Load and validate both immutable geometry recipes and lineage membership.
6. Load both source-file and original stored-artifact references.
7. Exit read UoW without commit.
8. Read/decrypt/hash-verify immutable original bytes.
9. Decode and independently replay both recipes.
10. Produce two fresh uncompressed RGB rasters.
11. Deterministically normalize dimensions without upscaling.
12. Compose on fresh opaque white RGB.
13. Call final PR-011 encoder once.
14. Validate the selected candidate and contract.
15. Open one write UoW.
16. Re-read and revalidate every authoritative region, recipe, source, and artifact.
17. Recheck all caller IDs against authority.
18. Preflight the ordered natural key.
19. Publish the encrypted final JPEG exactly once.
20. Insert stored-artifact metadata.
21. Insert aggregate, version, and prepared composition artifact.
22. Insert privacy-safe audit event.
23. Commit exactly once.
24. Exit successfully, then return the byte-free result.

Steps 1–14 cannot publish or write. Read UoW never commits. Failure before
publication creates no object; publication failure creates no rows; any later
database failure rolls back all rows. The filesystem and SQLCipher transaction
are not atomic. A late uniqueness/commit conflict leaves the encrypted object
unreferenced for read-only orphan reconciliation only: never adopt or delete it
automatically, and return privacy-safe `PERSISTENCE_CONFLICT`. No result is
returned from inside the UoW.

## 6. Persistence, migration, and natural key

The immutable aggregate/version/artifact persist every field listed in ADR-027,
including ordered region/recipe identities, explicit settings, fixed background
contract, pipeline/output identities, encrypted stored-artifact reference,
actor, UTC timestamp, and correlation ID. Canonical payload and projected
columns must agree on read; inconsistency/corruption fails closed. Foreign keys
bind accepted existing records. Repository exposes create/get/find-by-natural-key
only; update/delete/replace/latest APIs are forbidden and database triggers
reject mutation.

Future migration name is exactly `v0009_document_side_composition`, forward-only
schema 8→9, including immutable tables, FKs, ordered natural-key uniqueness,
canonical validation, and mutation-rejection triggers. It must migrate populated
encrypted schema-8 databases without changing any row. V0001–v0008 remain
byte-for-byte unchanged. No migration is created here; future v0009 checksum is
recorded/frozen only after implementation acceptance.

Natural key: ordered side-1 region identity + recipe identity/version, ordered
side-2 region identity + recipe identity/version, layout, margin, gap,
composition pipeline identity/version, and output contract identity/version.
Swapping sides changes the key. An existing exact key yields
`COMPOSITION_ALREADY_EXISTS` before publication.

## 7. Controlled error contract

The exact codes and meanings are ADR-027's table and are mandatory:
`COMPOSITION_INPUT_COUNT_INVALID`, `COMPOSITION_INPUT_DUPLICATE`,
`COMPOSITION_ORDER_INVALID`, `COMPOSITION_LAYOUT_INVALID`,
`COMPOSITION_MARGIN_INVALID`, `COMPOSITION_GAP_INVALID`, `REGION_NOT_FOUND`,
`REGION_SET_NOT_FOUND`, `REGION_SELECTION_INVALID`,
`GEOMETRY_RECIPE_NOT_FOUND`, `GEOMETRY_RECIPE_INVALID`,
`SOURCE_FILE_NOT_FOUND`, `ORIGINAL_ARTIFACT_NOT_FOUND`, `ORIGINAL_BYTES_INVALID`,
`SOURCE_DIMENSIONS_MISMATCH`, `GEOMETRY_RENDER_FAILED`,
`COMPOSITION_RENDER_FAILED`, `JPEG_ENCODING_FAILED`, `SIZE_LIMIT_UNREACHABLE`,
`IDENTITY_CONFLICT`, `COMPOSITION_ALREADY_EXISTS`,
`STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_CONFLICT`, `PERSISTENCE_FAILED`,
`COMMIT_FAILED`, and `PERSISTED_DATA_INVALID`. Existing semantics are reused
only when exact; no conflicting duplicate is permitted. Messages never contain
raw exceptions or sensitive values.

## 8. Audit and privacy

Use existing `AuditEvent` with action `document_side_composition.created`,
object type `document_side_composition`, outcome `success`; details are limited
to layout, side count 2, and controlled pipeline/output identities. Audit and
composition rows share the one write UoW/commit.

Commands/results/errors/logs/audit/verifier/tests exclude image/raster bytes,
paths, filenames, hashes, coordinates, dimensions, byte size, quality, resize,
layout pixel sizes, OCR/MRZ/document/personal values, keys, SQL, and exception
text. Processing is offline/local. Originals and all history are immutable.
Real documents and personal data are prohibited in Git, Codex, CI, logs, and
reports.

## 9. Expected future files (implementation PR only)

Expected additions/edits are confined to existing layers: domain composition
module and exports/errors; application composition DTO/ports/service; image
pipeline composer; persistence repository/UoW/schema migration v0009; sanitized
Windows verifier and CI wiring; focused unit/integration/migration/privacy tests;
and lifecycle docs. No parallel storage, encoder, UoW, or audit architecture.

## 10. Required future automated tests

### Unit/domain/composition/output

Tests must prove exactly two inputs; duplicate rejection; significant order;
invalid layout/margin/gap rejection; aware timestamps; pairwise IDs; byte/path-
free DTOs; vertical/horizontal semantics; aspect preservation; no upscaling;
exact normalization, white background, margins, gap and pixel placement;
deterministic dimensions and byte-identical repeats; swapped-order output/key;
one final encoder call; no prepared-JPEG input or intermediate JPEG; valid RGB
JPEG; no alpha/EXIF/ICC/XMP/IPTC/name/path/comment; non-progressive 4:4:4;
boundary acceptance at 1,992,294 and rejection at 1,992,295; controlled
unreachable-size; and no publication after unsuccessful preparation.

### Integration/application/privacy

Tests must prove the 24-step order; read UoW no commit; write UoW one commit;
authoritative revalidation/natural-key preflight before publication; no object
on pre-publication DB failure; no rows on storage failure; rollback after
publication; late conflict leaves only reconcilable encrypted orphan; no
adoption/deletion; atomic audit+composition persistence; result only after UoW
exit and contains no bytes/paths. Controlled errors, audit and logs are scanned
for forbidden values. Verifier stdout uses an exact allowlist; stderr is empty
on success and supported inconclusive outcomes.

### Migration/encryption

Tests must prove schema 8→9 and populated encrypted migration; every schema-8
row preserved; v0001–v0008 unchanged; v0009 checksum not frozen until accepted;
immutable records and update/delete/replace rejection; natural-key uniqueness
and ordered significance; canonical projection validation; FK integrity;
encrypted close/reopen; wrong-key and ordinary SQLite rejection; corruption
fails closed.

CI must run architecture limits, repository policy, lock check/sync, Ruff format
and lint, exact workflow mypy, full pytest on Ubuntu and Windows, sanitized
Windows verifier, and sdist/wheel builds without weakening existing jobs.

## 11. Synthetic Windows verifier and manual smoke

The future verifier uses production SQLCipher and encrypted storage adapters and
only deterministic generated geometric RGB images—no text, faces, documents,
templates, or private evidence. It proves schema 9/v0009, encrypted storage,
two-source and same-source/two-region cases, both layouts, determinism/order,
RGB metadata-free size-compliant output, immutable originals/region/geometry
history, persistence/audit, encrypted reopen, wrong-key/ordinary-SQLite
rejection, rollback, orphan reconciliation, and privacy-safe output.

Manual synthetic smoke repeats both layouts and both source arrangements,
visually confirms exact colored geometric side order, margins/gap/white
background, compares repeat hashes locally, checks originals/history unchanged,
reopens encrypted persistence, exercises a controlled rollback/orphan case, and
records only PASS/FAIL plus approved commit/run identifiers. No image or private
report enters Git, Codex, CI, logs, or test reports.

Physical Windows 11 x64 installation, packaged startup, installer/upgrade,
installed-app offline verification, Excel/terminal/upload integration, and final
workstation acceptance remain deferred.

## 12. Non-goals and acceptance/reporting

Non-goals are OCR, MRZ, barcode, detection/classification/inferred layout,
terminal defaults, final/upload UI, person/vehicle cards, field verification,
snapshots, Excel/adapters/templates/export packages, installer, backup/restore,
Konversta/browser automation, cloud, telemetry/analytics, PR-009 quality-policy
activation, Q-021 resolution, and PR-014+.

Future acceptance requires all specified tests on the exact authorized head,
successful package builds, privacy-policy pass, manual synthetic PASS and
Product-owner review; it does not itself complete M3/Gate 2 or installed-Windows
acceptance. The implementation report must name base/head/PR/merge state,
schema/migration checksum, changed files, algorithm and persistence decisions,
exact commands/counts/platform results/builds, manual steps, privacy evidence,
limitations, orphan/atomicity behavior, working-tree/push/CI state, and next
safe step. No success may be claimed without evidence.

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

MERGING THIS DOCUMENTATION PR DOES NOT BY ITSELF AUTHORIZE PR-013 PRODUCTION IMPLEMENTATION.
