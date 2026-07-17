# Roadmap

## M0 — Requirements locked

Result: requirements package, open-question status model, accepted decisions and repository documentation.

Gate: MVP scope is confirmed, real documents are excluded from the cloud/public development contour, the repository privacy boundary is accepted for non-sensitive code, terminal-specific blockers are either externally confirmed or staged to downstream gates under ADR-016, and no placeholder terminal values are invented.

GATE-M0 is in review. ADR-016 records the approved M0 decision for this PR, but PR-004 remains blocked until the GATE-M0 PR is merged and human acceptance confirms the decision in `main`.

## M1 — Safe repository

PR-001–003.

Result: reproducible environment, CI, AGENTS, privacy guardrails and minimal UI.

M1 is accepted by the product owner after PR-003 was completed and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`.

## M2 — Local data core

PR-004–007.

Result: domain, SQLite, immutable storage and audit.

PR-004 — Core Domain is the only implementation task authorized by the approved M0 decision, and only after the GATE-M0 PR is merged and human acceptance confirms the decision in `main`. PR-005, PR-006, PR-007 and every later implementation task remain unauthorized. PR-005 and PR-006 remain blocked until a separate accepted security ADR resolves Q-010 encryption staging.

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

GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance occurred after merge of PR #5. M0: ACCEPTED. M1: ACCEPTED. PR-004: IN REVIEW after implementation submission; PR-004 is authorized and started by this PR, but is not completed before merge and human acceptance. PR-005: UNAUTHORIZED. PR-006: UNAUTHORIZED. PR-007 AND LATER: UNAUTHORIZED. Gate 1 is not accepted. M2 is not completed. Q-010 remains open. The template enforcement PR remains future work and does not block PR-004. The sensitive-data/private-contour gate remains open for real data.
