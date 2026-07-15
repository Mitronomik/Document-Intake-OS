# Модель локального файлового хранилища

## 1. Структура

```text
DocumentIntakeData/
├── database/
├── originals/
├── artifacts/
├── snapshots/
├── exports/
├── templates/
├── models/
├── backups/
├── temp/
└── logs/
```

## 2. Originals

```text
originals/<year>/<month>/<batch-id>/<source-file-id>/
├── content.bin
└── metadata.json
```

Требования:

- байты неизменяемы;
- имя водителя не используется;
- metadata содержит исходное имя, media type, размер, SHA-256;
- приложение не заменяет файл под существующим ID.

## 3. Artifacts

```text
artifacts/<document-id>/<recipe-version>/
├── preview.jpg
├── prepared.jpg
└── recipe.json
```

Recipe содержит source IDs, regions, transforms, composition, compression, pipeline version and result checksum.

## 4. Snapshots

```text
snapshots/<snapshot-id>/
├── snapshot.json
├── snapshot.sha256
└── document-map.json
```

Snapshot содержит только данные, необходимые для воспроизводимого экспорта.

## 5. Exports

```text
exports/2026-07-15_MGS_APP-000527/
├── Заявка_MGS_APP-000527.xlsx
├── manifest.json
├── warnings.txt
└── drivers/
    └── 01_Фамилия_Имя/
        ├── 01_passport.jpg
        └── 02_migration_card.jpg
```

Человекочитаемые имена допустимы только в экспортном пакете.

## 6. Имена

Внутренние файлы используют UUID и не содержат ФИО, паспорт, VIN или госномер.

Экспортные имена:

- очищаются от Windows-символов;
- ограничиваются по длине;
- не включают номер паспорта;
- получают числовой порядок;
- получают suffix при совпадении.

## 7. Atomic publish

1. временная папка;
2. запись;
3. закрытие;
4. checksum/structure verification;
5. атомарное переименование;
6. фиксация статуса в БД.

## 8. Templates

```text
templates/<terminal>/<version>/
├── original.xls[x]
└── manifest.yaml
```

Шаблон read-only, versioned, checksum-verified. Старые версии сохраняются.

## 9. Models

OCR-модели хранятся по engine/version, поставляются офлайн и имеют checksums и сведения о лицензии.

## 10. Temp

Ограниченные права, отсутствие PII в имени, очистка после завершения и после crash recovery.

## 11. Logs

Разрешены IDs, action/error codes, duration, component version. Запрещены OCR text, MRZ, фото, адрес, телефон, полные номера.

## 12. Удаление

Политика хранения не подтверждена. Автоматическое окончательное удаление до решения не реализуется.

## 13. Целостность

Административная проверка контролирует originals, artifacts, snapshots, template hashes, export manifests and backups, не выводя PII.
