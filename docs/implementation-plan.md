# План реализации по независимым PR

## Общие правила

- один PR решает одну понятную задачу;
- каждый PR содержит тесты, документацию и manual verification;
- следующий крупный этап начинается после приемки gate;
- ADR-015 created a narrow exception for PR-001 through PR-003 repository-safety work while M0 remained open;
- PR-003 is completed and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`;
- M1 Safe Repository is accepted;
- GATE-M0 and M0 are accepted; PR-004 is completed and human accepted; GATE-S1 is completed and human accepted; ADR-018 is accepted; PR #9 merged PR-S001 as a research harness; PR-S001 is ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11; PR-005 is COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`; PR-006 and PR-007 are COMPLETED AND HUMAN ACCEPTED; PR-008 is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK; ADR-023 is ACCEPTED; PR-009 is IMPLEMENTED AND IN REVIEW, NOT HUMAN ACCEPTED; Q-021 is OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE; no production default quality policy is active; final PR-009 human acceptance remains blocked until Q-021 is accepted; PR-010 and later tasks remain UNAUTHORIZED; Gate 2 is NOT ACCEPTED; M3 is IN PROGRESS;
- реальные документы не используются в Codex Web;
- OCR начинается только после готовности ручного контура.

## Этап 0. Репозиторий

### PR-001 — Repository bootstrap

**Цель:** создать Python 3.12/PySide6 каркас.

Scope:

- `pyproject.toml`;
- uv;
- package layout;
- minimal desktop entry point;
- Ruff, mypy, pytest;
- README;
- smoke test.

Non-goals: OCR, БД, Excel и бизнес-логика.

Acceptance: sync, lint, typecheck, tests, запуск окна без сетевых запросов.

### PR-002 — Documentation baseline

Scope:

- audit the existing documentation package;
- normalize source priority;
- verify required files;
- verify relative Markdown links;
- update lifecycle and handoff state;
- add automated documentation-baseline tests;
- preserve unresolved questions;
- introduce no new requirements or decisions.

### PR-003 — CI and privacy guardrails

**Status:** COMPLETED and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`; accepted by the product owner.

Scope:

- repository-policy scanner using tracked files from `git ls-files -z`;
- high-confidence secret signatures with safe diagnostics;
- private-fixture protection;
- terminal-template protection, permitting only `resources/templates/README.md` as a policy marker under `resources/templates/`;
- tracked-image location and 1,992,294-byte synthetic-image size policy;
- CI integration on Ubuntu and Windows;
- fixture-policy documentation;
- automated tests.

Non-goals: domain, persistence, storage, image pipeline, UI workflow, OCR, Excel implementation, PR-004, M2, real documents, terminal templates and fixtures.

## Этап 1. Домен и хранение

### PR-004 — Core domain

Entities, value objects, enums, transitions, verification policy and snapshot invariants.

### PR-005 — SQLite persistence

COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 (`PR-005: Add encrypted SQLite persistence and migrations`) at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9` from final reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2`. The PR-005 merge date is `2026-07-19`; final migration v0001 checksum is `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`. Exact-head CI run #73 succeeded on Ubuntu and Windows, including Windows SQLCipher evidence for the PR-005 acceptance boundary. Migration v0001 is frozen after merge; every future schema change must use migration v0002 or later. PR-S001 does not create a production persistence API.

### PR-006 — Immutable filesystem storage

COMPLETED AND HUMAN ACCEPTED through GitHub PR #17. PR-S001 did not create production filesystem storage.

### PR-007 — Audit events

Authorized and in review, not accepted. This slice implements immutable PII-safe audit-event foundations only; correction and verification workflow integration remain later work.

**Gate 1:** COMPLETED AND HUMAN ACCEPTED after PR-007 acceptance. M2 is COMPLETED AND HUMAN ACCEPTED after immutable filesystem storage and audit acceptance.

## Этап 2. Изображения

### PR-008 — File import and duplicate detection

JPG/PNG/HEIC, metadata, SHA-256 and perceptual duplicate warning.

### PR-009 — Orientation and quality assessment

Status: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. Q-021 remains open, no production default quality policy is active, and final human acceptance remains blocked until Q-021 is accepted.

EXIF, dimensions, blur/glare/contrast diagnostics.

### PR-010 — Geometry tools

Rotate, crop, perspective, recipe and manual parameters.

### PR-011 — JPEG ≤1.90 MiB

RGB, metadata removal, iterative compression, readability and deterministic tests.

### PR-012 — Multiple documents per image

Regions, manual boundaries and two-document workflow.

### PR-013 — Merge document sides

Order, vertical/horizontal setting, one logical JPEG and retained originals.

**Gate 2:** ручная подготовка JPEG работает без OCR.

## Этап 3. Ручной рабочий контур

### PR-014 — Upload batches UI

Create batch, drag/drop, import statuses and background tasks.

### PR-015 — Manual classification

Country, document type, side, template version and correction audit.

### PR-016 — Person and vehicle cards

Use-case CRUD, duplicate suggestions, separate tractor/trailer.

### PR-017 — Verification workflow

Candidates, operator entry, critical field statuses and audit.

### PR-018 — Applications and snapshots

Terminal selection, assignments, completeness port, immutable snapshot and current batch/all database.

**Gate 3:** оператор может вручную подготовить снимок заявки.

## Этап 4. Excel

### PR-019 — Terminal adapter contract

Common interface, template manifest, validation report, typed errors and synthetic snapshot.

### PR-020 — Visitors adapter

Exact mapping, Types, comments/validations, citizenship split, pedestrian, multiple vehicles and golden tests.

### PR-021 — MGS adapter

A–Y, Z–AD, exact spaces, table expansion, external connection safety and golden tests.

### PR-022 — TSP adapter

`.xls` decision, sheet `ТСП`, row 2, reserved columns, Windows Excel integration if required and local tests.

### PR-023 — Export package

Excel, driver folders, JPEGs, manifest, warnings, atomic publish and repeat export.

**Gate 4:** все три книги прошли реальную загрузку.

## Этап 5. OCR

### PR-024 — Recognition port and local runtime

Versioned adapter, candidates, diagnostics and no verified mutation.

### PR-025 — MRZ parser

Formats, normalization, check digits and conflict model.

### PR-026 — Passport/ID extraction

Visual fields, MRZ comparison, source regions and priority countries.

### PR-027 — Vehicle extraction

Template versions, zones and VIN/registration candidates.

### PR-028 — Confidence and review UI

BBox navigation, statuses, conflict comparison and rerun version.

### PR-029 — Migration card assistance

Printed fields, passport suggestions, mandatory human review and dates/stamps.

**Gate 5:** OCR пилот принят на локальном наборе.

## Этап 6. Промышленная доводка

### PR-030 — Encryption

Только после ADR: DB, storage, key handling, migration and recovery.

### PR-031 — Local users

Operator/admin, login, timeout, permissions and override.

### PR-032 — Backup and restore

Encrypted archive, manifest, integrity and restore test.

### PR-033 — Windows installer

Runtime, models, templates, offline install and versioning.

### PR-034 — Offline and security tests

Network block, PII logs, template tampering, formula injection and fault injection.

### PR-035 — Pilot fixes

Только подтвержденные пилотом дефекты, regression tests and release candidate.

## Оценка

Рабочий Windows MVP: 8–12 недель. Стабильная версия после пилота: 3–5 месяцев. Оценка пересматривается после Gate 1 и Gate 4.

## Current lifecycle state

GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance of GATE-M0 occurred after PR #5 merge. M0: ACCEPTED. M1: ACCEPTED. PR-004: COMPLETED AND HUMAN ACCEPTED. GATE-S1: COMPLETED AND HUMAN ACCEPTED. ADR-018: ACCEPTED. PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11. PR-005: COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9` from reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2`. PR-005 final migration v0001 checksum is `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`; v0001 is frozen and every future schema change must use migration v0002 or later. Exact-head CI run #73 succeeded on Ubuntu and Windows, including `Python checks (ubuntu-latest)`, `Python checks (windows-latest)`, `PR-S001 Windows encryption spike` and `PR-S001 DPAPI cross-runner negative`; Windows SQLCipher evidence is complete for the PR-005 acceptance boundary.

PR-006: COMPLETED AND HUMAN ACCEPTED. PR-007: COMPLETED AND HUMAN ACCEPTED. PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK; RISK-PR008-W11-SMOKE: ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE. ADR-023: ACCEPTED. PR-009: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. Q-021: OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE. Production default quality policy: NOT ACTIVE. Final PR-009 human acceptance: BLOCKED UNTIL Q-021 IS ACCEPTED. PR-010 AND LATER: UNAUTHORIZED. Gate 2: NOT ACCEPTED. M3: IN PROGRESS. Gate 1: COMPLETED AND HUMAN ACCEPTED. M2: COMPLETED AND HUMAN ACCEPTED. Q-010: ACCEPTED. Q-017 remains DEFERRED. The template enforcement PR remains future work. The sensitive-data/private-contour gate remains open, and real documents and personal data remain prohibited in Git, Codex and CI. PR-007 is completed and human accepted.

## Historical PR-005 lifecycle update

PR-S001-F1: COMPLETED. PR-S001-F2: COMPLETED. PR-S001-F3: COMPLETED. PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13; PR-S001-F4 merge commit: `985fae37c7645e8f65edbe4d1609100ee24a2097`.

PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.

PR-005 is COMPLETED AND HUMAN ACCEPTED after merge through GitHub PR #15 on `2026-07-19`. Final reviewed head: `325b49555dee49fa22b008d9522bbbc6eb873ca2`. Merge commit: `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`. Final v0001 checksum: `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`. Local validation was `191 passed, 2 skipped on macOS`; the skipped tests were Windows AMD64 SQLCipher integration tests skipped locally as designed, and the full Windows CI pytest step passed on the reviewed PR head in CI run #73. The four final persistence audit blockers were closed before merge: SQLite replacement forms cannot replace immutable snapshot rows; loss of the outer transaction invalidates and closes the UoW; list reads detect payload/projection corruption before filtering; canonical boolean and collection deserialization is strict.

RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.

PR-006 and PR-007 are COMPLETED AND HUMAN ACCEPTED; PR-008 is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK; PR-009 is AUTHORIZED, NOT STARTED; PR-010 and later remain UNAUTHORIZED; Gate 1 and M2 are COMPLETED AND HUMAN ACCEPTED.

Q-009: DEFERRED. PR-006 implements no retention, deletion or secure-deletion policy.


## Historical lifecycle snapshot after PR-006 acceptance

PR-006: `COMPLETED AND HUMAN ACCEPTED`.
PR-007: `COMPLETED AND HUMAN ACCEPTED`
PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`.
Gate 1: `COMPLETED AND HUMAN ACCEPTED`.
M2: `COMPLETED AND HUMAN ACCEPTED`.
Q-009: `DEFERRED`.
Q-017: `DEFERRED`.
Q-017 remains deferred.

## Lifecycle update — PR-006 acceptance and PR-007 authorization

Verified live base SHA: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.

PR-006: `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`, final reviewed head `28d8b590adb7a7ae11e35f631eb9895c930b3cef`, merge commit `4c117ededc250d57961e2f5f4c8b4de01edf0c54`, merge date `2026-07-19`, final v0001 checksum `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`, final v0002 checksum `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`, local verification `306 passed, 2 skipped on macOS`, exact-head GitHub Actions jobs passed for Python checks on Ubuntu, Python checks on Windows, PR-S001 Windows encryption spike and PR-S001 DPAPI cross-runner negative, and exact-head CI workflow run `CI #85` succeeded.

ADR numbering after repair: ADR-019 is PR-005 SQLCipher binding and raw-key staging; ADR-020 is immutable encrypted filesystem storage v1; ADR-021 is immutable PII-safe audit events. The PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction.

PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-007 was merged and human accepted through GitHub PR #19. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. PR-009 is authorized, not started; PR-010 and later remain unauthorized.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.

## Lifecycle update — PR-007 acceptance and PR-008 authorization

PR-007: `COMPLETED AND HUMAN ACCEPTED`. GitHub PR: `#19`. Final reviewed head: `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`. Merge commit: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`. Merged date: `2026-07-20`. Exact-head CI: `CI #92`, successful. Migration v0003 final checksum: `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`.

M2: `COMPLETED AND HUMAN ACCEPTED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK` for the non-UI encrypted original import and advisory duplicate-detection foundation only, governed by ADR-022, PR #21 and PR-008-D1. PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`. Do not claim Gate 2 is accepted, do not claim a physical Windows 11 smoke occurred, and do not begin PR-010 or later work.

Q-006: `DEFERRED`. Q-007: `DEFERRED`. Q-009: `DEFERRED`. Q-010: `ACCEPTED`. Q-017: `DEFERRED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. The sensitive-data/private-contour gate remains open for real documents and real personal data. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports.

## PR-008 implementation note

PR-008 adds source import domain contracts, Pillow/pi-heif decoding, DHASH64 advisory duplicate checks, encrypted original publication through the PR-006 storage port, SQLCipher persistence migration v0004, and PR-007 audit event creation. No UI, OCR, export, quality assessment, or PR-009 behavior is in scope.

## Historical PR-009 orientation and quality contract

PR-009 is `AUTHORIZED, CONTRACT PROPOSED, PRODUCTION IMPLEMENTATION NOT STARTED`. The implementation base for future production code must be the exact merge commit of the contract PR, not `063e4b5a981f8ef6914c055e9f50666bbf1be734`. Future implementation is limited to deterministic whole-frame EXIF orientation, encoded/effective dimensions, resolution, blur/sharpness, contrast, glare/highlight clipping and exposure diagnostics with explicit typed `ImageQualityPolicy`. No hidden thresholds are allowed; Q-021 is `OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE`. Production activation of a default quality policy and final human acceptance remain blocked until Q-021 is accepted. PR-010 AND LATER remain `UNAUTHORIZED`; Gate 2 remains `NOT ACCEPTED`; M3 remains `IN PROGRESS`.


## PR-009 implementation lifecycle update — 2026-07-21

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED.
Q-021: OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE.
Production default quality policy: NOT ACTIVE.
Final PR-009 human acceptance: BLOCKED UNTIL Q-021 IS ACCEPTED.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

PR-009 implements deterministic whole-frame metrics, explicit caller-provided typed policy handling, full-resolution orientation-normalized decoding, append-only persistence, audit integration, controlled service errors, synthetic tests and a cross-platform verifier. It does not select or activate production thresholds, add UI integration, reject documents automatically, implement PR-010 geometry, PR-011 JPEG preparation, PR-012 document detection/segmentation or use real-document calibration. Migration v0005 checksum: `6d020d1acfbce3fcb7168e935617f2ae008a32bea7def1f37de84e36e9e2224f`.
