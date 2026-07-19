# Матрица трассируемости

| Требование | Модуль | Проверка | План |
|---|---|---|---|
| FR-01 Партии | application/persistence/ui | batch tests | PR-014 |
| FR-02 Импорт | storage/image | immutable import | PR-008 |
| FR-03 Дубли | storage/domain | SHA-256/pHash | PR-008 |
| FR-04 Качество | image | quality fixtures | PR-009 |
| FR-05 Области | image/ui | one/two docs | PR-012 |
| FR-06 Классификация | recognition/ui | review | PR-015/024 |
| FR-07 Предобработка | image | geometry | PR-010 |
| FR-08 OCR/MRZ | recognition | MRZ/candidate | PR-024–028 |
| FR-09 Рукопись | recognition/ui | migration | PR-029 |
| FR-10 Связывание | domain/application | duplicate proposals | PR-016 |
| FR-11 Проверка | ui | field-region | PR-017/028 |
| FR-12 Подтверждение | domain/audit | critical policy | PR-017 |
| FR-13 База | persistence | migrations | PR-005 |
| FR-14 Терминал | application | selection | PR-019 |
| FR-15 Участники | application/ui | filters | PR-018 |
| FR-16 Комплектность | domain/adapters | rule tests | PR-019–023 |
| FR-17 JPEG | image | merge/export | PR-011/013 |
| FR-18 1,90 МиБ | image | boundary | PR-011 |
| FR-19 Excel | adapters | golden | PR-020–022 |
| FR-20 Комплект | storage/application | manifest | PR-023 |
| FR-21 История | snapshots | immutable export | PR-018/023 |
| FR-22 Backup | security/storage | restore | PR-032 |
| FR-23 Шаблоны | admin/adapters | checksum/version | later |
| NFR-01 Offline | all | network block | PR-034 |
| NFR-02 Windows | build | Windows smoke | PR-033 |
| NFR-03 Excel | adapters | reopen/upload | PR-020–023 |
| NFR-04 Performance | recognition | benchmark | PR-024–029 |
| NFR-05 Reliability | storage/UoW | fault injection | all |
| NFR-06 Privacy | logging/CI | PII scan | PR-003/030 |
| NFR-07 Usability | ui | operator test | PR-014–018 |
| NFR-08 Size | build | measurement | PR-033 |

## Правило изменения

Изменение требования обновляет source document, decision log, acceptance criteria, tests and this matrix.


## Gate and decision traceability

| Gate item | Source | Status | Verification |
|---|---|---|---|
| PR-003 completion | ADR-016 | COMPLETED at `ad5782045473d3ef5eb0a097cc8f6982bab821c7` | documentation baseline test |
| M1 Safe Repository | ADR-016 | ACCEPTED | documentation baseline test |
| M0 Requirements Locked | ADR-016 | DECISION APPROVED during GATE-M0 PR; recorded in `main` only after merge and human acceptance | documentation baseline test |
| PR-004 authorization boundary | ADR-016 | Limited to PR-004 Core Domain after gate merge and acceptance | documentation baseline test |
| PR-005/PR-006 encryption staging | ADR-016 / Q-010 / ADR-018 / PR #14 | PR-005 AUTHORIZED, NOT STARTED; PR-006 UNAUTHORIZED | documentation baseline test |
| MVP workstation topology | ADR-017 / Q-008 | One Windows 11 x64 workstation with one active operator session at a time | documentation baseline test |
| Terminal-specific staged questions | Q-001–Q-005 | External confirmation required before target adapter/export PRs | documentation baseline test |
| Local evidence staged questions | Q-012–Q-015 | Real-document and environment evidence remains outside Git, Codex and CI | documentation baseline test |
| Approved template artifact policy | ADR-016 | Product policy permits approved PII-free terminal templates and derivatives after inspection/enforcement update | documentation baseline test |


## PR-004 traceability update

| Gate item | Source | Status | Verification |
|---|---|---|---|
| GATE-M0 | GitHub PR #5 | COMPLETED at `3dada63ea82163c7c4497e290b303d2cc781b085`; human acceptance occurred after merge | documentation baseline test |
| M0 | Product-owner authorization | ACCEPTED | documentation baseline test |
| M1 | Product-owner authorization | ACCEPTED | documentation baseline test |
| PR-004 | GitHub PR #6 | COMPLETED AND HUMAN ACCEPTED at merge commit `6f3021a38305cb92d733a46426cde427828bac04` | domain and documentation tests |
| GATE-S1 | ADR-018 / Q-010 | COMPLETED AND HUMAN ACCEPTED at merge commit `fb9984036f7df0c34badfc3a93f6faec1bc5d38e` | documentation baseline test |
| ADR-018 | Q-010 | ACCEPTED | documentation baseline test |
| PR-S001 | ADR-018 acceptance / PR #14 | ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11 | documentation baseline test |
| PR-005 | Q-010 / PR #14 authorization boundary | AUTHORIZED, NOT STARTED | documentation baseline test |
| PR-006 | Q-010 / authorization boundary | UNAUTHORIZED | documentation baseline test |
| PR-007 AND LATER | authorization boundary | UNAUTHORIZED | documentation baseline test |

## Current lifecycle state

GATE-M0: COMPLETED. M0: ACCEPTED. M1: ACCEPTED. PR-004: COMPLETED AND HUMAN ACCEPTED. GATE-S1: COMPLETED AND HUMAN ACCEPTED. ADR-018: ACCEPTED. Q-010: ACCEPTED. PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11; PR-S001-F1: COMPLETED; PR-S001-F2: COMPLETED; PR-S001-F3: COMPLETED; PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13; PR-S001-F4 merge commit: `985fae37c7645e8f65edbe4d1609100ee24a2097`. PR-005: AUTHORIZED, NOT STARTED. PR-006: UNAUTHORIZED. PR-007 AND LATER: UNAUTHORIZED. Gate 1: NOT ACCEPTED. M2: NOT COMPLETED. The next safe step is prepare and review the exact PR-005 implementation contract, then implement PR-005 under the authorization recorded by PR #14 after PR #14 is merged.

PR-S001-F1, PR-S001-F2, PR-S001-F3 and PR-S001-F4 are completed. PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-005 is AUTHORIZED, NOT STARTED after PR #14 is merged. The exact PR-005 implementation contract must be prepared and reviewed before implementation; the contract review is not a second authorization gate. No additional authorization PR is required for PR-005 within the accepted scope. PR-006 remains UNAUTHORIZED pending its own task review and explicit authorization. Q-017 remains deferred. The sensitive-data/private-contour gate remains open, and real documents and personal data remain prohibited in Git, Codex and CI.


PR-S001 lifecycle boundary: PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only; PR-S001 contains no production persistence/storage API; a negative feasibility result is valid; PR #14 records the explicit product-owner authorization for PR-005. No additional authorization PR is required for PR-005 within the accepted scope. PR-005 has not started.


## PR-005 traceability update

FR-13: PR-005 IN REVIEW. Verification references migration tests, SQLCipher Windows integration, repository round trips, Unit of Work transaction tests, immutable snapshot persistence and privacy tests. FR-13 is not accepted.
