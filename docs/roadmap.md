# Roadmap

## M0 — Requirements locked

Result: requirements package, open-question status model, accepted decisions and repository documentation.

Gate: MVP scope is confirmed, real documents are excluded from the cloud/public development contour, the repository privacy boundary is accepted for non-sensitive code, terminal-specific blockers are either externally confirmed or staged to downstream gates under ADR-016, and no placeholder terminal values are invented.

GATE-M0 is completed and human accepted. PR-004 is completed and human accepted. GATE-S1 is completed and human accepted with ADR-018 accepted.

## M1 — Safe repository

PR-001–003.

Result: reproducible environment, CI, AGENTS, privacy guardrails and minimal UI.

M1 is accepted by the product owner after PR-003 was completed and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`.

## M2 — Local data core

PR-004–007.

Result: domain, SQLite, immutable storage and audit.

PR-004 — Core Domain is completed and human accepted. GATE-S1 is completed and human accepted. ADR-018 is accepted for Q-010. PR #9 merged PR-S001 as a research harness; PR-S001 is ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11. PR-005 is COMPLETED AND HUMAN ACCEPTED through GitHub PR #15. PR-006 and PR-007 are COMPLETED AND HUMAN ACCEPTED. M2 is completed and human accepted by PR-007 acceptance. PR-008 is completed and human accepted with documented residual risk. PR-009 is completed and human accepted with a documented residual limitation. ADR-024 and the PR-010 contract are accepted; PR-010 is completed and human accepted. ADR-025 is proposed; the PR-011 contract is proposed for human review; PR-011 production implementation and PR-012 and later are unauthorized.

## M3 — Manual image workflow

PR-008–013.

Result: import, quality, crop/perspective, multiple docs, merge and JPEG ≤1.90 MiB.

Gate: типовые реальные фото локально готовятся без потери originals. Local evidence remains outside Git, Codex and CI.

M3 status:

- PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK.
- PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
- PR-010: COMPLETED AND HUMAN ACCEPTED.
- ADR-024 and PR-010 contract: ACCEPTED.
- Q-021: DEFERRED; production PR-009 policy, automatic blocking and production `RETAKE_REQUIRED`: NOT ACTIVE; production `policy_id` and `policy_version`: NOT ASSIGNED.
- ADR-025: PROPOSED.
- PR-011 contract: PROPOSED FOR HUMAN REVIEW.
- PR-011 production implementation and PR-012 and later: UNAUTHORIZED.
- Gate 2: NOT ACCEPTED. M3: IN PROGRESS.

The next safe task is review of ADR-025 and the proposed PR-011 contract. PR-011 implementation requires a later explicit Product owner acceptance and authorization naming this documentation PR merge commit. The physical Windows 11 evidence remains outside Git, Codex and CI.

## M4 — Manual end-to-end MVP

PR-014–018.

Result: batches, classification, cards, verification, application and snapshot.

Gate: приложение полезно без OCR.

## M5 — Three terminal exports

PR-019–023.

Result: Visitors, MGS, TSP and export package.

Gate: all terminal-specific external confirmations required by Q-001 through Q-005 and Q-015 exist, no placeholder terminal values are invented, approved template artifacts have passed technical privacy inspection and repository-policy enforcement if committed, all workbooks open without repair and real terminal upload is verified locally without committing real application data.

## M6 — OCR assistance

PR-024–029.

Result: local runtime, MRZ, passports/ID, vehicle documents, review UI and migration assistance.

Gate: field-level metrics are measured on local evidence outside Git, Codex and CI, and critical errors do not bypass the operator.

## M7 — Production hardening

PR-030–035.

Result: encryption, users, backup, installer, security tests and RC.

Gate: offline local acceptance and release decision.

## Future

- macOS build after Windows stabilization;
- дополнительные документы;
- несколько рабочих мест;
- новые терминалы;
- официальная интеграция only if an allowed API is separately approved.

## Не делать преждевременно

Cloud, web frontend, microservices, Kubernetes, event broker, vector DB, LLM, browser automation and plugin system.

## Historical lifecycle snapshot after PR-005 merge and acceptance

GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance of GATE-M0 occurred after PR #5 merge. M0: ACCEPTED. M1: ACCEPTED. PR-004: COMPLETED AND HUMAN ACCEPTED. GATE-S1: COMPLETED AND HUMAN ACCEPTED. ADR-018: ACCEPTED. PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11; PR-S001-F1: COMPLETED; PR-S001-F2: COMPLETED; PR-S001-F3: COMPLETED; PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13 at merge commit `985fae37c7645e8f65edbe4d1609100ee24a2097`.

PR-005: COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 (`PR-005: Add encrypted SQLite persistence and migrations`) at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9` from final reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2`; final migration v0001 checksum is `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`. Exact-head CI run #73 succeeded on Ubuntu and Windows, including Windows SQLCipher evidence for the PR-005 acceptance boundary. Migration v0001 is frozen after merge and every future schema change must use migration v0002 or later.

PR-006: COMPLETED AND HUMAN ACCEPTED. PR-007: COMPLETED AND HUMAN ACCEPTED. PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK; RISK-PR008-W11-SMOKE: ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE; PR-009: AUTHORIZED, NOT STARTED; PR-010 AND LATER: UNAUTHORIZED; Gate 2: NOT ACCEPTED; M3: IN PROGRESS. Gate 1: COMPLETED AND HUMAN ACCEPTED. M2: COMPLETED AND HUMAN ACCEPTED. Q-010: ACCEPTED. Q-017 remains DEFERRED. The sensitive-data/private-contour gate remains open, and real documents and personal data remain prohibited in Git, Codex and CI.

RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.

PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.

PR-007 is completed and human accepted. The template enforcement PR remains future work and does not close the sensitive-data/private-contour gate.

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

## Historical PR-009 contract staging update

PR-009 is now `AUTHORIZED, CONTRACT PROPOSED, PRODUCTION IMPLEMENTATION NOT STARTED`. It is documentation-only until the contract PR is reviewed. PR-009 whole-frame diagnostics advance FR-04 but do not complete cut edges, perspective, document presence or document count. Q-021 remains `OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE`; no final production thresholds are selected. PR-010 remains the staged perspective/geometry task, PR-012 remains the staged document-region/presence/count workflow task, PR-010 AND LATER remain `UNAUTHORIZED`, Gate 2 remains `NOT ACCEPTED`, and M3 remains `IN PROGRESS`.


## Historical lifecycle snapshot — PR-009 calibration lifecycle update — 2026-07-22

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE MERGE BOUNDARY.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

PR-009 infrastructure is ready for human acceptance and may be merged under the documented limitation without activating a production default policy. Human acceptance and merge remain separate pending actions. PR-010 and later require a separate post-merge product-owner decision.
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

PR-013 implements exactly two explicitly ordered confirmed region references, deterministic vertical or horizontal BICUBIC composition on a fresh opaque-white RGB raster, one final PR-011 JPEG encode, immutable encrypted storage and schema-9 persistence, complete write-phase revalidation, and a typed privacy-safe audit event. The v0008 frozen checksum remains `ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b`; the v0009 candidate checksum is `001795f9da8289fd9f06b1a4758e9153c34c2176867c30cb3c06a56bffaeb902`. No human acceptance or merge authorization is claimed.
