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

PR-005: `COMPLETED AND HUMAN ACCEPTED`. PR-006: `COMPLETED AND HUMAN ACCEPTED`. PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `IMPLEMENTED AND IN REVIEW, NOT ACCEPTED`; PR-009 and later: `UNAUTHORIZED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. Q-009: `DEFERRED`; PR-006 implements immutable stored final artifacts and no retention, deletion or secure-deletion policy. Q-017: `DEFERRED`; PR-006 storage layout is backup-neutral and PR-032 remains responsible for encrypted backup/restore. Real documents and personal data remain prohibited in Git, Codex and CI.

## Lifecycle update — PR-006 acceptance and PR-007 authorization

Verified live base SHA: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.

PR-006: `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`, final reviewed head `28d8b590adb7a7ae11e35f631eb9895c930b3cef`, merge commit `4c117ededc250d57961e2f5f4c8b4de01edf0c54`, merge date `2026-07-19`, final v0001 checksum `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`, final v0002 checksum `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`, local verification `306 passed, 2 skipped on macOS`, exact-head GitHub Actions jobs passed for Python checks on Ubuntu, Python checks on Windows, PR-S001 Windows encryption spike and PR-S001 DPAPI cross-runner negative, and exact-head CI workflow run `CI #85` succeeded.

ADR numbering after repair: ADR-019 is PR-005 SQLCipher binding and raw-key staging; ADR-020 is immutable encrypted filesystem storage v1; ADR-021 is immutable PII-safe audit events. The PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction.

PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-007 was merged and human accepted through GitHub PR #19. PR-008: `IMPLEMENTED AND IN REVIEW, NOT ACCEPTED`; PR-009 and later: `UNAUTHORIZED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. PR-009 and later remain unauthorized.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.

## Lifecycle update — PR-007 acceptance and PR-008 authorization

PR-007: `COMPLETED AND HUMAN ACCEPTED`. GitHub PR: `#19`. Final reviewed head: `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`. Merge commit: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`. Merged date: `2026-07-20`. Exact-head CI: `CI #92`, successful. Migration v0003 final checksum: `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`.

M2: `COMPLETED AND HUMAN ACCEPTED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `IMPLEMENTED AND IN REVIEW, NOT ACCEPTED` for the non-UI encrypted original import and advisory duplicate-detection foundation only, governed by ADR-022 and `docs/tasks/PR-008-file-import-duplicate-detection.md`. PR-009 and later: `UNAUTHORIZED`. Do not describe PR-008 as completed or accepted. Do not begin PR-009 or later work.

Q-006: `DEFERRED`. Q-007: `DEFERRED`. Q-009: `DEFERRED`. Q-010: `ACCEPTED`. Q-017: `DEFERRED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. The sensitive-data/private-contour gate remains open for real documents and real personal data. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports.

## PR-008 implementation evidence note

PR-008 implementation records encrypted source-file import and advisory duplicate detection only. Original bytes are stored through the accepted encrypted storage port, metadata remains in SQLCipher, source paths are not persisted, decoder dependencies are pinned to `Pillow==12.3.0` and `pi-heif==1.4.0`, and no OCR, telemetry, cloud service, export, or PR-009 behavior is authorized by this change.
