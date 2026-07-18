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

## Current lifecycle state

GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance of GATE-M0 occurred after PR #5 merge. M0: ACCEPTED. M1: ACCEPTED. PR-004: COMPLETED AND HUMAN ACCEPTED. GATE-S1: COMPLETED AND HUMAN ACCEPTED. ADR-018: ACCEPTED. PR-S001: MERGED AS RESEARCH HARNESS; PR-S001 FINAL ACCEPTANCE: NOT ACCEPTED; PR-S001-F1: COMPLETED AND MERGED THROUGH PR #10 at merge commit `b9c07a0c2b152bdad21e5d50126917c55b349e12`; PR-S001-F2: CURRENT CORRECTION. PR-005: UNAUTHORIZED. PR-006: UNAUTHORIZED. PR-007 AND LATER: UNAUTHORIZED. Gate 1: NOT ACCEPTED. M2: NOT COMPLETED. Q-010: ACCEPTED. Under ADR-016, the template enforcement PR remains future work and does not block PR-004. The sensitive-data/private-contour gate remains open for real data.

## Authorization boundary

GATE-S1 is completed and human accepted after GitHub PR #7. PR #9 merged PR-S001 as a research harness; PR-S001 final acceptance is NOT ACCEPTED and PR-S001-F1 is the current correction. PR-005, PR-006, PR-007 and later work remain unauthorized.

## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption staging, PII logs, critical field bypass and insufficient local OCR samples.

## Продолжение

The next safe step is complete PR-S001-F2 WAL/rollback-journal evidence correction before product-owner PR-S001 feasibility review. Before each later task, read the authoritative sources, check the applicable gate, form a single PR contract and preserve unresolved questions unless an accepted ADR explicitly resolves them.

PR-S001-F2 is the only authorized current correction; PR-S001-F1 completed and merged through PR #10. PR-S001/PR-S001-F1/PR-S001-F2 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-005 does not start automatically after PR-S001 merge; explicit human acceptance and authorization are required after PR-S001. PR-006 remains blocked until PR-S001 acceptance and a separate PR-006 task review. Q-017 remains deferred. The sensitive-data/private-contour gate remains open, and real documents and personal data remain prohibited in Git, Codex and CI.


PR-S001 lifecycle boundary: PR-S001/PR-S001-F1/PR-S001-F2 use fictional synthetic data only; PR-S001 contains no production persistence/storage API; a negative feasibility result is valid; PR-S001 merge does not authorize PR-005; human acceptance and separate authorization remain required.
