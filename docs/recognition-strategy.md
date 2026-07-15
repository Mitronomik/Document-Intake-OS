# Стратегия локального распознавания

## 1. Контракт доверия

```text
Распознавание → кандидат → проверки → оператор → подтвержденное значение
```

OCR не изменяет verified data напрямую.

## 2. Источники

- visual OCR;
- MRZ;
- barcode;
- zonal/template OCR;
- related document;
- operator entry.

Кандидат хранит raw, normalized, source, confidence, region, model version, validations and conflicts.

## 3. Классификация

Результат: country, document type, side, template version, confidence and alternatives. Низкая уверенность переводит документ в `NEEDS_CLASSIFICATION`.

## 4. MRZ

- detect;
- identify format;
- recognize;
- normalize allowed symbols;
- validate check digits;
- build candidates;
- compare visual zone;
- expose conflict.

MRZ не является источником кириллического ФИО.

## 5. Barcode

Отдельный источник. Payload не попадает в обычный лог. Расхождение с визуальной зоной — conflict.

## 6. Паспорта и ID

Извлекать ФИО, number, citizenship, birth/issue/expiry dates, sex, birth place, issuer and personal number. Номер и даты подтверждаются оператором.

## 7. Миграционные карты

1. распознать форму и печатные серию/номер;
2. загрузить verified passport data;
3. предложить совпадения рукописных полей;
4. показать паспорт и область карты;
5. не принимать рукопись автоматически;
6. отдельно подтвердить даты.

## 8. Транспорт

Извлекать registration, VIN/chassis, make, model, year, type, color, masses, owner and document number.

- versions внутри страны;
- zonal OCR;
- VIN validation только вспомогательная;
- не заменять алфавит неявно;
- VIN/registration/trailer require verification.

## 9. Confidence

Не является юридической вероятностью. UI показывает высокий, средний, низкий, conflict или unavailable. Пороги конфигурируются и проверяются локально.

## 10. Конфликты

- MRZ vs visual;
- passport vs migration card;
- multiple OCR;
- verified record vs new document;
- format vs value;
- expiry vs application date.

Critical conflict blocks export.

## 11. Версионность

Engine, runtime, models, extractor, document template, preprocessing recipe and timestamp фиксируются. Повторный запуск создает новый RecognitionRun.

## 12. Офлайн

Запрещены HTTP, download-on-demand, cloud fallback, telemetry, external translation/transliteration and online error reporting.

## 13. Тестовые наборы

Git: synthetic/anonymized. Local private set: controlled access and field-level ground truth. До заявления о стабильности — минимум 30 примеров массового класса/версии.

## 14. Метрики

Exact/normalized match, character error rate, conflict rate, manual correction rate and escaped critical error rate. Главная метрика — отсутствие неподтвержденной критической ошибки в export.
