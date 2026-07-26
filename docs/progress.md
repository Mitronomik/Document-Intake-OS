# Progress

**Обновлено:** 2026-07-26
**Статус:** PR-005, PR-006, PR-007 and PR-010: COMPLETED AND HUMAN ACCEPTED; PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK; PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION; ADR-024 and PR-010 contract: ACCEPTED; Q-021: DEFERRED; production PR-009 policy and automatic blocking: NOT ACTIVE; ADR-025: PROPOSED; PR-011 contract: PROPOSED FOR HUMAN REVIEW; PR-011 production implementation and PR-012+: UNAUTHORIZED; Gate 2: NOT ACCEPTED; M3: IN PROGRESS

## Завершено

- [x] Q-010: ACCEPTED;
- [x] PR-005: COMPLETED AND HUMAN ACCEPTED;

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
- [x] PR-009 MPO/JPEG compatibility correction: MPO detected by Pillow is mapped to JPEG, only primary frame 0 is decoded, original bytes remain immutable, and secondary frames are ignored in MVP; synthetic tests and both existing verifiers cover the rule without changing their public records.

MPO detected as a JPEG container is accepted as JPEG.
Only primary frame 0 is decoded.
Original bytes remain immutable.
Secondary frames are ignored in MVP.

This correction does not accept Q-021, activate a production default quality policy, human-accept PR-009, authorize PR-010 or later, accept Gate 2 or complete M3.

## Historical lifecycle snapshot — Current lifecycle state

This dated pre-closure snapshot is retained as historical evidence of PR-010 review status.

## In review / unauthorized

- [x] PR-010 is completed and human accepted.
- [ ] ADR-025 and the proposed PR-011 contract are in review.
- [ ] PR-011 production implementation and PR-012 and later remain unauthorized.

PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, must not use real documents or personal data, and must not create production database/storage APIs. PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.

## Blockers and staged questions

- Q-001 through Q-005 are staged as external terminal confirmations and do not block domain-only PR-004 under ADR-016.
- Q-008 is accepted by ADR-017: one Windows 11 x64 workstation with one active operator session at a time.
- Q-010: ACCEPTED; ADR-018 is ACCEPTED and resolves Q-010 at the architecture and sequencing level.
- Q-012 through Q-015 require local evidence outside Git, Codex and CI.
- Q-017 remains DEFERRED.
- Approved PII-free template artifacts are permitted by product policy after technical privacy inspection and repository-policy enforcement updates; real documents, PII-bearing artifacts and private acceptance materials remain outside Git, Codex and CI.

## Следующий безопасный шаг

Review ADR-025 and the proposed PR-011 contract. Do not implement PR-011 yet. After this documentation PR merges, a separate Product owner decision must accept ADR-025 and the contract, authorize implementation, and identify this documentation PR merge commit as the exact implementation base.

## Historical lifecycle snapshot — Current PR-010 geometry contract staging — 2026-07-23

This current section supersedes historical lifecycle sections for current status only and does not rewrite the historical record.

PR #26 merged successfully on 2026-07-23 from reviewed head `cc79a80fcacdbde2667cae858815b30176f87555` at merge commit `f27647e8cdfb2f8d3e5bb13478a4df50987ca1cb`; exact-head CI `CI #129` succeeded. PR-009 is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. Q-021 is DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. Production default PR-009 quality policy is NOT ACTIVE. Production `policy_id` and `policy_version` are NOT ASSIGNED. Automatic PR-009 quality-based document blocking and production RETAKE_REQUIRED enforcement are NOT ACTIVE. `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` remains OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY. ADR-024 is PROPOSED. PR-010 CONTRACT is PROPOSED FOR HUMAN REVIEW. PR-010 PRODUCTION IMPLEMENTATION is UNAUTHORIZED. PR-011 AND LATER are UNAUTHORIZED. Gate 2 is NOT ACCEPTED. M3 is IN PROGRESS.

## Historical lifecycle snapshot after PR-006 acceptance

PR-006: `COMPLETED AND HUMAN ACCEPTED`.
PR-007: `COMPLETED AND HUMAN ACCEPTED`
PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`.
Gate 1: `COMPLETED AND HUMAN ACCEPTED`.
M2: `COMPLETED AND HUMAN ACCEPTED`.
Q-009: `DEFERRED`.
Q-017: `DEFERRED`.
Q-017 remains deferred.

## Historical lifecycle snapshot — Lifecycle update — PR-006 acceptance and PR-007 authorization

Verified live base SHA: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.

PR-006: `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`, final reviewed head `28d8b590adb7a7ae11e35f631eb9895c930b3cef`, merge commit `4c117ededc250d57961e2f5f4c8b4de01edf0c54`, merge date `2026-07-19`, final v0001 checksum `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`, final v0002 checksum `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`, local verification `306 passed, 2 skipped on macOS`, exact-head GitHub Actions jobs passed for Python checks on Ubuntu, Python checks on Windows, PR-S001 Windows encryption spike and PR-S001 DPAPI cross-runner negative, and exact-head CI workflow run `CI #85` succeeded.

ADR numbering after repair: ADR-019 is PR-005 SQLCipher binding and raw-key staging; ADR-020 is immutable encrypted filesystem storage v1; ADR-021 is immutable PII-safe audit events. The PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction.

PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-007 was merged and human accepted through GitHub PR #19. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. PR-009 is authorized, not started; PR-010 and later remain unauthorized.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.

## Historical lifecycle snapshot — Lifecycle update — PR-007 acceptance and PR-008 authorization

PR-007: `COMPLETED AND HUMAN ACCEPTED`. GitHub PR: `#19`. Final reviewed head: `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`. Merge commit: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`. Merged date: `2026-07-20`. Exact-head CI: `CI #92`, successful. Migration v0003 final checksum: `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`.

M2: `COMPLETED AND HUMAN ACCEPTED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK` for the non-UI encrypted original import and advisory duplicate-detection foundation only, governed by ADR-022, PR #21 and PR-008-D1. PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`. Do not claim Gate 2 is accepted, do not claim a physical Windows 11 smoke occurred, and do not begin PR-010 or later work.

Q-006: `DEFERRED`. Q-007: `DEFERRED`. Q-009: `DEFERRED`. Q-010: `ACCEPTED`. Q-017: `DEFERRED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. The sensitive-data/private-contour gate remains open for real documents and real personal data. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports.

## Historical PR-008 implementation status at acceptance

PR-008 — File import and duplicate detection is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK through GitHub PR #21, final reviewed head `99dfefe467762e241f0584c2ca1a81bc662c1ab0`, merge commit `bf7af9617d33a205f27eb9a4734fea6ecee18b58`, merge date `2026-07-20`, CI #106, workflow database ID `29776664038`, and frozen larger-image DHASH64 `1810111f39f11131`. PR-007, M2 and Gate 1 remain COMPLETED AND HUMAN ACCEPTED. Gate 2 remains not accepted. PR-009 is AUTHORIZED, NOT STARTED; PR-010 and later remain UNAUTHORIZED.

## Historical lifecycle snapshot — Lifecycle update — PR-008 acceptance and PR-009 authorization

Decision date: `2026-07-21`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`. Product-owner decision record: `docs/decisions/PR-008-D1-lifecycle-acceptance.md`.

PR-008 GitHub PR: `#21` — `PR-008: Add encrypted source import and advisory duplicate detection`. Final reviewed head: `99dfefe467762e241f0584c2ca1a81bc662c1ab0`. Merge commit: `bf7af9617d33a205f27eb9a4734fea6ecee18b58`. Merge date: `2026-07-20`.

Final exact-head CI evidence: `CI #106`, workflow database ID `29776664038`, conclusion `success`. Required jobs passed: `Python checks (ubuntu-latest)`, `Python checks (windows-latest)`, `PR-S001 Windows encryption spike`, and `PR-S001 DPAPI cross-runner negative`. Final recorded test evidence: macOS `465 passed, 3 skipped`; Ubuntu `465 passed, 3 skipped`; Windows `467 passed, 1 skipped`. Final supported Windows CI verifier: `PR008_VERIFY result=PASS`. Frozen larger-image DHASH64: `1810111f39f11131`.

RISK-PR008-W11-SMOKE status: `ACCEPTED FOR THE PR-008 DEVELOPMENT ACCEPTANCE BOUNDARY; DEFERRED TO WINDOWS INSTALLER, PILOT, OR FINAL RELEASE ACCEPTANCE`. No physical Windows 11 x64 smoke was performed or claimed; hosted Windows Server AMD64 evidence is accepted only for the PR-008 development acceptance boundary. The physical Windows 11 smoke remains deferred to Windows packaging, installer, pilot or final release acceptance.

PR-009: `AUTHORIZED, NOT STARTED`. PR-010 AND LATER: `UNAUTHORIZED`. Gate 2: `NOT ACCEPTED`. M3: `IN PROGRESS`.

Next safe step: Implement PR-009 — Orientation and quality assessment only after this lifecycle PR is merged.

## Historical PR-009 contract proposal update

- [x] PR #22 merge commit recorded for contract base: `063e4b5a981f8ef6914c055e9f50666bbf1be734`;
- [x] PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`;
- [x] PR-009: `AUTHORIZED, CONTRACT PROPOSED, PRODUCTION IMPLEMENTATION NOT STARTED`;
- [ ] ADR-023: `PROPOSED`;
- [ ] Q-021: `OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE`;
- [x] PR-010 AND LATER: `UNAUTHORIZED`;
- [x] Gate 2: `NOT ACCEPTED`;
- [x] M3: `IN PROGRESS`.

PR-009 whole-frame contract scope is EXIF orientation, orientation-normalized analysis view, encoded/effective dimensions, minimum resolution, blur/sharpness, contrast, glare/highlight clipping and exposure. Deferred scope is cut edges, perspective/skew, document presence/count, segmentation, crop, perspective correction and geometric transformation. No production implementation, migration, dependency, workflow, real document or PII change is made by the contract proposal.


## Historical lifecycle snapshot — PR-009 implementation lifecycle update — 2026-07-21

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED.
Q-021: OPEN — REQUIRES PRODUCT-OWNER ACCEPTANCE.
Production default quality policy: NOT ACTIVE.
Final PR-009 human acceptance: BLOCKED UNTIL Q-021 IS ACCEPTED.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

PR-009 implements deterministic whole-frame metrics, explicit caller-provided typed policy handling, full-resolution orientation-normalized decoding, append-only persistence, audit integration, controlled service errors, synthetic tests and a cross-platform verifier. It does not select or activate production thresholds, add UI integration, reject documents automatically, implement PR-010 geometry, PR-011 JPEG preparation, PR-012 document detection/segmentation or use real-document calibration. Migration v0005 checksum: `6d020d1acfbce3fcb7168e935617f2ae008a32bea7def1f37de84e36e9e2224f`.

PR-009 review correction: the accepted PR-008 verifier output field `migration_v0004` now validates the exact five-migration chain through v0005 and all five frozen checksums. Migration v0005 forward-rebuilds the immutable audit table so the accepted PR-009 action and subject values can be persisted while historical rows, indexes and immutability triggers are preserved. Its final checksum is calculated from the corrected production statements; the earlier candidate checksum described the incomplete migration and is not used. The PR-009 verifier uses the production SQLCipher Unit of Work, immutable encrypted storage, production import and quality services, aggregate and audit repositories, literal synthetic vectors, complete aggregate/audit round trips, failing-audit rollback, deterministic listing, storage/source immutability and corruption rejection. Supported Windows CI remains the production PASS boundary; unsupported macOS execution remains inconclusive.

## Historical lifecycle snapshot — Q-021 negative calibration lifecycle update — 2026-07-22

The product owner completed the private local Q-021 calibration contour and accepted its negative result as valid evidence. The safe aggregate record is: 60 samples processed; 60 metric sets calculated; zero failures and no failure stages; 43 calibration samples; 17 held-out validation samples; 54 Pareto candidates; no candidate accepted; no production policy selected or activated.

The narrow accepted conclusion is that the current PR-009 V1 whole-frame metrics, current candidate search space and tested severity combinations did not produce an acceptable production quality policy on the completed local Q-021 calibration and validation set. No universal algorithm-failure claim is made. No private input, path, filename, hash, thumbnail, EXIF payload, document text, sample mapping or exported calibration artifact is recorded here.

Q-021 is `DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED`. `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` is open and accepted for the PR-009 infrastructure merge boundary. Production composition must fail closed without an accepted policy, and no unaccepted PR-009 policy may automatically reject, delete, suppress or block a document. The production default PR-009 quality policy remains `NOT ACTIVE`.

PR-009 is `IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION`. PR #24 remains open and unmerged at the time of this correction; human acceptance and merge remain pending. PR-010 AND LATER remain `UNAUTHORIZED`; Gate 2 remains `NOT ACCEPTED`; M3 remains `IN PROGRESS`.

## 2026-07-22 — PR-009 human acceptance and PR-010 contract-definition authorization

GitHub PR #24 (`PR-009: Implement orientation and quality assessment`) merged on 2026-07-22. Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`. Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.

PR-009 is COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. Q-021 remains DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. No production default PR-009 quality policy is active. Production `policy_id` is NOT ASSIGNED. Production `policy_version` is NOT ASSIGNED. Automatic PR-009 quality-based document blocking is NOT ACTIVE. Automatic PR-009 production `RETAKE_REQUIRED` enforcement is NOT ACTIVE.

`RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` remains OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY. PR-010 CONTRACT DEFINITION is AUTHORIZED, NOT STARTED. PR-010 PRODUCTION IMPLEMENTATION remains UNAUTHORIZED. PR-011 AND LATER remain UNAUTHORIZED. Gate 2 remains NOT ACCEPTED. M3 remains IN PROGRESS.

Lifecycle authorization exact status: PR-011 AND LATER: UNAUTHORIZED.


## Historical lifecycle snapshot — PR-010 geometry implementation review — 2026-07-23

ADR-024 is ACCEPTED by Product owner. PR-010 production implementation is AUTHORIZED AND IN REVIEW from base `329dd5653a3faadd3c62387c1d900710f14b2f4e`. PR-011 and later remain UNAUTHORIZED; Gate 2 remains NOT ACCEPTED; M3 remains IN PROGRESS; Q-021 remains DEFERRED; production PR-009 quality policy is NOT ACTIVE. PR-010 adds deterministic offline geometry recipe creation only and does not publish prepared JPEGs.


## Current lifecycle state — 2026-07-26

This current section supersedes earlier lifecycle snapshots for current status only and does not rewrite the historical record.

PR-005: COMPLETED AND HUMAN ACCEPTED. PR-006: COMPLETED AND HUMAN ACCEPTED. PR-007: COMPLETED AND HUMAN ACCEPTED. PR-008: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK. PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION. PR-010: COMPLETED AND HUMAN ACCEPTED. ADR-024: ACCEPTED. PR-010 contract: ACCEPTED. PR-010 CONTRACT: ACCEPTED.

PR-010 evidence: GitHub PR #28; final reviewed head `8b6a3cf69d697807a20e763605b4601104844f04`; merge commit `99cdcaebe25551a24062e4e356ff47e868ac8f6a`; exact-head workflow `CI #138`; workflow run ID `30034157725`; conclusion `success`. Ubuntu and Windows full pytest, Ubuntu and Windows `uv build`, and Windows PR-006 through PR-010 verifiers passed. Current schema version before PR-011: `6`. Frozen v0006 checksum: `ac9d5bfbe79160d880f30af6ee1ed645ab500b9be140a18b9d6498cc68eba5ec`.

The accepted PR-010 boundary is immutable originals; EXIF orientation applied exactly once; deterministic source-effective coordinate space; manual quadrilateral geometry; perspective transformation; clockwise quarter-turn rotation; deterministic output dimensions; append-only geometry-recipe revisions; canonical persistence validation; atomic geometry-recipe and audit persistence; no final prepared JPEG publication; and no PR-011 or later behavior. PR-010 alone does not complete manual JPEG preparation because PR-011, PR-012 and PR-013 remain incomplete.

Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED. RISK-PR009-NO-PRODUCTION-QUALITY-POLICY remains OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY. Production PR-009 quality policy: NOT ACTIVE. Production `policy_id`: NOT ASSIGNED. Production `policy_version`: NOT ASSIGNED. Automatic PR-009 quality blocking: NOT ACTIVE. Automatic production `RETAKE_REQUIRED`: NOT ACTIVE. ADR-025: ACCEPTED. PR-011 CONTRACT: ACCEPTED. PR-011 PRODUCTION IMPLEMENTATION: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-012 AND LATER: UNAUTHORIZED. Gate 2: NOT ACCEPTED. M3: IN PROGRESS.

PR-011 is implemented in review on the accepted exact base; PR-012 and PR-013 remain unauthorized.

Real documents and personal data remain prohibited in Git, Codex and CI.


Product owner authorization date: 2026-07-26. Accepted contract and implementation base: `f007fb5a04a5c69c70a37faf7ba12fa6775ae819`. Current schema version: `7`. Final v0007 checksum: `afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7`. V0007 uses a checksum-protected `DISABLED_DURING_TABLE_REBUILD` execution mode, a transactional populated-table copy, foreign-key checks before and after restoration, and no internal SQLite schema edits. Candidate evidence uses the production attempt generator and observer; determinism reuses the same PR-010 RGB render; verifier privacy uses an exact allowlist and runtime forbidden-value checks. ADR-025: ACCEPTED. PR-011 CONTRACT: ACCEPTED. PR-011 PRODUCTION IMPLEMENTATION: IMPLEMENTED AND IN REVIEW; NOT HUMAN ACCEPTED. PR-012 AND LATER: UNAUTHORIZED. Q-021: DEFERRED. PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE. PRODUCTION `policy_id`: NOT ASSIGNED. PRODUCTION `policy_version`: NOT ASSIGNED. AUTOMATIC PR-009 QUALITY BLOCKING: NOT ACTIVE. AUTOMATIC PRODUCTION `RETAKE_REQUIRED`: NOT ACTIVE. GATE 2: NOT ACCEPTED. M3: IN PROGRESS. Real documents and personal data remain prohibited in Git, Codex and CI.
## PR-011 acceptance-control status

This normative acceptance status supersedes broader implementation wording for current readiness only; dated historical snapshots remain historical.

- PR-011 PRODUCTION CODE: IMPLEMENTED IN REVIEW
- PR-011 ACCEPTANCE EVIDENCE: INCOMPLETE
- PR-011 HUMAN ACCEPTANCE: BLOCKED
- PR-012 AND LATER: UNAUTHORIZED
- Q-021: DEFERRED
- PRODUCTION PR-009 QUALITY POLICY: NOT ACTIVE
- GATE 2: NOT ACCEPTED
- M3: IN PROGRESS

CI success proves the checked implementation and tests pass; it does not prove that every acceptance-manifest entry exists.
