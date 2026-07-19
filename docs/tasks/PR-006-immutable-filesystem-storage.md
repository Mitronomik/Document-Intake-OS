# PR-006 — Immutable encrypted filesystem storage

Status: `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`.

Goal: implement production-structured immutable encrypted filesystem storage for original source bytes, prepared document artifacts and future export artifacts. Inputs are caller-supplied `EntityId`, `ArtifactKind`, plaintext bytes and timezone-aware creation time. Outputs are immutable `StoredArtifactRecord` rows and exact plaintext reads only when an authoritative expected record is supplied.

Key-provider contract: `StorageKey(version: int, key_bytes: bytes)` validates positive non-bool versions and exactly 32-byte keys; `StorageKeyProvider.get_current_key()` and `get_key(version)` are the only key boundary. No DPAPI, HKDF, DEK wrapping, key generation or plaintext key persistence is implemented.

Envelope v1: `DIOSOBJ1` magic, 4-byte big-endian canonical-header length, canonical UTF-8 JSON header, AES-256-GCM ciphertext plus 16-byte tag. Format version is 1, nonce is 12 bytes, AAD is magic plus encoded header length plus header, and the complete envelope SHA-256 is stored in expected state.

Filesystem layout: `objects/<uuid_hex[0:2]>/<uuid_hex[2:4]>/<canonical_uuid>.diosobj`; temporary encrypted files are `.tmp-<uuid>.diosobj` in the final directory. Paths contain only UUID-derived components and never source names or PII.

Migration v0002 schema: `stored_artifacts` with immutable artifact metadata projections and `canonical_payload`; constraints enforce generation 1, non-negative plaintext length, 64-character digests, positive key version, storage format 1 and the three accepted artifact kinds. UPDATE and DELETE triggers reject mutation. Final v0002 checksum: `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`.

Transaction boundary: object first, database second. Failures before publication leave no final object; failures after final publication and before commit create read-only reconciliation orphans. No PENDING state and no SQLite/filesystem distributed transaction are claimed.

Reconciliation: classifies healthy, missing, invalid, orphan final objects and encrypted temporary files using artifact IDs, stable codes and counts only. It is read-only. Temporary cleanup removes only exact managed temporary filenames; retention, deletion and secure deletion are non-goals.

Security invariants: plaintext is never written to managed disk files, final artifact IDs publish once, reads require `StoredArtifactRecord`, old-envelope replay with unchanged expected state is detected, copied envelopes are detected, and coordinated full database plus filesystem rollback is outside the claim.

Stable errors: storage diagnostics expose only `ERR_STORAGE_*` codes and suppress paths, keys, digests, content and raw exceptions.

Acceptance criteria and tests cover envelope tamper rejection, immutable publication, expected-state rollback anchors, reconciliation, migration, repository immutability, crash boundaries and synthetic manual verification. Lifecycle: PR-005 is `COMPLETED AND HUMAN ACCEPTED`; PR-006 is `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`; PR-007 and later are `UNAUTHORIZED`; Gate 1 is `NOT ACCEPTED`; M2 is `NOT COMPLETED`; Q-009 and Q-017 remain `DEFERRED`; real documents and personal data remain prohibited in Git, Codex and CI.
