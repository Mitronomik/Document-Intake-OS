# Стратегия тестирования

## 1. Цель

Доказать соблюдение offline, immutable originals, operator verification, JPEG limit, Excel contracts, reproducible export and privacy.

## 2. Уровни

- unit: domain, normalization, transitions, completeness, naming, mapping;
- integration: SQLite, storage, image pipeline, recognition adapters, snapshots, export, backup;
- golden: all three Excel adapters;
- UI: smoke, navigation, errors, export blocking;
- local acceptance: Windows 11 and real documents outside Git.

## 3. Fixtures

Committed document/data fixtures must be fictional and synthetic. Committed document fixture files may exist only under `tests/fixtures/synthetic/`. ADR-016 permits structural template fixtures, approved-template-derived golden files and synthetic output workbooks using only the three approved terminal templates and fully fictional data after technical privacy inspection and after a repository-policy enforcement PR updates scanner and `.gitignore` rules.

PR-003 adds no document fixtures. Large document test inputs must normally be generated at test runtime. Private acceptance datasets, real-document fixtures and real-application workbooks remain outside Git, Codex and CI. Repository-policy tests use temporary files only.

Private local set: controlled access, local ground truth, no inclusion in reports or cloud tools.

## 4. CI

```bash
python scripts/check_repository_policy.py
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/check_repository_policy.py
uv run pytest -ra
uv build
```

После настройки: coverage, dependency/license audit and network guard. The repository-policy scanner is a preventive tracked-file guardrail; it does not implement semantic PII detection.

## 5. Domain tests

- critical field requires actor;
- conflict blocks export;
- override requires reason;
- snapshot immutable;
- later edits do not change snapshot;
- vehicle assignment is application-scoped;
- pedestrian has no vehicle;
- visitors splits citizenship;
- multiple vehicles create rows.

## 6. Storage tests

- original bytes unchanged;
- checksum mismatch;
- exact duplicate;
- atomic publish;
- temp cleanup;
- orphan detection;
- backup manifest;
- restore version check.

## 7. Image tests

- EXIF;
- RGB;
- no metadata;
- JPEG ≤1,90 MiB;
- one/two documents;
- manual regions;
- perspective;
- side order;
- determinism;
- unreadable output blocked;
- source unchanged.

## 8. Recognition tests

- source/confidence mandatory;
- bbox stored;
- MRZ checksums;
- visual/MRZ conflict;
- versioned rerun;
- no overwrite verified;
- related passport remains separate source;
- low confidence review;
- missing model error.

## 9. Excel golden tests

Проверять sheets, exact headers, values, cell types, formats, comments, validations, tables, merged cells, styles, reserved columns, external connections and reopen.

### TSP

`ТСП`, row 2, 25 columns, T–Y empty, `.xls` if confirmed.

### Visitors

`Данные`, `Types`, 24 columns, lists/comments, one citizenship, pedestrian, multiple vehicles.

### MGS

`Данные`, 30 columns, A–Y active, Z–AD empty, exact spaces and safe external connection.

## 10. Offline test

With network disabled: launch, import, prepare, recognize, verify, export, backup and restore. Unexpected outbound connection fails test.

## 11. Security tests

No secrets/PII in logs, formula injection, template checksum, timeout, permission checks, encrypted backup, temp cleanup, corrupted DB/file and source replacement.

## 12. Регрессия

Каждый дефект получает тест. Изменение image recipe, extractor, normalization, mapping or snapshot format требует version bump and targeted regression.

## 13. Acceptance protocol

Фиксировать build, OS, Excel version, models, template hashes, sample count, results, defects and release decision without PII.


## PR-005 persistence testing

PR-005 testing covers Windows SQLCipher integration, migration checksum/history validation, repository round trips and projection-tamper rejection, Unit of Work lifecycle/cleanup behavior, ordinary SQLite rejection, wrong-key behavior, deterministic multi-page ciphertext tamper and truncation, key/PII leak checks and database-trigger snapshot immutability. The real `sqlcipher3==0.6.2` integration remains active on Windows AMD64 and skips only off that target; a macOS skip is not Windows acceptance.

## PR-006 lifecycle note

PR-005: `COMPLETED AND HUMAN ACCEPTED`. PR-006: `AUTHORIZED AND IN REVIEW, NOT ACCEPTED`. PR-007 and later: `UNAUTHORIZED`. Gate 1: `NOT ACCEPTED`. M2: `NOT COMPLETED`. Q-009: `DEFERRED`; PR-006 implements immutable stored final artifacts and no retention, deletion or secure-deletion policy. Q-017: `DEFERRED`; PR-006 storage layout is backup-neutral and PR-032 remains responsible for encrypted backup/restore. Real documents and personal data remain prohibited in Git, Codex and CI.
