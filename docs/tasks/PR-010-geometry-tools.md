# PR-010 — Geometry Tools Contract

**Status:** CONTRACT ACCEPTED; PRODUCTION IMPLEMENTATION AUTHORIZED AND IN REVIEW

## 1. Status and lifecycle boundary

PR #26 is merged successfully. Final reviewed head: `cc79a80fcacdbde2667cae858815b30176f87555`. Merge commit: `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`. Merge date: `2026-07-23`. Exact-head CI: `CI #129`, run ID `29972502518`, conclusion `success`. PR-009 lifecycle documentation and test corrections delivered through PR #26 are completed and human accepted.

ADR-024 is ACCEPTED by Product owner on 2026-07-23. PR-010 CONTRACT is ACCEPTED. PR-010 PRODUCTION IMPLEMENTATION is AUTHORIZED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-011 AND LATER are UNAUTHORIZED. Gate 2 is NOT ACCEPTED. M3 is IN PROGRESS. Q-021 remains DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. No production PR-009 quality policy is active; production `policy_id` and `policy_version` are NOT ASSIGNED; automatic PR-009 quality-based document blocking and production `RETAKE_REQUIRED` enforcement are NOT ACTIVE.

## 2. Verified implementation base rule

The historical documentation-contract PR was based on `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`.

The current PR-010 production implementation is based on accepted contract merge commit `329dd5653a3faadd3c62387c1d900710f14b2f4e`. This implementation is in review, not completed and not human accepted.

## 3. Goal

Implement the accepted deterministic, non-UI geometry recipe contract for one manually selected document area from one immutable source file. PR-010 does not publish a final JPEG.

## 4. Exact scope

Manual source quadrilateral; axis-aligned crop as rectangular quadrilateral; perspective correction; coarse clockwise quarter-turn output rotation; immutable versioned geometry recipe; deterministic synthetic rendering; recipe persistence; application service integration; audit integration.

## 5. Deferred scope

PR-011 compression and prepared-JPEG publication; PR-012 multiple independently confirmed document regions, document count and region workflow; PR-013 side merge/final prepared document flow; UI controls; OCR; Excel; terminal rules; production quality-policy activation.

## 6. Existing accepted contracts that must remain unchanged

Preserve immutable original storage; PR-008 media detection; PR-008 primary-frame behavior; accepted MPO-as-JPEG handling; DHASH64 behavior and frozen vectors; PR-009 EXIF interpretation; PR-009 full-resolution quality decoder behavior; PR-009 V1 metric identities and formulas; PR-009 persisted quality assessments; Q-021 deferred state; explicit-policy quality infrastructure; existing audit immutability; existing Unit of Work atomicity; existing SQLCipher boundary; frozen migrations v0001 through v0005. PR-010 must not use or activate a hidden production PR-009 quality policy. Quality status must not automatically block creation of a manual geometry recipe in PR-010.

## 7. Exact coordinate system

The only authoritative V1 coordinate model is `SOURCE_EFFECTIVE_PIXELS_V1`.

Coordinates are integer pixel-edge coordinates in the full-resolution, EXIF-normalized effective raster. `(0, 0)` is the outer top-left boundary of the raster. x increases right. y increases down. Valid x range is `0 <= x <= source_effective_width`. Valid y range is `0 <= y <= source_effective_height`. `(source_effective_width, source_effective_height)` is the outer bottom-right boundary, not a pixel center. The full-frame quadrilateral is `(0, 0)`, `(width, 0)`, `(width, height)`, `(0, height)`.

Coordinates never refer to a scaled UI preview, viewport, zoom, screen coordinate, prepared artifact or compressed artifact. Preview coordinates must be converted before command construction. Original bytes remain immutable. EXIF is applied exactly once. The command supplies `expected_source_effective_width` and `expected_source_effective_height`; the service compares them with decoded effective dimensions after decode and fails with `SOURCE_DIMENSIONS_MISMATCH` when they differ.

## 8. Exact geometry recipe domain contract

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

## 9. Exact decoder and renderer port contracts

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

## 10. Exact application command and result DTO contracts

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


@dataclass(frozen=True, slots=True)
class CreateImageGeometryRecipeResult:
    recipe: ImageGeometryRecipe
    rendered_width: int
    rendered_height: int
    pipeline: GeometryPipelineVersion
```

Caller supplies every field. The command uses no generated UUID, no system clock, no inferred actor, no inferred correlation and no hidden pipeline default. `recipe_version_id != audit_event_id`; timestamps are UTC-normalized; expected dimensions are positive; pipeline is validated before storage access. The result excludes RGB bytes, encoded image bytes, filename, path, hash, thumbnail, OCR, personal fields, arbitrary metadata and raw exceptions.

## 11. Exact service contract

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

## 12. Exact transformation order

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

## 13. Exact validation rules

Canonical project order is `top_left`, `top_right`, `bottom_right`, `bottom_left`. Validation order is: field types; coordinate bounds; duplicate points; signed shoelace area; clockwise order in y-down coordinates; non-adjacent edge intersections; strict convexity; minimum area; output dimensions; minimum output dimensions.

`signed_twice_area = Σ(x_i * y_(i+1) - y_i * x_(i+1))` with index modulo four. In the y-down coordinate system, `signed_twice_area > 0` means clockwise; `signed_twice_area <= 0` is rejected; exact zero is degenerate; minimum accepted area is four square effective pixels, therefore `signed_twice_area >= 8`. Use integer arithmetic for cross products and shoelace calculations.

All four consecutive-triple cross products must be strictly positive. Zero rejects collinear adjacent edges; mixed signs reject non-convex ordering. Reject non-adjacent intersections between `top_left → top_right` and `bottom_right → bottom_left`, and between `top_right → bottom_right` and `bottom_left → top_left`, using deterministic integer orientation tests.

## 14. Exact output-dimension derivation

Calculate Euclidean edge lengths with `distance(a, b) = sqrt((b.x - a.x)^2 + (b.y - a.y)^2)`. Use a local Decimal context with `precision = 28` and `rounding = ROUND_HALF_UP`; do not mutate the process-global Decimal context.

`unrounded_width = max(distance(top_left, top_right), distance(bottom_left, bottom_right))`. `unrounded_height = max(distance(top_left, bottom_left), distance(top_right, bottom_right))`. Quantize each maximum exactly once using `ROUND_HALF_UP`; do not round individual opposite edges before selecting the maximum. Both rectified dimensions must be at least `2`. For 90° and 270° clockwise quarter-turns, final width and height are swapped. No caller-supplied output dimensions are permitted in V1.

## 15. Exact persistence contract

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

## 16. Proposed migration v0006 contract

Future migration `v0006_image_geometry` is staged only; do not create it in this PR. Future table `image_geometry_recipes` columns are `recipe_version_id`, `source_file_id`, `superseded_recipe_version_id`, `revision`, `coordinate_space`, `source_effective_width`, `source_effective_height`, `quarter_turn_clockwise`, all eight quadrilateral coordinates, `geometry_pipeline_id`, `geometry_pipeline_version`, `created_at_utc` and `canonical_payload`.

Required constraints: primary key; source-file foreign key; nullable self foreign key; unique `(source_file_id, revision)`; unique non-null `superseded_recipe_version_id`; positive revision and dimensions; coordinate space exactly `SOURCE_EFFECTIVE_PIXELS_V1`; quarter turn exactly 0/90/180/270; pipeline exactly `PILLOW_QUAD_BICUBIC`, version 1; x coordinates in `0..source_effective_width`; y coordinates in `0..source_effective_height`; update prohibited; delete prohibited; replace prohibited; projection/canonical-payload equality; strict controlled-value deserialization; corruption detected before filtering or returning results. Frozen migrations v0001 through v0005 remain unchanged.

## 17. Unit of Work and atomicity

```python
class UnitOfWork(Protocol):
    ...
    image_geometry_recipes: ImageGeometryRecipeRepository
```

Use exactly one Unit of Work and exactly one `uow.commit()`. Recipe persistence and audit insertion are in the same transaction. Do not create a standalone database connection, independent repository factory, independent audit connection, separate transaction or automatic repository commit. No application result is constructed or returned before the successful Unit of Work commit and exit.

## 18. Audit-event contract

The exact audit action is `AuditAction.IMAGE_GEOMETRY_RECIPE_CREATED`. The exact audit subject type is `AuditSubjectType.IMAGE_GEOMETRY_RECIPE`. Subject ID is `recipe_version_id`. Reason code is `IMAGE_GEOMETRY_RECIPE_CREATED`. Non-sensitive after summary is `IMAGE_GEOMETRY_RECIPE`. Audit payload must not contain coordinates, dimensions, filename, path, hashes, source bytes, rendered bytes, thumbnails, OCR, PII or raw exceptions.

## 19. Controlled error contract

Controlled error identity uses `GeometryErrorCode` values only, not free-text messages: `SOURCE_FILE_NOT_FOUND`, `ARTIFACT_NOT_FOUND`, `ARTIFACT_INTEGRITY_FAILED`, `DECODE_FAILED`, `SOURCE_DIMENSIONS_MISMATCH`, `POINT_OUT_OF_BOUNDS`, `DUPLICATE_POINT`, `NON_CLOCKWISE_QUADRILATERAL`, `SELF_INTERSECTING_QUADRILATERAL`, `NON_CONVEX_QUADRILATERAL`, `AREA_TOO_SMALL`, `OUTPUT_DIMENSIONS_TOO_SMALL`, `INVALID_QUARTER_TURN`, `INVALID_PIPELINE_VERSION`, `REVISION_CONFLICT`, `RENDER_FAILED`, `RECIPE_PERSISTENCE_FAILED`, `AUDIT_PERSISTENCE_FAILED` and `COMMIT_FAILED`. Error DTOs, logs and audit records remain PII-safe.

## 20. Expected future implementation files

Staged new production files: `src/document_intake/domain/image_geometry.py`; `src/document_intake/image_pipeline/geometry_transformer.py`; `src/document_intake/application/dto/image_geometry.py`; `src/document_intake/application/services/image_geometry.py`; `src/document_intake/persistence/repositories/image_geometry.py`; `src/document_intake/persistence/migrations/v0006_image_geometry.py`; `scripts/verify_pr010_geometry.py`.

Staged existing integration files: `src/document_intake/application/ports/media.py`; `src/document_intake/application/ports/persistence.py`; `src/document_intake/application/ports/storage.py`; `src/document_intake/persistence/unit_of_work.py`; `src/document_intake/persistence/database.py`; `src/document_intake/persistence/repositories.py`; `src/document_intake/persistence/serialization.py`; `src/document_intake/persistence/migrations/__init__.py`; `src/document_intake/domain/enums.py`; `src/document_intake/domain/entities/audit.py`; package `__init__.py` exports; `tests/domain/test_image_geometry.py`; `tests/image_pipeline/test_geometry_transformer.py`; `tests/application/test_image_geometry_service.py`; `tests/persistence/test_image_geometry_repository.py`; `tests/test_verify_pr010_geometry.py`. Do not create these files in this documentation-only PR.

## 21. Exact test plan

Synthetic-only tests must cover immutable original checksum before/after success and every failure; EXIF orientation 1 through 8 exactly once; asymmetric images detecting double orientation; source-effective mapping; axis-aligned rectangular crop; non-axis-aligned perspective correction; canonical TL/TR/BR/BL ordering; clockwise quarter-turn 0/90/180/270; width/height swap for 90/270; deterministic dimension derivation; round-half-up edge conversion; colored-corner and grid-line mapping; point-out-of-bounds, duplicate, self-intersection, non-convex, zero-area, output-too-small, invalid rotation and revision-conflict rejection; append-only persistence; no update/delete/replace; canonical-payload/projection equality; corruption detection; deterministic repository ordering; audit and recipe atomicity; rollback on render, recipe persistence and audit failure; PII-safe DTOs/errors; no paths or filenames in logs; no coordinates in audit payload; no image bytes in persistence; no network access; deterministic rerun; preservation of every PR-008 and PR-009 regression test.

## 22. Synthetic fixture rules

The future verifier and tests must use generated synthetic raster data only. No real document, document-derived crop, photograph, scan, OCR payload or personal data may be used.

## 23. Manual verification

Local manual verification uses a generated synthetic image only. It verifies visible corner mapping, crop boundaries, perspective rectification, clockwise rotation, output dimensions, unchanged original checksum, no original overwrite, recipe persistence, audit insertion, deterministic rerun and controlled invalid-geometry failure. No real-photo or Windows 11 pilot acceptance is part of PR-010.

## 24. Acceptance criteria

Accept this implementation review only when coordinate space is unambiguous; EXIF is applied exactly once; originals remain immutable; transformation order is fixed; recipe versions are append-only; persistence and audit are atomic; PR-010 does not encode, persist or publish a final prepared JPEG; PR-011, PR-012 and PR-013 boundaries are preserved; implementation remains in review, not completed and not human accepted; documentation tests, repository policy and production tests pass; no production code outside PR-010 geometry scope, real documents or personal data are added.

## 25. Non-goals

No production code outside PR-010 geometry scope; no UI; no drag handles; no batch UI; no automatic boundary detection; no automatic perspective detection; no automatic deskew; no automatic crop; no multiple document regions; no document count; no image classification; no final prepared artifact publication; no JPEG encoding; no compression; no 1.90 MiB enforcement; no readability acceptance; no front/back merging; no terminal rules; no Excel; no OCR; no cloud APIs; no telemetry; no real documents; no production quality-policy activation; no Q-021 resolution; no PR-011 or later implementation.

## 26. Security and privacy prohibitions

Do not log complete identity numbers, phones, addresses, OCR payloads, MRZ, filenames, local paths, image bytes, thumbnails, full quadrilateral coordinates or raw exceptions. Do not upload data, add telemetry, add cloud OCR/storage/AI APIs, commit real documents or commit personal data.

## 27. Future implementation authorization boundary

The historical documentation-contract PR recorded the PR-010 geometry contract and did not itself authorize production implementation. The Product owner later accepted ADR-024 and the PR-010 contract on 2026-07-23, then explicitly authorized PR-010 production implementation from base `329dd5653a3faadd3c62387c1d900710f14b2f4e`. The current implementation remains AUTHORIZED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-011 AND LATER remain UNAUTHORIZED.


## PR-010 implementation review state

Product owner accepted ADR-024 on 2026-07-23 and authorized production implementation in review from exact base `329dd5653a3faadd3c62387c1d900710f14b2f4e`. PR-011 and later remain UNAUTHORIZED. Gate 2 remains NOT ACCEPTED. M3 remains IN PROGRESS. Q-021 remains DEFERRED. Production PR-009 quality policy remains NOT ACTIVE.
