# PR-006 — Immutable encrypted filesystem storage

Status: `COMPLETED AND HUMAN ACCEPTED`

GitHub PR: `#17`

Title: `PR-006: Add immutable encrypted filesystem storage`

Final reviewed head: `28d8b590adb7a7ae11e35f631eb9895c930b3cef`

Merge commit: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`

Merge date: `2026-07-19`

Final migration v0001 checksum: `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`

Final migration v0002 checksum: `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`

Local macOS verification: `306 passed, 2 skipped on macOS`

Exact-head CI workflow run: `CI #85`, successful.

Exact-head GitHub Actions jobs passed:

- Python checks, Ubuntu;
- Python checks, Windows;
- PR-S001 Windows encryption spike;
- PR-S001 DPAPI cross-runner negative.

## Accepted closure

PR-006 is completed and human accepted. Storage decision: ADR-020 after the ADR numbering repair. The GitHub PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction; historical Git commits and the merged PR description are not rewritten.

Accepted scope: immutable encrypted filesystem storage with AES-256-GCM envelope v1, `DIOSOBJ1` magic, immutable UUID-derived object paths, object-first/database-second publication, SQLCipher expected-state records, read-time verification and read-only reconciliation.

Accepted non-goals remain: no retention, deletion, purge, secure deletion, backup/restore, import workflow, image-processing workflow, snapshot workflow, export workflow, UI, OCR, MRZ, barcode, telemetry, network or cloud service.

## Continuing lifecycle

PR-007: `AUTHORIZED, NOT STARTED`. PR-007 implementation may begin only after the lifecycle pull request that records this closure is merged into `main`.

PR-008 and later: `UNAUTHORIZED`.

Gate 1: `NOT ACCEPTED`.

M2: `NOT COMPLETED`.

Gate 1 and M2 remain incomplete until PR-007 is implemented, reviewed, merged and separately human accepted through a later lifecycle decision.

Q-009 remains `DEFERRED`. Q-017 remains `DEFERRED`. Q-010 remains `ACCEPTED`.

`RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved.

Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.
