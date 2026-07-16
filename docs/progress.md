# Progress

**Обновлено:** 2026-07-16  
**Статус:** PR-002 IN REVIEW

## Завершено

- [x] собран бизнес-контекст;
- [x] изучены реальные типы фотографий;
- [x] получены три Excel-формы вне публичного Git-контура;
- [x] подготовлено ТЗ v1.0;
- [x] зафиксирован offline;
- [x] Windows 11 выбрана первой платформой;
- [x] JPEG limit 1,90 МиБ;
- [x] OCR draft + operator verification;
- [x] Konversta integration исключена из MVP;
- [x] подготовлен пакет Markdown-документации;
- [x] GitHub repository exists;
- [x] repository is temporarily public by explicit product-owner decision;
- [x] PR-001 принят и смержен в `main` коммитом `6ca116e`;
- [x] создан Python 3.12 repository skeleton;
- [x] `uv.lock` сгенерирован через uv и добавлен в Git;
- [x] добавлен минимальный PySide6 entry point;
- [x] зафиксированы архитектурные границы пакетов;
- [x] добавлены bootstrap smoke tests;
- [x] Ubuntu и Windows CI прошли на финальной версии PR;
- [x] local macOS bootstrap smoke test passed;
- [x] no terminal templates are committed;
- [x] no personal data are committed.

## В работе

- [ ] PR-002 documentation-baseline implementation is submitted for review;
- [ ] privacy gate remains open;
- [ ] terminal and security questions required for subsequent stages remain unresolved.

## Не начато

- [ ] PR-003 CI and privacy guardrails; PR-003 must not start before PR-002 acceptance and an explicit product-owner decision on M0/M1 lifecycle sequencing that permits repository-safety work to continue;
- [ ] approved private development contour for terminal templates and template-derived golden files;
- [ ] domain implementation;
- [ ] storage implementation;
- [ ] image pipeline;
- [ ] terminal adapters;
- [ ] OCR benchmark;
- [ ] installer.

## Блокеры

Visitors terminal name, TSP format, participant limits, completeness matrix, merge rules, workstation count, retention, encryption and missing document samples remain unresolved.

M0/M1 lifecycle sequencing remains unresolved: `docs/implementation-plan.md` requires a gate acceptance before the next major stage, `docs/roadmap.md` groups PR-001–PR-003 under M1 Safe Repository, and M0 cannot close while terminal questions and the privacy gate remain open. Formal M1 entry is not asserted until an explicit product-owner sequencing decision is recorded.

## Следующий безопасный шаг

1. complete human review and CI for PR-002 without marking it completed before merge;
2. keep M0 open until terminal questions and the privacy gate are resolved;
3. after PR-002 acceptance and an explicit product-owner lifecycle-sequencing decision, prepare PR-003 only if that decision permits the repository-safety work to continue.

M0 remains open because terminal questions and the privacy gate remain open.
