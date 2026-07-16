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

## Текущий этап

PR-001 is completed and merged. PR-002 is the current repository-safety task and remains under review until it is merged and accepted.

M0 remains open because terminal questions and the privacy gate remain unresolved. Formal M1 entry is not asserted while the M0 gate remains unresolved.

The sequencing of M0 and the PR-001–PR-003 repository-safety work requires an explicit product-owner decision. PR-003 must not begin before PR-002 acceptance and that sequencing decision.

## PR-002 boundaries

No OCR, domain, persistence, storage, image processing, UI workflow or Excel implementation should start in PR-002.

Real documents, document-derived fixtures, terminal templates, cleaned or anonymized terminal templates and template-derived golden Excel files remain outside the public repository.

## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption, PII logs, critical field bypass and insufficient samples.

## Продолжение

Before each task, read the authoritative sources, check the applicable gate, form a single PR contract and preserve unresolved questions unless an accepted ADR explicitly resolves them.
