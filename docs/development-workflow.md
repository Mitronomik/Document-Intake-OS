# Процесс разработки

## 1. Репозиторий

Целевой рабочий контур — приватный GitHub с protected `main` и merge только через PR. Временный публичный bootstrap допускается по ADR-014/ADR-016: без реальных данных, документов, закрытых acceptance fixtures, PII or secrets. ADR-016 permits the three approved PII-free terminal templates and their technical derivatives after technical privacy inspection and repository-policy enforcement updates.

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

Before submitting a change, run:

```bash
python scripts/check_repository_policy.py
```

Policy failures block merge. Policy rules must not be bypassed through renamed files. Product policy permits the three approved PII-free terminal templates and technical derivatives, but the current scanner and `.gitignore` remain temporarily stricter until a separate enforcement PR updates approved paths and tests. Exceptions affecting privacy or data boundaries require an accepted ADR. Developers must inspect `git status` and `git diff --cached` before pushing. Real acceptance files remain outside the repository.

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
