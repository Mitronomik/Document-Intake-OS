# Архитектура Document Intake OS

## 1. Принципы

1. Полностью локальная обработка после установки.
2. Неразрушающая работа с оригиналами.
3. Домен отделен от инфраструктуры.
4. OCR не изменяет подтвержденные записи.
5. Excel-шаблоны являются внешними контрактами.
6. Экспорт выполняется только из снимка заявки.
7. Сбой адаптера не повреждает БД и оригиналы.
8. MVP — простой модульный монолит для одного рабочего места; ADR-017 fixes the first MVP topology as one Windows 11 x64 workstation with one active operator session at a time.
9. Windows-зависимости изолируются в адаптерах.

## 2. Контекст

```mermaid
flowchart LR
    Operator[Оператор] --> App[Document Intake OS]
    Admin[Администратор] --> App
    App --> DB[(Локальная БД)]
    App --> FS[(Локальное хранилище)]
    App --> OCR[Локальные модели]
    App --> Excel[Терминальные шаблоны]
    App --> Export[Экспортный комплект]
    Export --> Browser[Ручная загрузка в браузере]
```

Программной связи с «Конверстой» в MVP нет.

## 2.1. MVP workstation topology

ADR-017 fixes the first MVP topology as one Windows 11 x64 workstation with one active operator session at a time. The MVP does not assume a shared multi-workstation database, network-shared application storage, concurrent application writers or cross-workstation synchronization. SQLite may be evaluated for this single-workstation topology. Filesystem ownership and locking may assume one active application session. Future local accounts are not prohibited, but authentication, passwords, inactivity timeout and recovery remain deferred to PR-031. This documentation gate does not implement SQLite, storage, users or authentication.


## 3. Слои

```mermaid
flowchart TB
    UI[Presentation]
    APP[Application]
    DOMAIN[Domain]
    PORTS[Ports]
    ADAPTERS[Infrastructure adapters]

    UI --> APP
    APP --> DOMAIN
    APP --> PORTS
    ADAPTERS -. implements .-> PORTS
    ADAPTERS --> DOMAIN
```

### Domain

Сущности, value objects, статусы, переходы, политики подтверждения, комплектность и снимки. Не импортирует PySide6, SQLite, OpenCV, OCR и Excel.

### Application

Use cases:

- создать партию;
- импортировать оригинал;
- создать области;
- подготовить документ;
- запустить OCR;
- подтвердить поля;
- связать сущности;
- создать заявку;
- проверить комплектность;
- создать snapshot;
- экспортировать;
- backup/restore.

### Persistence

Репозитории, unit of work, миграции и транзакции. Предлагается SQLite. Механизм шифрования выбирается отдельным ADR.

### Storage

Immutable originals, artifacts, snapshots, exports, checksums, atomic writes and backup.

### Image pipeline

EXIF, quality, segmentation, crop, perspective, correction, merge and JPEG compression.

### Recognition

Classification, OCR, MRZ, barcode, field extraction, confidence and source regions.

### Terminal adapters

Общий контракт, TSP, Visitors, MGS, completeness rules and golden tests.

### UI

Главная, партии, сегментация, OCR review, люди, транспорт, заявки, экспорт и администрирование.

## 4. Структура пакета

```text
src/document_intake/
├── domain/
│   ├── entities/
│   ├── value_objects/
│   ├── policies/
│   ├── enums.py
│   └── errors.py
├── application/
│   ├── commands/
│   ├── queries/
│   ├── ports/
│   └── dto/
├── persistence/
├── storage/
├── image_pipeline/
├── recognition/
├── terminal_adapters/
└── ui/
```

## 5. Основные порты

### StoragePort

- импорт оригинала;
- чтение по ID;
- хранение подготовленного артефакта;
- проверка checksum;
- atomic publish.

### RecognitionPort

Получает `RecognitionRequest`, возвращает версионный `RecognitionResult` с кандидатами, источниками, confidence и diagnostics.

### TerminalAdapter

- `validate_snapshot`;
- `export`;
- `verify_output`;
- terminal/template/rules version.

### UnitOfWork

Обеспечивает согласованность репозиториев и статусов. Файловые операции публикуются до фиксации конечного статуса.

## 6. Основной поток

```mermaid
sequenceDiagram
    actor O as Оператор
    participant UI
    participant APP as Application
    participant FS as Storage
    participant IMG as Image pipeline
    participant REC as Recognition
    participant DB as Persistence

    O->>UI: Загружает фото
    UI->>APP: ImportFiles
    APP->>FS: Копировать оригиналы
    FS-->>APP: IDs и SHA-256
    APP->>DB: Сохранить метаданные
    O->>UI: Подтверждает границы и тип
    UI->>APP: PrepareDocument
    APP->>IMG: Создать рабочий артефакт
    APP->>REC: Распознать
    REC-->>APP: FieldCandidates
    APP->>DB: Сохранить черновик
    O->>UI: Подтвердить поля
    UI->>APP: VerifyFields
    APP->>DB: Подтверждения и AuditEvent
```

## 7. Экспорт

1. загрузить текущие сущности;
2. применить терминальные правила;
3. убедиться, что critical fields подтверждены;
4. создать immutable snapshot;
5. проверить template checksum;
6. сформировать Excel во временной папке;
7. подготовить JPEG и manifest;
8. повторно открыть/проверить книгу;
9. атомарно опубликовать пакет;
10. поставить `EXPORTED`.

## 8. Транзакционность

- импорт считается успешным только после записи файла и метаданных;
- артефакт пишется во временное имя;
- `EXPORTED` ставится только после публикации;
- повторный export не меняет snapshot;
- OCR failure не меняет verified data;
- restart очищает незавершенный temp без удаления валидных файлов.

## 9. Фоновые задачи

OCR, quality analysis и export выполняются вне UI thread. Отмена не должна оставлять ложный статус. Повторный OCR создает новый run.

## 10. Платформенность

- домен не использует Windows API;
- `pathlib`;
- Excel COM только внутри TSP adapter;
- key storage за портом;
- UI и бизнес-логика не зависят от реестра Windows.

## 11. Нерешенные решения

- encryption;
- key storage;
- OCR runtime;
- migrations library;
- `.xlsx` library;
- `.xls` strategy;
- local authentication.


## PR-005 encrypted persistence candidate

Persistence now includes an encrypted SQLCipher adapter candidate for PR-005. Application ports remain independent of SQLCipher; repositories and Unit of Work are implemented by the persistence adapter. Filesystem storage remains separate. PR-005 selects an internal forward-only migration runner. DPAPI, key hierarchy and filesystem encryption remain outside PR-005. No plaintext adapter exists and final release binding/licensing approval is not claimed.

## Historical PR-006 lifecycle note

PR-005: `COMPLETED AND HUMAN ACCEPTED`. PR-006: `COMPLETED AND HUMAN ACCEPTED`. PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. Q-009: `DEFERRED`; PR-006 implements immutable stored final artifacts and no retention, deletion or secure-deletion policy. Q-017: `DEFERRED`; PR-006 storage layout is backup-neutral and PR-032 remains responsible for encrypted backup/restore. Real documents and personal data remain prohibited in Git, Codex and CI.

## Lifecycle update — PR-006 acceptance and PR-007 authorization

Verified live base SHA: `4c117ededc250d57961e2f5f4c8b4de01edf0c54`.

PR-006: `COMPLETED AND HUMAN ACCEPTED` through GitHub PR `#17`, final reviewed head `28d8b590adb7a7ae11e35f631eb9895c930b3cef`, merge commit `4c117ededc250d57961e2f5f4c8b4de01edf0c54`, merge date `2026-07-19`, final v0001 checksum `e1e1f5f6d8d675a146f3d0c538a0d544b6f8a984c301d177ee1ad86e42f2d500`, final v0002 checksum `fb953af64efd3e860960eae8ef1f4078afd0a6ec078a33594e271a9285d7db3d`, local verification `306 passed, 2 skipped on macOS`, exact-head GitHub Actions jobs passed for Python checks on Ubuntu, Python checks on Windows, PR-S001 Windows encryption spike and PR-S001 DPAPI cross-runner negative, and exact-head CI workflow run `CI #85` succeeded.

ADR numbering after repair: ADR-019 is PR-005 SQLCipher binding and raw-key staging; ADR-020 is immutable encrypted filesystem storage v1; ADR-021 is immutable PII-safe audit events. The PR #17 description historically referred to the storage decision as ADR-019 before this documentation numbering correction.

PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-007 was merged and human accepted through GitHub PR #19. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`. PR-009 is authorized, not started; PR-010 and later remain unauthorized.

Q-009: `DEFERRED`. Q-017: `DEFERRED`. Q-010: `ACCEPTED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. Existing unresolved SQLCipher legal, redistribution and release-binding questions remain unresolved. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports. The sensitive-data/private-contour gate remains open for real data.

## Lifecycle update — PR-007 acceptance and PR-008 authorization

PR-007: `COMPLETED AND HUMAN ACCEPTED`. GitHub PR: `#19`. Final reviewed head: `c6d6852ba3cf28060d8fbb76e27201cbbcaade54`. Merge commit: `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`. Merged date: `2026-07-20`. Exact-head CI: `CI #92`, successful. Migration v0003 final checksum: `e01d441c2572ca484cf5227d94f57a3cb62fa8e6e3e223eefc6852b81f6eb3c1`.

M2: `COMPLETED AND HUMAN ACCEPTED`. Gate 1: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK` for the non-UI encrypted original import and advisory duplicate-detection foundation only, governed by ADR-022, PR #21 and PR-008-D1. PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`. Do not claim Gate 2 is accepted, do not claim a physical Windows 11 smoke occurred, and do not begin PR-010 or later work.

Q-006: `DEFERRED`. Q-007: `DEFERRED`. Q-009: `DEFERRED`. Q-010: `ACCEPTED`. Q-017: `DEFERRED`. `RISK-PR005-RAWKEY-PRAGMA` remains open for installer, pilot and production release. The sensitive-data/private-contour gate remains open for real documents and real personal data. Real documents and personal data remain prohibited in Git, Codex, CI, logs and test reports.

## PR-008 implementation evidence note

PR-008 implementation records encrypted source-file import and advisory duplicate detection only. Original bytes are stored through the accepted encrypted storage port, metadata remains in SQLCipher, source paths are not persisted, decoder dependencies are pinned to `Pillow==12.3.0` and `pi-heif==1.4.0`, and no OCR, telemetry, cloud service, export, or PR-009 behavior is authorized by this change.


## PR-009 calibration lifecycle update — 2026-07-22

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE MERGE BOUNDARY.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

PR-009 implements deterministic whole-frame metrics, explicit caller-provided typed policy handling, full-resolution orientation-normalized decoding, append-only persistence, audit integration, controlled service errors, synthetic tests and a cross-platform verifier. The residual limitation blocks production activation of PR-009 quality decisions, not human acceptance or merge of the explicit-policy infrastructure. Human acceptance and merge are still pending; PR-010 and later require a separate post-merge product-owner decision.
## PR-009 human acceptance lifecycle state — 2026-07-22

PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
Production policy_id: NOT ASSIGNED.
Production policy_version: NOT ASSIGNED.
Automatic PR-009 quality-based document blocking: NOT ACTIVE.
Automatic PR-009 production RETAKE_REQUIRED enforcement: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.
PR-010 CONTRACT DEFINITION: AUTHORIZED, NOT STARTED.
PR-010 PRODUCTION IMPLEMENTATION: UNAUTHORIZED.
PR-011 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

GitHub PR: #24.
Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`.
Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.
Merge date: 2026-07-22.

This current PR-009-D4-backed section supersedes earlier historical lifecycle snapshots for current status only. It does not rewrite those historical records and does not authorize PR-010 production implementation or PR-011 and later work. FR-04 remains incomplete because geometry, document regions and later image-preparation work remain future scope.


## PR-010 geometry contract staging

ADR-024 proposes the deterministic image geometry recipe v1 boundary for future PR-010. The staged implementation must use existing application ports in `src/document_intake/application/ports/`, the accepted SQLCipher Unit of Work in `src/document_intake/persistence/unit_of_work.py`, immutable storage, image-pipeline adapters under `src/document_intake/image_pipeline/`, and PII-safe audit integration. It must not add production code in this documentation-only PR.
