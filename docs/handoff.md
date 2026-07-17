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

## Текущий этап

PR-001 and PR-002 are completed. PR-003 is completed and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`. M1 Safe Repository is accepted by the product owner.

GATE-M0 is in review. M0 decision is approved in this PR, but not yet recorded in `main`. PR-004 remains blocked until the GATE-M0 PR is merged and human acceptance confirms the decision in `main`.

ADR-016 accepts the repository privacy boundary for non-sensitive code and documentation while keeping the sensitive-data/private-contour gate open for real documents, personal data, real application data, private fixtures and local acceptance evidence. Approved PII-free template artifacts are permitted by product policy, while current technical enforcement remains temporarily stricter until a separate repository-policy enforcement PR updates scanner and `.gitignore` rules.

## Authorization boundary

GATE-M0 does not start PR-004. After this PR is merged and accepted, the next repository update may prepare PR-004 — Core Domain only.

PR-005 and PR-006 remain unauthorized until a separate accepted security ADR resolves Q-010 encryption staging. PR-007 and later tasks remain unauthorized by GATE-M0.

## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption staging, PII logs, critical field bypass and insufficient local OCR samples.

## Продолжение

Before each task, read the authoritative sources, check the applicable gate, form a single PR contract and preserve unresolved questions unless an accepted ADR explicitly resolves them. The next safe step is GATE-M0 review, CI, merge and human acceptance; do not start PR-004 until that happens.
