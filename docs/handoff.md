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

PR-001 and PR-002 are completed. ADR-015 resolves repository-safety sequencing for PR-001 through PR-003 only.

PR-003 is the current task and remains under review until it is merged and accepted. M0 remains open because terminal questions and the privacy gate remain open. The privacy gate remains open. M1 is not completed before PR-003 merge and human acceptance.

M2 and product implementation remain blocked until M0 is accepted and M1 repository-safety work is accepted.

## PR-003 boundaries

PR-003 records ADR-015 and adds repository-safety guardrails only. It does not use real documents or terminal templates, and it does not add fixtures.

No OCR, domain, persistence, storage, image processing, UI workflow or Excel implementation should start in PR-003. Real documents, document-derived fixtures, terminal templates, cleaned or anonymized terminal templates and template-derived golden Excel files remain outside the public repository.

## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption, PII logs, critical field bypass and insufficient samples.

## Продолжение

Before each task, read the authoritative sources, check the applicable gate, form a single PR contract and preserve unresolved questions unless an accepted ADR explicitly resolves them. The next safe step is PR-003 review and acceptance; do not start PR-004 until M0 and M1 acceptance allow it.
