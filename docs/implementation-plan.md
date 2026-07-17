# План реализации по независимым PR

## Общие правила

- один PR решает одну понятную задачу;
- каждый PR содержит тесты, документацию и manual verification;
- следующий крупный этап начинается после приемки gate;
- ADR-015 created a narrow exception for PR-001 through PR-003 repository-safety work while M0 remained open;
- PR-003 is completed and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`;
- M1 Safe Repository is accepted;
- GATE-M0 is in review: M0 decision approved, not yet recorded in `main`;
- PR-004 remains blocked until the GATE-M0 PR is merged and human acceptance confirms the decision in `main`;
- PR-005 and later tasks remain unauthorized;
- реальные документы не используются в Codex Web;
- OCR начинается только после готовности ручного контура.

## Этап 0. Репозиторий

### PR-001 — Repository bootstrap

**Цель:** создать Python 3.12/PySide6 каркас.

Scope:

- `pyproject.toml`;
- uv;
- package layout;
- minimal desktop entry point;
- Ruff, mypy, pytest;
- README;
- smoke test.

Non-goals: OCR, БД, Excel и бизнес-логика.

Acceptance: sync, lint, typecheck, tests, запуск окна без сетевых запросов.

### PR-002 — Documentation baseline

Scope:

- audit the existing documentation package;
- normalize source priority;
- verify required files;
- verify relative Markdown links;
- update lifecycle and handoff state;
- add automated documentation-baseline tests;
- preserve unresolved questions;
- introduce no new requirements or decisions.

### PR-003 — CI and privacy guardrails

**Status:** COMPLETED and merged through GitHub PR #4 at `ad5782045473d3ef5eb0a097cc8f6982bab821c7`; accepted by the product owner.

Scope:

- repository-policy scanner using tracked files from `git ls-files -z`;
- high-confidence secret signatures with safe diagnostics;
- private-fixture protection;
- terminal-template protection, permitting only `resources/templates/README.md` as a policy marker under `resources/templates/`;
- tracked-image location and 1,992,294-byte synthetic-image size policy;
- CI integration on Ubuntu and Windows;
- fixture-policy documentation;
- automated tests.

Non-goals: domain, persistence, storage, image pipeline, UI workflow, OCR, Excel implementation, PR-004, M2, real documents, terminal templates and fixtures.

## Этап 1. Домен и хранение

### PR-004 — Core domain

Entities, value objects, enums, transitions, verification policy and snapshot invariants.

### PR-005 — SQLite persistence

Unauthorized by GATE-M0. Schema, migrations, repositories, unit of work and transaction tests remain blocked until a separate accepted security ADR resolves Q-010 encryption staging. Конкретное шифрование не реализовать до ADR.

### PR-006 — Immutable filesystem storage

Unauthorized by GATE-M0. Original import, SHA-256, metadata, atomic writes and integrity tests remain blocked until a separate accepted security ADR resolves Q-010 encryption staging for production personal data.

### PR-007 — Audit events

Unauthorized by GATE-M0. Masked audit model, critical operations and PII-safe tests remain a later task.

**Gate 1:** domain/storage приняты.

## Этап 2. Изображения

### PR-008 — File import and duplicate detection

JPG/PNG/HEIC, metadata, SHA-256 and perceptual duplicate warning.

### PR-009 — Orientation and quality assessment

EXIF, dimensions, blur/glare/contrast diagnostics.

### PR-010 — Geometry tools

Rotate, crop, perspective, recipe and manual parameters.

### PR-011 — JPEG ≤1.90 MiB

RGB, metadata removal, iterative compression, readability and deterministic tests.

### PR-012 — Multiple documents per image

Regions, manual boundaries and two-document workflow.

### PR-013 — Merge document sides

Order, vertical/horizontal setting, one logical JPEG and retained originals.

**Gate 2:** ручная подготовка JPEG работает без OCR.

## Этап 3. Ручной рабочий контур

### PR-014 — Upload batches UI

Create batch, drag/drop, import statuses and background tasks.

### PR-015 — Manual classification

Country, document type, side, template version and correction audit.

### PR-016 — Person and vehicle cards

Use-case CRUD, duplicate suggestions, separate tractor/trailer.

### PR-017 — Verification workflow

Candidates, operator entry, critical field statuses and audit.

### PR-018 — Applications and snapshots

Terminal selection, assignments, completeness port, immutable snapshot and current batch/all database.

**Gate 3:** оператор может вручную подготовить снимок заявки.

## Этап 4. Excel

### PR-019 — Terminal adapter contract

Common interface, template manifest, validation report, typed errors and synthetic snapshot.

### PR-020 — Visitors adapter

Exact mapping, Types, comments/validations, citizenship split, pedestrian, multiple vehicles and golden tests.

### PR-021 — MGS adapter

A–Y, Z–AD, exact spaces, table expansion, external connection safety and golden tests.

### PR-022 — TSP adapter

`.xls` decision, sheet `ТСП`, row 2, reserved columns, Windows Excel integration if required and local tests.

### PR-023 — Export package

Excel, driver folders, JPEGs, manifest, warnings, atomic publish and repeat export.

**Gate 4:** все три книги прошли реальную загрузку.

## Этап 5. OCR

### PR-024 — Recognition port and local runtime

Versioned adapter, candidates, diagnostics and no verified mutation.

### PR-025 — MRZ parser

Formats, normalization, check digits and conflict model.

### PR-026 — Passport/ID extraction

Visual fields, MRZ comparison, source regions and priority countries.

### PR-027 — Vehicle extraction

Template versions, zones and VIN/registration candidates.

### PR-028 — Confidence and review UI

BBox navigation, statuses, conflict comparison and rerun version.

### PR-029 — Migration card assistance

Printed fields, passport suggestions, mandatory human review and dates/stamps.

**Gate 5:** OCR пилот принят на локальном наборе.

## Этап 6. Промышленная доводка

### PR-030 — Encryption

Только после ADR: DB, storage, key handling, migration and recovery.

### PR-031 — Local users

Operator/admin, login, timeout, permissions and override.

### PR-032 — Backup and restore

Encrypted archive, manifest, integrity and restore test.

### PR-033 — Windows installer

Runtime, models, templates, offline install and versioning.

### PR-034 — Offline and security tests

Network block, PII logs, template tampering, formula injection and fault injection.

### PR-035 — Pilot fixes

Только подтвержденные пилотом дефекты, regression tests and release candidate.

## Оценка

Рабочий Windows MVP: 8–12 недель. Стабильная версия после пилота: 3–5 месяцев. Оценка пересматривается после Gate 1 и Gate 4.
