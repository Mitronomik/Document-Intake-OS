# Модель локального файлового хранилища

## 1. Accepted PR-006 managed object store

PR-006 implements the managed storage layer as encrypted managed object files only. The physical store is not the earlier conceptual `originals/<year>/<month>/...` or `artifacts/<document-id>/...` layout.

Accepted physical model:

- encrypted managed object files only;
- AES-256-GCM envelope v1;
- `DIOSOBJ1` magic;
- immutable UUID-derived object paths;
- object-first/database-second publication;
- authoritative expected state in encrypted SQLCipher persistence;
- read-time expected-state verification;
- read-only reconciliation;
- no automatic orphan adoption;
- no automatic orphan deletion;
- no plaintext managed object files;
- no source filenames or PII in managed paths;
- no retention or secure-deletion implementation.

The SQLCipher database is authoritative for each stored artifact's expected object ID, storage-relative path, SHA-256 digest, size, media type, artifact kind, encryption metadata and lifecycle state. Reads verify the encrypted object envelope and expected state before returning bytes.

## 2. Logical categories

Source files, prepared documents, snapshots and exports remain domain concepts for future workflows. PR-006 does not claim that import, image preparation, snapshot generation or export package workflows are implemented.

Future workflows may classify managed objects by logical purpose, but managed object paths remain UUID-derived encrypted-object paths rather than human-readable source or document layouts.

## 3. Publication and immutability

Publication is object-first/database-second:

1. create an encrypted object with a fresh UUID-derived path;
2. write the AES-256-GCM envelope with `DIOSOBJ1` magic;
3. verify object bytes and SHA-256;
4. insert the authoritative SQLCipher record;
5. expose no update or delete operation for the stored object record.

If database publication fails after object creation, reconciliation may report an orphan. Reconciliation is read-only and must not adopt or delete the orphan automatically.

## 4. Exports and templates

Export packages and template storage are future or separate concerns. Human-readable filenames may be used only in explicit export packages after their own accepted workflow. Managed encrypted object paths must not contain names, passport numbers, VINs, registrations, source filenames or other PII.

## 5. Temporary files and logs

Temporary files use restricted locations, avoid PII in names and are cleaned after completion or crash recovery where practical. Logs may contain IDs, action/error codes, duration and component versions. Logs must not contain OCR text, MRZ, photos, addresses, phones, full identity numbers, source filenames or filesystem paths that disclose private data.

## 6. Retention, deletion and backup

Q-009 remains `DEFERRED`; no retention, deletion, purge or secure-deletion policy is implemented. Q-017 remains `DEFERRED`; PR-006 storage is backup-neutral and PR-032 remains responsible for encrypted backup/restore.

## 7. Historical lifecycle note

PR-006: `COMPLETED AND HUMAN ACCEPTED`. PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. Storage decision: ADR-020. Audit decision: ADR-021.

## Lifecycle update — PR-007 acceptance and PR-008 authorization

PR-007: `COMPLETED AND HUMAN ACCEPTED`. GitHub PR: `#19`. Final reviewed head: `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`. Merge commit: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`. Merged date: `2026-07-20`. Exact-head CI: `CI #92`, successful. Migration v0003 final checksum: `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`.

M2: `COMPLETED AND HUMAN ACCEPTED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK` for the non-UI encrypted original import and advisory duplicate-detection foundation only, governed by ADR-022, PR #21 and PR-008-D1. PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`. Do not claim Gate 2 is accepted, do not claim a physical Windows 11 smoke occurred, and do not begin PR-010 or later work.

Q-006: `DEFERRED`. Q-007: `DEFERRED`. Q-009: `DEFERRED`. Q-010: `ACCEPTED`. Q-017: `DEFERRED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. The sensitive-data/private-contour gate remains open for real documents and real personal data. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports.


## PR-009 calibration lifecycle update — 2026-07-22

ADR-023: ACCEPTED.
PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.
PR-010 CONTRACT DEFINITION: AUTHORIZED, NOT STARTED.
PR-010 PRODUCTION IMPLEMENTATION: UNAUTHORIZED.
PR-011 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

Original-byte immutability and the no-storage-publication PR-009 boundary remain unchanged. No unaccepted quality policy may reject, delete, suppress, block or modify a document.


## PR-009 human acceptance lifecycle state — 2026-07-22

PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

GitHub PR: #24.
Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`.
Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.
Merge date: 2026-07-22.
Production policy_id: NOT ASSIGNED.
Production policy_version: NOT ASSIGNED.
Automatic PR-009 quality-based document blocking: NOT ACTIVE.
Automatic PR-009 production RETAKE_REQUIRED enforcement: NOT ACTIVE.
PR-010 CONTRACT DEFINITION: AUTHORIZED, NOT STARTED.
PR-010 PRODUCTION IMPLEMENTATION: UNAUTHORIZED.
PR-011 AND LATER: UNAUTHORIZED.

The next safe task is preparation of the exact PR-010 documentation contract. PR-010 production implementation and PR-011 and later remain unauthorized. This lifecycle update does not define or implement PR-010 runtime behavior, and FR-04 remains incomplete because geometry, document regions and later image-preparation work remain future scope.
