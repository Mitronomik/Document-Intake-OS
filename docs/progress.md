# Progress

**Обновлено:** 2026-07-16  
**Статус:** PR-003 IN REVIEW

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
- [x] PR-001 completed and merged in `main` commit `6ca116e`;
- [x] PR-002 completed and merged through GitHub PR #3 with merge commit `d7203f82`;
- [x] ADR-015 accepted by the product owner;
- [x] no terminal templates are committed;
- [x] no personal data are committed.

## В работе

- [ ] PR-003 implementation is under review;
- [ ] M0 remains open;
- [ ] privacy gate remains open;
- [ ] terminal and security questions remain unresolved;
- [ ] M1 is not completed before PR-003 merge and human acceptance;
- [ ] M2 and PR-004+ remain blocked.

## Не начато

- [ ] approved private development contour for terminal templates and template-derived golden files;
- [ ] domain implementation;
- [ ] storage implementation;
- [ ] image pipeline;
- [ ] terminal adapters;
- [ ] OCR benchmark;
- [ ] installer.

## Блокеры

Visitors terminal name, TSP format, participant limits, completeness matrix, merge rules, workstation count, retention, encryption and missing document samples remain unresolved.

ADR-015 resolves repository-safety sequencing only for PR-001 through PR-003. Completion of PR-003 does not imply completion of M0, does not close the privacy gate and does not automatically authorize M2.

## Следующий безопасный шаг

1. complete human review and CI for PR-003 without marking it completed before merge;
2. keep M0 open until terminal questions and the privacy gate are resolved;
3. keep M2 and PR-004+ blocked until M0 is accepted and M1 repository-safety work is accepted.

M0 remains open because terminal questions and the privacy gate remain open.
