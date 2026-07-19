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
| PR-005/PR-006 encryption staging | ADR-016 / Q-010 / ADR-018 / PR #14 / PR #15 | PR-005 COMPLETED AND HUMAN ACCEPTED through PR #15; PR-006 COMPLETED AND HUMAN ACCEPTED through PR #17 | documentation baseline test |
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
| PR-005 | Q-010 / PR #14 authorization boundary / PR #15 | COMPLETED AND HUMAN ACCEPTED at reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2` and merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`; verified by documentation baseline checks and persistence tests | documentation and persistence test verification |
| PR-006 | Q-010 / authorization boundary / PR #17 | COMPLETED AND HUMAN ACCEPTED | documentation baseline test |
| PR-007 AND LATER | authorization boundary | UNAUTHORIZED | documentation baseline test |

## Current lifecycle state

GATE-M0: COMPLETED. M0: ACCEPTED. M1: ACCEPTED. PR-004: COMPLETED AND HUMAN ACCEPTED. GATE-S1: COMPLETED AND HUMAN ACCEPTED. ADR-018: ACCEPTED. Q-010: ACCEPTED. PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11; PR-S001-F1: COMPLETED; PR-S001-F2: COMPLETED; PR-S001-F3: COMPLETED; PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13; PR-S001-F4 merge commit: `985fae37c7645e8f65edbe4d1609100ee24a2097`.

PR-005: COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 (`PR-005: Add encrypted SQLite persistence and migrations`) at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9` from final reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2`; final migration v0001 checksum is `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`. Exact-head CI run #73 succeeded on Ubuntu and Windows, including Windows SQLCipher evidence for the PR-005 acceptance boundary. Migration v0001 is frozen after merge and every future schema change must use migration v0002 or later.

PR-006: COMPLETED AND HUMAN ACCEPTED. PR-007: AUTHORIZED, NOT STARTED. PR-008 AND LATER: UNAUTHORIZED. Gate 1: NOT ACCEPTED. M2: NOT COMPLETED. Q-017 remains DEFERRED. The sensitive-data/private-contour gate remains open, and real documents and personal data remain prohibited in Git, Codex and CI. The next safe step is merging this lifecycle PR before starting PR-007 implementation.

RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.

PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.

## PR-005 traceability update

The PR-005 persistence slice for FR-13 is COMPLETED AND HUMAN ACCEPTED. The accepted slice covers persistence of the existing PR-004 domain scope: Person, IdentityDocument, MigrationDocument, Vehicle, Terminal, Document, FieldCandidate, Application with ParticipantAssignment, VerifiedField and ValidationReport issues, and immutable ApplicationSnapshot artifact references. FR-13 remains not fully complete beyond this accepted slice because later storage and application concepts remain deferred.

Verification includes migrations, SQLCipher Windows integration, repository round trips, Unit of Work transaction tests, immutable snapshots and privacy tests. PR-005 final-audit correction verification covers UoW terminal-state enforcement and cleanup, canonical payload/projection consistency, projection tamper detection, complete immutable snapshot ordinals, applied migration-prefix validation, independent literal v0001 checksum verification, stable persistence/deserialization errors, the intentionally opaque vehicle registration-document reference and real Windows production-adapter ciphertext tamper/truncation tests. Gate 1 and M2 remain incomplete, PR-006 is authorized and in review but not accepted, and RISK-PR005-RAWKEY-PRAGMA remains open for installer, pilot and production release.

Q-009: DEFERRED. PR-006 implements no retention, deletion or secure-deletion policy.


## PR-006 current lifecycle

PR-006: `COMPLETED AND HUMAN ACCEPTED`.
PR-007: `AUTHORIZED, NOT STARTED`
PR-008 and later: `UNAUTHORIZED`.
Gate 1: `NOT ACCEPTED`.
M2: `NOT COMPLETED`.
Q-009: `DEFERRED`.
Q-017: `DEFERRED`.
Q-017 remains deferred.

## Lifecycle update — PR-006 acceptance and PR-007 authorization

Verified live base SHA: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.

PR-006: `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`, final reviewed head `28d8b590adb7a7ae11e35f631eb9895c930b3cef`, merge commit `4c117ededc250d57961e2f5f4c8b4de01edf0c54`, merge date `2026-07-19`, final v0001 checksum `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`, final v0002 checksum `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`, local verification `306 passed, 2 skipped on macOS`, exact-head GitHub Actions jobs passed for Python checks on Ubuntu, Python checks on Windows, PR-S001 Windows encryption spike and PR-S001 DPAPI cross-runner negative, and exact-head CI workflow run `CI #85` succeeded.

ADR numbering after repair: ADR-019 is PR-005 SQLCipher binding and raw-key staging; ADR-020 is immutable encrypted filesystem storage v1; ADR-021 is immutable PII-safe audit events. The PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction.

PR-007: `AUTHORIZED, NOT STARTED`. PR-007 implementation may begin only after this lifecycle pull request is merged into `main`. PR-008 and later: `UNAUTHORIZED`. Gate 1: `NOT ACCEPTED`. M2: `NOT COMPLETED`. Gate 1 and M2 remain incomplete until PR-007 is implemented, reviewed, merged and separately human accepted through a later lifecycle decision.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.

## PR-007 audit traceability

| Item | Source | Current status | Verification |
| --- | --- | --- | --- |
| FR-12 | Technical specification / ADR-021 / PR-007 / PR-017 | PR-007 provides immutable PII-safe audit foundation only; FR-12 remains incomplete after PR-007 alone; PR-017 remains responsible for operator correction and verification event emission | future PR-007 and PR-017 tests |
| FR-13 | Technical specification / ADR-021 / PR-007 | PR-007 authorized to add append-only audit persistence foundation | future PR-007 tests |

Current lifecycle: PR-007: `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`; PR-008 and later: `UNAUTHORIZED`; Gate 1: `NOT ACCEPTED`; M2: `NOT COMPLETED`.
