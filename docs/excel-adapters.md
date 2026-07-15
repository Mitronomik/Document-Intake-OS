# Excel-адаптеры трех терминалов

## 1. Общие правила

Реальные шаблоны:

- `TSPMAINFILE.xls`;
- `visitors_example.xlsx`;
- `MGSMAINFILE.xlsx`.

Они являются внешними контрактами. Нельзя без отдельного решения менять имена листов, точные заголовки, опечатки, комментарии, validations, форматирование, порядок столбцов, служебные листы и формат файла.

Адаптер обязан:

1. проверить template checksum/version;
2. работать с копией;
3. очищать только разрешенную data area;
4. заполнять данные из snapshot;
5. хранить идентификаторы как строки;
6. записывать даты настоящими Excel dates;
7. сохранять структуру и оформление;
8. повторно открыть и проверить результат;
9. возвращать diagnostics and checksums.

## 2. TSP

Файл: `TSPMAINFILE.xls`  
Рабочий лист: `ТСП`  
Первая строка данных: 2.

| Колонка | Точный заголовок | Каноническое поле |
|---|---|---|
| A | Фамилия | `person.last_name_cyr` |
| B | Имя | `person.first_name_cyr` |
| C | Отчество | `person.patronymic_cyr` |
| D | Должность | `employment.position` |
| E | Телефон | `person.phone` |
| F | ДР | `person.birth_date` |
| G | М.Р. | `person.birth_place` |
| H | Гражданство | `person.citizenship` |
| I | Паспорт серия | `identity.series` |
| J | Паспорт номер | `identity.number` |
| K | Кем выдан | `identity.issuer` |
| L | дата выдачи | `identity.issue_date` |
| M | Место жительства | `person.registration_address` |
| N | Марка авто | `tractor.make` |
| O | гос номер | `tractor.registration_number` |
| P | п/п | `trailer.registration_number` |
| Q | цвет | `tractor.color` |
| R | собственик авто | `tractor.owner` |
| S | собственик пп | `trailer.owner` |
| T–Y | Столбец1–Столбец6 | резерв |

Правила:

- опечатки в R/S сохраняются;
- серия и номер раздельно и как текст;
- T–Y пустые;
- `Лист1` не изменяется;
- обязательность `.xls` требует подтверждения;
- если `.xls` обязателен, Windows Excel automation изолируется в TSP adapter.

## 3. Visitors

Файл: `visitors_example.xlsx`  
Листы: `Данные`, `Types`.

| Колонка | Точный заголовок | Каноническое поле |
|---|---|---|
| A | Фамилия | `person.last_name_cyr` |
| B | Имя | `person.first_name_cyr` |
| C | Отчество | `person.patronymic_cyr` |
| D | Дата рождения | `person.birth_date` |
| E | Место рождения | `person.birth_place` |
| F | Гражданство | `person.citizenship` |
| G | Вид документа | `identity.export_document_type` |
| H | Серия и номер документа | `identity.full_number` |
| I | Дата выдачи | `identity.issue_date` |
| J | Дата окончания | `identity.expiry_date` |
| K | Код подразделения | `identity.division_code` |
| L | Кем выдан | `identity.issuer` |
| M | Адрес регистрации | `person.registration_address` |
| N | Мобильный телефон | `person.phone` |
| O | Наименование организации | `employment.organization_name` |
| P | ИНН организации | `employment.organization_inn` |
| Q | Должность | `employment.position` |
| R | Гос. рег. знак транспортного средства (ТС) | `tractor.registration_number` |
| S | Тип ТС | `tractor.vehicle_type` |
| T | Номер прицепа | `trailer.registration_number` |
| U | Марка ТС | `tractor.make` |
| V | Модель ТС | `tractor.model` |
| W | Цвет ТС | `tractor.color` |
| X | Собственник ТС | `tractor.owner` |

Специальные правила:

- одно гражданство в одной заявке;
- смешанный выбор автоматически разбивается;
- для иностранца ожидается значение `Национальный паспорт` из списка;
- F и S используют значения `Types`;
- ИНН допустим только при организации;
- пешеходный пропуск: R–X пустые;
- несколько ТС: отдельные строки;
- примерная строка удаляется только из data area;
- `Types`, comments and validations сохраняются.

Официальное название терминала требует подтверждения.

## 4. MGS

Файл: `MGSMAINFILE.xlsx`  
Рабочий лист: `Данные`.

| Колонка | Точный заголовок | Каноническое поле |
|---|---|---|
| A | Фамилия | `person.last_name_cyr` |
| B | Имя␠ | `person.first_name_cyr` |
| C | Отчество | `person.patronymic_cyr` |
| D | Дата рождения | `person.birth_date` |
| E | Место рождения | `person.birth_place` |
| F | Гражданство | `person.citizenship` |
| G | Вид документа | `identity.export_document_type` |
| H | Серия и номер документа | `identity.full_number` |
| I | Дата выдачи | `identity.issue_date` |
| J | Дата окончания | `identity.expiry_date` |
| K | Код подразделения | `identity.division_code` |
| L | Кем выдан | `identity.issuer` |
| M | Адрес регистрации | `person.registration_address` |
| N | Мобильный телефон | `person.phone` |
| O | Наименование организации | `employment.organization_name` |
| P | ИНН организации | `employment.organization_inn` |
| Q | Должность | `employment.position` |
| R | № А/М␠ | `tractor.registration_number` |
| S | Тип ТС | `tractor.vehicle_type` |
| T | № П/П | `trailer.registration_number` |
| U | Марка ТС | `tractor.make` |
| V | Модель ТС | `tractor.model` |
| W | Цвет ТС | `tractor.color` |
| X | Собственник ТС | `tractor.owner` |
| Y | Собственник П/П | `trailer.owner` |
| Z–AD | Столбец1–Столбец5 | резерв |

`␠` — значимый завершающий пробел.

Правила:

- A–Y активны;
- Z–AD пустые;
- таблица расширяется с сохранением оформления;
- Power Query/external connection не должен перезаписывать export;
- исходный template не изменяется.

## 5. Template manifest

Для каждой версии хранить terminal code, template version, filename, SHA-256, workbook format, required sheets, data sheet, header row, first data row, adapter version and rules version.

## 6. Golden tests

Проверять:

- sheet names/order;
- exact headers and spaces;
- values and cell types;
- date formats;
- leading zeros;
- comments;
- validations;
- tables/ranges;
- styles;
- merged cells;
- reserved columns;
- external connections;
- reopen without repair.

Бинарное совпадение `.xlsx` не обязательно, структурное — обязательно.

## 7. Ошибки

`TEMPLATE_NOT_FOUND`, `TEMPLATE_CHECKSUM_MISMATCH`, `UNSUPPORTED_TEMPLATE_VERSION`, `SHEET_MISSING`, `HEADER_MISMATCH`, `VALIDATION_VALUE_INVALID`, `SNAPSHOT_INVALID`, `EXTERNAL_CONNECTION_UNSAFE`, `XLS_RUNTIME_UNAVAILABLE`, `WORKBOOK_SAVE_FAILED`, `WORKBOOK_REOPEN_FAILED`.

## 8. Ручная приемка

Для каждого терминала: synthetic export → Microsoft Excel Windows 11 → отсутствие repair → проверка comments/lists → реальная тестовая загрузка → локальный протокол без PII.
