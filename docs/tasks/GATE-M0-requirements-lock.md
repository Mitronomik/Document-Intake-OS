# GATE-M0 — Requirements lock and PR-004 authorization

## Status

GATE-M0 IN REVIEW.

This task records the product-owner-approved M0 decision packet. It does not implement PR-004 and does not start domain, persistence, storage, image, OCR, Excel, UI, authentication, backup or installer work.

## Base

Base commit: `ad5782045473d3ef5eb0a097cc8f6982bab821c7`.

This is the merge commit of GitHub PR #4, which delivered PR-003.

## Lifecycle recorded by this gate

- PR-003: COMPLETED and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`.
- M1: ACCEPTED by the product owner.
- M0: DECISION APPROVED in this gate PR, not yet recorded in `main` until merge and human acceptance.
- PR-004: BLOCKED UNTIL GATE-M0 PR MERGE AND HUMAN ACCEPTANCE.

## Approved decisions

### M0-01 — Privacy and public-repository boundary

Accepted.

M0 may be accepted and PR-004 may proceed while the repository remains temporarily public under ADR-014 as partially superseded by ADR-016.

`REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE` remains accepted.

`SENSITIVE-DATA / PRIVATE-CONTOUR GATE — OPEN` remains open for real documents, personal data, real application data, operational databases, real acceptance datasets, real OCR/MRZ output, operational logs, real exports, backups and secrets. It is not a blanket gate against the approved terminal templates.

### Product-owner template decision

The product owner approves these three terminal templates as non-sensitive project contract files:

- `TSPMAINFILE.xls`;
- `visitors_example.xlsx`;
- `MGSMAINFILE.xlsx`.

They may be stored in the project repository after technical content validation confirms that they contain no real personal data, credentials or confidential operational data.

Permitted derivatives include approved original Excel templates, cleaned copies, anonymized copies, empty structural copies, binary golden files, synthetic output workbooks, screenshots showing template structure, real template checksum values, extracted structural manifests, machine-generated mappings, manually maintained mappings, workbook structural metadata, sheet names and order, exact headers, comments, validations, named ranges, tables and ranges, styles, merged-cell definitions and external-connection metadata that contains no credentials or confidential paths.

No separate product-owner decision is required for each checksum, manifest, screenshot, mapping or golden file derived from one of the three approved templates. A new template belonging to another terminal still requires a separate product-owner decision.

### Content-based restriction

Template origin or binary format does not make a file prohibited. A permitted template artifact must not contain real driver or visitor records, real application rows, real names, real dates of birth, real passport, identity-document or migration-document numbers, real phone numbers, real registration addresses, real VINs, real vehicle or trailer registration numbers, real organization data when it identifies an actual application participant, photographs or scans of real documents, OCR output from real documents, MRZ payloads from real documents, authentication credentials, passwords, API tokens, private keys, confidential connection strings, confidential local or network paths or operational data not authorized for publication.

Golden files and synthetic output workbooks may contain only fully fictional test values. A screenshot is permitted only when it contains empty structure or fully fictional values. A manifest is permitted only when it contains structural metadata and no real personal or operational records. Real checksum values of the approved source templates are permitted and are not personal data.

### Technical privacy inspection

Each approved template must undergo technical privacy inspection before its first commit. The inspection must cover visible cells, hidden sheets, hidden rows and columns, comments and notes, workbook and document properties, author and last-editor metadata, custom properties, defined names, external links, Power Query and workbook connections, cached connection results, embedded objects, images, macros where applicable, local usernames, local filesystem paths, network paths, credentials and connection strings.

The inspection is not a new product decision. It is a technical acceptance check proving that the artifact complies with the already accepted content boundary. Do not claim that all three files have passed this inspection unless all three files were actually available and inspected.

### Transitional technical enforcement

Product policy permits the three approved PII-free terminal templates and their technical derivatives. The current scanner and `.gitignore` remain temporarily more restrictive. Before the first permitted binary artifact is committed, a separate repository-policy enforcement PR must update the scanner, `.gitignore` and related tests.

The future enforcement PR is required before committing an Excel template, binary golden file, template screenshot, generated manifest or generated mapping artifact. That future enforcement PR does not block PR-004. It blocks only the first actual commit of those artifact classes.

No template artifact is added by GATE-M0 / PR #5.

### M0-02 — MVP workstation topology

Accepted.

The first MVP topology is one Windows 11 x64 workstation with one active operator session at a time.

Consequences:

- no shared multi-workstation database;
- no network-shared application storage;
- no concurrent application writers;
- no cross-workstation synchronization;
- SQLite may be evaluated for this single-workstation topology;
- filesystem ownership and locking may assume one active application session;
- future local accounts are not prohibited;
- authentication, passwords, inactivity timeout and recovery remain deferred to PR-031;
- this decision does not implement SQLite, storage, users or authentication.

### M0-03 — M0 acceptance and authorization boundary

Accepted, subject to this Phase B documentation and tests passing and the gate PR being merged and human accepted.

After this gate PR is merged and accepted, the repository may record:

```text
PR-003: COMPLETED
M1: ACCEPTED
M0: ACCEPTED
PR-004: AUTHORIZED
```

Authorization is limited to PR-004 — Core Domain. It does not authorize PR-005, PR-006, PR-007 or any later implementation task.

PR-005 and PR-006 remain entirely unauthorized until a separate accepted security ADR resolves Q-010 encryption staging. This task does not select an encryption technology.

## Terminal-gate staging rule

For M0 and PR-004 authorization, a terminal-specific question may be treated as non-blocking only when all of the following are recorded:

1. the question remains present;
2. it has an explicit status;
3. its required evidence or confirmation is identified;
4. its owner is identified;
5. its target PR or milestone is identified;
6. implementation depending on that answer remains blocked until evidence exists;
7. no placeholder terminal value is invented.

This rule does not answer the terminal question. It stages the question to the correct downstream gate and prevents it from blocking domain-only PR-004.

## Open-question status summary

| Question | Status | Target |
|---|---|---|
| Q-001 | EXTERNAL_CONFIRMATION_REQUIRED | before PR-020 operator-facing/adapter naming |
| Q-002 | EXTERNAL_CONFIRMATION_REQUIRED | before PR-022 |
| Q-003 | EXTERNAL_CONFIRMATION_REQUIRED | before applicable terminal adapter/export enforcement |
| Q-004 | EXTERNAL_CONFIRMATION_REQUIRED | before PR-023 |
| Q-005 | EXTERNAL_CONFIRMATION_REQUIRED | before PR-019–PR-023 terminal rules |
| Q-006 | DEFERRED | PR-013 |
| Q-007 | DEFERRED | PR-009/PR-011 and pilot |
| Q-008 | ACCEPTED | ADR-017 |
| Q-009 | DEFERRED | before storage/audit/backup policy is implemented |
| Q-010 | OPEN | separate security ADR before PR-005; blocks PR-005 and PR-006 |
| Q-011 | DEFERRED | PR-031 |
| Q-012 | LOCAL_EVIDENCE_REQUIRED | M6 local OCR evidence |
| Q-013 | LOCAL_EVIDENCE_REQUIRED | M6 local OCR evidence |
| Q-014 | LOCAL_EVIDENCE_REQUIRED | M6 local OCR evidence |
| Q-015 | LOCAL_EVIDENCE_REQUIRED | before PR-022/PR-023 and installer acceptance |
| Q-016 | DEFERRED | PR-023 |
| Q-017 | DEFERRED | before PR-006 if storage layout changes, no later than PR-032 |
| Q-018 | DEFERRED | PR-033/PR-034 |
| Q-019 | SUPERSEDED | ADR-002 and NFR-02 |
| Q-020 | DEFERRED | Future; direct integration remains outside MVP under ADR-007 |

## Scope

Allowed changes are documentation and documentation-baseline tests only. No runtime code, dependencies, fixtures, databases, real or anonymized documents, private acceptance artifacts or repository-policy scanner changes are included. No template artifact is added by GATE-M0 / PR #5.

## Verification

Required local verification:

```bash
git diff --check
python scripts/check_repository_policy.py
uv sync --locked --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/check_repository_policy.py
uv run pytest -ra
uv build
git diff --name-only ad5782045473d3ef5eb0a097cc8f6982bab821c7...HEAD
git status --short
git ls-files
```


## Post-merge lifecycle transition for PR-004

GATE-M0: COMPLETED. GATE-M0 merge commit: `3dada63ea82163c7c4497e290b303d2cc781b085`. Human acceptance occurred after merge of PR #5. M0: ACCEPTED. M1: ACCEPTED. PR-004: IN REVIEW after implementation submission; PR-004 is authorized and started by this PR. PR-004 is not completed before merge and human acceptance. PR-005: UNAUTHORIZED. PR-006: UNAUTHORIZED. PR-007 AND LATER: UNAUTHORIZED. Gate 1 is not accepted. M2 is not completed. Q-010 remains open. The template enforcement PR remains future work and does not block PR-004. The sensitive-data/private-contour gate remains open for real data.
