# Handoff

## Проект

Document Intake OS — локальная Windows-программа подготовки документов и Excel-заявок для трех терминалов.

## Подтверждено

- вход — отдельные фото водителей;
- разные страны и поколения документов;
- фон, наклон, несколько документов и две стороны;
- originals immutable;
- output JPEG RGB ≤1,90 MiB;
- OCR only suggests;
- operator verifies critical data;
- local database;
- TSP, Visitors and MGS exports;
- manual Konversta upload;
- no real PII in cloud development.

## Source of truth

Canonical source priority:

1. `docs/technical-specification.md`
2. `docs/decisions.md`
3. `docs/product-spec.md`
4. `docs/architecture.md`
5. `docs/domain-model.md`
6. `docs/security.md`
7. `docs/testing-strategy.md`
8. current PR task under `docs/tasks/`

Conflicts must be reported instead of resolved silently.

## Архитектура

Modular monolith: domain, application, persistence, storage, image pipeline, recognition, terminal adapters and UI.

ADR-017 fixes the first MVP topology as one Windows 11 x64 workstation with one active operator session at a time. This does not implement SQLite, storage, users or authentication.

## Historical lifecycle snapshot — Current lifecycle state

PR #26 merged successfully on 2026-07-23: final reviewed head `cc79a80fcacdbde2667cae858815b30176f87555`, merge commit `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`, exact-head CI `CI #129`, run ID `29972502518`, conclusion `success`.


GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance of GATE-M0 occurred after PR #5 merge. M0: ACCEPTED. M1: ACCEPTED. PR-004: COMPLETED AND HUMAN ACCEPTED. GATE-S1: COMPLETED AND HUMAN ACCEPTED. ADR-018: ACCEPTED. PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11; PR-S001-F1: COMPLETED; PR-S001-F2: COMPLETED; PR-S001-F3: COMPLETED; PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13; PR-S001-F4 merge commit: `985fae37c7645e8f65edbe4d1609100ee24a2097`. PR-005: COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9` from final reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2`. PR-005 final migration v0001 checksum is `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`; v0001 is frozen and every future schema change must use migration v0002 or later. Exact-head CI run #73 succeeded on Ubuntu and Windows, and Windows SQLCipher evidence is complete for the PR-005 acceptance boundary.

PR-006: COMPLETED AND HUMAN ACCEPTED. PR-007: COMPLETED AND HUMAN ACCEPTED. PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK. ADR-023: ACCEPTED. PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. Production default PR-009 quality policy: NOT ACTIVE. Production policy_id: NOT ASSIGNED. Production policy_version: NOT ASSIGNED. Automatic PR-009 quality-based document blocking: NOT ACTIVE. Automatic PR-009 production RETAKE_REQUIRED enforcement: NOT ACTIVE. RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY. ADR-024: ACCEPTED. PR-010 CONTRACT: ACCEPTED. PR-010 PRODUCTION IMPLEMENTATION: AUTHORIZED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-011 AND LATER: UNAUTHORIZED. Gate 2: NOT ACCEPTED. M3: IN PROGRESS. Gate 1: COMPLETED AND HUMAN ACCEPTED. M2: COMPLETED AND HUMAN ACCEPTED. Q-010: ACCEPTED. Q-017 remains DEFERRED. Under ADR-016, the template enforcement PR remains future work and does not block PR-004 or PR-005 closure. The sensitive-data/private-contour gate remains open for real data, and real documents and personal data remain prohibited in Git, Codex and CI.

## Authorization boundary

ADR-026 and the PR-012 contract are accepted. PR-012 production implementation is authorized and remains in review. PR-012 human acceptance has not been granted, and merge remains unauthorized. PR-013 and later remain unauthorized. Gate 2 is not accepted, and M3 remains in progress.

## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption staging, PII logs, critical field bypass and insufficient local OCR samples.

## Продолжение

The next safe activity is continued PR-012 correction, executable evidence completion, and Product-owner review preparation. Do not merge PR-012 and do not begin PR-013 or later work. The local Q-021 calibration remains complete with accepted negative evidence; no production policy was selected.

PR-S001-F1, PR-S001-F2, PR-S001-F3 and PR-S001-F4 are completed. PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-006 is COMPLETED AND HUMAN ACCEPTED through PR #17. Q-017 remains deferred. The sensitive-data/private-contour gate remains open, and real documents and personal data remain prohibited in Git, Codex and CI.

## PR-005 closure record

PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.

PR-005 is COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 (`PR-005: Add encrypted SQLite persistence and migrations`). Final reviewed head: `325b49555dee49fa22b008d9522bbbc6eb873ca2`. Merge commit: `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`. Merge date: `2026-07-19`. Final migration v0001 checksum: `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`. Exact-head CI run #73 succeeded with `Python checks (ubuntu-latest)`, `Python checks (windows-latest)`, `PR-S001 Windows encryption spike` and `PR-S001 DPAPI cross-runner negative`; Windows SQLCipher evidence is complete for the PR-005 acceptance boundary. Local validation was `191 passed, 2 skipped on macOS`; the skipped local tests were Windows AMD64 SQLCipher integration tests and were skipped locally as designed, while full Windows CI pytest passed on the reviewed PR head.

The four final persistence audit blockers were closed before merge: SQLite replacement forms cannot replace immutable snapshot rows; loss of the outer transaction invalidates and closes the UoW; list reads detect payload/projection corruption before filtering; canonical boolean and collection deserialization is strict. Migration v0001 is frozen after merge, and every future schema change must use migration v0002 or later. RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.

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

## Historical PR-008 handoff note

PR-008 was merged through PR #21 and human accepted with documented residual risk; do not reuse branch `codex-uj32ni`. PR-009 is authorized, not started. PR-010 and later remain unauthorized.

## Historical PR-008 acceptance handoff

PR-008 is closed as `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK` through PR #21, final reviewed head `99dfefe467762e241f0584c2ca1a81bc662c1ab0`, merge commit `bf7af9617d33a205f27eb9a4734fea6ecee18b58`, merge date `2026-07-20`, CI #106 / workflow database ID `29776664038`, and `PR008_VERIFY result=PASS` on supported hosted Windows CI. Do not reopen PR-008 or claim it remains in review.

`RISK-PR008-W11-SMOKE` is `ACCEPTED FOR THE PR-008 DEVELOPMENT ACCEPTANCE BOUNDARY; DEFERRED TO WINDOWS INSTALLER, PILOT, OR FINAL RELEASE ACCEPTANCE`. No physical Windows 11 x64 smoke occurred and none may be fabricated or inferred. Hosted Windows Server AMD64 is not the same as a physical Windows 11 x64 workstation.

At that historical acceptance point, the next authorized implementation task was PR-009 only: `AUTHORIZED, NOT STARTED`. PR-010 AND LATER: `UNAUTHORIZED`. Gate 2: `NOT ACCEPTED`. M3: `IN PROGRESS`.

## Historical PR-009 contract handoff

At the contract handoff, PR #22 merge commit `063e4b5a981f8ef6914c055e9f50666bbf1be734` was recorded as the verified lifecycle base for this documentation-only contract. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; PR-009: `AUTHORIZED, CONTRACT PROPOSED, PRODUCTION IMPLEMENTATION NOT STARTED`; ADR-023: `PROPOSED`; Q-021: `OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. The historical implementation instruction was to wait until the contract PR merged and branch from its exact merge commit. Final calibrated thresholds, physical Windows 11 validation, Gate 2 acceptance and PR-010+ authorization were not claimed.


## PR-009 Q-021 correction handoff — 2026-07-22

ADR-023: ACCEPTED.
PR: GitHub PR #24, branch `codex/implement-pr-009-orientation-assessment`.
Starting correction head: `da250542f15b103bfa8cdf8ff6098ebddc8e4b73`.
PR-009: IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE MERGE BOUNDARY.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

The completed private local contour processed 60 samples and calculated 60 metric sets with zero failures, using 43 calibration samples, 17 held-out validation samples and 54 Pareto candidates. No policy was accepted. Only this safe aggregate evidence belongs in repository documentation. Production composition must fail closed without an accepted policy, and no unaccepted policy may automatically reject, delete, suppress or block a document.

This documentation correction still requires publication and exact-published-head CI. Human acceptance and merge remain pending, and PR #24 must remain open and unmerged until those separate actions occur.
## Historical lifecycle snapshot — PR-009 human acceptance lifecycle state — 2026-07-22

PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
Production policy_id: NOT ASSIGNED.
Production policy_version: NOT ASSIGNED.
Automatic PR-009 quality-based document blocking: NOT ACTIVE.
Automatic PR-009 production RETAKE_REQUIRED enforcement: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.
PR-010 CONTRACT DEFINITION: AUTHORIZED, NOT STARTED.
PR-010 PRODUCTION IMPLEMENTATION: AUTHORIZED AND IN REVIEW; NOT HUMAN ACCEPTED.
PR-011 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

GitHub PR: #24.
Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`.
Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.
Merge date: 2026-07-22.

This current PR-009-D4-backed section supersedes earlier historical lifecycle snapshots for current status only. It does not rewrite those historical records and does not authorize PR-010 production implementation or PR-011 and later work. FR-04 remains incomplete because geometry, document regions and later image-preparation work remain future scope.
## Historical lifecycle snapshot — Current PR-010 geometry contract staging — 2026-07-23

This current section supersedes historical lifecycle sections for current status only and does not rewrite the historical record.

PR #26 merged successfully on 2026-07-23 from reviewed head `cc79a80fcacdbde2667cae858815b30176f87555` at merge commit `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`; exact-head CI `CI #129` succeeded. PR-009 is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. Q-021 is DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. Production default PR-009 quality policy is NOT ACTIVE. Production `policy_id` and `policy_version` are NOT ASSIGNED. Automatic PR-009 quality-based document blocking and production RETAKE_REQUIRED enforcement are NOT ACTIVE. `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` remains OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY. ADR-024 is PROPOSED. PR-010 CONTRACT is PROPOSED FOR HUMAN REVIEW. PR-010 PRODUCTION IMPLEMENTATION is UNAUTHORIZED. PR-011 AND LATER are UNAUTHORIZED. Gate 2 is NOT ACCEPTED. M3 is IN PROGRESS.


## Historical lifecycle snapshot — Current lifecycle state — 2026-07-26

This current section supersedes earlier lifecycle snapshots for current status only and does not rewrite the historical record.

PR-005: COMPLETED AND HUMAN ACCEPTED. PR-006: COMPLETED AND HUMAN ACCEPTED. PR-007: COMPLETED AND HUMAN ACCEPTED. PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK. PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. PR-010: COMPLETED AND HUMAN ACCEPTED. ADR-024: ACCEPTED. PR-010 contract: ACCEPTED. PR-010 CONTRACT: ACCEPTED.

PR-010 evidence: GitHub PR #28; final reviewed head `8b6a3cf69d697807a20e763605b4601104844f04`; merge commit `99cdcaebe25551a24062e4e356ff47e868ac8f6a`; exact-head workflow `CI #138`; workflow run ID `30034157725`; conclusion `success`. Ubuntu and Windows full pytest, Ubuntu and Windows `uv build`, and Windows PR-006 through PR-010 verifiers passed. Current schema version before PR-011: `6`. Frozen v0006 checksum: `ac9d5bfbe79160d880f30af6ee1ed645ab500b9be140a18b9d6498cc68eba5ec`.

The accepted PR-010 boundary is immutable originals; EXIF orientation applied exactly once; deterministic source-effective coordinate space; manual quadrilateral geometry; perspective transformation; clockwise quarter-turn rotation; deterministic output dimensions; append-only geometry-recipe revisions; canonical persistence validation; atomic geometry-recipe and audit persistence; no final prepared JPEG publication; and no PR-011 or later behavior. PR-010 alone does not complete manual JPEG preparation because PR-011, PR-012 and PR-013 remain incomplete.

Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. RISK-PR009-NO-PRODUCTION-QUALITY-POLICY remains OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY. Production PR-009 quality policy: NOT ACTIVE. Production `policy_id`: NOT ASSIGNED. Production `policy_version`: NOT ASSIGNED. Automatic PR-009 quality blocking: NOT ACTIVE. Automatic production `RETAKE_REQUIRED`: NOT ACTIVE. ADR-025: ACCEPTED. PR-011 CONTRACT: ACCEPTED. PR-011 PRODUCTION IMPLEMENTATION: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-012 AND LATER: UNAUTHORIZED. Gate 2: NOT ACCEPTED. M3: IN PROGRESS.

PR-011 is implemented in review on the accepted exact base; PR-012 and PR-013 remain unauthorized.

Real documents and personal data remain prohibited in Git, Codex and CI.


Product owner authorization date: 2026-07-26. Accepted contract and implementation base: `f007fb5a04a5c69c70a37faf7ba12fa6775ae819`. Current schema version: `7`. Final v0007 checksum: `afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7`. V0007 uses a checksum-protected `DISABLED_DURING_TABLE_REBUILD` execution mode, a transactional populated-table copy, foreign-key checks before and after restoration, and no internal SQLite schema edits. Candidate evidence uses the production attempt generator and observer; determinism reuses the same PR-010 RGB render; verifier privacy uses an exact allowlist and runtime forbidden-value checks. ADR-025: ACCEPTED. PR-011 CONTRACT: ACCEPTED. PR-011 PRODUCTION IMPLEMENTATION: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-012 AND LATER: UNAUTHORIZED. Q-021: DEFERRED. PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE. PRODUCTION `policy_id`: NOT ASSIGNED. PRODUCTION `policy_version`: NOT ASSIGNED. AUTOMATIC PR-009 QUALITY BLOCKING: NOT ACTIVE. AUTOMATIC PRODUCTION `RETAKE_REQUIRED`: NOT ACTIVE. GATE 2: NOT ACCEPTED. M3: IN PROGRESS. Real documents and personal data remain prohibited in Git, Codex and CI.


## Historical lifecycle snapshot — PR-012 contract proposal before acceptance — 2026-07-28

This section records the pre-acceptance proposal state only. It is historical and does not define current lifecycle status.

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


## Current lifecycle state — PR-012 production review (authoritative, 2026-07-28)

This is the single authoritative current lifecycle section. All earlier lifecycle snapshots are historical and do not define current status.

```text
ADR-026: ACCEPTED
PR-012 CONTRACT: ACCEPTED
PR-012 PRODUCTION IMPLEMENTATION: AUTHORIZED AND IN REVIEW
PR-012 HUMAN ACCEPTANCE: NOT GRANTED
PR-012 MERGE: NOT AUTHORIZED
PR-013 AND LATER: UNAUTHORIZED
GATE 2: NOT ACCEPTED
M3: IN PROGRESS
```

Implementation base: `e326ff30c9ab83615c97579c02e480e2497838ab`. Earlier lifecycle sections remain historical.
