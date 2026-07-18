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

PR-004 — Core Domain is completed and human accepted. GATE-S1 is completed and human accepted. ADR-018 is accepted for Q-010. PR #9 merged PR-S001 as a research harness; PR-S001 final acceptance is NOT ACCEPTED and PR-S001-F3 is the current correction. PR-005, PR-006, PR-007 and every later implementation task remain unauthorized. PR-005 and PR-006 remain blocked until accepted PR-S001 review and explicit follow-up authorization and later authorization.

## M3 — Manual image workflow

PR-008–013.

Result: import, quality, crop/perspective, multiple docs, merge and JPEG ≤1.90 MiB.

Gate: типовые реальные фото локально готовятся без потери originals. Local evidence remains outside Git, Codex and CI.

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

## Current lifecycle after GATE-M0 merge

GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance of GATE-M0 occurred after PR #5 merge. M0: ACCEPTED. M1: ACCEPTED. PR-004: COMPLETED AND HUMAN ACCEPTED. GATE-S1: COMPLETED AND HUMAN ACCEPTED. ADR-018: ACCEPTED. PR-S001: MERGED AS RESEARCH HARNESS; PR-S001 FINAL ACCEPTANCE: NOT ACCEPTED; PR-S001-F1: COMPLETED AND MERGED THROUGH PR #10 at merge commit `b9c07a0c2b152bdad21e5d50126917c55b349e12`; PR-S001-F2: COMPLETED AND MERGED THROUGH PR #11; PR-S001-F2 merge commit: `7559dbb6189f6e0181eec8a44a7de262cadf036f`; PR-S001-F3: CURRENT CORRECTION. PR-005: UNAUTHORIZED. PR-006: UNAUTHORIZED. PR-007 AND LATER: UNAUTHORIZED. Gate 1: NOT ACCEPTED. M2: NOT COMPLETED. Q-010: ACCEPTED. The template enforcement PR remains future work and does not block PR-004. The sensitive-data/private-contour gate remains open for real data. The next safe step is complete PR-S001-F3 ACL diagnostics correction before product-owner PR-S001 feasibility review. PR-005 must not start without accepted encryption staging and later authorization.

PR-S001-F3 is the only authorized current correction; PR-S001-F1 completed and merged through PR #10. PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-005 does not start automatically after PR-S001 merge; explicit human acceptance and authorization are required after PR-S001. PR-006 remains blocked until PR-S001 acceptance and a separate PR-006 task review. Q-017 remains deferred. The sensitive-data/private-contour gate remains open, and real documents and personal data remain prohibited in Git, Codex and CI.


PR-S001 lifecycle boundary: PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3 use fictional synthetic data only; PR-S001 contains no production persistence/storage API; a negative feasibility result is valid; PR-S001 merge does not authorize PR-005; human acceptance and separate authorization remain required.
