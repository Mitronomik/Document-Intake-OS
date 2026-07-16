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

M0 may be accepted and PR-004 may proceed while the repository remains temporarily public under ADR-014. The accepted public-repository state is `REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE`.

The public repository may contain only:

- non-sensitive application source code;
- non-sensitive documentation;
- ordinary development configuration;
- fully fictional synthetic source-code tests that contain no document-derived data.

The public repository must not contain:

- real documents or document photographs;
- personal data;
- anonymized or cleaned real documents;
- terminal templates;
- template-derived golden files;
- template-derived screenshots, manifests, checksums or mappings;
- databases or journals;
- OCR or MRZ payloads;
- private or local acceptance fixtures;
- operational logs or backups;
- secrets, keys, certificates or tokens.

`SENSITIVE-DATA / PRIVATE-CONTOUR GATE — OPEN` remains open. Real terminal templates and local acceptance materials remain outside Git, Codex and CI. The open sensitive-data gate does not block PR-004 because PR-004 requires no sensitive input. It continues to block every task that requires real documents, terminal templates, template-derived artifacts or private acceptance materials.

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

Allowed changes are documentation and documentation-baseline tests only. No runtime code, dependencies, fixtures, templates, databases, real or anonymized documents, private acceptance artifacts or repository-policy scanner changes are included.

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
