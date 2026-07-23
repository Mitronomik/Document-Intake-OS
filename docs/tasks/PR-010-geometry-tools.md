# PR-010 — Geometry Tools Contract

**Status:** CONTRACT PROPOSED; PRODUCTION IMPLEMENTATION NOT AUTHORIZED

## 1. Status and lifecycle boundary

PR #26 is merged successfully. Final reviewed head: `cc79a80fcacdbde2667cae858815b30176f87555`. Merge commit: `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`. Merge date: `2026-07-23`. Exact-head CI: `CI #129`, run ID `29972502518`, conclusion `success`. PR-009 lifecycle documentation and test corrections delivered through PR #26 are completed and human accepted.

ADR-024 is PROPOSED. PR-010 CONTRACT is PROPOSED FOR HUMAN REVIEW. PR-010 PRODUCTION IMPLEMENTATION is UNAUTHORIZED. PR-011 AND LATER are UNAUTHORIZED. Gate 2 is NOT ACCEPTED. M3 is IN PROGRESS. Q-021 remains DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. No production PR-009 quality policy is active; production `policy_id` and `policy_version` are NOT ASSIGNED; automatic PR-009 quality-based document blocking and production `RETAKE_REQUIRED` enforcement are NOT ACTIVE.

## 2. Verified implementation base rule

This documentation-contract PR is based on `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`.

Future PR-010 production implementation must branch from the exact merge commit of this documentation-contract PR. Placeholder: `PR-010 implementation base = <FILL ONLY AFTER THIS CONTRACT PR MERGE COMMIT EXISTS>`. Do not invent this SHA before merge.

## 3. Goal

Define an implementation-ready, deterministic, non-UI geometry recipe contract for one manually selected document area from one immutable source file, without implementing production code in this PR.

## 4. Exact scope

Manual source quadrilateral; axis-aligned crop as rectangular quadrilateral; perspective correction; coarse clockwise quarter-turn output rotation; immutable versioned geometry recipe; deterministic synthetic rendering; recipe persistence; application service integration; audit integration.

## 5. Deferred scope

PR-011 compression and prepared-JPEG publication; PR-012 multiple independently confirmed document regions, document count and region workflow; PR-013 side merge/final prepared document flow; UI controls; OCR; Excel; terminal rules; production quality-policy activation.

## 6. Existing accepted contracts that must remain unchanged

Preserve immutable original storage; PR-008 media detection; PR-008 primary-frame behavior; accepted MPO-as-JPEG handling; DHASH64 behavior and frozen vectors; PR-009 EXIF interpretation; PR-009 full-resolution quality decoder behavior; PR-009 V1 metric identities and formulas; PR-009 persisted quality assessments; Q-021 deferred state; explicit-policy quality infrastructure; existing audit immutability; existing Unit of Work atomicity; existing SQLCipher boundary; frozen migrations v0001 through v0005. PR-010 must not use or activate a hidden production PR-009 quality policy. Quality status must not automatically block creation of a manual geometry recipe in PR-010.

## 7. Exact coordinate system

Use `SOURCE_EFFECTIVE_PIXELS_V1`. Coordinates refer to full-resolution imported source content after accepted EXIF orientation is applied exactly once for the geometry working view. `(0, 0)` is the top-left of the effective pixel grid, x increases right, y increases downward. Coordinates never refer to a UI preview, scaled display, viewport, zoom, screen coordinate, prepared artifact or compressed artifact. Original encoded bytes remain immutable. Future UI must convert preview coordinates to `SOURCE_EFFECTIVE_PIXELS_V1` before creating commands.

## 8. Exact geometry recipe domain contract

A V1 immutable recipe has recipe version ID, source file ID, optional superseded recipe version ID, positive revision, coordinate-space identifier, source effective width and height, coarse clockwise quarter-turn, canonical source quadrilateral, geometry pipeline ID, geometry pipeline version and UTC creation timestamp. It excludes filenames, paths, source/rendered bytes, thumbnails, UI viewport state, zoom, raw exceptions, arbitrary metadata, OCR data and personal fields. Each operator change creates a new append-only recipe version; no update/delete/replace is allowed.

Canonical corner order is exactly `top_left`, `top_right`, `bottom_right`, `bottom_left`.

## 9. Exact decoder and renderer port contracts

Extend the accepted decoder boundary to decode full-resolution immutable source bytes for geometry and apply EXIF exactly once. The renderer uses Pillow, produces RGB internal raster output, strips EXIF/geolocation/comments/ICC/arbitrary metadata, and uses the fixed V1 rendering contract: `Image.Transform.QUAD`, `Image.Resampling.BICUBIC`, `fill=1`, `fillcolor=(255, 255, 255)`, and TL/BL/BR/TR Pillow source order conversion. Do not add OpenCV, cloud libraries, network calls or a second image stack. PR-010 does not publish a final JPEG.

## 10. Exact application command and result DTO contracts

The future command must contain caller-supplied recipe version ID, source file ID, optional superseded recipe version ID, revision, quadrilateral, quarter-turn, created-at timestamp, actor, audit event ID and correlation ID. The success result returns an immutable recipe plus internal geometry-render result metadata such as final dimensions and geometry pipeline identity; it must not expose bytes, paths, filenames, OCR, personal fields or raw exceptions.

## 11. Exact service contract

The service must not generate UUIDs, read the system clock, infer actor, infer correlation ID, infer geometry from the image, select a hidden default crop or silently correct invalid points. It must use the accepted storage port, decoder port extension, Unit of Work factory, recipe repository and audit repository.

## 12. Exact transformation order

1. Read immutable original bytes through accepted storage.
2. Verify stored object through accepted storage boundary.
3. Decode full-resolution source.
4. Apply EXIF orientation exactly once.
5. Validate source effective dimensions.
6. Validate source quadrilateral.
7. Perspective-crop to rectangular RGB raster.
8. Apply coarse clockwise quarter-turn rotation.
9. Return internal geometry-render result.
10. Persist immutable recipe and audit event atomically.

No step rewrites originals. Do not apply EXIF after step 4.

## 13. Exact validation rules

Require exactly four points; integer source-effective pixel coordinates; all points within source bounds; no duplicate points; positive area; convex shape; no self-intersection; canonical clockwise corner order; deterministic validation errors; quarter-turn only 0/90/180/270 clockwise; derived dimensions at least 2 pixels.

## 14. Exact output-dimension derivation

Before rotation, output width is the greater of top and bottom edge lengths; output height is the greater of left and right edge lengths. Convert with deterministic round-half-up integer conversion. For 90 and 270 degrees clockwise, swap final width and height. V1 does not accept caller-supplied arbitrary output dimensions and does not rescale to terminal dimensions.

## 15. Exact persistence contract

Persistence is append-only in SQLCipher through the accepted Unit of Work. Deterministic list order is by source file ID, revision, created-at, recipe version ID unless a narrower query states otherwise. Rehydration must compare canonical payload and projections and detect corruption. Updates, deletes and replacements are prohibited.

## 16. Proposed migration v0006 contract

Future migration: `v0006_image_geometry`. Do not create it in this documentation-only PR. Proposed table `image_geometry_recipes`: `recipe_version_id` primary key; `source_file_id` foreign key to `source_files`; nullable `superseded_recipe_version_id` self-reference; `revision`; `coordinate_space`; `source_effective_width`; `source_effective_height`; `quarter_turn_clockwise`; integer `top_left_x`, `top_left_y`, `top_right_x`, `top_right_y`, `bottom_right_x`, `bottom_right_y`, `bottom_left_x`, `bottom_left_y`; `geometry_pipeline_id`; `geometry_pipeline_version`; `created_at_utc`; `canonical_payload`. Constraints: positive revision and dimensions, coordinate space exactly `SOURCE_EFFECTIVE_PIXELS_V1`, quarter turn in 0/90/180/270, immutable triggers preventing update/delete, source-file relationship, superseded-recipe relationship, unique `(source_file_id, revision)`, canonical payload/projection equality checks, corruption detection during rehydration. Frozen migrations v0001 through v0005 must not change.

## 17. Unit of Work and atomicity

Recipe persistence and audit insertion occur in one Unit of Work transaction with one commit. Any failure before successful commit leaves no committed recipe and no committed audit row. Do not use a separate transaction, automatic repository commit or independent audit connection.

## 18. Audit-event contract

Future controlled action: `IMAGE_GEOMETRY_RECIPE_CREATED`. Audit is PII-safe and may include controlled entity IDs and recipe version metadata. It must not include filename, local path, original bytes, rendered bytes, thumbnail, full quadrilateral coordinates, arbitrary metadata, raw exception, OCR values or personal data.

## 19. Controlled error contract

Typed controlled failures: source file not found; immutable stored object missing; stored-object integrity failure; unsupported decode; geometry decode failure; source-dimension mismatch; point outside bounds; duplicate point; self-intersecting quadrilateral; non-convex quadrilateral; zero or insufficient area; derived output too small; invalid quarter-turn; revision conflict; persistence conflict; audit persistence failure; render failure. Error DTOs, logs and audit records remain PII-safe.

## 20. Expected future implementation files

Expected new production files are staged as `src/document_intake/domain/image_geometry.py`, `src/document_intake/image_pipeline/geometry_transformer.py`, `src/document_intake/application/dto/image_geometry.py`, `src/document_intake/application/services/image_geometry.py`, `src/document_intake/persistence/repositories/image_geometry.py`, `src/document_intake/persistence/migrations/v0006_image_geometry.py` and `scripts/verify_pr010_geometry.py`.

Expected existing integration files are `src/document_intake/application/ports/media.py`, `src/document_intake/application/ports/persistence.py`, `src/document_intake/application/ports/storage.py`, `src/document_intake/persistence/unit_of_work.py`, `src/document_intake/persistence/database.py`, `src/document_intake/persistence/repositories.py`, `src/document_intake/persistence/serialization.py`, `src/document_intake/persistence/migrations/__init__.py`, `src/document_intake/domain/enums.py`, `src/document_intake/domain/entities/audit.py`, package `__init__.py` exports and tests under `tests/application`, `tests/domain`, `tests/image_pipeline` and `tests/persistence`. This documentation-only PR creates none of those production files.

## 21. Exact test plan

Synthetic-only tests must cover immutable original checksum before/after success and every failure; EXIF orientation 1 through 8 exactly once; asymmetric images detecting double orientation; source-effective mapping; axis-aligned rectangular crop; non-axis-aligned perspective correction; canonical TL/TR/BR/BL ordering; clockwise quarter-turn 0/90/180/270; width/height swap for 90/270; deterministic dimension derivation; round-half-up edge conversion; colored-corner and grid-line mapping; point-out-of-bounds, duplicate, self-intersection, non-convex, zero-area, output-too-small, invalid rotation and revision-conflict rejection; append-only persistence; no update/delete/replace; canonical-payload/projection equality; corruption detection; deterministic repository ordering; audit and recipe atomicity; rollback on render, recipe persistence and audit failure; PII-safe DTOs/errors; no paths or filenames in logs; no coordinates in audit payload; no image bytes in persistence; no network access; deterministic rerun; preservation of every PR-008 and PR-009 regression test.

## 22. Synthetic fixture rules

The future verifier and tests must use generated synthetic raster data only. No real document, document-derived crop, photograph, scan, OCR payload or personal data may be used.

## 23. Manual verification

Future local manual verification uses a generated synthetic image only. It verifies visible corner mapping, crop boundaries, perspective rectification, clockwise rotation, output dimensions, unchanged original checksum, no original overwrite, recipe persistence, audit insertion, deterministic rerun and controlled invalid-geometry failure. Manual verification in this contract PR is documentation only; no real-photo or Windows 11 pilot occurred.

## 24. Acceptance criteria

Accept only when coordinate space is unambiguous; EXIF is applied exactly once; originals remain immutable; transformation order is fixed; recipe versions are append-only; persistence and audit are atomic; no final JPEG is produced; PR-011, PR-012 and PR-013 boundaries are preserved; PR-010 production implementation remains unauthorized; documentation tests and repository policy pass; no production code, real documents or personal data are added.

## 25. Non-goals

No production code in this PR; no UI; no drag handles; no batch UI; no automatic boundary detection; no automatic perspective detection; no automatic deskew; no automatic crop; no multiple document regions; no document count; no image classification; no final prepared artifact publication; no JPEG encoding; no compression; no 1.90 MiB enforcement; no readability acceptance; no front/back merging; no terminal rules; no Excel; no OCR; no cloud APIs; no telemetry; no real documents; no production quality-policy activation; no Q-021 resolution; no PR-011 or later implementation.

## 26. Security and privacy prohibitions

Do not log complete identity numbers, phones, addresses, OCR payloads, MRZ, filenames, local paths, image bytes, thumbnails, full quadrilateral coordinates or raw exceptions. Do not upload data, add telemetry, add cloud OCR/storage/AI APIs, commit real documents or commit personal data.

## 27. Future implementation authorization boundary

This contract does not authorize production implementation. Merging this PR only records a proposed contract for human review. PR-010 production implementation may be authorized only by a separate explicit product-owner decision after this contract is reviewed and merged. PR-011 AND LATER remain UNAUTHORIZED.

## Exact contract completion addendum

This task incorporates the exact ADR-024 V1 contract and leaves no `Exact` section to future interpretation.

### Exact domain enum staging

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

`pipeline_id = PILLOW_QUAD_BICUBIC`; `pipeline_version = 1`; locked Pillow version is `12.3.0`. The command supplies `GeometryPipelineVersion` explicitly and the service validates it before storage access.

### Exact dataclass staging

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


@dataclass(frozen=True, slots=True)
class CreateImageGeometryRecipeResult:
    recipe: ImageGeometryRecipe
    rendered_width: int
    rendered_height: int
    pipeline: GeometryPipelineVersion
```

All IDs use existing `EntityId`; actor uses existing `ActorRef`; timestamps are timezone-aware UTC; dimensions and revision are positive; revision `1` requires `superseded_recipe_version_id is None`; revision greater than `1` requires a non-null superseded ID; `recipe_version_id != audit_event_id`; recipe/result/DTO reprs are deterministic and PII-safe. `CreateImageGeometryRecipeResult` excludes `rgb_pixels`, encoded image bytes, filename, path, hash, thumbnail, OCR, personal fields, arbitrary metadata and raw exceptions.

### Exact coordinate and geometry math staging

Coordinates are integer pixel-edge coordinates. Valid x range is `0 <= x <= source_effective_width`; valid y range is `0 <= y <= source_effective_height`. `(width, height)` is the outer bottom-right boundary. Full-frame quadrilateral is `(0,0), (width,0), (width,height), (0,height)`. The command includes `expected_source_effective_width` and `expected_source_effective_height`; mismatch with decoded dimensions fails with `SOURCE_DIMENSIONS_MISMATCH`.

Validation order: field types; coordinate bounds; duplicate points; signed shoelace area; clockwise order in y-down coordinates; non-adjacent edge intersections; strict convexity; minimum area; output dimensions; minimum output dimensions. `signed_twice_area = Σ(x_i * y_(i+1) - y_i * x_(i+1))`; y-down clockwise requires `signed_twice_area > 0`; accepted minimum area is 4 square effective pixels, therefore `signed_twice_area >= 8`. All four consecutive-triple cross products are strictly positive. Reject `top_left → top_right` against `bottom_right → bottom_left` and `top_right → bottom_right` against `bottom_left → top_left` when non-adjacent edges intersect.

Output dimensions use Euclidean distance with local Decimal `precision = 28` and `rounding = ROUND_HALF_UP`. Compute `unrounded_width = max(distance(top_left, top_right), distance(bottom_left, bottom_right))` and `unrounded_height = max(distance(top_left, bottom_left), distance(top_right, bottom_right))`; quantize each maximum once; minimum rectified dimensions are `2`; 90°/270° clockwise swap final width/height; V1 accepts no caller-supplied output dimensions.

### Exact Protocol, renderer, repository and Unit of Work staging

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


class UnitOfWork(Protocol):
    ...
    image_geometry_recipes: ImageGeometryRecipeRepository
```

Do not merge geometry decoding into the 9×8 import decoder. Do not derive RGB geometry pixels from PR-009 grayscale pixels. Repository list order is revision ascending, created-at ascending, recipe-version ID ascending. Revision-chain rule: no latest recipe requires revision 1 and superseded ID `None`; otherwise new revision equals latest revision + 1 and superseded ID equals latest recipe ID; no branching history; failure is `REVISION_CONFLICT`.

The Pillow renderer uses `Image.transform`, `Image.Transform.QUAD`, `Image.Resampling.BICUBIC`, `fill=1`, `fillcolor=(255, 255, 255)`, RGB output and no metadata. Project canonical order is `TL, TR, BR, BL`; Pillow `QUAD` source order is `upper-left, lower-left, lower-right, upper-right`; conversion is:

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

Clockwise mapping after QUAD: 0° no transpose; 90° `Image.Transpose.ROTATE_270`; 180° `Image.Transpose.ROTATE_180`; 270° `Image.Transpose.ROTATE_90`. Do not use `rotate()`, OpenCV, `LANCZOS`, `BILINEAR` or `NEAREST`.

### Exact service, audit and persistence staging

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

Binding order: validate command/pipeline/invariants; create one Unit of Work; load source file; load stored original artifact record; read and verify immutable original through `StoragePort`; decode geometry media; compare decoded dimensions with expected dimensions; validate quadrilateral; derive pre-rotation dimensions; render internal RGB raster; validate rendered dimensions and byte length; load latest recipe; validate revision chain; construct `ImageGeometryRecipe`; add through `uow.image_geometry_recipes`; construct audit; add through `uow.audit_events`; call `uow.commit()` exactly once; exit Unit of Work; only then construct and return `CreateImageGeometryRecipeResult`. Any failure before commit returns no result, commits no recipe/audit and does not alter the original.

Audit action is exactly `AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED`; subject type exactly `AuditSubjectType.IMAGE_GEOMETRY_RECIPE`; subject ID `recipe_version_id`; reason code `IMAGE_GEOMETRY_RECIPE_CREATED`; non-sensitive after summary `IMAGE_GEOMETRY_RECIPE`; no coordinates, dimensions, filename, path, hashes, source bytes, rendered bytes, thumbnails, OCR, PII or raw exceptions.

Future migration `v0006_image_geometry` table `image_geometry_recipes` has `recipe_version_id`, `source_file_id`, `superseded_recipe_version_id`, `revision`, `coordinate_space`, `source_effective_width`, `source_effective_height`, `quarter_turn_clockwise`, all eight quadrilateral coordinates, `geometry_pipeline_id`, `geometry_pipeline_version`, `created_at_utc`, `canonical_payload`; constraints include primary key, source-file foreign key, nullable self foreign key, unique `(source_file_id, revision)`, unique non-null `superseded_recipe_version_id`, positive revision/dimensions, exact coordinate space, exact quarter turn, exact pipeline, x/y coordinate ranges, update/delete/replace prohibition, projection/canonical-payload equality, strict controlled-value deserialization and corruption detection before filtering/return.

### Exact future integration files

Staged new production files: `src/document_intake/domain/image_geometry.py`; `src/document_intake/image_pipeline/geometry_transformer.py`; `src/document_intake/application/dto/image_geometry.py`; `src/document_intake/application/services/image_geometry.py`; `src/document_intake/persistence/repositories/image_geometry.py`; `src/document_intake/persistence/migrations/v0006_image_geometry.py`; `scripts/verify_pr010_geometry.py`.

Staged existing integration files: `src/document_intake/application/ports/media.py`; `src/document_intake/application/ports/persistence.py`; `src/document_intake/application/ports/storage.py`; `src/document_intake/persistence/unit_of_work.py`; `src/document_intake/persistence/database.py`; `src/document_intake/persistence/repositories.py`; `src/document_intake/persistence/serialization.py`; `src/document_intake/persistence/migrations/__init__.py`; `src/document_intake/domain/enums.py`; `src/document_intake/domain/entities/audit.py`; `src/document_intake/__init__.py`; `src/document_intake/application/dto/__init__.py`; `src/document_intake/application/services/__init__.py`; `src/document_intake/image_pipeline/__init__.py`; `src/document_intake/persistence/__init__.py`; `tests/domain/test_image_geometry.py`; `tests/image_pipeline/test_geometry_transformer.py`; `tests/application/test_image_geometry_service.py`; `tests/persistence/test_image_geometry_repository.py`; `tests/test_verify_pr010_geometry.py`.

PR-010 PRODUCTION IMPLEMENTATION is UNAUTHORIZED in this exact contract completion addendum.
