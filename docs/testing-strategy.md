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

## Historical lifecycle snapshot — Historical PR-006 lifecycle note

PR-005: `COMPLETED AND HUMAN ACCEPTED`. PR-006: `COMPLETED AND HUMAN ACCEPTED`. PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. Q-009: `DEFERRED`; PR-006 implements immutable stored final artifacts and no retention, deletion or secure-deletion policy. Q-017: `DEFERRED`; PR-006 storage layout is backup-neutral and PR-032 remains responsible for encrypted backup/restore. Real documents and personal data remain prohibited in Git, Codex and CI.

## Historical lifecycle snapshot — Lifecycle update — PR-006 acceptance and PR-007 authorization

Verified live base SHA: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.

PR-006: `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`, final reviewed head `28d8b590adb7a7ae11e35f631eb9895c930b3cef`, merge commit `4c117ededc250d57961e2f5f4c8b4de01edf0c54`, merge date `2026-07-19`, final v0001 checksum `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`, final v0002 checksum `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`, local verification `306 passed, 2 skipped on macOS`, exact-head GitHub Actions jobs passed for Python checks on Ubuntu, Python checks on Windows, PR-S001 Windows encryption spike and PR-S001 DPAPI cross-runner negative, and exact-head CI workflow run `CI #85` succeeded.

ADR numbering after repair: ADR-019 is PR-005 SQLCipher binding and raw-key staging; ADR-020 is immutable encrypted filesystem storage v1; ADR-021 is immutable PII-safe audit events. The PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction.

PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-007 was merged and human accepted through GitHub PR #19. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. PR-009 is authorized, not started; PR-010 and later remain unauthorized.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.

## Historical lifecycle snapshot — Lifecycle update — PR-007 acceptance and PR-008 authorization

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

## Historical lifecycle snapshot — PR-009 calibration lifecycle update — 2026-07-22

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE MERGE BOUNDARY.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

Synthetic policies remain permitted in tests and verifiers. No test may imply that a production policy was selected or activated; future metric changes require new algorithm versions and local recalibration.
## Historical lifecycle snapshot — PR-009 human acceptance lifecycle state — 2026-07-22

PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
Production policy_id: NOT ASSIGNED.
Production policy_version: NOT ASSIGNED.
Automatic PR-009 quality-based document blocking: NOT ACTIVE.
Automatic PR-009 production RETAKE_REQUIRED enforcement: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.
ADR-024: ACCEPTED.
PR-010 CONTRACT: ACCEPTED.
PR-010 PRODUCTION IMPLEMENTATION: AUTHORIZED AND IN REVIEW; NOT HUMAN ACCEPTED.
PR-011 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

GitHub PR: #24.
Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`.
Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.
Merge date: 2026-07-22.

This current PR-009-D4-backed section supersedes earlier historical lifecycle snapshots for current status only. It does not rewrite those historical records and does not authorize PR-010 production implementation or PR-011 and later work. FR-04 remains incomplete because geometry, document regions and later image-preparation work remain future scope.
## PR-010 geometry contract test staging

Future PR-010 tests must use generated synthetic rasters only and cover immutable originals, EXIF orientation exactly once, source-effective coordinate mapping, quadrilateral validation, deterministic dimensions, RGB rendering, append-only persistence, one Unit of Work atomicity, PII-safe audit/errors, no production JPEG, no network access, and preservation of PR-008/PR-009 regressions.


## Historical lifecycle snapshot — Current PR-010 geometry contract staging — 2026-07-23

This current section supersedes historical lifecycle sections for current status only and does not rewrite the historical record.

PR #26 merged successfully on 2026-07-23 from reviewed head `cc79a80fcacdbde2667cae858815b30176f87555` at merge commit `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`; exact-head CI `CI #129` succeeded. PR-009 is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. Q-021 is DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. Production default PR-009 quality policy is NOT ACTIVE. Production `policy_id` and `policy_version` are NOT ASSIGNED. Automatic PR-009 quality-based document blocking and production RETAKE_REQUIRED enforcement are NOT ACTIVE. `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` remains OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY. ADR-024 is PROPOSED. PR-010 CONTRACT is PROPOSED FOR HUMAN REVIEW. PR-010 PRODUCTION IMPLEMENTATION is UNAUTHORIZED. PR-011 AND LATER are UNAUTHORIZED. Gate 2 is NOT ACCEPTED. M3 is IN PROGRESS.


## Historical lifecycle snapshot — PR-010 geometry implementation review — 2026-07-23

ADR-024 is ACCEPTED by Product owner. PR-010 production implementation is AUTHORIZED AND IN REVIEW from base `329dd5653a3faadd3c62387c1d900710f14b2f4e`. PR-011 and later remain UNAUTHORIZED; Gate 2 remains NOT ACCEPTED; M3 remains IN PROGRESS; Q-021 remains DEFERRED; production PR-009 quality policy is NOT ACTIVE. PR-010 adds deterministic offline geometry recipe creation only and does not publish prepared JPEGs.


## Historical lifecycle snapshot — Current lifecycle state — 2026-07-26

This current section supersedes earlier lifecycle snapshots for current status only and does not rewrite the historical record.

PR-005: COMPLETED AND HUMAN ACCEPTED. PR-006: COMPLETED AND HUMAN ACCEPTED. PR-007: COMPLETED AND HUMAN ACCEPTED. PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK. PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. PR-010: COMPLETED AND HUMAN ACCEPTED. ADR-024: ACCEPTED. PR-010 contract: ACCEPTED. PR-010 CONTRACT: ACCEPTED.

PR-010 evidence: GitHub PR #28; final reviewed head `8b6a3cf69d697807a20e763605b4601104844f04`; merge commit `99cdcaebe25551a24062e4e356ff47e868ac8f6a`; exact-head workflow `CI #138`; workflow run ID `30034157725`; conclusion `success`. Ubuntu and Windows full pytest, Ubuntu and Windows `uv build`, and Windows PR-006 through PR-010 verifiers passed. Current schema version before PR-011: `6`. Frozen v0006 checksum: `ac9d5bfbe79160d880f30af6ee1ed645ab500b9be140a18b9d6498cc68eba5ec`.

The accepted PR-010 boundary is immutable originals; EXIF orientation applied exactly once; deterministic source-effective coordinate space; manual quadrilateral geometry; perspective transformation; clockwise quarter-turn rotation; deterministic output dimensions; append-only geometry-recipe revisions; canonical persistence validation; atomic geometry-recipe and audit persistence; no final prepared JPEG publication; and no PR-011 or later behavior. PR-010 alone does not complete manual JPEG preparation because PR-011, PR-012 and PR-013 remain incomplete.

Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. RISK-PR009-NO-PRODUCTION-QUALITY-POLICY remains OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY. Production PR-009 quality policy: NOT ACTIVE. Production `policy_id`: NOT ASSIGNED. Production `policy_version`: NOT ASSIGNED. Automatic PR-009 quality blocking: NOT ACTIVE. Automatic production `RETAKE_REQUIRED`: NOT ACTIVE. ADR-025: ACCEPTED. PR-011 CONTRACT: ACCEPTED. PR-011 PRODUCTION IMPLEMENTATION: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-012 AND LATER: UNAUTHORIZED. Gate 2: NOT ACCEPTED. M3: IN PROGRESS.

PR-011 is implemented in review on the accepted exact base; PR-012 and PR-013 remain unauthorized.

Real documents and personal data remain prohibited in Git, Codex and CI.


Product owner authorization date: 2026-07-26. Accepted contract and implementation base: `f007fb5a04a5c69c70a37faf7ba12fa6775ae819`. Current schema version: `7`. Final v0007 checksum: `afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7`. V0007 uses a checksum-protected `DISABLED_DURING_TABLE_REBUILD` execution mode, a transactional populated-table copy, foreign-key checks before and after restoration, and no internal SQLite schema edits. Candidate evidence uses the production attempt generator and observer; determinism reuses the same PR-010 RGB render; verifier privacy uses an exact allowlist and runtime forbidden-value checks. ADR-025: ACCEPTED. PR-011 CONTRACT: ACCEPTED. PR-011 PRODUCTION IMPLEMENTATION: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-012 AND LATER: UNAUTHORIZED. Q-021: DEFERRED. PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE. PRODUCTION `policy_id`: NOT ASSIGNED. PRODUCTION `policy_version`: NOT ASSIGNED. AUTOMATIC PR-009 QUALITY BLOCKING: NOT ACTIVE. AUTOMATIC PRODUCTION `RETAKE_REQUIRED`: NOT ACTIVE. GATE 2: NOT ACCEPTED. M3: IN PROGRESS. Real documents and personal data remain prohibited in Git, Codex and CI.
## Historical lifecycle snapshot — PR-011 acceptance-control status

This normative acceptance status supersedes broader implementation wording for current readiness only; dated historical snapshots remain historical.

- PR-011 PRODUCTION CODE: IMPLEMENTED IN REVIEW
- PR-011 ACCEPTANCE EVIDENCE: INCOMPLETE
- PR-011 HUMAN ACCEPTANCE: BLOCKED
- PR-012 AND LATER: UNAUTHORIZED
- Q-021: DEFERRED
- PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE
- GATE 2: NOT ACCEPTED
- M3: IN PROGRESS

CI success proves the checked implementation and tests pass; it does not prove that every acceptance-manifest entry exists.


### PR-011 scoped repository acceptance rule

Each public repository method must constrain its SQL query to the requested scope. Every row returned by that scoped SQL query must be fully deserialized and projection-validated before any result is returned. Corruption inside the query result set fails closed. Corruption outside the query result set must not poison an unrelated query.


## Current lifecycle state — 2026-07-28

This section is authoritative for current lifecycle status. It supersedes earlier dated lifecycle snapshots for current status only and does not rewrite their historical record.

```text
PR-011: COMPLETED AND HUMAN ACCEPTED
PR-011 FINAL REVIEWED HEAD:
639e1c68e2fd5f3de15c45028d4926c1fa8c10bf
PR-011 MERGE COMMIT:
72cf3852e286b711969f7277539654573818d859
PR-011 EXACT-HEAD CI:
CI #166 / run ID 30362433088 / success
SCHEMA VERSION:
7
V0007 CHECKSUM:
afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7
ADR-026:
PROPOSED
PR-012 CONTRACT:
PROPOSED FOR HUMAN REVIEW
PR-012 PRODUCTION IMPLEMENTATION:
UNAUTHORIZED
PR-013 AND LATER:
UNAUTHORIZED
GATE 2:
NOT ACCEPTED
M3:
IN PROGRESS
```

PR-011 is merged and human accepted under [PR-011-D3](decisions/PR-011-D3-lifecycle-acceptance.md). [ADR-026](decisions/ADR-026-document-regions-v1.md) and the [PR-012 contract](tasks/PR-012-multiple-documents-per-image.md) are proposals for Product-owner review only. Contract preparation is authorized; production implementation is not.

Q-021: DEFERRED. PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE. PRODUCTION `policy_id`: NOT ASSIGNED. PRODUCTION `policy_version`: NOT ASSIGNED. AUTOMATIC PR-009 QUALITY BLOCKING: NOT ACTIVE. AUTOMATIC PRODUCTION `RETAKE_REQUIRED`: NOT ACTIVE. Real documents and personal data remain prohibited in Git, Codex, and CI.

## Historical lifecycle state — PR-012 closure and PR-013 contract proposal (2026-08-02)

This section is preserved as historical evidence and does not define current authorization.

```text
PR-012: COMPLETED AND HUMAN ACCEPTED
ADR-026: ACCEPTED
PR-012 CONTRACT: ACCEPTED
PR-012 MERGE: COMPLETED THROUGH GITHUB PR #32
PR-012 REVIEWED HEAD: 9a6af1b72a064c47c66989b1e7dbc78d72768957
PR-012 MERGE COMMIT: 6a0f0df1e2d43e67395d4dee9415b6703181ab41
PR-012 EXACT-HEAD CI: CI #203 / run 30698992893 / SUCCESS
CURRENT SCHEMA VERSION: 8
MIGRATIONS V0001 THROUGH V0008: FROZEN
ADR-027: PROPOSED
PR-013 CONTRACT: PROPOSED FOR HUMAN REVIEW
PR-013 PRODUCTION IMPLEMENTATION: UNAUTHORIZED
PR-014 AND LATER: UNAUTHORIZED
M3: IN PROGRESS
GATE 2: NOT ACCEPTED
Q-021: DEFERRED
PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE
PRODUCTION POLICY_ID: NOT ASSIGNED
PRODUCTION POLICY_VERSION: NOT ASSIGNED
AUTOMATIC QUALITY-BASED DOCUMENT BLOCKING: NOT ACTIVE
AUTOMATIC PRODUCTION RETAKE_REQUIRED: NOT ACTIVE
```

The v0008 frozen checksum is `ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b`. PR-008 through PR-012 are completed and human accepted (with their recorded limitations/risks). PR-013 is the final planned production slice of M3, but this proposed contract does not authorize it. Real documents and personal data remain prohibited in Git, Codex, CI, logs, and test reports. Physical Windows 11 installed-application, packaging, Excel, terminal-template, terminal-upload, and final workstation acceptance remain deferred. The next safe step after this documentation PR is reviewed and merged is a separate Product-owner decision accepting ADR-027 and the PR-013 contract, authorizing implementation, and naming this PR's merge commit as its exact base.


## Current lifecycle state — PR-013 implementation (authoritative, 2026-08-02)

All earlier lifecycle sections are historical evidence. The Product owner directly accepted ADR-027 and the PR-013 contract and authorized implementation without a separate lifecycle-only pull request.

```text
PR-012: COMPLETED AND HUMAN ACCEPTED
ADR-026: ACCEPTED
PR-012 CONTRACT: ACCEPTED
PR-013 BASE: bb25421b4b1630a45359a0b82f949e2b044eaafa
ADR-027: ACCEPTED
PR-013 CONTRACT: ACCEPTED
PR-013 PRODUCTION IMPLEMENTATION: AUTHORIZED AND IN REVIEW
PR-013 HUMAN ACCEPTANCE: NOT GRANTED
PR-013 MERGE: NOT AUTHORIZED
CURRENT SCHEMA VERSION: 9
MIGRATIONS V0001 THROUGH V0008: FROZEN
MIGRATION V0009: CANDIDATE — NOT FROZEN UNTIL PR-013 MERGE
PR-014 AND LATER: UNAUTHORIZED
M3: IN PROGRESS
GATE 2: NOT ACCEPTED
Q-021: DEFERRED
PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE
```

PR-013 implements exactly two explicitly ordered confirmed region references, deterministic vertical or horizontal BICUBIC composition on a fresh opaque-white RGB raster, one final PR-011 JPEG encode, immutable encrypted storage and schema-9 persistence, complete write-phase revalidation, and a typed privacy-safe audit event. Its acceptance evidence covers complete side lineage, composite member foreign keys, both lineage guards, populated schema 8-to-9 preservation, failed-v0009 rollback, post-publication rollback/orphan behavior, production SQLCipher reopen, wrong-key rejection, and ordinary SQLite rejection. The v0008 frozen checksum remains `ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b`; the v0009 candidate checksum is `0b0e0637ba4aa3defb29e6e27c241f28d333ec3c8bb6e8751c6cc7acc1b24b49`. No human acceptance or merge authorization is claimed.
