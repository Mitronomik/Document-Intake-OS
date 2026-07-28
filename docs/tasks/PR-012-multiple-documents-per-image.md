# PR-012 — Multiple documents per image

## Status

```text
CONTRACT PROPOSED FOR HUMAN REVIEW
PRODUCTION IMPLEMENTATION UNAUTHORIZED
```

ADR-026 and this contract require later explicit Product-owner acceptance. PR-013 and later remain unauthorized; Gate 2 is not accepted; M3 is in progress.

## 1. Objective

Implement deterministic operator-confirmed handling of one or two document regions in one immutable source image. The implementation creates independent region geometry-recipe lineages, one immutable ordered region-set version, privacy-safe audit events, forward-only persistence, and queries for current and historical confirmed sets. It must not publish prepared JPEGs.

## 2. Expected implementation base

```text
PR-012_IMPLEMENTATION_BASE = TO_BE_SET_AFTER_CONTRACT_PR_MERGE
```

The implementation base is unknown until this documentation PR merges. A later explicit Product-owner decision must accept ADR-026, accept this contract, authorize production implementation, and replace the placeholder with this documentation PR's exact merge commit. Codex must not choose the implementation base.

## 3. Domain changes

Proposed production changes extend `ImageGeometryRecipe` with stable `region_id`; add `DocumentRegionSetMember`, `DocumentRegionSetVersion`, and controlled PR-012 errors; preserve frozen PR-010 coordinate/rendering identities; and preserve existing recipe-version IDs. Existing PR-010 recipe-version IDs are neither renamed nor reinterpreted.

## 4. Application DTO

`ConfirmDocumentRegionsCommand` fields:

```text
region_set_version_id
source_file_id
superseded_region_set_version_id
set_revision
regions
region_set_audit_event_id
confirmed_at
actor
correlation_id
```

Each `RegionConfirmationInput` contains:

```text
order_index
region_id
recipe_version_id
superseded_recipe_version_id
recipe_revision
quadrilateral
quarter_turn
recipe_audit_event_id
```

All IDs and timestamps are caller supplied; timestamps are timezone-aware UTC. The service generates no UUID or current time. All record IDs are pairwise distinct. For a new region, `region_id == recipe_version_id`; for a revision, `region_id` is unchanged. Exactly one or two inputs are allowed, with indices `1` or `1, 2`. Commands contain no paths, filenames, image bytes, JPEG settings, document type/country/owner/side, or PR-009 policy identity.

`ConfirmDocumentRegionsResult` returns the persisted `DocumentRegionSetVersion` and ordered persisted `ImageGeometryRecipe` entities/identifiers only: no raster, JPEG bytes, filesystem path, original bytes, or PII.

## 5. Exact application operation order

1. validate source-independent command invariants;
2. validate region count;
3. validate contiguous order indices;
4. validate record-ID distinctness;
5. validate new/revision region identity rules;
6. reject exact duplicate canonical quadrilaterals;
7. open one read Unit of Work;
8. load and validate the source file;
9. load and validate the immutable original stored artifact;
10. load and validate the preceding region-set version when revision is greater than 1;
11. load and validate preceding recipe revisions for revised regions;
12. close the read Unit of Work without commit;
13. read immutable original bytes;
14. verify checksum and byte integrity;
15. decode the source once;
16. apply EXIF orientation exactly once;
17. compare decoded source-effective dimensions with authoritative metadata;
18. validate every region using accepted PR-010 geometry rules;
19. derive deterministic output dimensions for every region;
20. render every proposed region to an ephemeral RGB raster to prove the recipe is executable;
21. discard all ephemeral rasters;
22. open one write Unit of Work;
23. re-read and revalidate the source and original-artifact metadata;
24. re-read and revalidate preceding set/recipe revisions;
25. verify every caller-supplied record ID is absent;
26. verify set revision uniqueness;
27. verify independent region revision uniqueness;
28. add all new geometry-recipe revisions in `order_index` order;
29. add one PR-010-compatible recipe-created audit event per new recipe revision;
30. add `DocumentRegionSetVersion`;
31. add ordered region-set membership rows;
32. add the region-set confirmation audit event;
33. commit exactly once;
34. exit the Unit of Work;
35. construct and return the result.

No image artifact is published, no JPEG encoder is called, and no partial region set may commit.

## 6. Atomicity

All geometry-recipe revisions, recipe audit events, the region-set version, ordered memberships, and region-set audit event commit in one database Unit of Work. Any failure commits nothing: no new set, recipe, membership, or audit is visible; originals and existing recipes/sets remain unchanged. PR-012 publishes no filesystem artifact, so this service introduces no orphan-storage case.

## 7. Persistence and migration proposal

Future migration `v0008_document_regions` transitions `schema 7 -> schema 8`. Do not modify v0001–v0007 or assign a final v0008 checksum before implementation review.

It must extend immutable audit enums; safely rebuild `image_geometry_recipes`; add non-null `region_id`; deterministically backfill legacy PR-010 chains; preserve recipe-version IDs and every `prepared_image_artifacts.geometry_recipe_version_id`; replace old one-chain-per-source uniqueness; add immutable set/membership tables; preserve foreign-key/cipher integrity; and set `PRAGMA user_version = 8`.

Legacy backfill finds the root revision of each existing source recipe chain and uses the root `recipe_version_id` as `region_id` for every recipe in that chain. It generates no random IDs, rewrites no recipe-version IDs, and changes no prepared-artifact natural key.

```text
UNIQUE(source_file_id, region_id, revision)
UNIQUE(superseded_recipe_version_id)

UNIQUE(source_file_id, revision)
UNIQUE(superseded_region_set_version_id)

PRIMARY KEY(region_set_version_id, order_index)
UNIQUE(region_set_version_id, region_id)
UNIQUE(region_set_version_id, geometry_recipe_version_id)
CHECK(order_index IN (1, 2))
```

The parent geometry table rebuild must preserve the v0007 prepared-artifact foreign key using explicit controlled foreign-key handling, populated-table copy, integrity checks before and after restoration, no direct internal SQLite schema mutation, rollback on failure, no surviving temporary table, and unchanged wrong-key/encrypted-reopen behavior.

## 8. Repository behavior

```text
get_region_set_version(region_set_version_id)
list_region_set_versions_for_source(source_file_id)
get_latest_region_set_for_source(source_file_id)
get_geometry_recipe(recipe_version_id)
list_geometry_recipe_versions_for_region(source_file_id, region_id)
get_latest_geometry_recipe_for_region(source_file_id, region_id)
add_region_set_version(...)
add_geometry_recipe(...)
```

Scoped queries constrain SQL to requested scope, deserialize every returned row, compare canonical payload/projections, validate complete relevant chains, fail closed for in-scope corruption, and are not poisoned by unrelated out-of-scope corruption. Set reads validate contiguous revisions, immediate predecessors, one/two ordered members, order, source/region/recipe consistency, and absence of branches, missing predecessors, duplicate regions, and duplicate recipe references.

## 9. PR-011 compatibility

`prepare_geometry_recipe_as_jpeg` continues to receive one `geometry_recipe_version_id` and prepare one region. For two regions, call it separately for each confirmed recipe. PR-012 changes no JPEG settings, quality/resize sequences, byte limit, metadata removal, or PR-011 natural key; composes no regions; and never calls the pure encoder with a composed raster. Existing prepared artifacts remain valid after v0008. Production PR-006–PR-011 verifiers are forward-updated only as schema 8 requires and are never weakened.

## 10. Audit contract

Reuse the PR-010 recipe-created audit event for each new recipe revision. Add:

```text
AuditAction.DOCUMENT_REGION_SET_CONFIRMED
AuditSubjectType.DOCUMENT_REGION_SET
AuditReasonCode.DOCUMENT_REGION_SET_CONFIRMED
```

Exact set audit fields:

```text
event_id = command.region_set_audit_event_id
action = DOCUMENT_REGION_SET_CONFIRMED
subject_type = DOCUMENT_REGION_SET
subject_id = command.region_set_version_id
actor = command.actor
occurred_at = command.confirmed_at
field_key = None

before.classification = ABSENT
before.display_value = None
before.was_present = false

after.classification = NON_SENSITIVE
after.display_value = DOCUMENT_REGION_SET
after.was_present = true

reason_code = DOCUMENT_REGION_SET_CONFIRMED
correlation_id = command.correlation_id
```

Audits contain no polygons/coordinates, dimensions, region count/order, filenames, paths, checksums, bytes, prepared-JPEG information, document types, owners, OCR, PII, raw SQL, or raw exceptions.

## 11. Proposed controlled errors

```text
REGION_COUNT_INVALID
REGION_ORDER_INVALID
REGION_IDENTITY_CONFLICT
DUPLICATE_REGION
REGION_REVISION_CONFLICT
REGION_SET_REVISION_CONFLICT
REGION_SET_NOT_FOUND
PERSISTENCE_CONFLICT
PERSISTENCE_FAILED
PERSISTED_DATA_INVALID
COMMIT_FAILED
```

Applicable accepted PR-010/source codes remain: `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `SOURCE_DIMENSIONS_MISMATCH`, `POINT_OUT_OF_BOUNDS`, `DUPLICATE_POINT`, `NON_CLOCKWISE_QUADRILATERAL`, `SELF_INTERSECTING_QUADRILATERAL`, `NON_CONVEX_QUADRILATERAL`, `AREA_TOO_SMALL`, `OUTPUT_DIMENSIONS_TOO_SMALL`, `INVALID_QUARTER_TURN`, `INVALID_PIPELINE_VERSION`, and `RENDER_FAILED`.

Representations expose controlled codes only, never paths, filenames, bytes, checksums, coordinates, region/source identities, personal data, raw SQL, or raw exception messages.

## 12. Exact future files

```text
src/document_intake/domain/image_geometry.py
src/document_intake/domain/document_regions.py
src/document_intake/domain/audit.py
src/document_intake/application/dto/document_regions.py
src/document_intake/application/services/document_regions.py
src/document_intake/application/ports/persistence.py
src/document_intake/persistence/migrations/v0008_document_regions.py
src/document_intake/persistence/repositories/image_geometry.py
src/document_intake/persistence/repositories/document_regions.py
src/document_intake/persistence/serialization.py
src/document_intake/persistence/database.py
scripts/verify_pr012_regions.py
tests/domain/test_document_regions.py
tests/application/test_document_regions_service.py
tests/persistence/test_document_regions_repository.py
tests/persistence/test_pr012_migration_acceptance.py
tests/persistence/test_windows_sqlcipher_integration.py
tests/test_verify_pr012_regions.py
```

This narrow architectural list is not permission to create these files in this documentation PR. Avoid mixed-responsibility modules and keep region logic separate from PR-011 encoding.

## 13. Required future test matrix

### Domain

Prove one/two accepted; zero/three rejected; contiguous order; exact duplicates rejected; partial overlap allowed; independent identities; revision-1 identity and later ID preservation; linear set history; immutable historical sets.

### Application

Prove one decode and one EXIF application; all regions validated/rendered ephemerally; no JPEG or filesystem publication; one atomic commit; one failure prevents all writes; ID preflight before writes; write-UoW revalidation; atomic audits; no bytes/paths in result.

### Persistence

Prove independent chains; no cross-region supersession; exact current/historical reads; immutable mutation rejection; branch/missing/cross-source corruption rejection; duplicate membership rejection; scoped corruption; canonical/projection mismatch rejection.

### Migration

Prove populated schema 7 -> 8; root-recipe backfill; unchanged recipe IDs/prepared FKs; readable prepared artifacts; valid history/checksums; no temporary table; injected-failure rollback to schema 7; SQLite/Windows SQLCipher reopen; private controlled wrong-key behavior.

### Compatibility

Prove accepted PR-010 geometry; independent PR-011 preparation; exact byte boundary; PR-006–PR-011 verifiers on schema 8; full Ubuntu/Windows pytest and builds; Windows PR-012 verifier; encryption spike; DPAPI cross-runner negative proof.

## 14. Synthetic fixtures

Use deterministic synthetic images and fictional identifiers only: one rectangle; two non-overlapping, touching, or partially overlapping rectangles; changed boundary; reduction two-to-one; increase one-to-two; populated encrypted synthetic schema-7 recipes/prepared artifacts. Never use real identity/vehicle documents, real names/numbers/registrations, private templates, or real working directories.

## 15. Non-goals

PR-012 production implementation does not include:

- automatic document detection;
- automatic document count;
- automatic boundary inference;
- UI;
- drag handles;
- document classification;
- country selection;
- front/back side assignment;
- owner assignment;
- `Document` creation;
- OCR;
- MRZ;
- barcode processing;
- image-quality policy activation;
- automatic `RETAKE_REQUIRED`;
- JPEG composition;
- front/back merge;
- vertical or horizontal merge settings;
- PR-013;
- Excel;
- terminal adapters;
- export;
- Konversta integration;
- browser automation;
- cloud APIs;
- telemetry;
- analytics;
- more than two regions per source;
- deletion or secure deletion.

## 16. Manual verification for future implementation

Using synthetic files only: import one image with two rectangles; confirm two manual regions; load ordered set; verify independent lineages; prepare each through unchanged PR-011; verify separate JPEGs neither containing the other region; revise one while retaining the other's ID; read historical set/recipes; reopen encrypted DB and repeat queries; verify byte-identical originals. Physical real-photo verification remains outside Git, Codex, and CI.

## Authorization boundary

This contract remains proposed for human review. PR-012 production implementation is unauthorized. PR-013 and later are unauthorized. No production code, migration, or CI change is authorized by this document.
