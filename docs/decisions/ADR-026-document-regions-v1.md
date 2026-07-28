# ADR-026 — Document regions V1

## Status

PROPOSED

```text
PR-012 CONTRACT: PROPOSED FOR HUMAN REVIEW
PR-012 PRODUCTION IMPLEMENTATION: UNAUTHORIZED
```

## Context and problem to resolve

PR-010 `ImageGeometryRecipe` has no stable region identity, while PR-010 persistence enforces one revision sequence per source through `UNIQUE(source_file_id, revision)`. That model is incompatible with the requirement that one source image support two independently confirmed document regions, each with its own geometry-recipe revision lineage. PR-011 must still prepare each confirmed region recipe separately, and all existing PR-010 and PR-011 identities and records must remain valid. This one-source/one-chain conflict is explicit and must be resolved rather than hidden.

## Proposed V1 scope

PR-012 V1 supports one immutable source file, exactly one or two manually supplied document regions, an ordered confirmed region set, independent geometry-recipe revision histories for the two regions, operator confirmation, deterministic persistence, and no final JPEG publication inside region confirmation.

```text
minimum confirmed regions = 1
maximum confirmed regions = 2
```

Zero regions fail. Three or more regions fail in V1. Supporting more than two regions requires a future versioned decision.

## No automatic detection in PR-012 V1

PR-012 V1 does not implement neural or classical automatic document detection, automatic polygon inference, automatic document-presence decisions, automatic document-count prediction, automatic crop, automatic deskew, or automatic region acceptance. The operator supplies and confirms every boundary. Confirmed document count is the number of operator-confirmed regions. This does not complete automatic FR-05 detection.

## Geometry reuse

PR-012 reuses the accepted PR-010 geometry semantics:

```text
coordinate_space = SOURCE_EFFECTIVE_PIXELS_V1
geometry_pipeline_id = PILLOW_QUAD_BICUBIC
geometry_pipeline_version = 1
```

It preserves EXIF orientation applied exactly once, source-effective pixel coordinates, TL/TR/BR/BL clockwise point order, convex-quadrilateral validation, deterministic output dimensions, quarter-turn values `0`, `90`, `180`, `270`, immutable originals, no metadata propagation, no caller-supplied raster bytes, and no caller-supplied filesystem paths. PR-012 must not create a second geometry algorithm.

## Stable region lineage

`ImageGeometryRecipe` is conceptually extended with:

```text
region_id: EntityId
```

`region_id` is the stable identity of one document-region lineage.

```text
revision == 1:
    superseded_recipe_version_id is None
    region_id == recipe_version_id

revision > 1:
    superseded_recipe_version_id is required
    region_id equals the predecessor region_id
```

A revision never changes `source_file_id`, `region_id`, coordinate-space identity, or geometry-pipeline identity. Two regions in one source have different `region_id` values and independent revision chains. A revision from one region never supersedes another region.

## Confirmed region-set aggregate

Introduce immutable `DocumentRegionSetVersion`:

```text
region_set_version_id: EntityId
source_file_id: EntityId
superseded_region_set_version_id: EntityId | None
revision: int
members: ordered tuple[DocumentRegionSetMember, ...]
confirmed_at: datetime
confirmed_by: ActorRef
```

`DocumentRegionSetMember` fields are:

```text
order_index: int
region_id: EntityId
geometry_recipe_version_id: EntityId
```

Required invariants:

- member count is exactly 1 or 2;
- `order_index` values are contiguous and start at 1;
- member order is operator supplied; spatial position never determines it automatically;
- member `region_id` and `geometry_recipe_version_id` values are respectively unique;
- every recipe has the set's `source_file_id` and its member's `region_id`;
- every referenced recipe is the selected revision for that region in this set;
- the set revision chain is linear per source file;
- revision 1 has no predecessor; later revisions supersede the immediate previous set version;
- immutable historical sets remain readable;
- changing boundaries, count, or order creates a new set version;
- reducing two regions to one does not delete retired-region history;
- increasing one region to two creates a new independent region lineage;
- update-in-place, deletion, and replacement are forbidden.

## Duplicate and overlap policy

Two regions with exactly identical canonical quadrilaterals are rejected. V1 defines no semantic non-overlap threshold. Partially overlapping regions may be operator confirmed because documents may touch or occlude one another and requirements define no automatic overlap policy. No overlap percentage is silently invented.

## Persistence and migration proposal

Future migration `v0008_document_regions` proposes schema 7 to schema 8. It adds non-null `region_id`, replaces one-chain-per-source uniqueness with `UNIQUE(source_file_id, region_id, revision)`, and retains `UNIQUE(superseded_recipe_version_id)`. Existing chains are deterministically backfilled by finding each chain's root revision and using that root `recipe_version_id` as `region_id` for every recipe in the chain. No random ID is generated; recipe-version IDs are not rewritten. Every `prepared_image_artifacts.geometry_recipe_version_id` reference and prepared-artifact natural key remains unchanged.

The proposed immutable set tables use `UNIQUE(source_file_id, revision)` and `UNIQUE(superseded_region_set_version_id)`. Membership uses a primary key on `(region_set_version_id, order_index)`, uniqueness for each set's `region_id` and recipe reference, and `CHECK(order_index IN (1, 2))`. The parent-table rebuild must follow accepted forward-only populated-table migration safety, preserve foreign-key and cipher integrity, roll back on failure, and assign no final v0008 checksum until implementation review.

## PR-011 compatibility boundary

PR-012 preserves `prepare_geometry_recipe_as_jpeg`, which continues to accept one `geometry_recipe_version_id` and prepare exactly one region. A caller prepares a two-region source by invoking PR-011 separately for each confirmed recipe. PR-012 does not alter JPEG settings, deterministic sequences, the `1_992_294`-byte limit, metadata removal, or the prepared-artifact natural key; it does not compose regions or call the pure encoder with a composed raster. Existing PR-011 prepared artifacts remain valid after proposed v0008.

## Logical-document boundary

PR-012 creates and confirms region identities and geometry recipes. It neither creates nor classifies final `Document` records. Document type, country, side, owner, and template classification remain later manual-workflow scope. The product rule that each confirmed region becomes a separate logical document is completed only when later classification binds the region to a `Document`. PR-012 invents no document types.

## Decision and authorization

This model and its migration are proposals for human review, not accepted architecture or implementation permission. Production implementation remains unauthorized. PR-013 and later remain unauthorized; Gate 2 remains not accepted; M3 remains in progress.
