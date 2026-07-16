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

`SENSITIVE-DATA / PRIVATE-CONTOUR GATE — OPEN` remains open for real documents, personal data, real operational databases, real exports, logs, backups, OCR/MRZ outputs from real documents, private acceptance datasets, credentials and secrets.

### Product-owner terminal-template classification

The three real terminal Excel templates are classified by the product owner as non-sensitive project contract files.

The product owner confirms that these template files:

- do not contain personal data;
- do not contain real application rows;
- do not contain document images;
- do not contain authentication credentials, private keys or secret tokens;
- are authorized for use and storage in the project repository.

Permitted artifact classes are:

1. the three real Excel terminal templates;
2. cleaned or anonymized copies of those templates;
3. binary golden files derived from those templates;
4. screenshots or rendered images of those templates;
5. real template checksum values;
6. extracted template manifests;
7. machine-generated mappings extracted from those templates;
8. new mapping files derived from the approved terminal templates;
9. structural metadata, including workbook format, sheet names, headers, comments, validations, named ranges, tables, styles, merged cells, external connections and adapter mappings.

These artifacts are not considered personal data merely because they are derived from a terminal template.

No separate product-owner analysis or decision is required for each checksum, manifest, screenshot, binary golden file or mapping artifact when all of the following are true:

- it is derived only from one of the three approved terminal templates;
- it contains no real driver, vehicle or application data;
- it contains no real document image;
- it contains no secret or credential;
- synthetic test values, when present, are fully fictional;
- the artifact does not introduce data from another unapproved source.

This decision does not authorize arbitrary new terminal templates from other terminals. A new source terminal template outside the currently approved three-template set requires a separate product-owner decision.

### Data-content restrictions

The repository must still prohibit:

- real passports, identity cards, migration cards, work permits and vehicle documents;
- photographs or scans of real documents;
- real driver, vehicle, organization or application records;
- databases containing real or operational data;
- SQLite journals and database snapshots;
- exports produced from real applications;
- logs containing personal or operational data;
- backups containing personal or operational data;
- OCR outputs or MRZ payloads produced from real documents;
- screenshots containing personal data;
- golden files populated with real data;
- manifests containing personal data;
- mappings containing personal data;
- secrets;
- API tokens;
- passwords;
- private keys;
- certificates containing private credentials;
- connection credentials;
- confidential third-party materials that the project is not authorized to publish.

The determining boundary is content and authorization, not merely the `.xls` or `.xlsx` extension.

### ADR-014 relationship

ADR-014 remains accepted for personal data, real documents, operational databases, logs, backups, OCR/MRZ outputs, private acceptance datasets, credentials and secrets.

ADR-016 explicitly supersedes only the parts of ADR-014 that categorically prohibited the approved terminal templates, cleaned template copies, template-derived golden files, template screenshots, template checksum values, template manifests and template mappings.

ADR-014 is not fully superseded.

### Transitional enforcement state

The product policy permits approved non-sensitive terminal templates and template-derived technical artifacts. The current repository scanner and `.gitignore` remain intentionally more restrictive until a separate repository-policy implementation PR is reviewed and merged.

Before the first actual Excel template, screenshot, golden file, manifest or generated mapping is committed, a separate repository-policy implementation PR must update:

- `scripts/check_repository_policy.py`;
- `tests/test_repository_policy.py`;
- `.gitignore`;
- `resources/templates/README.md`;
- `docs/security.md`;
- `docs/testing-strategy.md`;
- `docs/development-workflow.md`.

That future PR must define approved template paths, approved derivative paths, golden-file locations, screenshot locations, manifest and mapping locations, provenance rules, synthetic-data-only golden-file rules and continued blocking of real documents, PII, databases, logs, backups and secrets.

The future enforcement PR does not block PR-004. It blocks only the first commit of the newly permitted template artifacts.

No template artifact is added by GATE-M0.

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

Allowed changes are documentation and documentation-baseline tests only. No runtime code, dependencies, fixtures, templates, databases, real or anonymized documents, private acceptance artifacts or repository-policy scanner changes are included. No template artifact is added by GATE-M0.

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
