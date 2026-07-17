# Progress

**Обновлено:** 2026-07-17
**Статус:** PR-004: IN REVIEW

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
- [x] M1: ACCEPTED by the product owner;
- [x] GATE-M0: COMPLETED;
- [x] GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`;
- [x] Human acceptance of GATE-M0 occurred after PR #5 merge;
- [x] M0: ACCEPTED;
- [x] no terminal templates are committed;
- [x] no personal data are committed.

## Current lifecycle state

- [ ] PR-004: IN REVIEW;
- [ ] PR-004 is the only authorized implementation task;
- [ ] PR-004: NOT COMPLETED BEFORE MERGE AND PRODUCT-OWNER ACCEPTANCE;
- [ ] PR-005: UNAUTHORIZED;
- [ ] PR-006: UNAUTHORIZED;
- [ ] PR-007 AND LATER: UNAUTHORIZED;
- [ ] Gate 1: NOT ACCEPTED;
- [ ] M2: NOT COMPLETED;
- [ ] Q-010: OPEN;
- [ ] REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE;
- [ ] The sensitive-data/private-contour gate remains open for real data.

## Not started / unauthorized

- [ ] PR-005 must not start after PR-004 merge without the separate Q-010 security ADR;
- [ ] PR-006 remains unauthorized pending a separate Q-010 security ADR;
- [ ] PR-007 and later implementation tasks remain unauthorized;
- [ ] The template enforcement PR remains future work and does not block PR-004;
- [ ] storage implementation;
- [ ] image pipeline;
- [ ] terminal adapters;
- [ ] OCR benchmark;
- [ ] installer.

## Blockers and staged questions

- Q-001 through Q-005 are staged as external terminal confirmations and do not block domain-only PR-004 under ADR-016.
- Q-008 is accepted by ADR-017: one Windows 11 x64 workstation with one active operator session at a time.
- Q-010: OPEN and blocks PR-005 and PR-006 until a separate accepted security ADR resolves encryption staging.
- Q-012 through Q-015 require local evidence outside Git, Codex and CI.
- Approved PII-free template artifacts are permitted by product policy after technical privacy inspection and repository-policy enforcement updates; real documents, PII-bearing artifacts and private acceptance materials remain outside Git, Codex and CI.

## Следующий безопасный шаг

Complete review, CI, merge and human acceptance for PR-004. Do not start PR-005 after PR-004 merge without the separate Q-010 security ADR. Do not start PR-006, PR-007 or later tasks until separately authorized.
