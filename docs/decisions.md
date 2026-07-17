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

## ADR-018 — Encryption Staging and Windows Key Protection

**Status:** PROPOSED
**Date:** 2026-07-17
**Proposal reference for:** Q-010

### Context

1. The first MVP is one Windows 11 x64 workstation with one active operator session.
2. The application stores passports, identity information, vehicle identifiers, document images and application data.
3. Database and filesystem storage must be encrypted.
4. The raw encryption key must not be stored beside the database or files.
5. PR-005 and PR-006 are blocked because encryption was previously scheduled only in PR-030.
6. Implementing plaintext persistence first and adding encryption later creates unacceptable migration and accidental-production-use risk.
7. PR-004 contains no persistence and does not resolve Q-010.

This ADR is a proposal for review only. It does not accept ADR-018, does not resolve Q-010, does not authorize PR-S001, PR-005, PR-006, PR-007 or later work, and does not implement encryption, database, storage or backup code.

### Recommended proposal for review

#### Encryption-first invariant

No production-capable database or document storage may write personal data to disk in plaintext. There must be no supported production mode that creates an unencrypted SQLite database, stores original documents as plaintext files, stores prepared document artifacts as plaintext files, silently falls back to plaintext when encryption is unavailable, or continues application startup after key-protection failure. Failure to initialize encryption must fail closed.

#### Application master key

The proposed protected-storage initialization generates a cryptographically random application master key locally. The key is never hardcoded, never derived directly from a username, predictable device identifier or default password, and the raw key is never stored in source code, configuration, environment variables, logs or database rows. Only a protected key blob is stored. The protected key blob is kept separate from encrypted database and storage content, has an explicit format version, and supports later rotation and re-wrapping without domain-model changes. This proposal does not implement key generation.

#### Windows local key protection

For the first MVP local key wrapper, the proposal uses Windows DPAPI with current-user scope. The application master key is wrapped through Windows DPAPI. The raw master key is held in memory only for the shortest practical duration. `LOCAL_MACHINE` scope is not the default because it broadens decryption access to other users of the same workstation. DPAPI failure blocks access to protected data. The protected key blob is not itself treated as sufficient for backup portability. Future local-user architecture may require key re-wrapping or migration. No Windows account or authentication implementation is added by this gate, and no DPAPI calls are implemented.

#### Database encryption

SQLite remains the logical persistence engine for the single-workstation MVP. Every production-capable database file must use full-database authenticated encryption through SQLCipher or a separately validated equivalent. No plaintext SQLite database may be migrated into production use without an explicit encrypted migration procedure. Wrong-key access must fail. Tampered or corrupt encrypted databases must not be treated as valid. Database keys must come from protected application key material and must not appear in SQL logs, exception messages or diagnostics. This ADR does not choose a final Python binding, package version or SQLCipher edition, and requires a separate Windows x64 feasibility and packaging spike before PR-005 authorization.

#### File encryption

Originals and derived artifacts use application-level authenticated encryption, such as AES-256-GCM or an equivalently reviewed construction. Every encrypted object has a unique nonce, and nonce reuse under the same key is prohibited. Authenticated metadata includes at least storage format version, entity/artifact identifier, artifact kind, and plaintext length or another integrity-bound size field. Encrypted object names and directories must not expose personal data. Ciphertext replacement under an existing immutable artifact ID is prohibited. Decrypted bytes must reproduce the original bytes exactly. Authentication failure blocks reading. There is no silent plaintext fallback and no PII in encryption errors or logs. This proposal does not implement encryption and does not add a cryptography dependency.

#### BitLocker position

BitLocker or Windows Device Encryption is recommended as defense in depth. Volume encryption is not accepted as the only application security control because deployment state may vary between workstations, configuration may be outside the application's control, external or backup media require separate protection, and application data must remain protected independently of accidental volume-policy changes. A future installer or preflight check may verify volume-encryption status, but this proposal does not implement that check.

#### Temporary plaintext

Plaintext temporary files are forbidden by default. Decryption should use memory or restricted short-lived files only when a later image/Excel integration proves that an external library requires a path. Any future temporary-file exception requires a dedicated threat analysis, restricted permissions, non-PII filenames, cleanup on success and handled failure, startup cleanup of abandoned files, and tests confirming cleanup. Secure deletion guarantees are not claimed for SSD storage. This proposal does not implement temporary-file handling.

#### Backup and recovery boundary

A DPAPI-protected local key blob normally belongs to the current Windows user and workstation. Copying only the DPAPI blob is not a portable backup strategy. Future encrypted backup/restore must use a separately designed recovery wrapping mechanism. The recovery wrapper must protect the application master key or a backup-specific key. The recovery secret must never be stored inside the same backup archive in usable plaintext. Backup destination, recovery ownership and recovery ceremony remain unresolved under Q-017. PR-032 remains responsible for backup/restore implementation. This proposal does not select a recovery password policy and does not implement backup.

### Compared options

#### Option A — Plaintext persistence until PR-030

**Decision recommendation:** REJECT

Rejected because it violates the production encryption requirement, creates migration risk, permits accidental real-data use before encryption, and changes persistence and storage formats late in the roadmap.

#### Option B — BitLocker-only protection

**Decision recommendation:** REJECT AS SOLE CONTROL

Rejected as the sole control because deployment and media protection vary outside application control. BitLocker remains recommended defense in depth.

#### Option C — Encryption-first application architecture

**Decision recommendation:** PREFERRED

Preferred proposal: DPAPI-protected application master key, encrypted SQLite through SQLCipher or a validated equivalent, application-level authenticated file encryption, fail-closed behavior, and later independent backup/recovery wrapping. Option C is preferred but not accepted; it remains a proposal until human acceptance.

### Required feasibility spike before PR-005

Proposed task: PR-S001 — Windows encryption feasibility and packaging spike. PR-S001 is proposed, not authorized, and is not implemented by GATE-S1.

Scope proposed for PR-S001:

1. use only fully fictional synthetic data;
2. run on Windows 11 x64;
3. verify Python 3.12 compatibility;
4. compare supported SQLCipher/equivalent packaging options;
5. document license and attribution obligations;
6. verify offline installation and bundling;
7. prove an encrypted database cannot be read as ordinary SQLite;
8. test correct-key, wrong-key, tamper and corruption behavior;
9. prototype DPAPI current-user wrapping with non-production synthetic key material;
10. prototype application-level authenticated file encryption;
11. verify unique nonce generation and authentication-failure behavior;
12. measure startup/read/write overhead;
13. confirm no key or synthetic plaintext appears in logs;
14. produce no production storage API;
15. introduce no real documents or PII.

Required sequence: GATE-S1 proposal → product-owner review → ADR-018 acceptance → PR-S001 → PR-S001 review and acceptance → PR-005 authorization → PR-006 authorization only after its own task review. PR-005 and PR-006 remain unauthorized in this proposal.

### Non-decisions

ADR-018 does not decide the final SQLCipher edition or distribution, final Python database binding, exact cryptography package and version, FIPS requirement, backup recovery password policy, backup destination, retention and deletion periods, secure deletion guarantees, local application users, authentication, idle timeout, administrator recovery ceremony, key rotation UI, multi-workstation key sharing or macOS keychain implementation.
