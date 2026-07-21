# Progress

**Обновлено:** 2026-07-21
**Статус:** PR-005: COMPLETED AND HUMAN ACCEPTED; PR-006: COMPLETED AND HUMAN ACCEPTED; PR-007: COMPLETED AND HUMAN ACCEPTED; PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK; RISK-PR008-W11-SMOKE: ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE; PR-009: AUTHORIZED, NOT STARTED; PR-010 AND LATER: UNAUTHORIZED; Gate 2: NOT ACCEPTED; M3: IN PROGRESS

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
- [x] PR-007: COMPLETED AND HUMAN ACCEPTED; PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK; RISK-PR008-W11-SMOKE: ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE; PR-009: AUTHORIZED, NOT STARTED; PR-010 AND LATER: UNAUTHORIZED; Gate 2: NOT ACCEPTED; M3: IN PROGRESS;
- [x] Gate 1: COMPLETED AND HUMAN ACCEPTED;
- [x] M2: COMPLETED AND HUMAN ACCEPTED;
- [x] Q-010: ACCEPTED;
- [ ] Q-017 remains DEFERRED;
- [x] REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE;
- [ ] The sensitive-data/private-contour gate remains open for real data;
- [ ] Real documents and personal data remain prohibited in Git, Codex and CI;
- [ ] RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.

## Not started / unauthorized

- [x] PR-006 is COMPLETED AND HUMAN ACCEPTED through PR #17;
- [x] PR-007 is COMPLETED AND HUMAN ACCEPTED; PR-008 is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK; PR-009 is AUTHORIZED, NOT STARTED; PR-010 and later implementation tasks remain UNAUTHORIZED;
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

Implement PR-009 — Orientation and quality assessment only after this lifecycle PR is merged.

Q-009: DEFERRED. PR-006 implements no retention, deletion or secure-deletion policy.


## PR-006 current lifecycle

PR-006: `COMPLETED AND HUMAN ACCEPTED`.
PR-007: `COMPLETED AND HUMAN ACCEPTED`
PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`.
Gate 1: `COMPLETED AND HUMAN ACCEPTED`.
M2: `COMPLETED AND HUMAN ACCEPTED`.
Q-009: `DEFERRED`.
Q-017: `DEFERRED`.
Q-017 remains deferred.

## Lifecycle update — PR-006 acceptance and PR-007 authorization

Verified live base SHA: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.

PR-006: `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`, final reviewed head `28d8b590adb7a7ae11e35f631eb9895c930b3cef`, merge commit `4c117ededc250d57961e2f5f4c8b4de01edf0c54`, merge date `2026-07-19`, final v0001 checksum `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`, final v0002 checksum `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`, local verification `306 passed, 2 skipped on macOS`, exact-head GitHub Actions jobs passed for Python checks on Ubuntu, Python checks on Windows, PR-S001 Windows encryption spike and PR-S001 DPAPI cross-runner negative, and exact-head CI workflow run `CI #85` succeeded.

ADR numbering after repair: ADR-019 is PR-005 SQLCipher binding and raw-key staging; ADR-020 is immutable encrypted filesystem storage v1; ADR-021 is immutable PII-safe audit events. The PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction.

PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-007 was merged and human accepted through GitHub PR #19. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. PR-009 is authorized, not started; PR-010 and later remain unauthorized.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.

## Lifecycle update — PR-007 acceptance and PR-008 authorization

PR-007: `COMPLETED AND HUMAN ACCEPTED`. GitHub PR: `#19`. Final reviewed head: `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`. Merge commit: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`. Merged date: `2026-07-20`. Exact-head CI: `CI #92`, successful. Migration v0003 final checksum: `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`.

M2: `COMPLETED AND HUMAN ACCEPTED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK` for the non-UI encrypted original import and advisory duplicate-detection foundation only, governed by ADR-022, PR #21 and PR-008-D1. PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`. Do not claim Gate 2 is accepted, do not claim a physical Windows 11 smoke occurred, and do not begin PR-010 or later work.

Q-006: `DEFERRED`. Q-007: `DEFERRED`. Q-009: `DEFERRED`. Q-010: `ACCEPTED`. Q-017: `DEFERRED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. The sensitive-data/private-contour gate remains open for real documents and real personal data. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports.

## PR-008 implementation status

PR-008 — File import and duplicate detection is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK through GitHub PR #21, final reviewed head `99dfefe467762e241f0584c2ca1a81bc662c1ab0`, merge commit `bf7af9617d33a205f27eb9a4734fea6ecee18b58`, merge date `2026-07-20`, CI #106, workflow database ID `29776664038`, and frozen larger-image DHASH64 `1810111f39f11131`. PR-007, M2 and Gate 1 remain COMPLETED AND HUMAN ACCEPTED. Gate 2 remains not accepted. PR-009 is AUTHORIZED, NOT STARTED; PR-010 and later remain UNAUTHORIZED.

## Lifecycle update — PR-008 acceptance and PR-009 authorization

Decision date: `2026-07-21`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`. Product-owner decision record: `docs/decisions/PR-008-D1-lifecycle-acceptance.md`.

PR-008 GitHub PR: `#21` — `PR-008: Add encrypted source import and advisory duplicate detection`. Final reviewed head: `99dfefe467762e241f0584c2ca1a81bc662c1ab0`. Merge commit: `bf7af9617d33a205f27eb9a4734fea6ecee18b58`. Merge date: `2026-07-20`.

Final exact-head CI evidence: `CI #106`, workflow database ID `29776664038`, conclusion `success`. Required jobs passed: `Python checks (ubuntu-latest)`, `Python checks (windows-latest)`, `PR-S001 Windows encryption spike`, and `PR-S001 DPAPI cross-runner negative`. Final recorded test evidence: macOS `465 passed, 3 skipped`; Ubuntu `465 passed, 3 skipped`; Windows `467 passed, 1 skipped`. Final supported Windows CI verifier: `PR008_VERIFY result=PASS`. Frozen larger-image DHASH64: `1810111f39f11131`.

RISK-PR008-W11-SMOKE status: `ACCEPTED FOR THE PR-008 DEVELOPMENT ACCEPTANCE BOUNDARY; DEFERRED TO WINDOWS INSTALLER, PILOT, OR FINAL RELEASE ACCEPTANCE`. No physical Windows 11 x64 smoke was performed or claimed; hosted Windows Server AMD64 evidence is accepted only for the PR-008 development acceptance boundary. The physical Windows 11 smoke remains deferred to Windows packaging, installer, pilot or final release acceptance.

PR-009: `AUTHORIZED, NOT STARTED`. PR-010 AND LATER: `UNAUTHORIZED`. Gate 2: `NOT ACCEPTED`. M3: `IN PROGRESS`.

Next safe step: Implement PR-009 — Orientation and quality assessment only after this lifecycle PR is merged.

## PR-009 contract proposal update

- [x] PR #22 merge commit recorded for contract base: `063e4b5a981f8ef6914c055e9f50666bbf1be734`;
- [x] PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`;
- [x] PR-009: `AUTHORIZED, CONTRACT PROPOSED, PRODUCTION IMPLEMENTATION NOT STARTED`;
- [ ] ADR-023: `PROPOSED`;
- [ ] Q-021: `OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE`;
- [x] PR-010 AND LATER: `UNAUTHORIZED`;
- [x] Gate 2: `NOT ACCEPTED`;
- [x] M3: `IN PROGRESS`.

PR-009 whole-frame contract scope is EXIF orientation, orientation-normalized analysis view, encoded/effective dimensions, minimum resolution, blur/sharpness, contrast, glare/highlight clipping and exposure. Deferred scope is cut edges, perspective/skew, document presence/count, segmentation, crop, perspective correction and geometric transformation. No production implementation, migration, dependency, workflow, real document or PII change is made by the contract proposal.


## PR-009 implementation lifecycle update — 2026-07-21

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED.
Q-021: OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE.
Production default quality policy: NOT ACTIVE.
Final PR-009 human acceptance: BLOCKED UNTIL Q-021 IS ACCEPTED.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

PR-009 implements deterministic whole-frame metrics, explicit caller-provided typed policy handling, full-resolution orientation-normalized decoding, append-only persistence, audit integration, controlled service errors, synthetic tests and a cross-platform verifier. It does not select or activate production thresholds, add UI integration, reject documents automatically, implement PR-010 geometry, PR-011 JPEG preparation, PR-012 document detection/segmentation or use real-document calibration. Migration v0005 checksum: `930d834c6c48ca2c16a1287faae18e0568da75ab6d47b72b7d5f46c52ce51885`.
