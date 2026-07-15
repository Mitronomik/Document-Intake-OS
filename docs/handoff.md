# Handoff

## Проект

Document Intake OS — локальная Windows-программа подготовки документов и Excel-заявок для трех терминалов.

## Подтверждено

- вход — отдельные фото водителей;
- разные страны и поколения документов;
- фон, наклон, несколько документов и две стороны;
- originals immutable;
- output JPEG RGB ≤1,90 MiB;
- OCR only suggests;
- operator verifies critical data;
- local database;
- TSP, Visitors and MGS exports;
- manual Konversta upload;
- no real PII in cloud development.

## Source of truth

`docs/technical-specification.md`.

## Архитектура

Modular monolith: domain, application, persistence, storage, image pipeline, recognition, terminal adapters and UI.

## Текущий этап

PRE-IMPLEMENTATION.

Не начинать с OCR. Первый полезный контур: import → immutable originals → manual image preparation → manual verification → snapshot → three Excel adapters.

## Риски

`.xls`, MGS Power Query, comments/validations, handwritten migration cards, encryption, PII logs, critical field bypass and insufficient samples.

## Следующая задача Codex

PR-001 Repository bootstrap:

- read `AGENTS.md`;
- no business logic;
- Python 3.12/PySide6 skeleton;
- uv/Ruff/mypy/pytest;
- smoke;
- no OCR/DB/network;
- update progress.

## Продолжение

Перед задачей прочитать technical specification, progress, decisions and open questions; проверить gate; сформировать один PR contract; после PR провести audit.
