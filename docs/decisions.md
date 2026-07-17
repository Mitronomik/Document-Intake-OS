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
**Partially superseded by:** ADR-016 for the three product-owner-approved,
non-sensitive terminal templates and their PII-free technical derivatives.

The repository remains public temporarily by explicit product-owner decision during bootstrap.

This temporary exception applies only to non-sensitive documentation, application bootstrap code, synthetic source-code tests that contain no document-derived data, and ordinary development configuration.

This exception does not permit real documents, document photographs, scans, document-derived screenshots, or any personal data.

ADR-014 remains fully active for real documents, personal data, real databases and journals, real exports, operational logs, backups, OCR and MRZ payloads from real documents, private acceptance datasets, secrets and credentials.

ADR-014 no longer categorically prohibits the three approved terminal templates and their PII-free technical derivatives. ADR-016 defines the content-based boundary, technical privacy inspection and transitional enforcement requirements for those artifacts.

`resources/templates` remains limited by current scanner and `.gitignore` enforcement until a separate repository-policy implementation PR is merged.

Before any unapproved template or document-derived fixture is committed, repository visibility and the approved security contour must be reviewed again and the files must be separately approved.

This decision does not change the offline and local-only runtime architecture.

The privacy gate remains open for real documents, personal data and operational sensitive data.

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
The product owner accepted PR-003 and accepted M1 Safe Repository. ADR-014 remains
accepted for real documents, personal data, operational sensitive data, private
acceptance datasets, OCR/MRZ payloads from real documents and secrets. ADR-016
partially supersedes ADR-014 only for the three product-owner-approved,
non-sensitive terminal templates and their PII-free technical derivatives.

M0 still required a requirements-lock decision because terminal-specific questions,
local-evidence questions and security-staging questions were still listed as open.
PR-004 is limited to Core Domain: entities, value objects, enums, transitions,
verification policy and snapshot invariants.

### Decision

1. PR-003 is completed and merged through GitHub PR #4 at
   `ad5782045473d3ef5eb0a097cc8f6982bab821c7`.
2. M1 Safe Repository is accepted.
3. `REPOSITORY PRIVACY BOUNDARY — ACCEPTED FOR NON-SENSITIVE CODE` is accepted.
   While the repository remains temporarily public, it may contain non-sensitive
   application source code, non-sensitive documentation, ordinary development
   configuration, fully fictional synthetic source-code tests and, after the
   transitional enforcement update, the approved PII-free terminal artifacts
   described by this ADR.
4. Approved terminal artifacts: the three approved terminal templates
   `TSPMAINFILE.xls`, `visitors_example.xlsx` and `MGSMAINFILE.xlsx` and their
   PII-free technical derivatives are permitted project artifacts after technical
   content validation confirms that they contain no real personal data,
   credentials or confidential operational data.
5. Permitted derivative classes include approved original Excel templates,
   cleaned copies, anonymized copies, empty structural copies, binary golden
   files, synthetic output workbooks, screenshots showing template structure,
   real template checksum values, extracted structural manifests,
   machine-generated mappings, manually maintained mappings, workbook structural metadata, sheet names and order, exact headers, comments, validations, named
   ranges, tables and ranges, styles, merged-cell definitions and
   external-connection metadata that contains no credentials or confidential
   paths.
6. No separate product-owner decision is required for each checksum, manifest,
   screenshot, mapping or golden file derived from one of the three approved
   templates. A new template belonging to another terminal still requires a
   separate product-owner decision.
7. Personal-data boundary: Template origin or binary format does not make a file prohibited. A file is prohibited when it contains real personal data, real
   document content, unauthorized operational data or secrets.
8. A permitted template artifact must not contain real driver or visitor records,
   real application rows, real names, real dates of birth, real passport,
   identity-document or migration-document numbers, real phone numbers, real
   registration addresses, real VINs, real vehicle or trailer registration
   numbers, real organization data when it identifies an actual application
   participant, photographs or scans of real documents, OCR output from real
   documents, MRZ payloads from real documents, authentication credentials,
   passwords, API tokens, private keys, confidential connection strings,
   confidential local or network paths or operational data not authorized for
   publication.
9. Golden-file boundary: binary golden files are permitted when generated from an
   approved terminal template, an immutable synthetic application snapshot and
   fully fictional test data. Golden files generated from a real application or
   real participant data remain prohibited. Synthetic output workbooks may contain
   only fully fictional test values.
10. Screenshot boundary: screenshots showing empty template structure or fully
    fictional data are permitted. Screenshots containing real personal data remain
    prohibited.
11. Manifest and mapping boundary: checksums, manifests and mappings derived from
    an approved template are permitted when they contain no PII or credentials.
    They do not require a separate product-owner decision. Real checksum values
    of the approved source templates are permitted and are not personal data. A
    manifest is permitted only when it contains structural metadata and no real
    personal or operational records.
12. Technical privacy inspection is required before each approved template is
    first committed. The inspection must cover visible cells, hidden sheets,
    hidden rows and columns, comments and notes, workbook and document properties,
    author and last-editor metadata, custom properties, defined names, external links, Power Query and workbook connections, cached connection results,
    embedded objects, images, macros where applicable, local usernames, local
    filesystem paths, network paths, credentials and connection strings. This is a
    technical acceptance check, not a new product decision.
13. `SENSITIVE-DATA / PRIVATE-CONTOUR GATE — OPEN` remains open for real
    documents, real personal data, operational databases, real acceptance
    datasets, real OCR/MRZ output, operational logs, real exports and backups. It
    is not a blanket gate against the approved terminal templates.
14. Product policy permits the three approved PII-free terminal templates and
    their technical derivatives. The current scanner and `.gitignore` remain
    temporarily more restrictive. Before the first permitted binary artifact is
    committed, a separate repository-policy enforcement PR must update the
    scanner, `.gitignore` and related tests.
15. The future enforcement PR is required before committing an Excel template,
    binary golden file, template screenshot, generated manifest or generated
    mapping artifact. It does not block PR-004 and blocks only the first actual
    commit of those artifact classes.
16. No template artifact is added by GATE-M0 / PR #5.
17. Terminal-specific questions may be staged to downstream gates for M0 and
    PR-004 authorization only when all of the following are recorded:

    * the question remains present;
    * it has an explicit status;
    * its required evidence or confirmation is identified;
    * its owner is identified;
    * its target PR or milestone is identified;
    * implementation depending on that answer remains blocked until evidence
      exists;
    * no placeholder terminal value is invented.
18. M0 Requirements Locked is accepted for the non-sensitive code/documentation
    contour.
19. Authorization is limited to PR-004 — Core Domain.
20. During the GATE-M0 PR, PR-004 remains blocked until this gate PR is merged and
    human acceptance confirms the recorded decision in `main`.
21. PR-005, PR-006, PR-007 and every later implementation task remain
    unauthorized.
22. Q-010 remains open and blocks PR-005 and PR-006 from storing production
    personal data until a separate accepted security ADR resolves the sequencing
    conflict between mandatory encrypted database/filesystem storage, persistence
    and filesystem implementation, and encryption currently planned later under
    PR-030.
23. No encryption technology is selected by this ADR.

### Consequences

- M0 is accepted only after this GATE-M0 PR is merged and human acceptance records
  the decision in `main`.
- PR-004 may be prepared after the gate PR is merged and accepted, but PR-004 is
  not started by this gate PR.
- PR-005 and PR-006 remain blocked pending a separate security ADR for encryption
  staging.
- Terminal adapters remain blocked by their external confirmations.
- OCR work remains blocked by local evidence requirements.
- Current repository-policy enforcement remains temporarily stricter than product
  policy for approved template artifacts until a separate enforcement PR is
  merged.
- No template artifact is added by GATE-M0 / PR #5.

### Non-decisions

ADR-016 does not decide encryption technology, retention periods,
terminal-specific values, Excel strategy, OCR technology, PR-005, PR-006, PR-007
or any later implementation task. It does not implement repository-policy scanner
or `.gitignore` changes for approved template artifacts.

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
