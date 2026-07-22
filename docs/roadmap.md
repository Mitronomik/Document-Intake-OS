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

PR-004 — Core Domain is completed and human accepted. GATE-S1 is completed and human accepted. ADR-018 is accepted for Q-010. PR #9 merged PR-S001 as a research harness; PR-S001 is ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11. PR-005 is COMPLETED AND HUMAN ACCEPTED through GitHub PR #15. PR-006 and PR-007 are COMPLETED AND HUMAN ACCEPTED. M2 is completed and human accepted by PR-007 acceptance. PR-008 is completed and human accepted with documented residual risk. PR-009 is implemented and ready for human acceptance with a documented residual limitation; PR-010 and every later implementation task remains unauthorized.

## M3 — Manual image workflow

PR-008–013.

Result: import, quality, crop/perspective, multiple docs, merge and JPEG ≤1.90 MiB.

Gate: типовые реальные фото локально готовятся без потери originals. Local evidence remains outside Git, Codex and CI.

M3 status:

- PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK.
- PR-009: IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION.
- Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
- Production default quality policy: NOT ACTIVE.
- RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE MERGE BOUNDARY.
- PR-010–PR-013: UNAUTHORIZED.
- Gate 2: NOT ACCEPTED.
- M3: IN PROGRESS.

The physical Windows 11 smoke risk `RISK-PR008-W11-SMOKE` remains deferred to Windows installer, pilot or final release acceptance; no physical Windows 11 smoke is claimed.

PR-009 infrastructure may be human accepted and merged without a production default policy. Policy injection remains explicit, production composition must fail closed when no accepted policy is configured, and the residual limitation blocks production quality decisions rather than infrastructure acceptance. Human acceptance and merge are still pending.

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

## Historical PR-009 contract staging update

PR-009 is now `AUTHORIZED, CONTRACT PROPOSED, PRODUCTION IMPLEMENTATION NOT STARTED`. It is documentation-only until the contract PR is reviewed. PR-009 whole-frame diagnostics advance FR-04 but do not complete cut edges, perspective, document presence or document count. Q-021 remains `OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE`; no final production thresholds are selected. PR-010 remains the staged perspective/geometry task, PR-012 remains the staged document-region/presence/count workflow task, PR-010 AND LATER remain `UNAUTHORIZED`, Gate 2 remains `NOT ACCEPTED`, and M3 remains `IN PROGRESS`.


## PR-009 calibration lifecycle update — 2026-07-22

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE MERGE BOUNDARY.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

PR-009 infrastructure is ready for human acceptance and may be merged under the documented limitation without activating a production default policy. Human acceptance and merge remain separate pending actions. PR-010 and later require a separate post-merge product-owner decision.
