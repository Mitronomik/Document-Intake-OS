# ADR-024 — Deterministic image geometry recipe v1

**Status:** ACCEPTED
**Date:** 2026-07-23

## Context

PR #26 is merged successfully. Final reviewed head: `cc79a80fcacdbde2667cae858815b30176f87555`. Merge commit: `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`. Merge date: `2026-07-23`. Exact-head CI: `CI #129`, run ID `29972502518`, conclusion `success`.

PR-009 remains COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. Q-021 remains DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. No production PR-009 quality policy is active; production `policy_id` and `policy_version` are NOT ASSIGNED; automatic PR-009 quality-based document blocking and production `RETAKE_REQUIRED` enforcement are NOT ACTIVE. `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` remains open and accepted. Gate 2 is NOT ACCEPTED. M3 is IN PROGRESS.

## Decision

ADR-024 is ACCEPTED by Product owner on 2026-07-23. It defines the exact deterministic image geometry recipe v1 contract for the documentation-only PR-010 contract proposal. PR-010 CONTRACT is PROPOSED FOR HUMAN REVIEW. PR-010 PRODUCTION IMPLEMENTATION is AUTHORIZED AND IN REVIEW. PR-011 AND LATER are UNAUTHORIZED. Merging this contract proposal does not authorize implementation; a later explicit product-owner decision is required.

## Geometry scope

PR-010 is a non-UI image-pipeline and application-contract slice for manual source quadrilateral selection; axis-aligned crop as the rectangular special case of the quadrilateral; perspective correction; coarse output rotation; immutable versioned geometry recipe; deterministic synthetic rendering; recipe persistence; application service and audit integration. PR-010 advances the manual image workflow but does not complete Gate 2.

## Coordinate space

The only authoritative V1 coordinate model is `SOURCE_EFFECTIVE_PIXELS_V1`.

Coordinates are integer pixel-edge coordinates in the full-resolution, EXIF-normalized effective raster. `(0, 0)` is the outer top-left boundary of the raster. x increases right. y increases down. Valid x range is `0 <= x <= source_effective_width`. Valid y range is `0 <= y <= source_effective_height`. `(source_effective_width, source_effective_height)` is the outer bottom-right boundary, not a pixel center. The full-frame quadrilateral is `(0, 0)`, `(width, 0)`, `(width, height)`, `(0, height)`.

Coordinates never refer to a scaled UI preview, viewport, zoom, screen coordinate, prepared artifact or compressed artifact. Preview coordinates must be converted before command construction. Original bytes remain immutable. EXIF is applied exactly once. The command supplies `expected_source_effective_width` and `expected_source_effective_height`; the service compares them with decoded effective dimensions after decode and fails with `SOURCE_DIMENSIONS_MISMATCH` when they differ.

## Exact operation order

1. Validate the caller-supplied command, controlled enum values, pipeline identity, timestamps, expected dimensions and primitive/domain invariants.
2. Create exactly one Unit of Work.
3. Load the source file through `uow.source_files`.
4. Load its immutable original artifact record through `uow.stored_artifacts`.
5. Read and integrity-verify the original through `StoragePort` without modifying it.
6. Decode the full-resolution RGB source and apply accepted EXIF orientation exactly once through `GeometryDecoderPort`.
7. Compare decoded effective dimensions with `expected_source_effective_width` and `expected_source_effective_height`.
8. Validate the source quadrilateral using the exact pixel-edge coordinate and geometry rules.
9. Derive pre-rotation rectified dimensions using the exact Euclidean and Decimal rules.
10. Render the internal RGB raster through `GeometryRendererPort` using the fixed Pillow QUAD/BICUBIC contract.
11. Apply the requested coarse clockwise quarter-turn through the exact transpose mapping.
12. Validate rendered dimensions, RGB mode, byte length and pipeline identity.
13. Load the latest recipe for the source.
14. Validate revision and superseded-recipe chain rules.
15. Construct the immutable `ImageGeometryRecipe`.
16. Add the recipe through `uow.image_geometry_recipes.add(...)`.
17. Construct the exact PII-safe `AuditEvent`.
18. Add the audit event through `uow.audit_events.add(...)`.
19. Call `uow.commit()` exactly once and exit the Unit of Work successfully.
20. Only after successful commit and successful Unit of Work exit, construct and return `CreateImageGeometryRecipeResult`.

No application result is constructed or returned before the successful Unit of Work commit and exit. Any failure before successful commit returns no result, commits no recipe, commits no audit event and leaves the original unchanged.

## Manual crop representation

Canonical project order is `top_left`, `top_right`, `bottom_right`, `bottom_left`. Validation order is: field types; coordinate bounds; duplicate points; signed shoelace area; clockwise order in y-down coordinates; non-adjacent edge intersections; strict convexity; minimum area; output dimensions; minimum output dimensions.

`signed_twice_area = Σ(x_i * y_(i+1) - y_i * x_(i+1))` with index modulo four. In the y-down coordinate system, `signed_twice_area > 0` means clockwise; `signed_twice_area <= 0` is rejected; exact zero is degenerate; minimum accepted area is four square effective pixels, therefore `signed_twice_area >= 8`. Use integer arithmetic for cross products and shoelace calculations.

All four consecutive-triple cross products must be strictly positive. Zero rejects collinear adjacent edges; mixed signs reject non-convex ordering. Reject non-adjacent intersections between `top_left → top_right` and `bottom_right → bottom_left`, and between `top_right → bottom_right` and `bottom_left → top_left`, using deterministic integer orientation tests.

## Rotation

Coarse rotation is limited to `0`, `90`, `180` and `270` degrees clockwise. Arbitrary-angle rotation is not part of PR-010. Perspective correction handles manual skew correction. Automatic deskew is outside PR-010.

## Output dimensions

Calculate Euclidean edge lengths with `distance(a, b) = sqrt((b.x - a.x)^2 + (b.y - a.y)^2)`. Use a local Decimal context with `precision = 28` and `rounding = ROUND_HALF_UP`; do not mutate the process-global Decimal context.

`unrounded_width = max(distance(top_left, top_right), distance(bottom_left, bottom_right))`. `unrounded_height = max(distance(top_left, bottom_left), distance(top_right, bottom_right))`. Quantize each maximum exactly once using `ROUND_HALF_UP`; do not round individual opposite edges before selecting the maximum. Both rectified dimensions must be at least `2`. For 90° and 270° clockwise quarter-turns, final width and height are swapped. No caller-supplied output dimensions are permitted in V1.

## Rendering boundary

```python
@dataclass(frozen=True, slots=True)
class DecodedGeometryMedia:
    media_type: SourceMediaType
    encoded_width: int
    encoded_height: int
    exif_orientation: int | None
    effective_width: int
    effective_height: int
    rgb_pixels: bytes


@dataclass(frozen=True, slots=True)
class RenderedGeometryRaster:
    width: int
    height: int
    rgb_pixels: bytes
    pipeline: GeometryPipelineVersion
```

`DecodedGeometryMedia` invariants: encoded/effective dimensions are positive; orientation is `None` or 1-8; effective dimension axis rules match PR-009; `len(rgb_pixels) == effective_width * effective_height * 3`; pixels are packed row-major RGB; EXIF orientation has already been applied exactly once; no metadata, filename, path, hash or exception text. `RenderedGeometryRaster` invariants: positive dimensions; `len(rgb_pixels) == width * height * 3`; pipeline is V1; no encoded JPEG; raster bytes are internal, ephemeral, not persisted by PR-010 and not returned by the application result DTO.

```python
class GeometryDecoderPort(Protocol):
    def decode_for_geometry(
        self,
        *,
        content: bytes,
    ) -> DecodedGeometryMedia: ...


class GeometryRendererPort(Protocol):
    def render_geometry(
        self,
        *,
        media: DecodedGeometryMedia,
        quadrilateral: SourceQuadrilateral,
        quarter_turn: GeometryQuarterTurn,
        pipeline: GeometryPipelineVersion,
    ) -> RenderedGeometryRaster: ...
```

Do not merge geometry decoding into the 9×8 import decoder. Do not derive RGB geometry pixels from PR-009 grayscale pixels.

The Pillow renderer uses `Image.transform`, `Image.Transform.QUAD`, `Image.Resampling.BICUBIC`, `fill=1`, `fillcolor=(255, 255, 255)`, RGB output and no metadata. Project canonical order is `TL, TR, BR, BL`; Pillow `QUAD` source order is `upper-left, lower-left, lower-right, upper-right`, i.e. TL, BL, BR, TR. Exact conversion:

```python
quad_data = (
    top_left.x,
    top_left.y,
    bottom_left.x,
    bottom_left.y,
    bottom_right.x,
    bottom_right.y,
    top_right.x,
    top_right.y,
)
```

Clockwise mapping after QUAD: 0° no transpose; 90° `Image.Transpose.ROTATE_270`; 180° `Image.Transpose.ROTATE_180`; 270° `Image.Transpose.ROTATE_90`. Do not use arbitrary-angle `rotate()`, OpenCV, `LANCZOS`, `BILINEAR` or `NEAREST`.

## Determinism

The same immutable source bytes, source checksum, effective dimensions, geometry recipe, `pipeline_id = PILLOW_QUAD_BICUBIC`, `pipeline_version = 1`, and locked Pillow version `12.3.0` must produce the same dimensions, operation sequence and structurally equivalent RGB raster. Synthetic golden vectors lock corner mapping, orientation handling, output dimensions, quarter-turn direction, Pillow `Image.Transform.QUAD`, `Image.Resampling.BICUBIC`, `fill=1`, `fillcolor=(255, 255, 255)` and invalid-geometry behavior. Do not promise cross-library equivalence.

## Original-file safety

Original bytes are read-only, never overwritten, never modified in place, never re-encoded as a replacement original and remain independently verifiable by checksum. No failure may remove or replace an original.

## Recipe immutability

```python
from enum import IntEnum, StrEnum


class GeometryCoordinateSpace(StrEnum):
    SOURCE_EFFECTIVE_PIXELS_V1 = "SOURCE_EFFECTIVE_PIXELS_V1"


class GeometryQuarterTurn(IntEnum):
    DEG_0 = 0
    DEG_90 = 90
    DEG_180 = 180
    DEG_270 = 270


class GeometryErrorCode(StrEnum):
    SOURCE_FILE_NOT_FOUND = "SOURCE_FILE_NOT_FOUND"
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
    ARTIFACT_INTEGRITY_FAILED = "ARTIFACT_INTEGRITY_FAILED"
    DECODE_FAILED = "DECODE_FAILED"
    SOURCE_DIMENSIONS_MISMATCH = "SOURCE_DIMENSIONS_MISMATCH"
    POINT_OUT_OF_BOUNDS = "POINT_OUT_OF_BOUNDS"
    DUPLICATE_POINT = "DUPLICATE_POINT"
    NON_CLOCKWISE_QUADRILATERAL = "NON_CLOCKWISE_QUADRILATERAL"
    SELF_INTERSECTING_QUADRILATERAL = "SELF_INTERSECTING_QUADRILATERAL"
    NON_CONVEX_QUADRILATERAL = "NON_CONVEX_QUADRILATERAL"
    AREA_TOO_SMALL = "AREA_TOO_SMALL"
    OUTPUT_DIMENSIONS_TOO_SMALL = "OUTPUT_DIMENSIONS_TOO_SMALL"
    INVALID_QUARTER_TURN = "INVALID_QUARTER_TURN"
    INVALID_PIPELINE_VERSION = "INVALID_PIPELINE_VERSION"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    RENDER_FAILED = "RENDER_FAILED"
    RECIPE_PERSISTENCE_FAILED = "RECIPE_PERSISTENCE_FAILED"
    AUDIT_PERSISTENCE_FAILED = "AUDIT_PERSISTENCE_FAILED"
    COMMIT_FAILED = "COMMIT_FAILED"
```

`pipeline_id = PILLOW_QUAD_BICUBIC`; `pipeline_version = 1`; locked Pillow version is `12.3.0`. `pipeline_id` accepts only `PILLOW_QUAD_BICUBIC` in V1; `pipeline_version` accepts only integer `1`; there is no hidden default pipeline; the command supplies `GeometryPipelineVersion` explicitly; the service validates it before storage access.

```python
@dataclass(frozen=True, slots=True)
class GeometryPipelineVersion:
    pipeline_id: str
    version: int


@dataclass(frozen=True, slots=True)
class GeometryPoint:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class SourceQuadrilateral:
    top_left: GeometryPoint
    top_right: GeometryPoint
    bottom_right: GeometryPoint
    bottom_left: GeometryPoint


@dataclass(frozen=True, slots=True)
class ImageGeometryRecipe:
    recipe_version_id: EntityId
    source_file_id: EntityId
    superseded_recipe_version_id: EntityId | None
    revision: int
    coordinate_space: GeometryCoordinateSpace
    source_effective_width: int
    source_effective_height: int
    quarter_turn: GeometryQuarterTurn
    quadrilateral: SourceQuadrilateral
    pipeline: GeometryPipelineVersion
    created_at: datetime
```

All IDs use existing `EntityId`; timestamps are timezone-aware UTC; dimensions and revision are positive; revision `1` requires `superseded_recipe_version_id is None`; revision greater than `1` requires a non-null superseded ID; recipe contains no filename, path, hash, pixels, thumbnail, OCR, PII, exception text or arbitrary metadata; `repr` is deterministic and PII-safe. Each accepted operator change creates a new append-only recipe version; no update, delete or replace is allowed.

## One-document boundary

PR-010 defines one geometry recipe for one manually selected document area from one source file. Multiple independently confirmed document regions from one image remain PR-012 scope. Do not implement document count, automatic region detection or multiple-region workflow in PR-010.

## Persistence boundary

```python
class ImageGeometryRecipeRepository(Protocol):
    def add(self, recipe: ImageGeometryRecipe) -> None: ...

    def get(
        self,
        recipe_version_id: EntityId,
    ) -> ImageGeometryRecipe | None: ...

    def get_latest_by_source(
        self,
        source_file_id: EntityId,
    ) -> ImageGeometryRecipe | None: ...

    def get_by_source_revision(
        self,
        source_file_id: EntityId,
        revision: int,
    ) -> ImageGeometryRecipe | None: ...

    def list_by_source(
        self,
        source_file_id: EntityId,
    ) -> tuple[ImageGeometryRecipe, ...]: ...
```

Exact list order is revision ascending, created-at ascending and recipe-version ID ascending. Revision-chain rule: no latest recipe requires revision 1 and superseded ID `None`; otherwise new revision equals latest revision + 1 and superseded ID equals latest recipe ID; no branching history is allowed; failure is `REVISION_CONFLICT`. Persistence is append-only in SQLCipher and detects projection/canonical-payload corruption before filtering or returning results.

Future migration `v0006_image_geometry` is staged only; do not create it in this PR. Future table `image_geometry_recipes` columns are `recipe_version_id`, `source_file_id`, `superseded_recipe_version_id`, `revision`, `coordinate_space`, `source_effective_width`, `source_effective_height`, `quarter_turn_clockwise`, all eight quadrilateral coordinates, `geometry_pipeline_id`, `geometry_pipeline_version`, `created_at_utc` and `canonical_payload`.

Required constraints: primary key; source-file foreign key; nullable self foreign key; unique `(source_file_id, revision)`; unique non-null `superseded_recipe_version_id`; positive revision and dimensions; coordinate space exactly `SOURCE_EFFECTIVE_PIXELS_V1`; quarter turn exactly 0/90/180/270; pipeline exactly `PILLOW_QUAD_BICUBIC`, version 1; x coordinates in `0..source_effective_width`; y coordinates in `0..source_effective_height`; update prohibited; delete prohibited; replace prohibited; projection/canonical-payload equality; strict controlled-value deserialization; corruption detected before filtering or returning results. Frozen migrations v0001 through v0005 remain unchanged.

## Service and transaction boundary

```python
def create_image_geometry_recipe(
    command: CreateImageGeometryRecipeCommand,
    *,
    decoder: GeometryDecoderPort,
    renderer: GeometryRendererPort,
    storage: StoragePort,
    unit_of_work_factory: UnitOfWorkFactory,
) -> CreateImageGeometryRecipeResult:
    ...
```

The service validates the caller-supplied command, controlled enum values, pipeline identity, timestamps, expected dimensions and primitive/domain invariants before storage access. It does not generate UUIDs, read the system clock, infer actor, infer correlation, infer geometry, select hidden crop defaults or silently correct invalid points.

```python
class UnitOfWork(Protocol):
    ...
    image_geometry_recipes: ImageGeometryRecipeRepository
```

Use exactly one Unit of Work and exactly one `uow.commit()`. Recipe persistence and audit insertion are in the same transaction. Do not create a standalone database connection, independent repository factory, independent audit connection, separate transaction or automatic repository commit. No application result is constructed or returned before the successful Unit of Work commit and exit.

1. Validate the caller-supplied command, controlled enum values, pipeline identity, timestamps, expected dimensions and primitive/domain invariants.
2. Create exactly one Unit of Work.
3. Load the source file through `uow.source_files`.
4. Load its immutable original artifact record through `uow.stored_artifacts`.
5. Read and integrity-verify the original through `StoragePort` without modifying it.
6. Decode the full-resolution RGB source and apply accepted EXIF orientation exactly once through `GeometryDecoderPort`.
7. Compare decoded effective dimensions with `expected_source_effective_width` and `expected_source_effective_height`.
8. Validate the source quadrilateral using the exact pixel-edge coordinate and geometry rules.
9. Derive pre-rotation rectified dimensions using the exact Euclidean and Decimal rules.
10. Render the internal RGB raster through `GeometryRendererPort` using the fixed Pillow QUAD/BICUBIC contract.
11. Apply the requested coarse clockwise quarter-turn through the exact transpose mapping.
12. Validate rendered dimensions, RGB mode, byte length and pipeline identity.
13. Load the latest recipe for the source.
14. Validate revision and superseded-recipe chain rules.
15. Construct the immutable `ImageGeometryRecipe`.
16. Add the recipe through `uow.image_geometry_recipes.add(...)`.
17. Construct the exact PII-safe `AuditEvent`.
18. Add the audit event through `uow.audit_events.add(...)`.
19. Call `uow.commit()` exactly once and exit the Unit of Work successfully.
20. Only after successful commit and successful Unit of Work exit, construct and return `CreateImageGeometryRecipeResult`.

No application result is constructed or returned before the successful Unit of Work commit and exit. Any failure before successful commit returns no result, commits no recipe, commits no audit event and leaves the original unchanged.

## Audit boundary

The exact audit action is `AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED`. The exact audit subject type is `AuditSubjectType.IMAGE_GEOMETRY_RECIPE`. Subject ID is `recipe_version_id`. Reason code is `IMAGE_GEOMETRY_RECIPE_CREATED`. Non-sensitive after summary is `IMAGE_GEOMETRY_RECIPE`. Audit payload must not contain coordinates, dimensions, filename, path, hashes, source bytes, rendered bytes, thumbnails, OCR, PII or raw exceptions.

## Controlled errors

Controlled error identity uses `GeometryErrorCode` values only, not free-text messages: `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `SOURCE_DIMENSIONS_MISMATCH`, `POINT_OUT_OF_BOUNDS`, `DUPLICATE_POINT`, `NON_CLOCKWISE_QUADRILATERAL`, `SELF_INTERSECTING_QUADRILATERAL`, `NON_CONVEX_QUADRILATERAL`, `AREA_TOO_SMALL`, `OUTPUT_DIMENSIONS_TOO_SMALL`, `INVALID_QUARTER_TURN`, `INVALID_PIPELINE_VERSION`, `REVISION_CONFLICT`, `RENDER_FAILED`, `RECIPE_PERSISTENCE_FAILED`, `AUDIT_PERSISTENCE_FAILED` and `COMMIT_FAILED`. Error DTOs, logs and audit records remain PII-safe.

## Non-decisions in ADR-024

ADR-024 does not decide automatic document detection, automatic crop, automatic deskew, multiple documents per source, document count, document classification, JPEG compression, the 1.90 MiB algorithm, readability thresholds, side merging, front/back order, OCR, UI workflow, terminal-specific output dimensions, production PR-009 quality policy or Q-021 resolution.

## Consequences

PR-010 implementation must branch from the exact merge commit of the documentation-contract PR after it exists. This ADR introduces no production source files, migrations, dependency changes, CI workflow changes, UI behavior, runtime image transformation behavior, final JPEG publication, production quality-policy activation or PR-011/PR-012/PR-013 implementation.


## PR-010 implementation review state

Product owner accepted ADR-024 on 2026-07-23 and authorized production implementation in review from exact base `329dd5653a3faadd3c62387c1d900710f14b2f4e`. PR-011 and later remain UNAUTHORIZED. Gate 2 remains NOT ACCEPTED. M3 remains IN PROGRESS. Q-021 remains DEFERRED. Production PR-009 quality policy remains NOT ACTIVE.
