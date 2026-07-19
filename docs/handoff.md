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


## Authorization boundary


## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption staging, PII logs, critical field bypass and insufficient local OCR samples.

## Продолжение



## PR-005 closure record

PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data. PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.

PR-005 is COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 (`PR-005: Add encrypted SQLite persistence and migrations`). Final reviewed head: `325b49555dee49fa22b008d9522bbbc6eb873ca2`. Merge commit: `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`. Merge date: `2026-07-19`. Final migration v0001 checksum: `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`. Exact-head CI run #73 succeeded with `Python checks (ubuntu-latest)`, `Python checks (windows-latest)`, `PR-S001 Windows encryption spike` and `PR-S001 DPAPI cross-runner negative`; Windows SQLCipher evidence is complete for the PR-005 acceptance boundary. Local validation was `191 passed, 2 skipped on macOS`; the skipped local tests were Windows AMD64 SQLCipher integration tests and were skipped locally as designed, while full Windows CI pytest passed on the reviewed PR head.

The four final persistence audit blockers were closed before merge: SQLite replacement forms cannot replace immutable snapshot rows; loss of the outer transaction invalidates and closes the UoW; list reads detect payload/projection corruption before filtering; canonical boolean and collection deserialization is strict. Migration v0001 is frozen after merge, and every future schema change must use migration v0002 or later. RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.

## Current lifecycle status

GATE-M0: COMPLETED.
M0: ACCEPTED.
M1: ACCEPTED.
PR-004: COMPLETED AND HUMAN ACCEPTED.
GATE-S1: COMPLETED AND HUMAN ACCEPTED.
ADR-018: ACCEPTED.
Q-010: ACCEPTED.
PR-S001: ACCEPTED WITH DOCUMENTED RESIDUAL RISK RISK-S001-W11.
PR-S001-F4: COMPLETED AND MERGED THROUGH PR #13 at 985fae37c7645e8f65edbe4d1609100ee24a2097.
PR-005: COMPLETED AND HUMAN ACCEPTED through GitHub PR #15 at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`.
PR-005: `COMPLETED AND HUMAN ACCEPTED`.
PR-006: `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`.
PR-006 is not completed, accepted or human accepted.
PR-007 and later: `UNAUTHORIZED`.
Gate 1: `NOT ACCEPTED`.
M2: `NOT COMPLETED`.
Q-009: `DEFERRED`; PR-006 implements immutable stored final artifacts and no retention, deletion or secure-deletion policy.
Q-017: `DEFERRED`; PR-006 storage layout is backup-neutral, PR-032 remains responsible for encrypted backup/restore, and the DPAPI blob alone is not portable backup material.
The sensitive-data/private-contour gate remains open.
Real documents and personal data remain prohibited in Git, Codex and CI.
Migration v0001 checksum remains `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`.
PR-S001/PR-S001-F1/PR-S001-F2/PR-S001-F3/PR-S001-F4 use fictional synthetic data only, may evaluate candidate packages and prototypes, must not create production database/storage APIs, and must not use real documents or personal data.
PR-S001 contains no production persistence/storage API; a negative feasibility result is valid.
ADR-016 remains the public-repository template and privacy boundary.
PR-S001-F1, PR-S001-F2 and PR-S001-F3: COMPLETED.
Q-017 remains deferred.
PR-005 is COMPLETED AND HUMAN ACCEPTED through GitHub PR #15.
