# Roadmap

## M0 — Requirements locked

Результат: ТЗ, очищенные шаблоны, open questions, decisions and repository docs.

Gate: scope MVP подтвержден, реальные документы исключены из облачного контура, терминальные блокеры закрыты.

M0 remains open and its gate remains unchanged. ADR-015 permits only the PR-001 through PR-003 repository-safety workstream to proceed while M0 is open. Completion of M1 repository-safety work does not imply completion of M0.

## M1 — Safe repository

PR-001–003.

Результат: воспроизводимая среда, CI, AGENTS, privacy guardrails and minimal UI.

M1 is not marked completed by PR-003. M1 can be considered complete only after PR-003 is merged and human acceptance confirms the repository-safety workstream.

## M2 — Local data core

PR-004–007.

Результат: domain, SQLite, immutable storage and audit.

Gate: original нельзя изменить, verification policy тестируется, migrations воспроизводимы.

M2 cannot begin until M0 is accepted and M1 repository-safety work is accepted. Completion of PR-003 does not automatically authorize M2.

## M3 — Manual image workflow

PR-008–013.

Результат: import, quality, crop/perspective, multiple docs, merge and JPEG ≤1.90 MiB.

Gate: типовые реальные фото локально готовятся без потери originals.

## M4 — Manual end-to-end MVP

PR-014–018.

Результат: batches, classification, cards, verification, application and snapshot.

Gate: приложение полезно без OCR.

## M5 — Three terminal exports

PR-019–023.

Результат: Visitors, MGS, TSP and export package.

Gate: все формы открываются без repair и проходят terminal upload.

## M6 — OCR assistance

PR-024–029.

Результат: local runtime, MRZ, passports/ID, vehicle documents, review UI and migration assistance.

Gate: field-level metrics измерены, critical errors не обходят оператора.

## M7 — Production hardening

PR-030–035.

Результат: encryption, users, backup, installer, security tests and RC.

Gate: offline local acceptance and release decision.

## Future

- macOS build;
- дополнительные документы;
- несколько рабочих мест;
- новые терминалы;
- официальная интеграция только при наличии разрешенного API.

## Не делать преждевременно

Cloud, web frontend, microservices, Kubernetes, event broker, vector DB, LLM, browser automation and plugin system.
