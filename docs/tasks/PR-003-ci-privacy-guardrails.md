# PR-003 — ADR-015, CI and privacy guardrails

## Context

PR-001 repository bootstrap is completed. PR-002 documentation baseline is completed and merged through GitHub PR #3 with merge commit `d7203f82`. PR-002 reported a lifecycle conflict between the M0 gate and the PR-001 through PR-003 repository-safety work grouped under M1. ADR-015 resolves only that repository-safety sequencing issue.

## ADR-015 product-owner decision

1. PR-001 through PR-003 form a narrow repository-safety workstream.
2. Repository-safety work under PR-001 through PR-003 may proceed while M0 remains open.
3. PR-003 is authorized by this decision.
4. PR-003 is limited to:

   * CI integration;
   * tracked-file privacy policy;
   * high-confidence secret detection;
   * private-fixture path protection;
   * terminal-template protection;
   * tracked-image location and size protection;
   * fixture-policy documentation and tests.
5. M0 remains open.
6. The privacy gate remains open.
7. Terminal and security questions remain unresolved.
8. This decision does not approve real documents, personal data, document-derived fixtures, terminal templates or template-derived golden files for the public repository.
9. This decision does not authorize domain, persistence, storage, image pipeline, UI workflow, OCR or Excel implementation.
10. This decision does not authorize PR-004 or any later implementation task.
11. M2 must not begin until:

    * M0 is accepted;
    * M1 repository-safety work is accepted.
12. Completion of PR-003 does not imply completion of M0.
13. Completion of PR-003 does not automatically authorize M2.
14. Q-001 through Q-020 remain unresolved.
15. Public-repository restrictions from ADR-014 remain unchanged.

## Goal

Create an enforceable repository-safety boundary that records ADR-015, scans currently tracked files, blocks prohibited paths and file types, blocks private fixtures and terminal-template content, permits synthetic images only in the approved location, detects high-confidence secret signatures, runs locally and in GitHub Actions, and keeps M0, the privacy gate, M2 and PR-004+ blocked.

## Authoritative sources

1. `docs/technical-specification.md`
2. `docs/decisions.md`
3. `docs/product-spec.md`
4. `docs/architecture.md`
5. `docs/domain-model.md`
6. `docs/security.md`
7. `docs/testing-strategy.md`
8. this PR task contract

## Exact allowed files

```text
.github/workflows/ci.yml
.gitignore
AGENTS.md
README.md
scripts/check_repository_policy.py
tests/test_repository_policy.py
tests/test_documentation_baseline.py
docs/decisions.md
docs/roadmap.md
docs/implementation-plan.md
docs/security.md
docs/testing-strategy.md
docs/development-workflow.md
docs/progress.md
docs/handoff.md
docs/tasks/PR-003-ci-privacy-guardrails.md
resources/templates/README.md
```

No other file may be created or modified.

## Inputs

Inputs are tracked repository paths, tracked repository file metadata, tracked text-file content and existing repository documentation.

## Outputs

Outputs are limited to the exact allowed files. No application runtime feature, document-processing feature or fixture file is required.

## Scanner architecture

`scripts/check_repository_policy.py` is a deterministic standard-library Python scanner. It uses `git ls-files -z`, does not recursively inspect untracked directories, exposes pure functions, normalizes repository-relative POSIX paths, evaluates path, extension, image-size, fixture, environment, symlink and text-secret policies, sorts violations deterministically and exits with `0`, `1` or `2`.

## Policy rules

Stable rule IDs:

```text
PATH_FORBIDDEN_ROOT
PATH_TERMINAL_TEMPLATE
PATH_FIXTURE_LOCATION
PATH_SYMLINK_ESCAPE
PATH_OUTSIDE_REPOSITORY
EXT_FORBIDDEN
ENV_FORBIDDEN
IMAGE_LOCATION
IMAGE_SIZE
FILE_READ_ERROR
SECRET_PRIVATE_KEY
SECRET_AWS_ACCESS_KEY_ID
SECRET_GITHUB_CLASSIC
SECRET_GITHUB_FINE_GRAINED
SECRET_OPENAI
SECRET_GOOGLE_API_KEY
SECRET_SLACK
SECRET_STRIPE_LIVE
```

Forbidden root paths are `data/`, `runtime/`, root `storage/`, `database/`, `backups/`, `exports/`, `logs/`, `temp/`, `tmp/`, `source-documents/`, `real-documents/`, `personal-data/`, `private-fixtures/` and `local-acceptance/`.

While the repository is public, `resources/templates/README.md` is the only permitted tracked file under `resources/templates/`. This exception permits repository-policy documentation only. It does not permit any template, fixture, manifest, checksum or template-derived information.

Committed fixture files may exist only under `tests/fixtures/synthetic/`. Tracked images are allowed only under that subtree and must not exceed 1,992,294 bytes.

Forbidden file types include Excel and Office templates, database files and journals, keys and key stores, documents and archives. Environment files are forbidden except `.env.example`, which still must pass secret scanning.

## Secret signatures

The scanner detects a deliberately narrow high-confidence set: private-key markers, AWS access-key IDs, GitHub classic tokens, GitHub fine-grained tokens, OpenAI-style keys, Google API keys, Slack tokens and Stripe live secret keys. It does not add broad entropy heuristics, generic keyword matching or semantic PII detection.

## Diagnostics contract

Each violation includes a stable rule ID, repository-relative path, line number when applicable and a safe explanation. Diagnostics never include matched secret values, surrounding source text, full source lines or binary content. Violations are sorted by path, rule ID and line number.

## CI changes

GitHub Actions runs on Ubuntu and Windows with read-only contents permission. Checkout uses `persist-credentials: false`. The repository-policy scanner runs after Python setup and before dependency installation. Existing package import, Ruff, format, mypy, pytest and build checks remain. Mypy checks `src` and `scripts/check_repository_policy.py`.

## Scope

PR-003 records ADR-015, adds the repository-policy scanner, updates CI, updates repository-safety documentation, rewrites the terminal-template directory policy marker and adds tests.

## Hard constraints

Do not add runtime code, dependencies, lockfile changes, terminal templates, document fixtures, real or anonymized documents, personal data, third-party secret-scanning actions, generic entropy scanning or semantic PII claims. Do not resolve Q-001 through Q-020. Do not close M0, the privacy gate or M1. Do not start M2 or PR-004.

## Non-goals

PR-003 does not implement full Git-history forensics, credential revocation, semantic PII classification, OCR-based fixture inspection, antivirus scanning, dependency vulnerability audit, license audit, network blocking tests, runtime offline enforcement, encryption, authentication, backup, production logging, domain logic, SQLite, filesystem storage, image pipeline, Excel adapters, Windows installer or real-data acceptance.

## Automated tests

Tests cover current repository pass, forbidden root paths, runtime-storage path distinction, terminal workbook rejection, exact `resources/templates/README.md` exception, private-fixture rejection, synthetic fixture allowance, image location, oversized images, forbidden document/archive types, environment files, private-key and token signatures, safe diagnostics, deterministic ordering, invalid UTF-8, read failure and symlink escape.

## Manual verification

Run:

```bash
git diff --check
python scripts/check_repository_policy.py
uv sync --locked --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/check_repository_policy.py
uv run pytest -ra
uv build
```

Also inspect changed files, tracked files and lifecycle markers.

## Acceptance criteria

ADR-015 is accepted and dated 2026-07-16. PR-003 is `IN REVIEW`, not completed. M0 and the privacy gate remain open. M2 and PR-004+ remain blocked. Q-001 through Q-020 remain unresolved. The current tracked repository passes the scanner. CI runs the scanner on Ubuntu and Windows before dependency installation. No fixture, template, runtime source or dependency file is added or changed outside the allowed list.

## Lifecycle status rule

PR-003 remains `IN REVIEW` until merge and human acceptance. Completion of PR-003 does not imply completion of M0 and does not authorize M2.

## Security limitations

The scanner reduces risk but cannot prove absence of every possible secret or PII item. It scans the current tracked tree only and is not Git-history forensics. Real-data acceptance remains local and outside Git, Codex and CI.

## Next safe step

After PR-003 merge and human acceptance, confirm whether M1 repository-safety work is accepted. Do not start PR-004 until M0 is accepted and M1 repository-safety work is accepted.
