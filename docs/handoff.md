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

GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance of GATE-M0 occurred after PR #5 merge. M0: ACCEPTED. M1: ACCEPTED. PR-004: IN REVIEW. PR-004 is the only authorized implementation task. PR-004: NOT COMPLETED BEFORE MERGE AND PRODUCT-OWNER ACCEPTANCE. PR-005: UNAUTHORIZED. PR-006: UNAUTHORIZED. PR-007 AND LATER: UNAUTHORIZED. Gate 1: NOT ACCEPTED. M2: NOT COMPLETED. Q-010: OPEN. Under ADR-016, the template enforcement PR remains future work and does not block PR-004. The sensitive-data/private-contour gate remains open for real data.

## Authorization boundary

PR-004 Core Domain is the only authorized implementation task. PR-005, PR-006, PR-007 and later work remain unauthorized. PR-005 cannot start after PR-004 merge without a separate accepted Q-010 security ADR.

## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption staging, PII logs, critical field bypass and insufficient local OCR samples.

## Продолжение

The next safe step is review, CI, merge and product-owner acceptance of PR-004. Before each later task, read the authoritative sources, check the applicable gate, form a single PR contract and preserve unresolved questions unless an accepted ADR explicitly resolves them.
