# Handoff

## Проект

Document Intake OS — локальная Windows-программа подготовки документов и Excel-заявок для трех терминалов.

## Подтверждено

- вход — отдельные фото водителей;
- разные страны и поколения документов;
- фон, наклон, несколько документов и две стороны;
- originals immutable;
- output JPEG RGB ≤1,90 MiB;
- OCR only suggests;
- operator verifies critical data;
- local database;
- TSP, Visitors and MGS exports;
- manual Konversta upload;
- no real PII in cloud development.

## Source of truth

Canonical source priority:

1. `docs/technical-specification.md`
2. `docs/decisions.md`
3. `docs/product-spec.md`
4. `docs/architecture.md`
5. `docs/domain-model.md`
6. `docs/security.md`
7. `docs/testing-strategy.md`
8. current PR task under `docs/tasks/`

Conflicts must be reported instead of resolved silently.

## Архитектура

Modular monolith: domain, application, persistence, storage, image pipeline, recognition, terminal adapters and UI.

ADR-017 fixes the first MVP topology as one Windows 11 x64 workstation with one active operator session at a time. This does not implement SQLite, storage, users or authentication.

## Current lifecycle state

GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance of GATE-M0 occurred after PR #5 merge. M0: ACCEPTED. M1: ACCEPTED. PR-004: COMPLETED AND HUMAN ACCEPTED. GATE-S1: COMPLETED AND HUMAN ACCEPTED. ADR-018: ACCEPTED. PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11; PR-S001-F1: COMPLETED; PR-S001-F2: COMPLETED; PR-S001-F3: COMPLETED; PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13; PR-S001-F4 merge commit: `985fae37c7645e8f65edbe4d1609100ee24a2097`. PR-005: COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9` from final reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2`. PR-005 final migration v0001 checksum is `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`; v0001 is frozen and every future schema change must use migration v0002 or later. Exact-head CI run #73 succeeded on Ubuntu and Windows, and Windows SQLCipher evidence is complete for the PR-005 acceptance boundary.

PR-006: AUTHORIZED AND IN REVIEW, NOT ACCEPTED. PR-007 AND LATER: UNAUTHORIZED. Gate 1: NOT ACCEPTED. M2: NOT COMPLETED. Q-010: ACCEPTED. Q-017 remains DEFERRED. Under ADR-016, the template enforcement PR remains future work and does not block PR-004 or PR-005 closure. The sensitive-data/private-contour gate remains open for real data, and real documents and personal data remain prohibited in Git, Codex and CI.

## Authorization boundary

GATE-S1 is completed and human accepted after GitHub PR #7. PR #9 merged PR-S001 as a research harness; PR-S001 is ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11. PR-005 is COMPLETED AND HUMAN ACCEPTED. PR-006 is AUTHORIZED AND IN REVIEW, NOT ACCEPTED; PR-007 and later work remain UNAUTHORIZED. PR-006 corrections may proceed only in PR #17; PR-006 remains in review and not accepted before merge and separate product-owner acceptance.

## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption staging, PII logs, critical field bypass and insufficient local OCR samples.

## Продолжение

The next safe step is completing and reviewing PR #17 corrections. PR-006 is authorized for in-review implementation in PR #17 only and remains not accepted. No PR-007 work may begin. Before each later task, read the authoritative sources, check the applicable gate, form a single PR contract and preserve unresolved questions unless an accepted ADR explicitly resolves them.

PR-S001-F1, PR-S001-F2, PR-S001-F3 and PR-S001-F4 are completed. PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-006 is AUTHORIZED AND IN REVIEW, NOT ACCEPTED through PR #17. Q-017 remains deferred. The sensitive-data/private-contour gate remains open, and real documents and personal data remain prohibited in Git, Codex and CI.

## PR-005 closure record

PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.

PR-005 is COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 (`PR-005: Add encrypted SQLite persistence and migrations`). Final reviewed head: `325b49555dee49fa22b008d9522bbbc6eb873ca2`. Merge commit: `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`. Merge date: `2026-07-19`. Final migration v0001 checksum: `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`. Exact-head CI run #73 succeeded with `Python checks (ubuntu-latest)`, `Python checks (windows-latest)`, `PR-S001 Windows encryption spike` and `PR-S001 DPAPI cross-runner negative`; Windows SQLCipher evidence is complete for the PR-005 acceptance boundary. Local validation was `191 passed, 2 skipped on macOS`; the skipped local tests were Windows AMD64 SQLCipher integration tests and were skipped locally as designed, while full Windows CI pytest passed on the reviewed PR head.

The four final persistence audit blockers were closed before merge: SQLite replacement forms cannot replace immutable snapshot rows; loss of the outer transaction invalidates and closes the UoW; list reads detect payload/projection corruption before filtering; canonical boolean and collection deserialization is strict. Migration v0001 is frozen after merge, and every future schema change must use migration v0002 or later. RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.

Q-009: DEFERRED. PR-006 implements no retention, deletion or secure-deletion policy.


## PR-006 current lifecycle

PR-006: `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`.
PR-007 and later: `UNAUTHORIZED`.
Gate 1: `NOT ACCEPTED`.
M2: `NOT COMPLETED`.
Q-009: `DEFERRED`.
Q-017: `DEFERRED`.
Q-017 remains deferred.
