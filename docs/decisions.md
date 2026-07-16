# Журнал решений

Статусы: `ACCEPTED`, `PROPOSED`, `SUPERSEDED`, `REJECTED`.

## ADR-001 — Полностью локальная обработка

**Статус:** ACCEPTED

OCR, изображения, база и export работают локально. Cloud OCR/API запрещены.

## ADR-002 — Windows 11 x64 первым

**Статус:** ACCEPTED

macOS учитывается архитектурно, но не входит в первый промышленный MVP.

## ADR-003 — OCR только черновик

**Статус:** ACCEPTED

OCR создает кандидаты. Critical fields подтверждаются пользователем.

## ADR-004 — Immutable originals

**Статус:** ACCEPTED

Все преобразования создают производные artifacts.

## ADR-005 — JPEG 1,90 МиБ

**Статус:** ACCEPTED

Output JPEG RGB ≤1,90 MiB. Потеря читаемости блокирует результат.

## ADR-006 — Excel templates as contracts

**Статус:** ACCEPTED

Точная структура сохраняется; adapter changes require golden tests and template checksum.

## ADR-007 — Ручная подача в «Конверсту»

**Статус:** ACCEPTED

API/Selenium/Playwright не входят в MVP.

## ADR-008 — Export from snapshot

**Статус:** ACCEPTED

Export читает immutable ApplicationSnapshot.

## ADR-009 — Модульный монолит

**Статус:** ACCEPTED

Одно desktop application с ports/adapters; без microservices.

## ADR-010 — SQLite

**Статус:** PROPOSED

Подходит для одного рабочего места. Окончательно после решения о рабочих местах и encryption.

## ADR-011 — Python 3.12 + PySide6

**Статус:** PROPOSED

Указано в ТЗ. Перед bootstrap проверить совместимость и лицензии зависимостей.

## ADR-012 — TSP `.xls`

**Статус:** PROPOSED

Если `.xls` обязателен, использовать Windows Excel automation внутри TSP adapter.

## ADR-013 — Реальные данные вне cloud dev

**Статус:** ACCEPTED

Реальные документы запрещены в ChatGPT/Codex/Git/CI. Приемка выполняется локально.

## ADR-014 — Temporary public repository during bootstrap

**Status:** ACCEPTED
**Date:** 2026-07-15
**Partially superseded by:** ADR-016 for approved non-sensitive terminal templates and template-derived technical artifacts.

The repository remains public temporarily by explicit product-owner decision during bootstrap.

This temporary exception applies only to non-sensitive documentation, application bootstrap code, synthetic source-code tests that contain no document-derived data, and ordinary development configuration.

This exception does not permit real documents, document photographs, scans, document-derived screenshots, or any personal data.

This exception does not permit unapproved terminal templates. ADR-016 supersedes this blanket prohibition for the three product-owner-approved non-sensitive terminal templates and their approved technical derivatives.

This exception does not permit unapproved template-derived golden Excel files. ADR-016 supersedes this blanket prohibition for approved synthetic golden files derived only from the three approved terminal templates.

This exception does not permit PII, databases, database journals, logs, backups, OCR outputs, MRZ payloads, private fixtures, local acceptance fixtures, secrets, keys, passwords, certificates or tokens.

Until a separate repository-policy implementation PR is merged, `resources/templates` must remain without terminal files while the repository scanner and `.gitignore` remain more restrictive than the product policy.

Before any unapproved template or document-derived fixture is committed, repository visibility and the approved security contour must be reviewed again and the files must be separately approved.

This decision does not change the offline and local-only runtime architecture.

The privacy gate remains open.

## ADR-015 — M0/M1 repository-safety sequencing

**Status:** ACCEPTED
**Date:** 2026-07-16

### Context

PR-002 discovered a lifecycle conflict: the implementation plan says the next major stage starts only after the applicable gate is accepted, the roadmap groups PR-001 through PR-003 under M1 Safe Repository, M0 remains open because terminal questions and the privacy gate remain unresolved, and no accepted decision previously allowed repository-safety work to continue while M0 was open.

### Decision

1. PR-001 through PR-003 form a narrow repository-safety workstream.
2. Repository-safety work under PR-001 through PR-003 may proceed while M0 remains open.
3. PR-003 is authorized by this decision.
4. PR-003 is limited to:

   * CI integration;
   * tracked-file privacy policy;
   * high-confidence secret detection;
   * private-fixture path protection;
   * terminal-template protection;
   * tracked-image location and size protection;
   * fixture-policy documentation and tests.
5. M0 remains open.
6. The privacy gate remains open.
7. Terminal and security questions remain unresolved.
8. This decision does not approve real documents, personal data, document-derived fixtures, terminal templates or template-derived golden files for the public repository.
9. This decision does not authorize domain, persistence, storage, image pipeline, UI workflow, OCR or Excel implementation.
10. This decision does not authorize PR-004 or any later implementation task.
11. M2 must not begin until:

    * M0 is accepted;
    * M1 repository-safety work is accepted.
12. Completion of PR-003 does not imply completion of M0.
13. Completion of PR-003 does not automatically authorize M2.
14. Q-001 through Q-020 remain unresolved.
15. Public-repository restrictions from ADR-014 remain unchanged.

### Rationale

Repository guardrails reduce privacy risk and do not depend on unresolved terminal mappings, real documents or Excel templates. The work is limited to repository safety and CI enforcement, so it can proceed without making product-runtime or data-architecture decisions.

### Consequences

- PR-003 is authorized.
- M0 remains open.
- The privacy gate remains open.
- M2 remains blocked.
- Public-repository restrictions remain unchanged.
- No product runtime implementation is authorized.
- After merge, PR-003 still requires human acceptance before M1 can be considered complete.

### Non-decisions

ADR-015 does not decide:

- Q-001 through Q-020;
- repository privacy timing;
- encryption;
- retention;
- workstations;
- authentication;
- secure deletion;
- terminal limits;
- terminal mappings;
- `.xls` handling;
- OCR technology;
- database implementation;
- filesystem storage implementation.

## ADR-016 — M0 Gate, Privacy Boundary and PR-004 Authorization

**Status:** ACCEPTED
**Date:** 2026-07-16

### Context

GitHub PR #4 merged PR-003 at commit `ad5782045473d3ef5eb0a097cc8f6982bab821c7`.
The product owner accepted PR-003 and accepted M1 Safe Repository. ADR-014 remains in
force for personal data, real documents, operational databases, logs, backups,
OCR/MRZ outputs, private acceptance datasets, credentials and secrets. ADR-016
partially supersedes ADR-014 only for the three product-owner-approved
non-sensitive terminal templates and approved template-derived technical
artifacts.

M0 still required a requirements-lock decision because terminal-specific questions,
local-evidence questions and security-staging questions were still listed as open.
PR-004 is limited to Core Domain: entities, value objects, enums, transitions,
verification policy and snapshot invariants. It does not require real documents,
databases, OCR payloads, private acceptance fixtures or any newly permitted
terminal-template artifact.

### Decision

1. PR-003 is completed and merged through GitHub PR #4 at
   `ad5782045473d3ef5eb0a097cc8f6982bab821c7`.
2. M1 Safe Repository is accepted.
3. `REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE` is accepted.
   While the repository remains temporarily public, it may contain non-sensitive
   application source code, non-sensitive documentation, ordinary development
   configuration, fully fictional synthetic source-code tests that contain no
   document-derived data, and the approved non-sensitive terminal-template
   artifacts described by this ADR.
4. `SENSITIVE-DATA / PRIVATE-CONTOUR GATE — OPEN` remains open for real documents,
   personal data, real operational databases, real exports, logs, backups,
   OCR/MRZ outputs from real documents, private acceptance datasets, credentials
   and secrets.
5. The three real terminal Excel templates are classified by the product owner as
   non-sensitive project contract files. The product owner confirms that these
   template files do not contain personal data; do not contain real application rows; do not
   contain document images; do not contain authentication credentials, private keys or secret tokens. The approved templates do not contain document images and are
   authorized for use and storage in the project repository.
6. Permitted template artifacts: the three product-owner-approved terminal
   templates and their non-sensitive technical derivatives may be stored in the
   repository. Permitted derivatives include:

   * cleaned or anonymized template copies;
   * binary golden files;
   * screenshots;
   * checksums;
   * manifests;
   * machine-generated mappings;
   * manually maintained mappings;
   * structural metadata;
   * synthetic output workbooks.
7. Structural metadata includes workbook format, sheet names, headers, comments,
   validations, named ranges, tables, styles, merged cells, external connections
   and adapter mappings.
8. Data restriction: no permitted template artifact may contain real personal
   data, real application records, real document images, OCR/MRZ payloads from real documents, secrets or
   credentials. Template artifacts must not contain secrets or credentials.
9. Golden-file rule: binary golden files may be committed when they are produced
   from an approved terminal template, an immutable synthetic application
   snapshot and fully fictional test data. Golden files produced from real application data remain prohibited.
10. Mapping rule: no separate product-owner decision is required for each mapping
    artifact derived from an already approved template. A mapping artifact must not contain real application data or secret values.
11. Screenshots: template screenshots are permitted when they contain only template
    structure and fictional or empty cells. Screenshots containing personal data remain prohibited.
12. Checksums and manifests: real checksum values and extracted structural
    manifests for approved templates are permitted. A manifest must not contain credentials, personal data or external-system secrets.
13. This decision does not authorize arbitrary new terminal templates from other
    terminals. A new source terminal template outside the currently approved
    three-template set requires a separate product-owner decision.
14. Transitional enforcement state: the product policy permits approved
    non-sensitive terminal templates and template-derived technical artifacts. The
    current repository scanner and `.gitignore` remain intentionally more
    restrictive until a separate repository-policy implementation PR is reviewed
    and merged.
15. Before the first actual Excel template, screenshot, golden file, manifest or
    generated mapping is committed, a separate repository-policy implementation PR
    must update `scripts/check_repository_policy.py`, `tests/test_repository_policy.py`,
    `.gitignore`, `resources/templates/README.md`, `docs/security.md`,
    `docs/testing-strategy.md` and `docs/development-workflow.md`.
16. That future enforcement PR must define approved template paths, approved
    derivative paths, golden-file locations, screenshot locations, manifest and
    mapping locations, provenance rules, synthetic-data-only golden-file rules and
    continued blocking of real documents, PII, databases, logs, backups and
    secrets.
17. The future enforcement PR does not block PR-004. It blocks only the first
    commit of the newly permitted template artifacts.
18. No template artifact is added by GATE-M0.
19. Terminal-specific questions may be staged to downstream gates for M0 and
    PR-004 authorization only when all of the following are recorded:

    * the question remains present;
    * it has an explicit status;
    * its required evidence or confirmation is identified;
    * its owner is identified;
    * its target PR or milestone is identified;
    * implementation depending on that answer remains blocked until evidence
      exists;
    * no placeholder terminal value is invented.
20. M0 Requirements Locked is accepted for the non-sensitive code/documentation
    contour.
21. Authorization is limited to PR-004 — Core Domain.
22. During the GATE-M0 PR, PR-004 remains blocked until this gate PR is merged and
    human acceptance confirms the recorded decision in `main`.
23. PR-005, PR-006, PR-007 and every later implementation task remain
    unauthorized.
24. Q-010 remains open and blocks PR-005 and PR-006 from storing production
    personal data until a separate accepted security ADR resolves the sequencing
    conflict between mandatory encrypted database/filesystem storage, persistence
    and filesystem implementation, and encryption currently planned later under
    PR-030.
25. No encryption technology is selected by this ADR.

### Consequences

- M0 is accepted only after this GATE-M0 PR is merged and human acceptance records
  the decision in `main`.
- PR-004 may be prepared after the gate PR is merged and accepted, but PR-004 is
  not started by this gate PR.
- PR-005 and PR-006 remain blocked pending a separate security ADR for encryption
  staging.
- Terminal adapters remain blocked by their external confirmations.
- OCR work remains blocked by local evidence requirements.
- The sensitive-data/private-contour gate remains open for real documents and
  personal data; it is not a blanket prohibition on the three approved
  non-sensitive terminal templates and their approved technical derivatives.
- No template artifact is added by GATE-M0.

### Non-decisions

ADR-016 does not decide encryption technology, retention periods,
terminal-specific values, Excel strategy, OCR technology, PR-005, PR-006, PR-007
or any later implementation task. It does not implement the repository-policy
changes required before newly permitted template artifacts can be committed.

## ADR-017 — MVP Workstation Topology

**Status:** ACCEPTED
**Date:** 2026-07-16

### Context

The architecture states that the MVP is a simple modular monolith for one
workstation, while the technical specification still asked whether the first
version needs one computer or multiple operators in a local network. ADR-010
remains proposed until workstation and encryption decisions are made.

### Decision

The first MVP topology is one Windows 11 x64 workstation with one active operator session at a time.

Consequences for the first MVP:

- no shared multi-workstation database;
- no network-shared application storage;
- no concurrent application writers;
- no cross-workstation synchronization;
- SQLite may be evaluated for this single-workstation topology;
- filesystem ownership and locking may assume one active application session;
- future local accounts are not prohibited;
- authentication, passwords, inactivity timeout and recovery remain deferred to
  PR-031;
- this decision does not implement SQLite, storage, users or authentication.

### Consequences

- Q-008 is accepted by ADR-017.
- PR-004 may use the single-workstation, one-active-session assumption for domain
  invariants that need a topology boundary.
- Persistence, filesystem storage, local users and authentication remain future
  implementation tasks and are not implemented by this ADR.

### Non-decisions

ADR-017 does not select encryption technology, implement SQLite, implement
filesystem storage, implement local accounts, implement authentication or
authorize shared multi-workstation data.
