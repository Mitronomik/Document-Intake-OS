# Document Intake OS

Локальное настольное приложение для Windows 11, предназначенное для приема фотографий документов водителей и транспорта, неразрушающей подготовки изображений, локального OCR, проверки оператором и формирования заявок по трем реальным Excel-шаблонам терминалов.

## Главные ограничения

1. Приложение работает офлайн после установки.
2. Реальные документы и персональные данные не передаются во внешние сервисы.
3. Первая промышленная платформа — Windows 11 x64.
4. Оригиналы не изменяются.
5. OCR создает только черновик.
6. Критические поля подтверждает оператор.
7. Подготовленный документ — JPEG RGB не более 1,90 МиБ.
8. Excel-шаблоны являются неизменяемыми внешними контрактами.
9. Прямая интеграция с «Конверстой» и браузерная автоматизация не входят в MVP.
10. Реальные документы запрещены в Git, Codex Web, CI, логах и тестовых отчетах.

## Приоритет источников

Канонический порядок источников для требований и реализации:

1. `docs/technical-specification.md`
2. `docs/decisions.md`
3. `docs/product-spec.md`
4. `docs/architecture.md`
5. `docs/domain-model.md`
6. `docs/security.md`
7. `docs/testing-strategy.md`
8. текущий PR-контракт в `docs/tasks/`

Нижестоящий документ не может переопределять вышестоящий источник. При конфликте разработка останавливается: конфликт нужно явно сообщить, а не разрешать молча.

## Документы

| Файл | Назначение |
|---|---|
| `AGENTS.md` | Правила для Codex и разработчиков |
| `docs/technical-specification.md` | Исходное техническое задание |
| `docs/project-charter.md` | Паспорт проекта |
| `docs/product-spec.md` | Продуктовые цели и границы MVP |
| `docs/architecture.md` | Архитектура приложения |
| `docs/domain-model.md` | Сущности и инварианты |
| `docs/image-pipeline.md` | Подготовка изображений |
| `docs/recognition-strategy.md` | OCR/MRZ и проверка полей |
| `docs/excel-adapters.md` | Контракты трех терминалов |
| `docs/file-storage-model.md` | Локальное хранилище |
| `docs/security.md` | Защита персональных данных |
| `docs/non-functional-requirements.md` | Нефункциональные требования |
| `docs/testing-strategy.md` | Стратегия тестирования |
| `docs/acceptance-criteria.md` | Критерии приемки |
| `docs/traceability-matrix.md` | Трассировка требований |
| `docs/implementation-plan.md` | План реализации по PR |
| `docs/roadmap.md` | Контрольные этапы |
| `docs/development-workflow.md` | Процесс разработки |
| `docs/decisions.md` | Журнал решений |
| `docs/open-questions.md` | Нерешенные вопросы |
| `docs/terminology.md` | Термины |
| `docs/progress.md` | Текущий статус |
| `docs/handoff.md` | Передача контекста |

## Предлагаемая структура кода

```text
src/document_intake/
├── domain/
├── application/
├── persistence/
├── storage/
├── image_pipeline/
├── recognition/
├── terminal_adapters/
└── ui/
```

## Безопасный старт

До OCR необходимо реализовать ручной контур: импорт, неизменяемые оригиналы, подготовка JPEG, ручная проверка, снимок заявки и три Excel-адаптера.

## Development setup

PR-001 established Python 3.12 and `uv` for dependency management. The bootstrap contains only the package skeleton and a minimal PySide6 shell; it does not implement OCR, persistence, image processing, Excel export, or business workflows. PR-002 audits and normalizes the documentation baseline; it does not start PR-003 or implement runtime features.

### Local commands

```bash
uv sync --locked --all-extras --dev
uv run python -c "import document_intake; print(document_intake.__version__)"
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -ra
uv build
```

### Run the bootstrap desktop shell

```bash
uv run document-intake
```

The module entry point delegates to the same application entry point:

```bash
uv run python -m document_intake
```

Run the automated offscreen event-loop smoke check with:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest -q tests/test_bootstrap.py::test_real_qt_event_loop_starts_and_exits
```

## Public repository security warning

The GitHub repository is temporarily public by explicit product-owner decision. This temporary public status does not change the local-only and offline runtime architecture.

While the repository remains public, do not commit terminal Excel templates, including cleaned or anonymized templates, and do not commit template-derived golden Excel files. Do not commit documents, document images, personal data, OCR results, MRZ payloads, databases, database journals, backups, logs, screenshots, local acceptance data, private fixtures, secrets, keys, passwords, certificates or tokens.

Terminal templates may be introduced only after a separate security review and only inside an approved private development contour.

### Data and fixtures

Only synthetic/no-document source-code tests are allowed in this repository and CI. Fictional scalar values are allowed only when they contain no document-derived layout and no personal data.
