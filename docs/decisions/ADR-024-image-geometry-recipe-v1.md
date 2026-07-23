# ADR-024 — Deterministic image geometry recipe v1

**Status:** PROPOSED
**Date:** 2026-07-23

## Context

PR #26 is merged successfully. Final reviewed head: `cc79a80fcacdbde2667cae858815b30176f87555`. Merge commit: `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`. Merge date: `2026-07-23`. Exact-head CI: `CI #129`, run ID `29972502518`, conclusion `success`.

PR-009 remains COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. Q-021 remains DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. No production PR-009 quality policy is active; production `policy_id` and `policy_version` are NOT ASSIGNED; automatic PR-009 quality-based document blocking and production `RETAKE_REQUIRED` enforcement are NOT ACTIVE. `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` remains open and accepted. Gate 2 is NOT ACCEPTED. M3 is IN PROGRESS.

## Decision

ADR-024 is PROPOSED. It defines the exact deterministic image geometry recipe v1 contract for the documentation-only PR-010 contract proposal. PR-010 CONTRACT is PROPOSED FOR HUMAN REVIEW. PR-010 PRODUCTION IMPLEMENTATION is UNAUTHORIZED. PR-011 AND LATER are UNAUTHORIZED. Merging this contract proposal does not authorize implementation; a later explicit product-owner decision is required.

## Geometry scope

PR-010 is a non-UI image-pipeline and application-contract slice for manual source quadrilateral selection; axis-aligned crop as the rectangular special case of the quadrilateral; perspective correction; coarse output rotation; immutable versioned geometry recipe; deterministic synthetic rendering; recipe persistence; application service and audit integration. PR-010 advances the manual image workflow but does not complete Gate 2.

## Coordinate space

The exact coordinate-space identifier is `SOURCE_EFFECTIVE_PIXELS_V1`.

Coordinates refer to the full-resolution imported source content. Accepted EXIF orientation is applied exactly once for the geometry working view. Coordinates use the resulting orientation-normalized effective pixel grid. `(0, 0)` is the top-left pixel of that effective grid; x increases to the right; y increases downward. Coordinates never refer to a scaled UI preview, never refer to a previously prepared or compressed artifact, and never rewrite the original encoded bytes.

Existing domain wording that coordinates refer to the original means immutable source content in the accepted effective-orientation coordinate system, not a derivative preview or rewritten original. A future UI must convert display-preview coordinates into `SOURCE_EFFECTIVE_PIXELS_V1` before creating a command. Preview scale, viewport position, zoom and screen coordinates must never be persisted as geometry recipe data.

## Exact operation order

1. Read immutable original bytes through the accepted storage port.
2. Verify the stored object through the accepted storage boundary.
3. Decode the full-resolution source.
4. Apply EXIF orientation exactly once.
5. Validate the source effective dimensions.
6. Validate the source quadrilateral.
7. Perspective-crop the quadrilateral into a rectangular RGB raster.
8. Apply coarse clockwise quarter-turn rotation to the rectified raster.
9. Render an internal geometry raster.
10. Persist the immutable recipe and matching audit event atomically.

No operation may rewrite the original. Do not apply EXIF again after step 4.

## Manual crop representation

A manual crop is represented by a four-corner source quadrilateral. An axis-aligned crop is the rectangular special case. Do not add a second competing crop-coordinate model.

Canonical corner order is exactly: `top_left`, `top_right`, `bottom_right`, `bottom_left`.

The implementation contract must require exactly four points; integer source-effective pixel coordinates; all points within source bounds; no duplicate points; positive area; convex shape; no self-intersection; canonical clockwise corner order; deterministic validation errors.

## Rotation

Coarse rotation is limited to `0`, `90`, `180` and `270` degrees clockwise. Arbitrary-angle rotation is not part of PR-010. Perspective correction handles manual skew correction. Automatic deskew is outside PR-010.

## Output dimensions

Before quarter-turn rotation, derive rectified dimensions from opposite quadrilateral edge lengths: output width from the greater of top and bottom edge lengths; output height from the greater of left and right edge lengths; use deterministic round-half-up conversion to integer pixels; both derived dimensions must be at least 2 pixels. For 90-degree and 270-degree output rotation, swap final width and height. V1 does not accept caller-supplied arbitrary output dimensions and does not rescale to a target terminal dimension.

## Rendering boundary

The contract prefers the already accepted and locked Pillow runtime. Do not add OpenCV, cloud libraries, network calls or a second image stack. The V1 Pillow transform mode, resampling mode and internal corner-order adaptation are fixed by ADR-024: `Image.Transform.QUAD`, `Image.Resampling.BICUBIC`, and TL/BL/BR/TR Pillow source order conversion. Use RGB output. Do not preserve EXIF, geolocation, comments, ICC metadata or arbitrary source metadata in the internal rendered result. PR-010 does not publish a final JPEG. The geometry-rendered raster is an internal result for later PR-011 processing.

## Determinism

The same immutable source bytes, source checksum, effective dimensions, geometry recipe, geometry pipeline version and locked Pillow version must produce the same dimensions, operation sequence and structurally equivalent RGB raster. Synthetic golden vectors must lock corner mapping, orientation handling, output dimensions, quarter-turn direction and invalid-geometry behavior. Do not promise cross-library equivalence.

## Original-file safety

Original bytes are read-only, never overwritten, never modified in place, never re-encoded as a replacement original and remain independently verifiable by checksum. No failure may remove or replace an original.

## Recipe immutability

Each accepted operator change creates a new immutable recipe version. No recipe row may be updated, deleted or replaced.

The V1 recipe has unique recipe version ID; source file ID; optional superseded recipe version ID; positive revision number; coordinate-space identifier; source effective width; source effective height; coarse clockwise quarter-turn; canonical source quadrilateral; geometry pipeline ID; geometry pipeline version; UTC creation timestamp.

The V1 recipe does not include filenames, filesystem paths, source pixel bytes, rendered pixel bytes, thumbnails, UI viewport state, zoom, raw exception text, arbitrary metadata, OCR data or personal fields.

## One-document boundary

PR-010 defines one geometry recipe for one manually selected document area from one source file. Multiple independently confirmed document regions from one image remain PR-012 scope. Do not implement document count, automatic region detection or multiple-region workflow in PR-010.

## Persistence boundary

Stage the future migration as `v0006_image_geometry`. Do not create the migration in this documentation-only PR. The future persistence design must be append-only and preserve the accepted SQLCipher, Unit of Work and immutable-history boundaries. The task contract defines exact table and column proposal, primary and foreign keys, source-file relationship, superseded-recipe relationship, canonical payload, projection/payload equality checks, deterministic list order, update/delete/replace prevention and corruption detection during rehydration. Frozen earlier migrations must not be modified.

## Service and transaction boundary

The future command must use caller-supplied recipe version ID, source file ID, optional superseded recipe version ID, revision, quadrilateral, quarter-turn, created-at timestamp, actor, audit event ID and correlation ID. The service must not generate UUIDs, read the system clock, infer actor, infer correlation ID, infer geometry from the image, select a hidden default crop or silently correct invalid points.

The service must use the accepted storage port, decoder port extension, Unit of Work factory, recipe repository and audit repository. Recipe persistence and audit insertion must occur in one Unit of Work transaction with one commit. Any failure before successful commit must leave no committed recipe or audit row.

## Audit boundary

The future audit event must record exactly `AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED` with subject type `AuditSubjectType.IMAGE_GEOMETRY_RECIPE`. It must be PII-safe. It may reference controlled entity IDs and recipe version metadata. It must not include filename, local path, original bytes, rendered bytes, thumbnail, full quadrilateral coordinates, arbitrary metadata, raw exception, OCR values or personal data.

## Controlled errors

Typed controlled failures must include source file not found; immutable stored object missing; stored-object integrity failure; unsupported decode; geometry decode failure; source-dimension mismatch; point outside bounds; duplicate point; self-intersecting quadrilateral; non-convex quadrilateral; zero or insufficient area; derived output too small; invalid quarter-turn; revision conflict; persistence conflict; audit persistence failure; render failure. Error DTOs, logs and audit records must remain PII-safe.

## Non-decisions in ADR-024

ADR-024 does not decide automatic document detection, automatic crop, automatic deskew, multiple documents per source, document count, document classification, JPEG compression, the 1.90 MiB algorithm, readability thresholds, side merging, front/back order, OCR, UI workflow, terminal-specific output dimensions, production PR-009 quality policy or Q-021 resolution.

## Consequences

PR-010 implementation must branch from the exact merge commit of the documentation-contract PR after it exists. This ADR introduces no production source files, migrations, dependency changes, CI workflow changes, UI behavior, runtime image transformation behavior, final JPEG publication, production quality-policy activation or PR-011/PR-012/PR-013 implementation.

## Exact PR-010 V1 contract completion

ADR-024 binds the following V1 symbols and execution rules. These are not left for the implementation PR to choose.

### Exact domain enums

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

Free-text error messages are not controlled error identity.

### Exact pipeline identity and locked runtime

```text
pipeline_id = PILLOW_QUAD_BICUBIC
pipeline_version = 1
locked Pillow version = 12.3.0
```

`pipeline_id` accepts only `PILLOW_QUAD_BICUBIC` in V1. `pipeline_version` accepts only integer `1`. There is no hidden default pipeline. The command supplies the pipeline version explicitly. The service validates it before storage access. A future rendering algorithm or Pillow transform change requires a new pipeline version. Do not change the Pillow dependency or `uv.lock` in this PR.

### Exact future dataclasses

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

Invariants: all IDs use existing `EntityId`; timestamp is timezone-aware and normalized to UTC; dimensions are positive integers; revision is positive; revision `1` requires `superseded_recipe_version_id is None`; revision greater than `1` requires a non-null superseded ID; coordinate space is exactly `SOURCE_EFFECTIVE_PIXELS_V1`; pipeline identity is exactly `PILLOW_QUAD_BICUBIC` version `1`; quarter turn is one of 0, 90, 180 or 270; recipe contains no filename, path, hash, pixels, thumbnail, OCR, PII, exception text or arbitrary metadata; `repr` is deterministic and PII-safe.

### Exact coordinate semantics

Coordinates are integer pixel-edge coordinates in the orientation-normalized effective raster. Origin `(0, 0)` is the outer top-left boundary of the raster. x increases right and y increases down. Valid x range is `0 <= x <= source_effective_width`. Valid y range is `0 <= y <= source_effective_height`. `(width, height)` is the outer bottom-right boundary, not a pixel center. The full-frame quadrilateral is `(0,0), (width,0), (width,height), (0,height)`. Coordinates never refer to a UI preview or compressed artifact. Preview coordinates must be converted before command creation. Original bytes are never rewritten. The command contains `expected_source_effective_width` and `expected_source_effective_height`; the service compares them with decoded dimensions and fails with `SOURCE_DIMENSIONS_MISMATCH` when they differ.

### Exact quadrilateral validation math

Canonical project order is `top_left`, `top_right`, `bottom_right`, `bottom_left`. Validation order is: validate field types; validate coordinate bounds; reject duplicate points; compute signed shoelace area; require clockwise order in the y-down coordinate system; reject non-adjacent edge intersections; require strict convexity; enforce minimum area; derive output dimensions; enforce minimum output dimensions.

Using canonical points `p0..p3`, calculate `signed_twice_area = Σ(x_i * y_(i+1) - y_i * x_(i+1))` with index modulo four. For the y-down coordinate system, `signed_twice_area > 0` means clockwise, `signed_twice_area <= 0` is rejected, exact zero is degenerate, minimum accepted area is 4 square effective pixels, therefore `signed_twice_area >= 8`. Use integer arithmetic for cross products and shoelace calculations.

For every consecutive triple, calculate the 2D cross product. All four cross products must be strictly positive in the y-down canonical clockwise order. Zero rejects collinear adjacent edges. Mixed signs reject non-convex ordering.

Reject intersections between `top_left → top_right` against `bottom_right → bottom_left` and `top_right → bottom_right` against `bottom_left → top_left`. Use deterministic integer orientation tests. Adjacent edges sharing their declared endpoint are allowed.

### Exact output dimensions

Calculate Euclidean edge lengths: `distance(a, b) = sqrt((b.x - a.x)^2 + (b.y - a.y)^2)`. Use a local Decimal context with `precision = 28` and `rounding = ROUND_HALF_UP`; do not mutate the process-global Decimal context.

Calculate `unrounded_width = max(distance(top_left, top_right), distance(bottom_left, bottom_right))` and `unrounded_height = max(distance(top_left, bottom_left), distance(top_right, bottom_right))`. Quantize each maximum exactly once to an integer using `ROUND_HALF_UP`. Do not round individual opposite edges before selecting the maximum. Both rectified dimensions must be at least `2`. For 90° and 270° clockwise quarter-turns, final result width and height are swapped. No caller-supplied output dimensions are permitted in V1.

### Exact decoded geometry media contract

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
```

Invariants: encoded/effective dimensions are positive; orientation is `None` or 1–8; effective dimension axis rules match the accepted PR-009 EXIF contract; `len(rgb_pixels) == effective_width * effective_height * 3`; pixel layout is packed row-major RGB with exactly three unsigned bytes per pixel; no metadata, filename, path, hash or exception text; EXIF orientation has already been applied exactly once; no later adapter applies EXIF again.

### Exact internal render result

```python
@dataclass(frozen=True, slots=True)
class RenderedGeometryRaster:
    width: int
    height: int
    rgb_pixels: bytes
    pipeline: GeometryPipelineVersion
```

Invariants: positive dimensions; `len(rgb_pixels) == width * height * 3`; pipeline is exactly V1; no encoded JPEG; no EXIF or arbitrary metadata; raster bytes are internal and ephemeral; raster bytes are not persisted by PR-010; raster bytes are not returned by the application result DTO.

### Exact Protocol signatures

```python
class GeometryDecoderPort(Protocol):
    def decode_for_geometry(
        self,
        *,
        content: bytes,
    ) -> DecodedGeometryMedia: ...
```

```python
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

Do not merge geometry decoding into the 9×8 import decoder. Do not derive RGB geometry pixels from PR-009 grayscale pixels. The accepted Pillow decoder may implement the new port while preserving all PR-008 and PR-009 behavior.

### Exact Pillow rendering contract

The V1 renderer reconstructs an RGB Pillow image from packed RGB bytes; calls `Image.transform`; uses `Image.Transform.QUAD`; uses `Image.Resampling.BICUBIC`; uses `fill=1`; uses `fillcolor=(255, 255, 255)`; uses the derived pre-rotation output dimensions; emits RGB mode; and preserves no metadata.

Project canonical quadrilateral is `TL, TR, BR, BL`. Pillow `QUAD` source order is `upper-left, lower-left, lower-right, upper-right`. The exact conversion is:

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

Do not pass project canonical order directly to Pillow.

Exact clockwise quarter-turn mapping after the QUAD transform: 0° clockwise uses no transpose; 90° clockwise uses `Image.Transpose.ROTATE_270`; 180° clockwise uses `Image.Transpose.ROTATE_180`; 270° clockwise uses `Image.Transpose.ROTATE_90`. Do not use arbitrary-angle `rotate()`. Do not use OpenCV. Do not use `LANCZOS`, `BILINEAR` or `NEAREST` for V1 geometry rendering. A resampling or transform-mode change requires a new geometry pipeline version.

### Exact command and result DTOs

```python
@dataclass(frozen=True, slots=True)
class CreateImageGeometryRecipeCommand:
    recipe_version_id: EntityId
    source_file_id: EntityId
    superseded_recipe_version_id: EntityId | None
    revision: int
    expected_source_effective_width: int
    expected_source_effective_height: int
    quadrilateral: SourceQuadrilateral
    quarter_turn: GeometryQuarterTurn
    pipeline: GeometryPipelineVersion
    created_at: datetime
    actor: ActorRef
    audit_event_id: EntityId
    correlation_id: EntityId
```

Required validation: caller supplies every field; no generated UUID; no system clock; no inferred actor; no inferred correlation; no hidden pipeline default; `recipe_version_id != audit_event_id`; all timestamps UTC-normalized; expected dimensions positive; pipeline validated before storage access.

```python
@dataclass(frozen=True, slots=True)
class CreateImageGeometryRecipeResult:
    recipe: ImageGeometryRecipe
    rendered_width: int
    rendered_height: int
    pipeline: GeometryPipelineVersion
```

The result excludes RGB bytes, encoded image bytes, filename, path, hash, thumbnail, OCR, personal fields, arbitrary metadata and raw exceptions.

### Exact repository and Unit of Work contract

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

Exact list order is revision ascending, created-at ascending, recipe-version ID ascending. Revision-chain rule: no current recipe requires revision `1` and superseded ID `None`; when a current latest recipe exists, the new revision equals latest revision + 1 and superseded ID equals latest recipe ID; otherwise fail with `REVISION_CONFLICT`. No branching history is allowed.

```python
class UnitOfWork(Protocol):
    ...
    image_geometry_recipes: ImageGeometryRecipeRepository
```

Do not create a standalone database connection, independent recipe repository factory or separate audit transaction.

### Exact service signature and return order

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

Binding order: validate command, pipeline and primitive/domain invariants; create exactly one Unit of Work; load source file; load stored original artifact record; read and verify immutable original through `StoragePort`; decode geometry media; compare decoded dimensions with command expected dimensions; validate quadrilateral; derive pre-rotation dimensions; render internal RGB raster; validate rendered dimensions and byte length; load current latest recipe for the source; validate revision and superseded-recipe chain; construct immutable `ImageGeometryRecipe`; add recipe through `uow.image_geometry_recipes`; construct exact PII-safe audit event; add audit through `uow.audit_events`; call `uow.commit()` exactly once; exit the Unit of Work successfully; only then construct and return `CreateImageGeometryRecipeResult`. Do not document or implement a return before persistence. Any failure before successful commit returns no result, commits no recipe, commits no audit event and does not alter the original.

### Exact audit contract

The exact future audit action is `AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED`. The exact future subject type is `AuditSubjectType.IMAGE_GEOMETRY_RECIPE`. The subject ID is `recipe_version_id`. The reason code is `IMAGE_GEOMETRY_RECIPE_CREATED`. The non-sensitive after summary is `IMAGE_GEOMETRY_RECIPE`. Do not use `or an equivalent action`. The audit event must not contain coordinates, dimensions, filename, path, hashes, source bytes, rendered bytes, thumbnails, OCR, PII or raw exceptions.

### Exact persistence proposal

Migration staging remains `v0006_image_geometry`; do not create it in this PR. The future table is `image_geometry_recipes` with columns `recipe_version_id`, `source_file_id`, `superseded_recipe_version_id`, `revision`, `coordinate_space`, `source_effective_width`, `source_effective_height`, `quarter_turn_clockwise`, all eight quadrilateral coordinates, `geometry_pipeline_id`, `geometry_pipeline_version`, `created_at_utc` and `canonical_payload`.

Required constraints: primary key on recipe version ID; source-file foreign key; nullable self foreign key; unique `(source_file_id, revision)`; unique non-null `superseded_recipe_version_id`; positive revision and dimensions; coordinate space exactly `SOURCE_EFFECTIVE_PIXELS_V1`; quarter turn exactly 0/90/180/270; pipeline exactly `PILLOW_QUAD_BICUBIC`, version 1; x coordinates in `0..source_effective_width`; y coordinates in `0..source_effective_height`; update prohibited; delete prohibited; replace prohibited; projection/canonical-payload equality; strict controlled-value deserialization; corruption detected before filtering or returning results. Frozen migrations v0001 through v0005 remain unchanged.

PR-010 PRODUCTION IMPLEMENTATION is UNAUTHORIZED in this exact V1 contract completion.
