# Открытые вопросы

Ответ становится требованием только после явного решения, записи ADR и обновления документов/тестов.

## Excel и терминалы

### Q-001

Официальное название терминала `visitors_example.xlsx`.

### Q-002

Обязан ли TSP принимать именно `.xls`?

### Q-003

Максимальное количество водителей для каждого терминала. Пометка «не более 10» пока не формализована.

### Q-004

Нужно ли вставлять изображения в Excel или достаточно папки рядом? Текущая гипотеза: достаточно папки.

### Q-005

Матрица обязательных документов по терминалу, гражданству, типу пропуска и транспорту.

## Изображения

### Q-006

Правило склейки: vertical/horizontal, порядок, поля and terminal differences.

### Q-007

Минимальные readability/resolution thresholds после пилота.

## Эксплуатация и безопасность

### Q-008

Один ПК, несколько пользователей на одном ПК или несколько ПК?

### Q-009

Срок хранения originals, artifacts, snapshots, exports, backups and audit.

### Q-010

Encryption and key storage.

### Q-011

Local accounts, password policy, timeout and recovery.

## OCR

### Q-012

Обезличенные примеры водительских удостоверений по приоритетным странам.

### Q-013

Типы и примеры work permits/patents.

### Q-014

Частотность country/type/version для приоритизации OCR.

## Эксплуатация

### Q-015

Будет ли Microsoft Excel установлен на всех рабочих ПК?

### Q-016

Куда сохранять export: local folder, network disk or removable drive?

### Q-017

Backup destination, owner, frequency and external copy.

### Q-018

Offline update process for application and models.

## Future

### Q-019

Нужна ли macOS сразу после Windows MVP?

### Q-020

Существует ли официальный согласованный API «Конверсты»? До подтверждения integration не проектируется.
