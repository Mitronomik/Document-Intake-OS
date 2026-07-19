# PR-005 — Encrypted SQLite persistence and migrations

Status: COMPLETED AND HUMAN ACCEPTED.

Lifecycle closure: PR-005 was merged through GitHub PR #15 (`PR-005: Add encrypted SQLite persistence and migrations`) on `2026-07-19` from final reviewed head `325b49555dee49fa22b008d9522bbbc6eb873ca2` at merge commit `2161fbbf7fb4065a5913fb6e62c207546caf5dd9`. The final migration v0001 checksum is `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`. Exact-head GitHub Actions CI run #73 succeeded, including Windows SQLCipher integration evidence for the PR-005 acceptance boundary.

## Goal

Implement a fail-closed encrypted SQLCipher persistence adapter for the PR-004 domain entities: Person, IdentityDocument, MigrationDocument, Vehicle, Terminal, Document, FieldCandidate, Application, ParticipantAssignment, VerifiedField, ValidationReport issues, ApplicationSnapshot and snapshot artifact references.

## Product-owner binding decision

PR-005 uses `sqlcipher3==0.6.2` for Windows AMD64 Python 3.12 development only. This is not final installer, redistribution, licensing or production-release approval.

## Residual risk

`RISK-PR005-RAWKEY-PRAGMA` is ACCEPTED BY PRODUCT OWNER FOR PR-005 DEVELOPMENT. The selected binding has no demonstrated binding-safe raw-key API, so PR-005 isolates a raw hexadecimal SQLCipher PRAGMA key helper. The risk remains open before installer, pilot and production release.

## Inputs and outputs

Inputs are a database path whose parent already exists and a `DatabaseKeyProvider` returning exactly 32 bytes. Outputs are an encrypted SQLCipher database, WAL/SHM sidecars as produced by SQLCipher, migration metadata, structured repository rows and immutable snapshot rows. No key, database, WAL, SHM, journal, logs, real documents or personal data may be committed.

## Allowed scope

Only PR-004 domain persistence is in scope. UploadBatch, SourceFile, DocumentRegion, RecognitionRun, ExportRun, AuditEvent, filesystem artifact behavior, deduplication and terminal completeness matrices remain deferred. `Application.batch_id`, document side IDs, prepared artifact IDs, snapshot artifact references and `Vehicle.registration_document_id` remain opaque IDs. In PR-005, `Vehicle.registration_document_id` is deliberately not a foreign key to `documents`; a future migration may normalize it only after the document ownership contract is designed and accepted.

## Security invariants

No plaintext production database mode exists. Production persistence imports SQLCipher lazily and does not import `sqlite3`. Every connection must key before schema queries, verify `cipher_status`, foreign keys, memory temp store, WAL, FULL synchronous mode, trusted schema OFF and cipher integrity. Failures map to stable persistence error codes without path, SQL, key, raw driver exception or entity payload disclosure. Wrong keys and early ciphertext corruption both map to `ERR_DB_KEY_REJECTED` when keyed schema access has not succeeded and the causes are not cryptographically distinguishable. Integrity failures detected after successful keyed schema access map to `ERR_DB_INTEGRITY_FAILED`.

## Schema/table list

Schema version: 1. Application ID: `0x44494F53`. Tables: `schema_migrations`, `persons`, `identity_documents`, `migration_documents`, `documents`, `document_sides`, `vehicles`, `terminals`, `field_candidates`, `field_candidate_validation_results`, `applications`, `application_assignments`, `application_verified_fields`, `application_validation_issues`, `application_snapshots`, `application_snapshot_artifact_refs`.

## Migration rules

Migrations are Python modules, forward-only, static statement tuples with SHA-256 checksums. The runner executes statements one at a time inside explicit transactions, records `schema_migrations`, sets `PRAGMA user_version`, verifies checksums/history/application ID and provides no down migration or destructive reset.

## Repository contracts

The canonical serialized payload is authoritative for each complete persisted domain entity. Structured scalar, relationship and child-table columns are deterministic projections for foreign keys, indexing and queries. Every add/update writes the payload and projections from the same entity atomically, and every read rejects projection mismatch as `ERR_PERSISTED_DATA_INVALID`. Repositories expose add/get/update/list operations only as defined by the application ports. Snapshot repositories expose add/get/list only. No repository exposes delete, commit, rollback, raw SQL, database path or key.

## Unit of Work semantics

`unit_of_work()` opens a fresh SQLCipher connection, validates the current schema, starts `BEGIN IMMEDIATE`, exposes repositories, commits only on explicit `commit()`, rolls back on exception or uncommitted exit, closes once and rejects nested/reused/closed use with stable errors.

## Acceptance criteria and tests

Acceptance requires SQLCipher Windows integration, migration checksum/history tests, repository round trips, UoW commit/rollback tests, ordinary SQLite rejection, wrong-key/tamper behavior, privacy leak checks and snapshot immutability tests. Off Windows AMD64, actual SQLCipher tests must skip rather than xfail.

## Manual verification

Synthetic-only manual verification must report exact commit, OS/architecture, Python version, `sqlcipher3` version, embedded SQLCipher version, schema version, application ID, migration checksums, ordinary SQLite rejection, correct-key result, wrong-key result, commit result, rollback result, snapshot immutability result and sanitized privacy result. It must not report the database path, key, key digest, raw SQL, username, hostname, local path or synthetic entity values.

## Non-goals and lifecycle boundary

PR-006 filesystem storage, originals, prepared JPEGs, encrypted file envelopes, DPAPI, key hierarchy, backup/restore, users, authentication, audit, retention, OCR/MRZ, image processing, Excel, UI, installer, telemetry, network/cloud services, downgrade and plaintext migration are not implemented. PR-005 is COMPLETED AND HUMAN ACCEPTED; PR-006 is UNAUTHORIZED; PR-007 and later are UNAUTHORIZED; Gate 1 is NOT ACCEPTED; M2 is NOT COMPLETED. RISK-PR005-RAWKEY-PRAGMA remains accepted only for the PR-005 development boundary and remains open for installer, pilot and production release.
