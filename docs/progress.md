# Progress

**Обновлено:** 2026-07-19
**Статус:** PR-005: COMPLETED AND HUMAN ACCEPTED; PR-006: COMPLETED AND HUMAN ACCEPTED; PR-007: AUTHORIZED AND IN REVIEW, NOT ACCEPTED; PR-008 AND LATER: UNAUTHORIZED

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
- [x] PR-004: COMPLETED AND HUMAN ACCEPTED;
- [x] GATE-S1: COMPLETED AND HUMAN ACCEPTED;
- [x] ADR-018: ACCEPTED;
- [x] PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11;
- [x] PR-S001-F1, PR-S001-F2 and PR-S001-F3: COMPLETED;
- [x] PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13 at merge commit `985fae37c7645e8f65edbe4d1609100ee24a2097`;
- [x] PR-005: COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 (`PR-005: Add encrypted SQLite persistence and migrations`), reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2`, merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`, merge date `2026-07-19`;
- [x] PR-005 final migration v0001 checksum: `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`;
- [x] PR-005 exact-head GitHub Actions CI run #73: success, including `Python checks (ubuntu-latest)`, `Python checks (windows-latest)`, `PR-S001 Windows encryption spike` and `PR-S001 DPAPI cross-runner negative`;
- [x] PR-005 local validation: `191 passed, 2 skipped on macOS`; the two skipped local tests were Windows AMD64 SQLCipher integration tests and were skipped locally as designed, while the full Windows CI pytest step passed on the reviewed PR head;
- [x] PR-005 final persistence audit blockers closed before merge: SQLite replacement forms cannot replace immutable snapshot rows; loss of the outer transaction invalidates and closes the UoW; list reads detect payload/projection corruption before filtering; canonical boolean and collection deserialization is strict;
- [x] no terminal templates are committed;
- [x] no personal data are committed.

## Current lifecycle state

- [x] PR-005: COMPLETED AND HUMAN ACCEPTED;
- [x] PR-005 was merged through GitHub PR #15 at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9` from final reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2`;
- [x] PR-005 v0001 migration checksum is final at `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`; migration v0001 is frozen after merge and every future schema change must use migration v0002 or later;
- [x] Windows SQLCipher evidence is complete for the PR-005 acceptance boundary through exact-head CI run #73;
- [x] PR-006: COMPLETED AND HUMAN ACCEPTED;
- [ ] PR-007: AUTHORIZED AND IN REVIEW, NOT ACCEPTED; PR-008 AND LATER: UNAUTHORIZED;
- [ ] Gate 1: NOT ACCEPTED;
- [ ] M2: NOT COMPLETED;
- [x] Q-010: ACCEPTED;
- [ ] Q-017 remains DEFERRED;
- [x] REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE;
- [ ] The sensitive-data/private-contour gate remains open for real data;
- [ ] Real documents and personal data remain prohibited in Git, Codex and CI;
- [ ] RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.

## Not started / unauthorized

- [x] PR-006 is COMPLETED AND HUMAN ACCEPTED through PR #17;
- [ ] PR-007 is AUTHORIZED AND IN REVIEW, NOT ACCEPTED; PR-008 and later implementation tasks remain UNAUTHORIZED;
- [ ] The template enforcement PR remains future work and does not block PR-004 or PR-005 closure;
- [ ] integration of immutable storage into the future file-import workflow;
- [ ] image pipeline;
- [ ] terminal adapters;
- [ ] OCR benchmark;
- [ ] installer.

## Blockers and staged questions

- Q-001 through Q-005 are staged as external terminal confirmations and do not block domain-only PR-004 under ADR-016.
- Q-008 is accepted by ADR-017: one Windows 11 x64 workstation with one active operator session at a time.
- Q-010: ACCEPTED; ADR-018 is ACCEPTED and resolves Q-010 at the architecture and sequencing level.
- Q-012 through Q-015 require local evidence outside Git, Codex and CI.
- Q-017 remains DEFERRED.
- Approved PII-free template artifacts are permitted by product policy after technical privacy inspection and repository-policy enforcement updates; real documents, PII-bearing artifacts and private acceptance materials remain outside Git, Codex and CI.

## Следующий безопасный шаг

PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.

PR-007 implementation is in review. Do not start PR-008 or later work.

Q-009: DEFERRED. PR-006 implements no retention, deletion or secure-deletion policy.


## PR-006 current lifecycle

PR-006: `COMPLETED AND HUMAN ACCEPTED`.
PR-007: `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`
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

PR-007: `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`. PR-007 implementation may begin only after this lifecycle pull request is merged into `main`. PR-008 and later: `UNAUTHORIZED`. Gate 1: `NOT ACCEPTED`. M2: `NOT COMPLETED`. Gate 1 and M2 remain incomplete until PR-007 is implemented, reviewed, merged and separately human accepted through a later lifecycle decision.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.
