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

Extend the accepted decoder boundary to decode full-resolution immutable source bytes for geometry and apply EXIF exactly once. The renderer uses Pillow, produces RGB internal raster output, strips EXIF/geolocation/comments/ICC/arbitrary metadata, and defines/test-locks exact Pillow transform mode, resampling mode and internal corner-order adaptation. Do not add OpenCV, cloud libraries, network calls or a second image stack. PR-010 does not publish a final JPEG.

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

Expected new files may include `src/document_intake/domain/image_geometry.py`, `src/document_intake/image_pipeline/geometry_transformer.py`, `src/document_intake/application/dto/image_geometry.py`, `src/document_intake/application/services/image_geometry.py`, `src/document_intake/persistence/repositories/image_geometry.py`, `src/document_intake/persistence/migrations/v0006_image_geometry.py` and `scripts/verify_pr010_geometry.py`.

Expected existing integration files include `src/document_intake/application/ports/media.py`, `src/document_intake/application/ports/persistence.py`, `src/document_intake/application/ports/storage.py`, `src/document_intake/persistence/unit_of_work.py`, `src/document_intake/persistence/database.py`, `src/document_intake/persistence/repositories.py`, `src/document_intake/persistence/serialization.py`, `src/document_intake/persistence/migrations/__init__.py`, `src/document_intake/domain/enums.py`, `src/document_intake/domain/entities/audit.py`, package `__init__.py` exports and tests under `tests/application`, `tests/domain`, `tests/image_pipeline` and `tests/persistence`. This documentation-only PR creates none of those production files.

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
