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

## 7. Lifecycle note

PR-006: `COMPLETED AND HUMAN ACCEPTED`. PR-007: `AUTHORIZED, NOT STARTED`. PR-008 and later: `UNAUTHORIZED`. Gate 1: `NOT ACCEPTED`. M2: `NOT COMPLETED`. Storage decision: ADR-020. Audit decision: ADR-021.
