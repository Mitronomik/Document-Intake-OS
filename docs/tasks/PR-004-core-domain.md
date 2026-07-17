# PR-004 — Core Domain

## Lifecycle state

- GATE-M0: COMPLETED
- GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`
- Human acceptance occurred after merge of GitHub PR #5.
- M0: ACCEPTED
- M1: ACCEPTED
- PR-004: IN REVIEW after implementation submission
- PR-004 is authorized and started by this PR.
- PR-004 is not completed before merge and product-owner acceptance.
- PR-005: UNAUTHORIZED
- PR-006: UNAUTHORIZED
- PR-007 AND LATER: UNAUTHORIZED
- Gate 1 is not accepted.
- M2 is not completed.
- Q-010 remains open and blocks PR-005 and PR-006 until a separate accepted security ADR resolves encryption staging.
- The template enforcement PR remains future work and does not block PR-004.
- The sensitive-data/private-contour gate remains open for real documents, PII, operational databases, real OCR/MRZ data, logs, exports and backups.

## Base SHA

`3dada63ea82163c7c4497e290b303d2cc781b085`

## Goal

Implement a pure Python core domain package for value objects, entities, document workflow transitions, human verification, critical-field resolution and deterministic application snapshots.

## Exact scope

Implemented source is limited to `document_intake.domain` plus the root package docstring. No dependencies, persistence, storage, OCR, image processing, Excel handling, telemetry, network behavior, authentication, encryption or audit events are added.

## Implemented public API

- Enums: `DocumentType`, `DocumentWorkflowStatus`, `VerificationStatus`, `CandidateSourceType`, `ActorKind`, `VehicleRole`, `TerminalCode`, `ApplicationStatus`, `OwnerKind`.
- Errors: `DomainError`, `InvalidValueError`, `InvalidTransitionError`, `VerificationPolicyError`, `SnapshotInvariantError`.
- Value objects: `EntityId`, `NonEmptyText`, `IdentifierText`, `CountryCode`, `FieldKey`, `FieldRef`, `Confidence`, `ActorRef`, `OwnerRef`, `ValidationIssue`, `ValidationReport`, `SnapshotPayload`.
- Entities: `Person`, `IdentityDocument`, `MigrationDocument`, `Vehicle`, `Terminal`, `Document`, `FieldCandidate`, `VerifiedField`, `ParticipantAssignment`, `Application`, `ApplicationSnapshot`.
- Policies: `can_transition_document`, `transition_document`, `CRITICAL_FIELD_KEYS`, `draft_from_candidate`, `verify_by_human`, `mark_conflict`, `mark_not_applicable`, `admin_override`, `unresolved_required_fields`, `create_application_snapshot`, `calculate_snapshot_sha256`.

## Inputs and outputs

Inputs are explicit identifiers, timestamps, scalar values, domain objects and canonical snapshot payload dictionaries. Outputs are domain objects, validation results, safe domain errors and deterministic snapshot hashes.

## Invariants

- Domain code imports only standard library modules and `document_intake.domain` modules.
- UUIDs and timestamps are supplied by callers.
- Identifier text preserves leading zeroes.
- OCR candidates remain drafts until human verification.
- Critical required fields must be resolved by complete `FieldRef` before snapshot creation.
- Snapshot creation validates before mutating the application.
- Application snapshots are immutable and hash the canonical semantic payload.
- Reprs and domain error messages exclude raw field values and PII-bearing text.

## Acceptance criteria

PR-004 is acceptable when domain imports without UI/infrastructure dependencies, enum values match the contract, transitions match the documented graph, verification blocks system-only critical confirmation, snapshots are deterministic and immutable, and tests pass without adding fixtures or dependencies.

## Tests

- `tests/domain/test_value_objects_and_entities.py`
- `tests/domain/test_document_transitions.py`
- `tests/domain/test_verification_policy.py`
- `tests/domain/test_application_snapshots.py`

## Manual verification

A Python-only manual check creates deterministic IDs and actors, creates a high-confidence candidate, confirms it remains unverified, verifies it through an operator, creates an application with a selected terminal and resolved critical fields, creates a snapshot, confirms the application becomes `SNAPSHOTTED`, and confirms snapshot hash stability after source payload mutation.

## Hard prohibitions

No real documents, PII, templates, binary golden files, runtime I/O, database, network, filesystem storage, OCR, MRZ parsing, image processing, Excel implementation, authentication, encryption, audit events, terminal limits, country-specific validation or later PR scope is included.

## Non-goals

Deferred: UploadBatch behavior, SourceFile metadata/import behavior, DocumentRegion geometry/version behavior, RecognitionRun lifecycle, ExportRun, AuditEvent, automatic deduplication, completeness matrices, terminal-specific participant limits, terminal-specific required-document rules, country-specific document validation, OCR/MRZ parsing, persistence repositories and filesystem references beyond opaque `EntityId` values.
