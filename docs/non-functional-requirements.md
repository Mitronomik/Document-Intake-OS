# Нефункциональные требования

## NFR-01 Офлайн

Основной поток, модели, база и export работают без интернета. Silent cloud fallback запрещен.

## NFR-02 Платформа

Windows 11 x64. Ежедневная работа без administrator privileges. DPI scaling, Russian locale, Unicode and Windows-safe paths.

## NFR-03 Производительность

Ориентир:

- OCR типового документа 5–20 секунд;
- пакет 20 фото до 5 минут без ручной проверки;
- UI остается отзывчивым;
- export типовой заявки до 30 секунд без учета длительных Excel COM операций.

Подтверждается на целевом ПК.

## NFR-04 Надежность

Immutable originals, transactions, atomic files, crash recovery, idempotent re-export, integrity checks and no false `EXPORTED`.

## NFR-05 Конфиденциальность

Local only, encrypted storage, masked logs, no telemetry, roles, encrypted backup and secure temp.

## NFR-06 Поддерживаемость

Typed modular code, migrations, versioned adapters/models/templates, small PR, tests and docs.

## NFR-07 Удобство

Mouse/keyboard, zoom, field-to-region navigation, clear statuses, actionable errors, batch/all filter and minimal filesystem work.

## NFR-08 Excel

Exact templates, reopen without repair, proper dates, string identifiers, comments, validations and terminal acceptance.

## NFR-09 Размер

Ориентир: installer 1–2 ГБ, installed 2–4 ГБ без большой LLM/VLM. Не жесткий gate до выбора моделей.

## NFR-10 Доступность

Backup, restore, manifest, version compatibility and clear corruption errors.

## NFR-11 Локализация

Russian UI, Unicode data, separate Cyrillic/Latin names, canonical internal dates.

## NFR-12 Диагностика

Typed error codes, correlation ID, component versions and local technical report without document contents.
