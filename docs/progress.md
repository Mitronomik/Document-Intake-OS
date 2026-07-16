# Progress

**Обновлено:** 2026-07-16  
**Статус:** PR-001 COMPLETED

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

- [ ] privacy gate remains open;
- [ ] terminal and security questions required for subsequent stages remain unresolved.

## Не начато

- [ ] approved private development contour for terminal templates and template-derived golden files;
- [ ] domain implementation;
- [ ] storage implementation;
- [ ] image pipeline;
- [ ] terminal adapters;
- [ ] OCR benchmark;
- [ ] installer.

## Блокеры

Visitors terminal name, TSP format, participant limits, completeness matrix, merge rules, workstation count, retention, encryption and missing document samples.

## Следующий безопасный шаг

1. review repository visibility and approve the private development contour before any template or template-derived golden file is introduced;
2. confirm Q-001–Q-007;
3. determine which unresolved decisions block PR-002 and PR-003;
4. prepare the next single-scope PR only after its dependencies and acceptance criteria are confirmed.

M0 пока не закрыт из-за терминальных вопросов и открытого privacy gate.
