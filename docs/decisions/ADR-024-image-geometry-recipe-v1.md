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
9. Return an internal geometry-render result.
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

The contract prefers the already accepted and locked Pillow runtime. Do not add OpenCV, cloud libraries, network calls or a second image stack. The future implementation must define and test the exact Pillow transform mode, resampling mode and internal corner-order adaptation. Use RGB output. Do not preserve EXIF, geolocation, comments, ICC metadata or arbitrary source metadata in the internal rendered result. PR-010 does not publish a final JPEG. The geometry-rendered raster is an internal result for later PR-011 processing.

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

The future audit event must record controlled action `IMAGE_GEOMETRY_RECIPE_CREATED` or an equivalently controlled accepted action. It must be PII-safe. It may reference controlled entity IDs and recipe version metadata. It must not include filename, local path, original bytes, rendered bytes, thumbnail, full quadrilateral coordinates, arbitrary metadata, raw exception, OCR values or personal data.

## Controlled errors

Typed controlled failures must include source file not found; immutable stored object missing; stored-object integrity failure; unsupported decode; geometry decode failure; source-dimension mismatch; point outside bounds; duplicate point; self-intersecting quadrilateral; non-convex quadrilateral; zero or insufficient area; derived output too small; invalid quarter-turn; revision conflict; persistence conflict; audit persistence failure; render failure. Error DTOs, logs and audit records must remain PII-safe.

## Non-decisions in ADR-024

ADR-024 does not decide automatic document detection, automatic crop, automatic deskew, multiple documents per source, document count, document classification, JPEG compression, the 1.90 MiB algorithm, readability thresholds, side merging, front/back order, OCR, UI workflow, terminal-specific output dimensions, production PR-009 quality policy or Q-021 resolution.

## Consequences

PR-010 implementation must branch from the exact merge commit of the documentation-contract PR after it exists. This ADR introduces no production source files, migrations, dependency changes, CI workflow changes, UI behavior, runtime image transformation behavior, final JPEG publication, production quality-policy activation or PR-011/PR-012/PR-013 implementation.
