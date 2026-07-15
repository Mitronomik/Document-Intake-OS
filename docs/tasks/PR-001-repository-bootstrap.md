# PR-001 — Repository bootstrap

## Goal

Create a production-oriented Python 3.12 repository skeleton for the offline Document Intake OS Windows desktop application.

## Required reading

- `AGENTS.md`
- `docs/technical-specification.md`
- `docs/architecture.md`
- `docs/domain-model.md`
- `docs/security.md`
- `docs/testing-strategy.md`
- `docs/progress.md`

## Scope

- configure `pyproject.toml`;
- use uv for dependency management;
- create the package layout defined in the architecture;
- configure pytest, Ruff and mypy;
- create a minimal PySide6 application entry point;
- create a minimal automated smoke test;
- add CI checks that do not require real documents or OCR models;
- update README development commands;
- update `docs/progress.md`.

## Hard constraints

- do not implement business functionality;
- do not add OCR;
- do not add database code;
- do not add network dependencies or telemetry;
- do not modify the supplied Excel templates;
- do not include any real personal data;
- do not make new security or persistence decisions.

## Non-goals

- image processing;
- domain implementation;
- persistence;
- Excel export;
- installer;
- production authentication.

## Acceptance criteria

1. `uv sync --all-extras --dev` succeeds.
2. `ruff check .` succeeds.
3. `ruff format --check .` succeeds.
4. `mypy src` succeeds.
5. `pytest` succeeds.
6. The package can be imported.
7. The minimal desktop entry point starts without network access.
8. README contains local development commands.
9. `docs/progress.md` records completion of PR-001.
10. CI uses synthetic/no document fixtures only.

## Before implementation

Report:

1. understanding;
2. planned files;
3. risks;
4. test plan;
5. non-goals.

## After implementation

Report:

1. files changed;
2. design decisions;
3. commands executed;
4. exact test results;
5. manual verification;
6. remaining limitations.
