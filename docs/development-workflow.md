# Процесс разработки

## 1. Репозиторий

Целевой рабочий контур — приватный GitHub с protected `main` и merge только через PR. Временный публичный bootstrap допускается исключительно по ADR-014: без реальных данных, документов, терминальных шаблонов, template-derived golden files и закрытых acceptance fixtures.

## 2. Ветки

```text
pr-001-repository-bootstrap
pr-011-jpeg-compression
fix-mgs-header-preservation
```

Одна ветка — один PR.

## 3. PR-контракт для Codex

Каждая задача содержит:

- контекст;
- цель;
- точные файлы;
- входы и выходы;
- hard constraints;
- scope;
- non-goals;
- acceptance criteria;
- tests;
- manual verification;
- docs updates.

Codex не принимает security/data decisions без ADR.

## 4. До реализации

Исполнитель сообщает понимание, файлы, план, риски, тесты и вопросы. При блокере код не пишется.

## 5. Checklist

- [ ] один scope;
- [ ] нет real PII;
- [ ] нет network functionality;
- [ ] tests;
- [ ] typecheck/lint;
- [ ] docs/progress;
- [ ] manual steps;
- [ ] no unrelated refactor.

Для Excel:

- [ ] golden file;
- [ ] exact headers;
- [ ] comments/validations;
- [ ] reopen;
- [ ] Windows Excel check;
- [ ] terminal upload before release.

## 6. Review

Проверять ТЗ, незаявленные решения, boundary violations, PII, failure modes, transactionality, test quality, silent fallback, operator bypass and template damage.

## 7. Severity

- `CRITICAL`: утечка, изменение original, unverified critical export, DB corruption;
- `HIGH`: неверный Excel, потеря данных, обход правила;
- `MEDIUM`: workflow defect;
- `LOW`: косметика.

CRITICAL/HIGH блокируют merge.

## 8. Documentation update

После PR обновляются progress, decisions, architecture/domain as needed, traceability and tests.

## 9. Windows verification

Codex Web не заменяет PySide6 launch, Excel COM, `.xls`, installer, antivirus, permissions, offline, OCR speed and terminal upload.

## 10. Definition of ready

Однозначные требования, завершенные зависимости, доступные synthetic inputs, измеримые criteria and no unresolved security decision.

## 11. Definition of done

Code/tests/manual/docs/review complete, no high findings, progress updated and decisions recorded.
