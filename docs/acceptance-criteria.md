# Критерии приемки MVP

## Общие

- установка на Windows 11 x64;
- основной процесс без сети;
- нет скрытых network calls;
- ошибки не повреждают originals/verified data;
- CI не требует real PII.

## Импорт

- файл копируется byte-identical;
- сохраняются metadata and SHA-256;
- exact duplicate обнаруживается;
- visual duplicate only warns.

## Изображения

- оператор создает/исправляет одну или несколько областей;
- стороны упорядочиваются;
- один логический документ создает один JPEG;
- output JPEG RGB, no EXIF, ≤1,90 MiB;
- readability failure blocks export;
- compression never chains from prior JPEG.

## OCR

- candidate has source and confidence;
- field opens source region;
- MRZ checks digits;
- MRZ/visual mismatch is conflict;
- critical fields require verification;
- rerun does not overwrite verified;
- handwriting requires operator.

## База

- people, documents, vehicles, batches, applications and audit persist;
- Cyrillic/Latin names separate;
- identifiers are strings;
- vehicle is not permanently tied to driver;
- snapshot remains unchanged.

## Заявка

- terminal selected before rules;
- current batch/all database modes;
- completeness before snapshot;
- snapshot immutable and hashed;
- export uses snapshot only.

## TSP

- sheet `ТСП`;
- row 2;
- exact 25 columns;
- separate text series/number;
- T–Y empty;
- `Лист1` unchanged;
- `.xls` preserved if required.

## Visitors

- sheets `Данные` and `Types`;
- comments/validations preserved;
- one citizenship;
- pedestrian R–X empty;
- multiple vehicles create rows;
- sample row safely removed.

## MGS

- sheet `Данные`;
- A–Y populated, Z–AD empty;
- exact headers including spaces;
- external refresh cannot overwrite;
- table expansion preserves formatting.

## Export

- Excel, driver folders, JPEG, manifest and warnings;
- Windows-safe names;
- workbook opens without repair;
- failure does not set `EXPORTED`;
- repeated export is reproducible.

## Security

- no full PII in logs;
- template checksum;
- encrypted/tested backup;
- operator cannot admin override;
- no real data in Git/CI.

## Release gate

Пилот запрещен, если любой Excel не прошел terminal upload, critical field can bypass review, network traffic exists, original can be overwritten, backup cannot restore or any critical defect remains.
