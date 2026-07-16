# PR-002 — Documentation Baseline Audit and Normalization

## Context

Document Intake OS is a fully local Windows 11 desktop application for importing driver and vehicle document photographs, non-destructive image preparation, local OCR/MRZ/barcode assistance, operator verification, local persistence, RGB JPEG generation not exceeding 1.90 MiB and Excel export through three real terminal templates.

PR-001 is completed and merged. The repository already contains a documentation package, so PR-002 audits, normalizes and tests that baseline rather than recreating it.

## Goal

Create a tested documentation baseline that defines a consistent source-of-truth hierarchy, verifies required repository documents, verifies relative Markdown links, updates lifecycle state, keeps unresolved questions unresolved and prepares the repository for PR-003 without implementing PR-003.

## Authoritative sources

Canonical source priority:

1. `docs/technical-specification.md`
2. `docs/decisions.md`
3. `docs/product-spec.md`
4. `docs/architecture.md`
5. `docs/domain-model.md`
6. `docs/security.md`
7. `docs/testing-strategy.md`
8. current PR task under `docs/tasks/`

A lower-priority document must not override a higher-priority source. Material conflicts must be reported instead of resolved silently.

## Exact files

PR-002 may create or modify only:

- `README.md`
- `AGENTS.md`
- `docs/handoff.md`
- `docs/implementation-plan.md`
- `docs/progress.md`
- `docs/tasks/PR-002-documentation-baseline.md`
- `tests/test_documentation_baseline.py`

If a documentation defect requires another file to change, implementation must stop and report the source file, broken destination and scope reason.

## Inputs

Inputs are the existing Markdown repository documents only.

Do not use real documents, document photographs, OCR payloads, MRZ values, real names or identifiers, terminal Excel files, cleaned or anonymized terminal templates, template-derived golden files, private fixtures, external APIs or web searches.

## Outputs

Expected outputs are the exact files listed above. No runtime output or application feature is required.

## Hard constraints

1. Do not add or modify application runtime code.
2. Do not change `pyproject.toml` or `uv.lock`.
3. Do not change CI in this PR.
4. Do not add secret scanning in this PR.
5. Do not add fixture scanning in this PR.
6. Do not add terminal templates.
7. Do not add golden Excel files.
8. Do not add real or anonymized document layouts.
9. Do not resolve Q-001 through Q-020.
10. Do not create a new ADR.
11. Do not change accepted business rules.
12. Do not introduce a new architecture or technology choice.
13. Do not start domain, persistence, storage, image, OCR, UI workflow or Excel implementation.
14. Do not claim M0 is complete.
15. Do not claim PR-002 is complete before merge.
16. Do not use network access as part of tests.
17. Do not weaken ADR-014 public-repository restrictions.
18. Do not modify files outside the exact allowed list.

## Implementation scope

- audit the existing documentation package;
- normalize source priority in `README.md` and `AGENTS.md`;
- verify required documentation files exist;
- verify relative Markdown links resolve;
- update lifecycle and handoff state;
- add automated documentation-baseline tests;
- preserve unresolved questions;
- introduce no new requirements or decisions.

## Non-goals

PR-002 does not implement PR-003 privacy guardrails, secret scanning, large-file scanning, prohibited fixture-pattern detection, OCR, MRZ, image processing, database schema, storage, domain entities, audit events, application workflows, production UI, Excel adapters, terminal rules, encryption, authentication, backup, installer or Windows production acceptance.

## Acceptance criteria

1. The implementation base is the accepted current-main commit `eff9404a8704161ed54cf95047a00c634cf13e64`.
2. Only allowed files are changed.
3. This PR task contract exists and contains the complete PR-002 scope.
4. Required documentation files exist.
5. Relative Markdown links resolve.
6. Markdown links in fenced code blocks are ignored.
7. `README.md` and `AGENTS.md` use the same source priority.
8. Conflicts must be reported rather than silently resolved.
9. `docs/handoff.md` reflects the current M1/PR-002 state.
10. PR-001 is not identified as current, next, under review or incomplete.
11. `docs/progress.md` records `PR-002 IN REVIEW`.
12. PR-002 is not marked completed.
13. M0 remains open.
14. The privacy gate remains open.
15. Q-001 through Q-020 remain present and unresolved.
16. No new product decision is introduced.
17. No new security decision is introduced.
18. No runtime code is changed.
19. No dependency or lockfile is changed.
20. No CI workflow is changed.
21. No terminal template or document-derived fixture is added.
22. Ruff passes.
23. Ruff format check passes.
24. Mypy passes.
25. Pytest passes.
26. Package build passes.
27. Ubuntu CI passes.
28. Windows CI passes.
29. Manual verification instructions are included in this task document.
30. The final implementation report distinguishes completed work from unresolved questions.

## Automated tests

Add `tests/test_documentation_baseline.py` with clear, independently named tests that verify:

- required documentation file existence;
- relative Markdown links in `README.md`, `AGENTS.md` and `docs/**/*.md`, ignoring fenced code blocks, external links, `mailto:` links and anchor-only links;
- canonical authoritative-source order in the dedicated source-priority sections of `README.md` and `AGENTS.md`;
- lifecycle state: PR-002 is in review, PR-002 is not completed, handoff is not pre-implementation, PR-001 is not current/next/under review/incomplete, PR-002 is current, PR-003 is next after acceptance, M0 and privacy gate are not closed;
- Q-001 through Q-020 headings remain present in `docs/open-questions.md`.

## Manual verification

Run:

```bash
git diff --check
uv sync --locked --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -ra
uv build
```

Also verify changed-file scope with the available accepted-main base reference:

```bash
git diff --name-only eff9404a8704161ed54cf95047a00c634cf13e64...HEAD
```

Expected changed files are limited to:

```text
AGENTS.md
README.md
docs/handoff.md
docs/implementation-plan.md
docs/progress.md
docs/tasks/PR-002-documentation-baseline.md
tests/test_documentation_baseline.py
```

Manually verify stale lifecycle markers:

```bash
grep -n "PRE-IMPLEMENTATION" docs/handoff.md
grep -n "PR-001 Repository bootstrap" docs/handoff.md
grep -n "PR-002 IN REVIEW" docs/progress.md
grep -n "PR-002 COMPLETED" docs/progress.md
```

The first two commands and the final command should return no matches. `PR-002 IN REVIEW` must be present.

## Progress-status rule

`docs/progress.md` must record `PR-002 IN REVIEW` while implementation is submitted but not yet merged and accepted.

PR-002 remains `IN REVIEW` until it is merged and accepted. PR-002 must not be marked completed in this PR.

## Rules for unresolved questions

PR-002 does not answer Q-001 through Q-020. Those questions remain unresolved unless a separate accepted ADR explicitly states otherwise.

## Security and privacy restrictions

The repository is temporarily public. While it remains public, do not commit real documents, document photographs, scans, screenshots derived from documents, real personal data, OCR outputs, MRZ payloads, production databases, database journals, backups, operational logs, secrets, private fixtures, terminal templates, cleaned or anonymized terminal templates or template-derived golden Excel files.

PR-002 must not add telemetry, cloud OCR, cloud storage, external AI APIs, external error reporting, browser automation or direct Konversta submission.
