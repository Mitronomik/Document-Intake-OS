# Progress

**Обновлено:** 2026-07-16  
**Статус:** GATE-M0 IN REVIEW

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
- [x] PR-003 COMPLETED and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`;
- [x] M1 ACCEPTED by the product owner;
- [x] no terminal templates are committed;
- [x] no personal data are committed.

## В работе

- [ ] GATE-M0 IN REVIEW;
- [ ] M0 DECISION APPROVED, NOT YET RECORDED IN MAIN;
- [ ] REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE;
- [ ] SENSITIVE-DATA / PRIVATE-CONTOUR GATE — OPEN;
- [ ] PR-004 BLOCKED UNTIL GATE-M0 PR MERGE AND HUMAN ACCEPTANCE.

## Не начато / unauthorized

- [ ] PR-004 implementation is not started in GATE-M0;
- [ ] PR-005 remains unauthorized pending a separate Q-010 security ADR;
- [ ] PR-006 remains unauthorized pending a separate Q-010 security ADR;
- [ ] PR-007 and later implementation tasks remain unauthorized by GATE-M0;
- [ ] Repository-policy enforcement update required before the first approved terminal template or template-derived binary artifact is committed;
- [ ] storage implementation;
- [ ] image pipeline;
- [ ] terminal adapters;
- [ ] OCR benchmark;
- [ ] installer.

## Блокеры and staged questions

- Q-001 through Q-005 are staged as external terminal confirmations and do not block domain-only PR-004 under ADR-016.
- Q-008 is accepted by ADR-017: one Windows 11 x64 workstation with one active operator session at a time.
- Q-010 remains OPEN and blocks PR-005 and PR-006 until a separate accepted security ADR resolves encryption staging.
- Q-012 through Q-015 require local evidence outside Git, Codex and CI.
- Approved PII-free template artifacts are permitted by product policy after technical privacy inspection and repository-policy enforcement updates; real documents, PII-bearing artifacts and private acceptance materials remain outside Git, Codex and CI.

## Следующий безопасный шаг

Complete review, CI and human acceptance for the GATE-M0 PR. Do not start PR-004 until the GATE-M0 PR is merged and accepted. Do not start PR-005, PR-006 or later tasks until separately authorized.
