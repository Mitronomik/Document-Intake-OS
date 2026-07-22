# Стратегия тестирования

## 1. Цель

Доказать соблюдение offline, immutable originals, operator verification, JPEG limit, Excel contracts, reproducible export and privacy.

## 2. Уровни

- unit: domain, normalization, transitions, completeness, naming, mapping;
- integration: SQLite, storage, image pipeline, recognition adapters, snapshots, export, backup;
- golden: all three Excel adapters;
- UI: smoke, navigation, errors, export blocking;
- local acceptance: Windows 11 and real documents outside Git.

## 3. Fixtures

Committed document/data fixtures must be fictional and synthetic. Committed document fixture files may exist only under `tests/fixtures/synthetic/`. ADR-016 permits structural template fixtures, approved-template-derived golden files and synthetic output workbooks using only the three approved terminal templates and fully fictional data after technical privacy inspection and after a repository-policy enforcement PR updates scanner and `.gitignore` rules.

PR-003 adds no document fixtures. Large document test inputs must normally be generated at test runtime. Private acceptance datasets, real-document fixtures and real-application workbooks remain outside Git, Codex and CI. Repository-policy tests use temporary files only.

Private local set: controlled access, local ground truth, no inclusion in reports or cloud tools.

## 4. CI

```bash
python scripts/check_repository_policy.py
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/check_repository_policy.py
uv run pytest -ra
uv build
```

После настройки: coverage, dependency/license audit and network guard. The repository-policy scanner is a preventive tracked-file guardrail; it does not implement semantic PII detection.

## 5. Domain tests

- critical field requires actor;
- conflict blocks export;
- override requires reason;
- snapshot immutable;
- later edits do not change snapshot;
- vehicle assignment is application-scoped;
- pedestrian has no vehicle;
- visitors splits citizenship;
- multiple vehicles create rows.

## 6. Storage tests

- original bytes unchanged;
- checksum mismatch;
- exact duplicate;
- atomic publish;
- temp cleanup;
- orphan detection;
- backup manifest;
- restore version check.

## 7. Image tests

- EXIF;
- RGB;
- no metadata;
- JPEG ≤1,90 MiB;
- one/two documents;
- manual regions;
- perspective;
- side order;
- determinism;
- unreadable output blocked;
- source unchanged.

## 8. Recognition tests

- source/confidence mandatory;
- bbox stored;
- MRZ checksums;
- visual/MRZ conflict;
- versioned rerun;
- no overwrite verified;
- related passport remains separate source;
- low confidence review;
- missing model error.

## 9. Excel golden tests

Проверять sheets, exact headers, values, cell types, formats, comments, validations, tables, merged cells, styles, reserved columns, external connections and reopen.

### TSP

`ТСП`, row 2, 25 columns, T–Y empty, `.xls` if confirmed.

### Visitors

`Данные`, `Types`, 24 columns, lists/comments, one citizenship, pedestrian, multiple vehicles.

### MGS

`Данные`, 30 columns, A–Y active, Z–AD empty, exact spaces and safe external connection.

## 10. Offline test

With network disabled: launch, import, prepare, recognize, verify, export, backup and restore. Unexpected outbound connection fails test.

## 11. Security tests

No secrets/PII in logs, formula injection, template checksum, timeout, permission checks, encrypted backup, temp cleanup, corrupted DB/file and source replacement.

## 12. Регрессия

Каждый дефект получает тест. Изменение image recipe, extractor, normalization, mapping or snapshot format требует version bump and targeted regression.

## 13. Acceptance protocol

Фиксировать build, OS, Excel version, models, template hashes, sample count, results, defects and release decision without PII.


## PR-005 persistence testing

PR-005 testing covers Windows SQLCipher integration, migration checksum/history validation, repository round trips and projection-tamper rejection, Unit of Work lifecycle/cleanup behavior, ordinary SQLite rejection, wrong-key behavior, deterministic multi-page ciphertext tamper and truncation, key/PII leak checks and database-trigger snapshot immutability. The real `sqlcipher3==0.6.2` integration remains active on Windows AMD64 and skips only off that target; a macOS skip is not Windows acceptance.

## Historical PR-006 lifecycle note

PR-005: `COMPLETED AND HUMAN ACCEPTED`. PR-006: `COMPLETED AND HUMAN ACCEPTED`. PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. Q-009: `DEFERRED`; PR-006 implements immutable stored final artifacts and no retention, deletion or secure-deletion policy. Q-017: `DEFERRED`; PR-006 storage layout is backup-neutral and PR-032 remains responsible for encrypted backup/restore. Real documents and personal data remain prohibited in Git, Codex and CI.

## Lifecycle update — PR-006 acceptance and PR-007 authorization

Verified live base SHA: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.

PR-006: `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`, final reviewed head `28d8b590adb7a7ae11e35f631eb9895c930b3cef`, merge commit `4c117ededc250d57961e2f5f4c8b4de01edf0c54`, merge date `2026-07-19`, final v0001 checksum `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`, final v0002 checksum `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`, local verification `306 passed, 2 skipped on macOS`, exact-head GitHub Actions jobs passed for Python checks on Ubuntu, Python checks on Windows, PR-S001 Windows encryption spike and PR-S001 DPAPI cross-runner negative, and exact-head CI workflow run `CI #85` succeeded.

ADR numbering after repair: ADR-019 is PR-005 SQLCipher binding and raw-key staging; ADR-020 is immutable encrypted filesystem storage v1; ADR-021 is immutable PII-safe audit events. The PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction.

PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-007 was merged and human accepted through GitHub PR #19. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. PR-009 is authorized, not started; PR-010 contract definition is authorized but not started; PR-010 production implementation and PR-011 and later remain unauthorized.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.

## Lifecycle update — PR-007 acceptance and PR-008 authorization

PR-007: `COMPLETED AND HUMAN ACCEPTED`. GitHub PR: `#19`. Final reviewed head: `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`. Merge commit: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`. Merged date: `2026-07-20`. Exact-head CI: `CI #92`, successful. Migration v0003 final checksum: `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`.

M2: `COMPLETED AND HUMAN ACCEPTED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK` for the non-UI encrypted original import and advisory duplicate-detection foundation only, governed by ADR-022, PR #21 and PR-008-D1. PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`. Do not claim Gate 2 is accepted, do not claim a physical Windows 11 smoke occurred, and do not begin PR-010 or later work.

Q-006: `DEFERRED`. Q-007: `DEFERRED`. Q-009: `DEFERRED`. Q-010: `ACCEPTED`. Q-017: `DEFERRED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. The sensitive-data/private-contour gate remains open for real documents and real personal data. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports.

## PR-008 implementation evidence note

PR-008 implementation records encrypted source-file import and advisory duplicate detection only. Original bytes are stored through the accepted encrypted storage port, metadata remains in SQLCipher, source paths are not persisted, decoder dependencies are pinned to `Pillow==12.3.0` and `pi-heif==1.4.0`, and no OCR, telemetry, cloud service, export, or PR-009 behavior is authorized by this change.

## PR-009 synthetic quality-test contract

PR-009 tests are synthetic-only and cover EXIF orientations 1-8, effective dimension swaps, one-time orientation, immutable original bytes, no transformed artifact, resolution thresholds, Laplacian blur frozen vectors, population contrast vectors, glare and exposure cutoff boundaries, aggregation to `GOOD`/`REVIEW_REQUIRED`/`RETAKE_REQUIRED`, append-only persistence, schema v5 migration from v0004, unchanged v0001-v0004 checksums, rollback, tamper detection and privacy allowlists. The PR-009 verifier runs the production encrypted database, immutable storage, import service, quality service, aggregate repository and audit repository on supported Windows SQLCipher CI. Literal synthetic decoder and seven-metric vectors are independent from production calculation helpers; verification proves complete persistence, the exact audit event, failing-audit transaction rollback, deterministic source listing, immutable source/storage state and fail-closed corruption rejection. It returns `0` for pass, `1` for product failure or `2` only for a documented unsupported environment. No real documents, document-derived fixtures or PII are used.


## MPO compatibility regression contract

MPO detected as a JPEG container is accepted as JPEG.
Only primary frame 0 is decoded.
Original bytes remain immutable.
Secondary frames are ignored in MVP.

Tests generate deterministic, PII-free, visually distinct primary and secondary frames with Pillow's pinned MPO writer. Decoder tests prove Pillow reports `MPO`, production mapping returns `SourceMediaType.JPEG`, frame-1 changes leave the import raster, DHASH64, quality pixels, dimensions and all seven metrics unchanged, frame-0 changes affect those outputs, EXIF is applied once, and source bytes are unchanged. Regression coverage retains ordinary JPEG, PNG, HEIF/HEIC, unsupported-format, orientations 1–8, transparency, frozen PR-008 import vectors, frozen PR-009 quality vectors and privacy-safe failure behavior. The PR-008 and PR-009 verifiers incorporate the same production-path MPO proof without adding or renaming public output records.

## PR-009 calibration lifecycle update — 2026-07-22

ADR-023: ACCEPTED.
PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.
PR-010 CONTRACT DEFINITION: AUTHORIZED, NOT STARTED.
PR-010 PRODUCTION IMPLEMENTATION: UNAUTHORIZED.
PR-011 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

Synthetic policies remain permitted in tests and verifiers. No test may imply that a production policy was selected or activated; future metric changes require new algorithm versions and local recalibration.


## PR-009 human acceptance lifecycle state — 2026-07-22

PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

GitHub PR: #24.
Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`.
Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.
Merge date: 2026-07-22.
Production policy_id: NOT ASSIGNED.
Production policy_version: NOT ASSIGNED.
Automatic PR-009 quality-based document blocking: NOT ACTIVE.
Automatic PR-009 production RETAKE_REQUIRED enforcement: NOT ACTIVE.
PR-010 CONTRACT DEFINITION: AUTHORIZED, NOT STARTED.
PR-010 PRODUCTION IMPLEMENTATION: UNAUTHORIZED.
PR-011 AND LATER: UNAUTHORIZED.

The next safe task is preparation of the exact PR-010 documentation contract. PR-010 production implementation and PR-011 and later remain unauthorized. This lifecycle update does not define or implement PR-010 runtime behavior, and FR-04 remains incomplete because geometry, document regions and later image-preparation work remain future scope.
