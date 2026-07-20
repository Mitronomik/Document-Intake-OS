# PR-007 — Audit events

Status: `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`

Status: PR-007 is AUTHORIZED AND IN REVIEW, NOT ACCEPTED. The lifecycle pull request that created this task has been merged into `main`; do not mark PR-007 completed or human accepted until a later lifecycle decision.

## Objective

Implement the immutable, append-only, PII-safe audit-event foundation authorized by ADR-021. Audit events are locally persisted security-relevant and business-critical records, not application logs, diagnostic journals or exception journals.

## Verified prerequisites

- PR-006 is `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`.
- PR-006 final reviewed head: `28d8b590adb7a7ae11e35f631eb9895c930b3cef`.
- PR-006 merge commit: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.
- PR-006 merge date: `2026-07-19`.
- v0001 checksum: `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`.
- v0002 checksum: `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`.
- Storage decision: ADR-020.
- Audit decision: ADR-021.
- Q-009 and Q-017 remain `DEFERRED`; Q-010 remains `ACCEPTED`.
- Gate 1 remains `NOT ACCEPTED`; M2 remains `NOT COMPLETED`.

## Accepted ADR references

- ADR-019 — PR-005 SQLCipher binding and raw-key staging.
- ADR-020 — Immutable encrypted filesystem storage v1.
- ADR-021 — Immutable PII-safe audit events.

## Exact production files

PR-007 may create or modify only where required in:

- `src/document_intake/domain/enums.py`
- `src/document_intake/domain/entities/audit.py`
- `src/document_intake/domain/entities/__init__.py`
- `src/document_intake/domain/value_objects/audit.py`
- `src/document_intake/domain/value_objects/__init__.py`
- `src/document_intake/domain/__init__.py`
- `src/document_intake/application/ports/persistence.py`
- `src/document_intake/persistence/__init__.py`
- `src/document_intake/persistence/database.py`
- `src/document_intake/persistence/errors.py`
- `src/document_intake/persistence/serialization.py`
- `src/document_intake/persistence/migrations/__init__.py`
- `src/document_intake/persistence/migrations/v0003_audit_events.py`
- `scripts/verify_pr007_audit.py`

`persistence/errors.py` may be changed only if the existing stable error taxonomy cannot represent a required fail-closed boundary. Prefer reuse of existing codes. Do not authorize a new application service, application command or query in PR-007.

## Exact test files

PR-007 may create or modify only where required in:

- `tests/domain/test_audit_events.py`
- `tests/persistence/test_audit_events.py`
- `tests/persistence/test_migrations.py`
- `tests/persistence/test_unit_of_work.py`
- `tests/persistence/test_privacy.py`
- `tests/persistence/test_static_contracts.py`
- `tests/persistence/test_windows_sqlcipher_integration.py`
- `tests/test_documentation_baseline.py`
- required lifecycle and architecture documentation updates.

Do not authorize unrelated test refactors.

## Exact inputs and outputs

Input is an application-supplied immutable `AuditEvent`. Outputs are persisted audit rows and repository reads. Repository reads return immutable `AuditEvent` objects or tuples of immutable `AuditEvent` objects. `get()` returns `None` when the event does not exist.

## Domain contract

`AuditEvent` must be a frozen, slotted immutable domain object with exactly these conceptual fields:

- `event_id: EntityId`
- `occurred_at: datetime`
- `actor: ActorRef`
- `action_code: AuditAction`
- `subject_type: AuditSubjectType`
- `subject_id: EntityId`
- `field_key: FieldKey | None`
- `before: AuditValueSummary | None`
- `after: AuditValueSummary | None`
- `reason_code: AuditReasonCode | None`
- `correlation_id: EntityId | None`

`occurred_at` must be timezone-aware, normalized to UTC during construction and persisted in canonical UTC representation. Naive datetimes must be rejected. All enum and value-object types must be explicitly validated. No mutable collections may be exposed. `repr()` must expose only safe identifiers, enums and presence flags.

Initial `AuditAction` values must be exactly `ENTITY_CREATED`, `ENTITY_UPDATED`, `FIELD_CORRECTED`, `FIELD_VERIFIED`, `SNAPSHOT_CREATED`, `ARTIFACT_REGISTERED` and `EXPORT_CREATED`.

Initial `AuditSubjectType` values must be exactly `PERSON`, `IDENTITY_DOCUMENT`, `MIGRATION_DOCUMENT`, `VEHICLE`, `DOCUMENT`, `FIELD_CANDIDATE`, `APPLICATION`, `APPLICATION_SNAPSHOT` and `STORED_ARTIFACT`.

## Actor boundary

Reuse the existing immutable `ActorRef` value object. `ActorRef` remains an opaque caller-supplied reference containing `actor_id: EntityId` and `kind: ActorKind`. Using `ActorRef` does not imply that a user record or authentication system exists. PR-031 remains responsible for local users and authentication.

Audit events must not store operator display name, email address, login, username, free-text identity, workstation username or Windows profile name.

## Masking policy

Introduce `AuditValueClassification` with exactly `ABSENT`, `NON_SENSITIVE` and `SENSITIVE_REDACTED`. Introduce immutable `AuditValueSummary` with `classification: AuditValueClassification`, `display_value: str | None` and `was_present: bool`.

Valid combinations are exactly:

- `ABSENT`: `was_present is False` and `display_value is None`.
- `NON_SENSITIVE`: `was_present is True`; `display_value` is required, 1 to 64 characters, and matches `^[A-Z0-9][A-Z0-9_.:-]{0,63}$`; it must be a controlled canonical value such as an enum, status, country code, document type or verification-state code.
- `SENSITIVE_REDACTED`: `was_present is True` and `display_value is None`.

For sensitive values, do not store original values, hashes, salted hashes, prefixes, suffixes, last digits, masked substrings, reconstructive lengths or normalization results. Sensitive values include passport and identity-document numbers, identity-document series and full numbers, personal numbers, MRZ, birth dates, places of birth, issue dates, expiry dates, migration dates, VINs, chassis numbers, body numbers, vehicle registrations, trailer registrations, phones, addresses, personal names, owner names, issuer names, OCR text, machine-readable-zone payloads, source-region text, original filenames and filesystem paths.

`before is None` or `after is None` means the side is not applicable. `AuditValueSummary(ABSENT)` means the side is applicable and explicitly known to contain no value.

## Reason-code policy

Do not use a raw unrestricted string for `reason_code`. Introduce immutable `AuditReasonCode`. Its canonical value must be 1 to 64 characters and match `^[A-Z][A-Z0-9_]{0,63}$`. It must contain no whitespace, no punctuation other than underscore, no user-entered prose, no document value, no name, no phone, no date, no identifier, no path and no OCR text. Reason codes are code-defined machine values, not operator comments.

## Migration v0003 contract

Create forward-only migration `src/document_intake/persistence/migrations/v0003_audit_events.py` with version `3` and name `audit_events_pr007`. Keep v0001 and v0002 byte-for-byte unchanged. Increase `CURRENT_SCHEMA_VERSION` to `3` and append v0003 to the ordered migration tuple.

Store audit events inside the encrypted SQLCipher database using the existing canonical payload plus projection-integrity pattern. Validate persisted projections against canonical payload and reject mismatches. Add database-level immutable-row protection rejecting UPDATE, DELETE, `INSERT OR REPLACE` replacement of an existing event and `REPLACE INTO` replacement of an existing event.

The v0003 table must project at least event ID, canonical UTC occurrence time, actor ID, actor kind, action code, subject type, subject ID, optional field key, before classification/presence/display value, after classification/presence/display value, optional reason code, optional correlation ID and canonical payload. Database constraints must validate enum values, required identifiers, nullable combinations, canonical boolean projections, summary classification combinations where practical and reason-code length/safe grammar where practical. The canonical domain deserializer remains the final invariant boundary.

## Repository contract and deterministic ordering

Expose exactly:

- `add(event: AuditEvent) -> None`
- `get(event_id: EntityId) -> AuditEvent | None`
- `list_for_subject(subject_type: AuditSubjectType, subject_id: EntityId) -> tuple[AuditEvent, ...]`
- `list_by_correlation(correlation_id: EntityId) -> tuple[AuditEvent, ...]`

Both list methods must order ascending by `occurred_at`, then `event_id` as the stable tie-breaker. Do not expose `list_all`, arbitrary SQL filters, caller-supplied sort expressions, pagination in PR-007, update, replace, delete or purge. Duplicate event insertion must use the existing stable sanitized `ENTITY_ALREADY_EXISTS` persistence error boundary. Malformed persisted audit data must use the existing sanitized persistence error taxonomy. Do not expose raw driver errors.

## Unit of Work contract

Add `audit_events: AuditEventRepository` to the existing Unit of Work port and production SQLCipher Unit of Work. The audit repository must use the same connection and outer transaction, become unusable after Unit of Work closure, follow existing commit and rollback behavior, not commit independently and not open an independent connection. A transaction containing both a fictional synthetic business write and an audit event must commit both or roll back both.

## Application boundary

Do not auto-write audit events inside low-level repositories. Low-level persistence repositories must not infer actor, action, reason or business meaning. Future application commands and services must explicitly add required audit events through the same Unit of Work. PR-007 implements only domain contracts, persistence port, repository, migration, Unit of Work integration, tests, synthetic verifier and documentation. PR-007 must not implement new business workflow commands or event emitters.

PR-007 advances FR-12 and FR-13 but does not fully complete FR-12. `FieldCandidate` remains the source of recognized candidate values; `VerifiedField` remains the source of confirmed values, actor and timestamp; persisted business entities remain the source of current values. PR-017 remains responsible for operator correction workflow, verification workflow integration, explicit `FIELD_CORRECTED` and `FIELD_VERIFIED` emission and transactional coordination of those events with operator actions.

## Failure behavior

Invalid audit domain data, naive timestamps, invalid summary combinations, unsafe reason codes, unsafe non-sensitive display values, projection/payload mismatches and malformed persisted data fail closed. Duplicate insertion fails with stable sanitized errors. Failed audit inserts roll back the transaction. Rollback removes both the business change and audit event. Repository access after Unit of Work closure fails with the existing stable closed-UoW error. No audit failure may expose PII, keys, SQL, database paths, payloads or raw driver messages.

## Security restrictions

No arbitrary metadata dictionary, free-text message field, filesystem paths, original filenames, document bytes, OCR payload, MRZ payload, exception trace, secret/key material, raw SQL, direct PII-bearing actor identity, telemetry, cloud services or network calls. Only fictional synthetic values may be used in tests and reports. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports.

## Acceptance criteria

PR-007 is acceptable only when the authorized files are respected, v0001/v0002 are unchanged, v0003 is checksummed and independently verified, schema version 3 is reached, audit rows are immutable at the database level, repositories round-trip and list deterministically, Unit of Work commit/rollback is atomic with audit events, failures are sanitized, forbidden synthetic PII markers are absent from payloads/projections/repr/exceptions/reports/console output, Ubuntu and Windows suites pass and the manual verifier passes on Windows through the production SQLCipher adapter without SQLite substitution.

## Automated tests

Required tests:

1. `AuditEvent` validation and immutability.
2. `AuditValueSummary` validation and immutability.
3. UTC-aware timestamp enforcement.
4. Canonical normalization of aware timestamps to UTC.
5. Controlled action enum.
6. Controlled subject enum.
7. Reuse and validation of `ActorRef`.
8. Reuse and validation of `FieldKey`.
9. `AuditReasonCode` safe grammar and length.
10. Rejection of free-text reason values.
11. Sensitive-value redaction with no original substring.
12. Rejection of invalid summary field combinations.
13. Rejection of arbitrary metadata and free-text messages.
14. Repository add/get round trip.
15. Subject-list round trip.
16. Correlation-list round trip.
17. Deterministic `(occurred_at, event_id)` ordering.
18. Duplicate event rejection.
19. Missing-event behavior.
20. Migration v0003 checksum and ordered migration history.
21. Independent literal verification of the v0003 checksum.
22. v0001 byte/checksum immutability.
23. v0002 byte/checksum immutability.
24. UPDATE rejection at database level.
25. DELETE rejection at database level.
26. `INSERT OR REPLACE` rejection for an existing audit row.
27. `REPLACE INTO` rejection for an existing audit row.
28. Canonical payload/projection tamper detection.
29. Invalid persisted enum detection.
30. Invalid persisted timestamp detection.
31. Invalid persisted summary detection.
32. Unit of Work commit behavior.
33. Unit of Work rollback behavior.
34. Atomic rollback of a business write and its audit event.
35. Repository-after-close behavior.
36. Stable sanitized persistence errors.
37. PII absence in payload projections.
38. PII absence in `repr()`.
39. PII absence in exceptions.
40. PII absence in verification reports.
41. Windows SQLCipher execution through the production adapter.
42. No network access.
43. Full regression suite on Ubuntu.
44. Full regression suite on Windows.

## Windows verification and manual verifier

Create `scripts/verify_pr007_audit.py`. It must use only fictional synthetic data and the production SQLCipher persistence adapter, create a temporary encrypted database, migrate through v0003, verify schema version 3, write/read an audit event, verify deterministic subject and correlation reads, prove UPDATE/DELETE/replacement-form rejection, prove rollback atomicity using a synthetic business entity and audit event, prove sensitive-value redaction, prove canonical payload/projection integrity, scan every rendered output line for forbidden synthetic PII markers, never print a temporary database path, never print raw exceptions, print only sanitized lines beginning with `PASS` or `FAIL`, include OS, architecture, Python version, schema version and v0003 checksum in sanitized `PASS` environment lines, remove all temporary artifacts in `finally`, require no network and exit zero only when all checks pass. It must pass on Windows through the production SQLCipher adapter and must not silently substitute ordinary SQLite.

## Non-goals

PR-007 must not authorize UI, image import, image processing, OCR, MRZ, barcode processing, Excel, terminal adapters, upload batches, source-file workflows, document-region workflows, local authentication, users, permissions, backup or restore, retention, deletion, purge, secure deletion, cloud services, network calls, telemetry, arbitrary audit metadata, free-text audit messages, real-document fixtures, automatic audit emission by repositories or complete FR-12 workflow integration.

## Final reporting requirements

The PR-007 final report must state changed files, decisions, exact migration v0003 checksum, confirmation that v0001 and v0002 are byte-for-byte unchanged, tests and exact results, Windows verifier output summary, manual steps, limitations, confirmation that no real documents or personal data were added, confirmation that Q-009 and Q-017 remain deferred, confirmation that PR-008 and later remain unauthorized, and confirmation that Gate 1 and M2 remain incomplete until PR-007 is merged and separately human accepted.
