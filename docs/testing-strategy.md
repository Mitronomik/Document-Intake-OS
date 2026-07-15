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

Git: fictional data, synthetic MRZ, generated documents, distortions, glare, multiple documents and sides.

Private local set: controlled access, local ground truth, no inclusion in reports or cloud tools.

## 4. CI

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

После настройки: coverage, secret scan, dependency/license audit, network guard and fixture privacy scan.

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
