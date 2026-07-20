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

**Status:** ACCEPTED
**Accepted date:** 2026-07-17
**Accepted by:** Product owner
**Acceptance basis:** Option C — Encryption-first application architecture
**GATE-S1 merge commit:** fb9984036f7df0c34badfc3a93f6faec1bc5d38e
**Date:** 2026-07-17
**Decision reference for:** Q-010

### Context

1. The first MVP is one Windows 11 x64 workstation with one active operator session.
2. The application stores passports, identity information, vehicle identifiers, document images and application data.
3. Database and filesystem storage must be encrypted.
4. The raw encryption key must not be stored beside the database or files.
5. PR-005 and PR-006 are blocked because encryption was previously scheduled only in PR-030.
6. Implementing plaintext persistence first and adding encryption later creates unacceptable migration and accidental-production-use risk.
7. PR-004 contains no persistence and does not resolve Q-010.

ADR-018 is accepted as the architecture direction. Acceptance authorizes preparation and execution of PR-S001 only. Acceptance does not authorize production persistence, storage or encryption implementation, does not authorize PR-005, PR-006, PR-007 or later work, and does not implement encryption, database, storage or backup code.

### Threat model and protection boundary

The accepted architecture is intended to protect data at rest against offline theft or copying of the workstation disk, access by another Windows user, copying the database or storage without the required Windows profile, accidental disclosure of individual encrypted files or later encrypted backups, and tampering detectable by authenticated encryption or database integrity checks.

The accepted architecture does not fully protect against malicious code running under the same Windows user credentials, a compromised or malicious Windows administrator, an already unlocked operator session, process-memory inspection, screen capture or operator-authorized plaintext access, or compromised application binaries. DPAPI Current User allows applications running under the same Windows credentials to request unprotection. DPAPI is not claimed to provide application-to-application isolation.

### Key hierarchy and purpose separation

The DPAPI-protected root/master key must not be used directly as the database encryption key, a file AEAD key, or a backup recovery key. Database, file-storage and future backup purposes require independent key material, and purpose/domain separation is mandatory. A compromise of one purpose key must not automatically expose other purpose keys. Key and envelope formats must be versioned. Exact derivation or wrapping mechanics are selected only after PR-S001 evidence, and GATE-S1 does not select the final KDF, provider or Python package.

PR-S001 must compare independent purpose-derived keys with wrapped per-database and per-object data-encryption keys. No key may be derived from predictable identifiers alone. Python code must not claim guaranteed secure zeroization of immutable byte or string objects. Implementations must minimize key copies and key lifetime in memory.

### Accepted decision

#### Encryption-first invariant

No production-capable database or document storage may write personal data to disk in plaintext. There must be no supported production mode that creates an unencrypted SQLite database, stores original documents as plaintext files, stores prepared document artifacts as plaintext files, silently falls back to plaintext when encryption is unavailable, or continues application startup after key-protection failure. Failure to initialize encryption must fail closed.

#### Application master key

The accepted protected-storage direction requires generating a cryptographically random application master key locally. The key is never hardcoded, never derived directly from a username, predictable device identifier or default password, and the raw key is never stored in source code, configuration, environment variables, logs or database rows. Only a protected key blob is stored. The protected key blob is kept separate from encrypted database and storage content, has an explicit format version, and supports later rotation and re-wrapping without domain-model changes. This acceptance does not implement key generation.

#### Windows local key protection

For the first MVP local key wrapper, the accepted direction uses Windows DPAPI with current-user scope. The application master key is wrapped through Windows DPAPI. The raw master key is held in memory only for the shortest practical duration. `LOCAL_MACHINE` scope is not the default because it broadens decryption access to other users of the same workstation. DPAPI failure blocks access to protected data. The protected key blob is not itself treated as sufficient for backup portability. Future local-user architecture may require key re-wrapping or migration. No Windows account or authentication implementation is added by this acceptance, and no DPAPI calls are implemented.

#### Database encryption

SQLite remains the logical persistence engine for the single-workstation MVP. Every production-capable database file must use full-database encryption with integrity authentication through SQLCipher or a separately validated equivalent. No plaintext SQLite database may be migrated into production use without an explicit encrypted migration procedure. Wrong-key access must fail. Tampered or corrupt encrypted databases must not be treated as valid. Database keys must come from protected application key material and must not appear in SQL logs, exception messages or diagnostics. This ADR does not choose a final Python binding, package version or SQLCipher edition, and requires a separate Windows x64 feasibility and packaging spike before PR-005 authorization.

#### File encryption

Originals and derived artifacts use application-level authenticated encryption, such as AES-256-GCM or an equivalently reviewed construction. Every encrypted object has a unique nonce, and nonce reuse under the same key is prohibited. Authenticated metadata includes at least storage format version, entity/artifact identifier, artifact kind, and plaintext length or another integrity-bound size field. Encrypted object names and directories must not expose personal data. Ciphertext replacement under an existing immutable artifact ID is prohibited. Decrypted bytes must reproduce the original bytes exactly. Authentication failure blocks reading. There is no silent plaintext fallback and no PII in encryption errors or logs. This acceptance does not implement encryption and does not add a cryptography dependency.

#### Encrypted object envelope

File storage must use a versioned encrypted object envelope defining at least format magic/version, algorithm identifier, key version or key identifier, nonce/IV, ciphertext, authentication tag, and a canonical authenticated metadata schema. Authenticated metadata must bind at least artifact ID, artifact kind, plaintext length, storage format version, and expected content checksum or another accepted rollback/replay control.

Nonce reuse under one key is prohibited. Truncated or partially written objects must fail authentication. Object writes use encrypted temporary output and atomic replacement. Plaintext temporary files remain forbidden by default. Authentication errors contain no PII. Exact algorithm, package and chunking format remain for PR-S001 evidence.

An authentication tag proves integrity and authenticity under the relevant key, but it does not by itself prove that the object is the latest accepted version. A checksum, object version or generation stored only inside the encrypted envelope is not sufficient to detect replacement of the entire envelope with an older valid envelope. Envelope-contained metadata remains authenticated, but it is not treated as its own independent rollback anchor.

Object-level rollback detection requires an authoritative expected-state record outside the replaceable encrypted object. That authoritative record must bind at least artifact ID, expected object generation or immutable version, expected plaintext hash, ciphertext hash or another independently validated object digest, key version, and storage format version. The authoritative record may later reside in the encrypted database or an immutable application snapshot.

Reading an encrypted object must fail closed when its artifact ID differs, its generation/version differs, its expected digest differs, its key version is not accepted, or its envelope metadata differs from the authoritative record. Replacing the current object with a prior valid envelope while leaving the authoritative record unchanged must be detected. The exact authoritative-record schema and transaction boundary remain for PR-S001 and later persistence/storage design.

ADR-018 does not claim detection of a coordinated rollback of the complete encrypted database, the complete encrypted storage, and every local authoritative-state copy. Coordinated full-system rollback detection would require a separately accepted external or monotonic trust anchor and remains a non-decision unless later required. No TPM counter, remote service, online timestamp or other external mechanism is selected; the application remains fully offline.

#### BitLocker position

BitLocker or Windows Device Encryption is recommended as defense in depth. Volume encryption is not accepted as the only application security control because deployment state may vary between workstations, configuration may be outside the application's control, external or backup media require separate protection, and application data must remain protected independently of accidental volume-policy changes. A future installer or preflight check may verify volume-encryption status, but this acceptance does not implement that check.

#### Temporary plaintext

Plaintext temporary files are forbidden by default. Decryption should use memory or restricted short-lived files only when a later image/Excel integration proves that an external library requires a path. Any future temporary-file exception requires a dedicated threat analysis, restricted permissions, non-PII filenames, cleanup on success and handled failure, startup cleanup of abandoned files, and tests confirming cleanup. Secure deletion guarantees are not claimed for SSD storage. This acceptance does not implement temporary-file handling.

#### Backup and recovery boundary

A DPAPI-protected local key blob normally belongs to the current Windows user and workstation. Copying only the DPAPI blob is not a portable backup strategy. Future encrypted backup/restore must use a separately designed recovery wrapping mechanism. The recovery wrapper must protect the application master key or a backup-specific key. The recovery secret must never be stored inside the same backup archive in usable plaintext. Backup destination, recovery ownership and recovery ceremony remain unresolved under Q-017. PR-032 remains responsible for backup/restore implementation. This acceptance does not select a recovery password policy and does not implement backup.

### Compared options

#### Option A — Plaintext persistence until PR-030

**Final state:** REJECTED

Rejected because it violates the production encryption requirement, creates migration risk, permits accidental real-data use before encryption, and changes persistence and storage formats late in the roadmap.

#### Option B — BitLocker-only protection

**Final state:** REJECTED AS SOLE CONTROL

Rejected as the sole control because deployment and media protection vary outside application control. BitLocker remains recommended defense in depth.

#### Option C — Encryption-first application architecture

**Final state:** ACCEPTED

Accepted direction: DPAPI Current User-protected application root/master-key wrapping, encrypted SQLite through SQLCipher or a validated equivalent, application-level authenticated file encryption, fail-closed behavior, mandatory purpose separation, versioned encrypted-object envelopes, independent object rollback anchors, and later independent backup/recovery wrapping.

### Required feasibility spike before PR-005

Authorized task: PR-S001 — Windows encryption feasibility and packaging spike. PR-S001 is authorized, not started, and is not implemented by this acceptance PR.

Authorized PR-S001 scope:

1. use only fully fictional synthetic data;
2. run on Windows 11 x64;
3. verify Python 3.12 compatibility;
4. compare supported SQLCipher/equivalent packaging options while keeping the final binding, edition and package version undecided;
5. test offline Windows 11 x64 packaging;
6. document license and attribution obligations;
7. verify SQLCipher encryption is active for every production connection;
8. treat an inactive encryption status as fail-closed;
9. verify HMAC/integrity authentication remains enabled;
10. verify the database cannot be opened through ordinary SQLite;
11. verify wrong-key behavior;
12. verify tamper and corruption behavior;
13. verify WAL and rollback-journal page content is encrypted;
14. ensure file-based SQLite temporary stores cannot contain plaintext;
15. verify required build/runtime temporary-store configuration;
16. disable or strictly constrain SQLCipher internal logging;
17. prove key material does not enter SQL logs, exceptions or diagnostics;
18. compare raw-key APIs or binding-safe keying mechanisms against SQL-string key injection;
19. verify that no security feature is silently disabled for performance;
20. prototype DPAPI current-user wrapping with non-production synthetic key material;
21. use Current User scope, not Local Machine scope by default;
22. use the non-interactive DPAPI path and do not rely on prompt-based DPAPI behavior;
23. validate same-user/same-machine behavior and failure after Windows-profile/key loss;
24. apply restrictive Windows ACLs to the protected key blob and application data directories;
25. confirm no DPAPI description, error or diagnostic contains key material or PII;
26. record that the protected blob alone is not a portable recovery mechanism;
27. compare independent purpose-derived keys with wrapped per-database/per-object data-encryption keys;
28. prototype application-level authenticated file encryption and the versioned encrypted object envelope;
29. verify unique nonce generation, rollback/replay detection and authentication-failure behavior;
30. verify a current encrypted object opens when its independent authoritative record matches;
31. verify bit modification fails authentication;
32. verify truncation fails authentication;
33. verify replacing the current envelope with an older valid envelope fails because the external expected generation/digest does not match;
34. verify modifying envelope metadata without a valid authentication tag fails;
35. verify copying an envelope to another artifact ID fails;
36. verify key-version mismatch fails closed;
37. verify failure diagnostics contain no artifact content, document identifiers or PII;
38. define an explicit crash-consistency design for the authoritative database record and encrypted-object publication;
39. document whether atomicity requires database transaction first, object publication first, staged pending state or recovery reconciliation;
40. avoid claiming coordinated full-database-plus-storage rollback detection unless an independent external anchor is actually demonstrated;
41. measure startup/read/write overhead;
42. confirm no key or synthetic plaintext appears in logs;
43. produce no production storage API;
44. introduce no real documents or PII.

Required sequence after acceptance: PR-S001 preparation, implementation, review and human acceptance → explicit PR-005 authorization if granted → PR-006 authorization only after its own task review. PR-005 and PR-006 remain unauthorized. PR-007 and later work remain unauthorized.

### Non-decisions

ADR-018 does not decide the final SQLCipher edition or distribution, final Python database binding, exact package version, exact cryptography package, exact KDF or wrapping construction, exact per-object key strategy, exact encrypted-envelope byte format, exact chunking format, exact crash-consistency transaction design, FIPS requirement, backup recovery password policy, backup destination, retention and deletion periods, external or monotonic full-system rollback anchor, local user authentication, idle timeout, administrator recovery ceremony, secure deletion guarantees, key rotation UI, multi-workstation key sharing or macOS keychain implementation.


## ADR-019 — PR-005 SQLCipher binding and raw-key staging

Status: ACCEPTED

Date: 2026-07-19

Decision owner: Product owner

Decision:

- use sqlcipher3==0.6.2 for PR-005 development;
- accept RISK-PR005-RAWKEY-PRAGMA for PR-005 development;
- require a 32-byte database key through DatabaseKeyProvider;
- prohibit plaintext fallback;
- do not implement DPAPI or key hierarchy in PR-005;
- keep legal/redistribution approval unresolved;
- require binding-safe API resolution or separate product-owner risk acceptance before installer, pilot or production release.

Non-decisions:

- no final release-package approval;
- no final license disposition;
- no final master-key implementation;
- no filesystem encryption;
- no backup recovery;
- no authentication;
- no installer design.

## ADR-020 — Immutable encrypted filesystem storage v1

Status: `ACCEPTED`.

Decision: PR-006 uses `cryptography==49.0.0`, AES-256-GCM, a storage-specific `StorageKeyProvider`, envelope format v1 with `DIOSOBJ1` magic, immutable UUID-derived object paths, no update/delete API, object-first/database-second publication, migration v0002 `stored_artifacts`, read-time expected-state verification and read-only reconciliation. Coordinated rollback of the full encrypted database plus full encrypted filesystem is not claimed as detected.


## ADR-021 — Immutable PII-safe audit events

Status: `ACCEPTED`.

Date: 2026-07-19

Decision owner: Product owner

Decision: PR-007 is authorized, not started, as the next production-code pull request only after this lifecycle pull request is merged into `main`. PR-007 must implement immutable, append-only, locally persisted, PII-safe audit events in encrypted SQLCipher persistence. Audit events are security-relevant and business-critical records, not application logs, diagnostic journals or exception journals.

Binding contract:

- audit events record actor reference, UTC occurrence time, controlled action code, controlled subject type, subject identifier, optional field key, safe before and after summaries, optional controlled reason code and optional correlation identifier;
- PR-007 must not implement users, passwords, authentication, sessions, permissions, local account persistence or operator profile data; it reuses existing immutable `ActorRef` with `actor_id: EntityId` and `kind: ActorKind`;
- audit events must not store operator display names, email addresses, logins, usernames, free-text identities, workstation usernames or Windows profile names; PR-031 remains responsible for local users and authentication;
- `AuditEvent` must be a frozen, slotted immutable domain object with exactly `event_id`, `occurred_at`, `actor`, `action_code`, `subject_type`, `subject_id`, `field_key`, `before`, `after`, `reason_code` and `correlation_id`;
- timestamps must be timezone-aware, normalized to UTC during construction and persisted canonically; naive datetimes must be rejected;
- no arbitrary metadata dictionary, free-text message, filesystem path, original filename, document bytes, OCR payload, MRZ payload, exception trace, secret/key material, raw SQL or direct PII-bearing actor identity may be stored; `repr()` must be safe;
- `AuditReasonCode` is an immutable value object whose canonical value is 1 to 64 characters and matches `^[A-Z][A-Z0-9_]{0,63}$`; reason codes are code-defined machine values, not operator comments;
- `AuditAction` initially contains exactly `ENTITY_CREATED`, `ENTITY_UPDATED`, `FIELD_CORRECTED`, `FIELD_VERIFIED`, `SNAPSHOT_CREATED`, `ARTIFACT_REGISTERED` and `EXPORT_CREATED`;
- `AuditSubjectType` initially contains exactly `PERSON`, `IDENTITY_DOCUMENT`, `MIGRATION_DOCUMENT`, `VEHICLE`, `DOCUMENT`, `FIELD_CANDIDATE`, `APPLICATION`, `APPLICATION_SNAPSHOT` and `STORED_ARTIFACT`;
- deletion, retention, purge, backup and restore actions remain prohibited while Q-009 and Q-017 are deferred;
- `AuditValueClassification` contains exactly `ABSENT`, `NON_SENSITIVE` and `SENSITIVE_REDACTED`; immutable `AuditValueSummary` contains `classification`, `display_value` and `was_present`;
- valid summaries are only: `ABSENT` with `was_present is False` and no display value; `NON_SENSITIVE` with `was_present is True` and a controlled display value 1 to 64 characters matching `^[A-Z0-9][A-Z0-9_.:-]{0,63}$`; `SENSITIVE_REDACTED` with `was_present is True` and no display value;
- sensitive before/after values must not store raw values, hashes, salted hashes, prefixes, suffixes, last digits, masked substrings, reconstructive lengths or normalization results;
- PR-007 advances FR-12 and FR-13 but does not complete FR-12; `FieldCandidate`, `VerifiedField` and persisted business entities remain sources of operational values; PR-017 remains responsible for correction and verification workflow integration and `FIELD_CORRECTED`/`FIELD_VERIFIED` emission;
- PR-007 creates forward-only migration `v0003_audit_events.py`, version `3`, name `audit_events_pr007`, keeps v0001/v0002 byte-for-byte unchanged, increases `CURRENT_SCHEMA_VERSION` to `3`, appends v0003 to the migration tuple and stores audit events in encrypted SQLCipher using canonical payload plus projection-integrity validation;
- database-level immutable-row protection must reject UPDATE, DELETE, `INSERT OR REPLACE` replacement and `REPLACE INTO` replacement; no update, replace, delete or purge repository methods are exposed;
- the repository API is exactly `add`, `get`, `list_for_subject` and `list_by_correlation`; list ordering is deterministic ascending by `occurred_at` then `event_id`; no `list_all`, arbitrary SQL filters, caller-supplied sorting or pagination is authorized in PR-007;
- the Unit of Work gains `audit_events: AuditEventRepository` using the same connection and transaction and no independent commits or connections;
- low-level repositories must not auto-write audit events or infer actor, action, reason or business meaning; future application services explicitly add audit events through the same Unit of Work;
- failures fail closed with stable sanitized errors and never expose PII, keys, SQL, database paths, payloads or raw driver messages;
- tests and the verifier may use only fictional synthetic values and must prove forbidden synthetic PII markers do not appear in payloads, projections, repr output, exceptions, verification reports or console output.

Non-decisions: no retention periods, deletion rules, backup destinations, restore procedures, local authentication, users, permissions, UI, OCR, MRZ, barcode, Excel, terminal adapters, upload batches, source-file workflows, document-region workflows, telemetry, cloud services, automatic audit emission or complete FR-12 workflow integration.

## ADR-022 — Encrypted original import and advisory duplicate detection

Status: `ACCEPTED`

Date: 2026-07-20

Decision owner: Product owner

Decision: PR-008 is authorized, not started, as the next production-code pull request only after GitHub PR #20 is merged into `main`. PR-008 implements the non-UI application and persistence foundation for upload batches, encrypted original import and advisory duplicate detection. PR-008 does not implement the upload-batch UI; that remains PR-014. PR-009 and later remain unauthorized.

### Implementation-base decision

The lifecycle preparation base for this documentation-and-contract PR is `71dfd7fa31bd67c9f9fa54cc9057684486e842ad`. The PR-008 implementation base is not that SHA; it must be the eventual exact merge commit of GitHub PR #20. Do not invent that future merge SHA. PR-008 must not branch from `71dfd7fa31bd67c9f9fa54cc9057684486e842ad` after PR #20 is merged, the PR-008 implementation prompt must use the actual PR #20 merge commit as its exact base, and PR-008 may not start from an earlier commit.

### Exact enums, value objects and entities

PR-008 defines exactly these enums:

- `UploadBatchStatus`: `NEW`, `PROCESSING`, `NEEDS_REVIEW`, `READY`, `ARCHIVED`. PR-008 creates batches only in `NEW` and does not implement later workflow transitions.
- `SourceMediaType`: `JPEG`, `PNG`, `HEIF`.
- `ImportWarningCode`: `EXACT_DUPLICATE`, `PERCEPTUAL_SIMILARITY`, `EXTENSION_CONTENT_MISMATCH`.
- `SourceImportErrorCode`: `BATCH_NOT_FOUND`, `SOURCE_READ_FAILED`, `SOURCE_BASENAME_INVALID`, `UNSUPPORTED_EXTENSION`, `UNSUPPORTED_FORMAT`, `DECODE_FAILED`, `STORAGE_PUBLICATION_FAILED`, `PERSISTENCE_FAILED`.

Errors remain sanitized and must not contain source names, paths, image bytes, hashes, SQL, database paths, storage paths, keys or raw exceptions.

PR-008 defines immutable frozen/slotted value objects: `BatchNumber` with canonical string length 1-64 and regex `^[A-Z0-9][A-Z0-9_-]{0,63}$`; `SourceBasename` as exact basename only, length 1-255 Unicode code points, rejecting `/`, `\`, NUL, U+0000-U+001F, U+007F, `.`, `..`, trimming, truncation and silent normalization, with `repr()` showing only `<redacted>`; `Sha256Digest` as exactly 64 lowercase hexadecimal characters computed over unchanged original bytes; and `PerceptualHash` with fields `algorithm_id`, `algorithm_version`, `bit_width`, `hex_value`, exact values `DHASH64`, `1`, `64`, and exactly 16 lowercase hexadecimal characters. Perceptual hash values must not appear in logs, errors, audit events, verifier output or duplicate warnings.

`UploadBatch` is immutable, frozen and slotted with exactly `id: EntityId`, `number: BatchNumber`, `created_at: datetime`, `created_by: ActorRef`, `status: UploadBatchStatus`, and `source_file_ids: tuple[EntityId, ...]`. `created_at` is timezone-aware and normalized to UTC, `created_by` is explicit, successful import order is preserved, duplicate source-file IDs are rejected, PR-008 appends IDs only by returning a new immutable instance, notes are not part of PR-008, and `repr()` exposes only ID, number, status and source count.

`SourceFile` is immutable, frozen and slotted with exactly `id: EntityId`, `batch_id: EntityId`, `original_artifact_id: EntityId`, `original_basename: SourceBasename`, `detected_media_type: SourceMediaType`, `byte_size: int`, `sha256: Sha256Digest`, `perceptual_hash: PerceptualHash`, `width: int`, `height: int`, `exif_orientation: int | None`, `imported_at: datetime`, and `imported_by: ActorRef`. It requires positive byte size and dimensions, dimensions before EXIF orientation, only EXIF orientation integer 1-8, no other EXIF/GPS/metadata persistence, UTC-normalized `imported_at`, and redacted basename, SHA-256 and perceptual hash in `repr()`. `quality_assessment` remains PR-009 and is not authorized in PR-008.

`ImportWarning` is immutable, frozen and slotted with exactly `code: ImportWarningCode`, `source_file_id: EntityId`, `related_source_file_id: EntityId | None`, `perceptual_distance: int | None`, `algorithm_id: str | None`, and `algorithm_version: int | None`. `EXACT_DUPLICATE` requires a related source ID and forbids distance and algorithm fields; `PERCEPTUAL_SIMILARITY` requires related source ID, distance, algorithm ID and algorithm version; `EXTENSION_CONTENT_MISMATCH` forbids related source ID, distance and algorithm fields; no warning may contain filenames, paths, bytes, hashes or PII.

### Exact DTO and service contracts

PR-008 defines exactly these immutable, frozen and slotted DTOs:

```python
@dataclass(frozen=True, slots=True)
class CreateUploadBatchCommand:
    batch_id: EntityId
    number: BatchNumber
    created_at: datetime
    actor: ActorRef
```

`created_at` is timezone-aware and normalized to UTC, `actor` is explicit, status is forced to `UploadBatchStatus.NEW`, UUIDs and timestamps are caller-supplied, and `repr()` is safe.

```python
@dataclass(frozen=True, slots=True)
class SourceFileImportInput:
    source_file_id: EntityId
    artifact_id: EntityId
    audit_event_id: EntityId
    source_path: Path
    imported_at: datetime
```

`source_file_id`, `artifact_id` and `audit_event_id` are distinct and caller-supplied. `imported_at` is caller-supplied, timezone-aware and normalized to UTC. No service-generated UUID and no implicit current-time call is authorized. `source_path` is ephemeral, never persisted, never included in results, and redacted from `repr()`. `audit_event_id` is required by the accepted immutable `AuditEvent` contract.

```python
@dataclass(frozen=True, slots=True)
class ImportSourceFilesCommand:
    batch_id: EntityId
    actor: ActorRef
    items: tuple[SourceFileImportInput, ...]
```

`items` is a non-empty tuple; duplicate `source_file_id`, `artifact_id` and `audit_event_id` values are rejected before any file is read; command `repr()` must not reveal any source path.

```python
@dataclass(frozen=True, slots=True)
class ImportedSourceFileResult:
    source_file: SourceFile
    warnings: tuple[ImportWarning, ...]

@dataclass(frozen=True, slots=True)
class FailedSourceFileResult:
    source_file_id: EntityId
    error_code: SourceImportErrorCode

@dataclass(frozen=True, slots=True)
class ImportSourceFilesResult:
    batch_id: EntityId
    imported: tuple[ImportedSourceFileResult, ...]
    failed: tuple[FailedSourceFileResult, ...]
```

`imported` preserves successful input order, `failed` preserves failed input order, a source ID must not appear in both collections, and no result contains basename, source path, hash value, storage path or raw exception.

PR-008 defines exactly two public application-service operations: `create_upload_batch(command: CreateUploadBatchCommand, *, unit_of_work_factory: UnitOfWorkFactory) -> UploadBatch` and `import_source_files(command: ImportSourceFilesCommand, *, storage: StoragePort, media_decoder: MediaDecoderPort, unit_of_work_factory: UnitOfWorkFactory) -> ImportSourceFilesResult`. No additional public PR-008 application service operation is authorized. Batch creation constructs an immutable batch, forces status `NEW`, starts one SQLCipher Unit of Work, calls `upload_batches.add(batch)`, explicitly commits, returns the persisted batch, creates no audit event and exposes no source path or PII in failures. Duplicate batch IDs or numbers fail with sanitized persistence/application errors and never silently replace an existing batch.

### Exact repository and Unit of Work contracts

```python
class UploadBatchRepository(Protocol):
    def add(self, batch: UploadBatch) -> None: ...
    def get(self, batch_id: EntityId) -> UploadBatch | None: ...
    def update(self, batch: UploadBatch) -> None: ...
    def get_by_number(self, number: BatchNumber) -> UploadBatch | None: ...
```

`get_by_number` enforces unique batch numbers without arbitrary filters. There is no delete method, raw SQL, caller-defined sorting or pagination. `update` validates canonical payload and projections and may only replace the immutable batch row with a valid batch instance whose ID, number, created time and creator are unchanged. PR-008 may only append one successfully imported source ID; status transitions remain outside PR-008.

```python
class SourceFileRepository(Protocol):
    def add(self, source_file: SourceFile) -> None: ...
    def get(self, source_file_id: EntityId) -> SourceFile | None: ...
    def list_by_batch(self, batch_id: EntityId) -> tuple[SourceFile, ...]: ...
    def list_by_sha256(self, sha256: Sha256Digest) -> tuple[SourceFile, ...]: ...
    def list_compatible_perceptual_hashes(
        self,
        algorithm_id: str,
        algorithm_version: int,
        bit_width: int,
    ) -> tuple[SourceFile, ...]: ...
```

There is no update method, delete method, `list_all`, arbitrary filter, caller-defined sorting or pagination. Ordering is ascending by `imported_at`, then `id`; canonical payload/projection validation occurs before rows are returned.

The existing `UnitOfWork` contract gains exactly `upload_batches: UploadBatchRepository` and `source_files: SourceFileRepository`. These repositories use the same SQLCipher connection and transaction as `stored_artifacts` and `audit_events`; no repository may open an independent connection or commit independently. If a factory port is needed, it is exactly `class UnitOfWorkFactory(Protocol): def unit_of_work(self) -> UnitOfWork: ...`, aligned with the existing database adapter entry point.

### Storage, file reading, media and duplicates

PR-008 reuses the PR-006 `StoragePort`. Every successfully validated original is published exactly as `storage.publish_bytes(artifact_id=item.artifact_id, artifact_kind=ArtifactKind.ORIGINAL, plaintext=original_bytes, created_at=item.imported_at)`. `ArtifactKind.ORIGINAL` is mandatory; `plaintext` is the exact byte sequence read from `source_path`; decoded, oriented, normalized, converted or recompressed bytes must not be passed; `created_at` is exactly `item.imported_at`; the returned `StoredArtifactRecord` is inserted through `uow.stored_artifacts.add(stored_artifact)`; the returned artifact ID must equal `item.artifact_id`; mismatch fails closed before inserting `SourceFile`; no second storage port or original-file storage implementation is authorized.

`source_path` is a `pathlib.Path`. The service derives the basename only as `source_path.name`; the complete path is never persisted and never appears in logs, errors, audit events, verifier output or test reports. File bytes are read once into memory. `SOURCE_READ_FAILED` covers file not found, permission denied, not a regular file, read failure and detectable file changes/disappearance during the read boundary. Raw OS exceptions are never exposed. Empty files fail before decoding. Basename validation occurs before reading image bytes where possible, and `SOURCE_BASENAME_INVALID` publishes no object.

The suffix used for validation is `source_path.suffix.lower()` and only ASCII extension tokens are recognized. Stored `SourceBasename` preserves the original basename exactly; no filename case normalization is persisted. `.jpg`, `.JPG`, `.JpG` and `.jpeg` variants map to `JPEG`; `.png` variants map to `PNG`; `.heic` and `.heif` variants map to `HEIF`. No suffix or a basename ending only with `.` produces `UNSUPPORTED_EXTENSION`; multiple suffixes use only the final suffix; unsupported extension fails before decoding and before storage publication. Supported extension plus corrupt or undecodable content produces `DECODE_FAILED`; content that decodes to no supported media type produces `UNSUPPORTED_FORMAT`; supported extension whose decoded supported type differs from the extension imports successfully with `EXTENSION_CONTENT_MISMATCH`; detected content type is authoritative for `SourceFile.detected_media_type`; validation occurs before encrypted object publication and no failed validation publishes an object.

SHA-256 over unchanged original bytes is the exact-content identity signal. Perceptual hashing is advisory only. PR-008 uses deterministic `DHASH64` version 1, bit width 64, primary decoded frame only, EXIF orientation applied in memory for hashing only, alpha composited onto opaque white, 8-bit grayscale, fixed LANCZOS resize to 9x8, row-major 64-bit storage, Hamming distance by XOR/popcount and warning threshold distance <= 8. Golden vectors are: ascending gradient `0000000000000000`, descending gradient `ffffffffffffffff`, alternating rows `00ff00ff00ff00ff`; tests must prove Ubuntu/Windows stability, leading-zero preservation, A/B distance 64, A/C distance 32, threshold 8 non-match for those pairs, one-bit distance 1 warning, and algorithm version 2 for any behavior-changing decoder/grayscale/EXIF/alpha/resampler change.

Duplicate lookup occurs before inserting the current `SourceFile`: validate basename/extension, read bytes, decode, compute SHA-256/DHASH64, open read-only or uncommitted lookup Unit of Work, query exact candidates by SHA-256, query perceptual candidates by compatible algorithm/version/bit width, exclude rows whose `id == item.source_file_id`, exclude rows whose `original_artifact_id == item.artifact_id`, close or roll back lookup Unit of Work, construct deterministic warnings, publish encrypted object, open write Unit of Work, re-check duplicate source/artifact IDs, insert storage record/source file/batch update/audit event and commit. The first MVP has no multi-writer conflict-resolution protocol, but write transactions reject duplicate IDs and never classify the new row as its own duplicate. Emit at most one exact and one perceptual warning per related source ID, suppress perceptual warning for an exact duplicate related source, do not collapse distinct related IDs, emit at most one extension mismatch warning, and order warnings by exact related ID, then perceptual distance and related ID, then extension mismatch.

### Audit, migration, verifier and dependency contracts

Successful original registration emits exactly one audit event using the same SQLCipher Unit of Work. The event uses `event_id=item.audit_event_id`, `occurred_at=item.imported_at`, `actor=command.actor`, `action_code=AuditAction.ARTIFACT_REGISTERED`, `subject_type=AuditSubjectType.STORED_ARTIFACT`, `subject_id=item.artifact_id`, `field_key=None`, `reason_code=AuditReasonCode("SOURCE_FILE_IMPORT")`, and `correlation_id=command.batch_id`. `before` is an `AuditValueSummary` constructed with `classification=AuditValueClassification.ABSENT`, `display_value=None`, `was_present=False`. `after` is an `AuditValueSummary` constructed with `classification=AuditValueClassification.NON_SENSITIVE`, `display_value="ORIGINAL"`, `was_present=True`. No factory methods are added to `AuditValueSummary`. The event is inserted through `uow.audit_events.add(audit_event)` and shares the write transaction with `StoredArtifactRecord`, `SourceFile` and immutable `UploadBatch` update. Audit insertion failure rolls back all database changes. Failed validation, failed storage publication and warnings create no audit event. PR-008 adds no audit enum values, no audit factories, no class methods, no free-text audit fields and no alternative audit value-object API.

Migration v0004 creates persistence for upload batches, ordered upload-batch source-file membership, source files, and required unique/lookup indexes. Constraints include unique batch ID, unique canonical batch number, status projection, UTC timestamp projection, canonical payload, projection-integrity validation, unique source-file ID, unique `original_artifact_id`, foreign keys to upload batch and stored artifact, positive byte size/dimensions, allowed media type, allowed EXIF orientation, lowercase SHA-256 shape validation, perceptual algorithm/version/bit-width/hash projections and canonical payload/projection-integrity validation. Indexes include batch membership ordering lookup, SHA-256 lookup, compatible perceptual algorithm/version/bit-width lookup and imported-time deterministic ordering. Database-level fuzzy-distance computation is not authorized; Hamming distance is computed in application code. Migration v0004 remains forward-only and append-only.

The exact verifier is `uv run python scripts/verify_pr008_import.py`, uses generated synthetic non-document images only, prints only controlled `PR008_VERIFY ...` records, exits `0` for pass, `1` for product failure and `2` only for unsupported/inconclusive environments, and allows inconclusive codes only `WINDOWS_SQLCIPHER_UNAVAILABLE`, `HEIF_DECODER_UNAVAILABLE`, `UNSUPPORTED_PLATFORM`. It must prove schema 4, v0004 checksum, unchanged v0001/v0002/v0003 checksums, ordinary SQLite rejection, byte identity, encrypted storage, JPEG/PNG/HEIF validation, extension case folding/mismatch/unsupported behavior, exact and perceptual duplicates, no self-match, warning order, per-file partial success, audit atomicity, orphan reconciliation, no orphan adoption/deletion and privacy. It must not claim acceptance of real documents or real-photo perceptual quality.

Domain and application contracts depend on local `MediaDecoderPort`, not third-party packages. `DecodedMedia` is immutable/frozen/slotted with `media_type`, `width`, `height`, `exif_orientation`, `grayscale_pixels`, `grayscale_width`, `grayscale_height`; `decode_for_import(content: bytes) -> DecodedMedia` receives bytes, makes no network call or runtime download, returns the primary frame and detected media type, retains only EXIF orientation 1-8, returns no GPS/filename/source path/camera metadata/arbitrary metadata, returns deterministic pixels for DHASH64, maps failures to controlled import errors and lets no raw decoder exception escape. PR-008 must document package name, exact pinned version, direct/transitive role, Python 3.12 support, Windows AMD64 wheel or packaging evidence, JPEG/PNG/HEIF support, offline installation/runtime evidence, license, redistribution obligations, native binaries, security/update considerations, no telemetry and no runtime downloads. If no compliant HEIF solution is available, PR-008 is blocked and must not silently omit HEIF, treat HEIF as future work, add runtime downloads, call external services or change media scope.

### Synthetic tests and non-goals

Tests use only generated or clearly synthetic non-document images under the permitted fixture boundary. PR-008 must not implement PySide upload UI, drag and drop, background job UI, quality scoring, blur/glare/contrast diagnostics, final EXIF orientation diagnostics, crop, perspective correction, segmentation, multiple-document regions, JPEG preparation or compression, OCR, MRZ, barcode, document classification, field candidates, operator verification, Excel, terminal adapters, export, backup/restore, retention/deletion, users/authentication, telemetry, cloud services, browser automation, `quality_assessment` or PR-009-or-later behavior.

## PR-008 implementation evidence note

PR-008 implementation records encrypted source-file import and advisory duplicate detection only. Original bytes are stored through the accepted encrypted storage port, metadata remains in SQLCipher, source paths are not persisted, decoder dependencies are pinned to `Pillow==12.3.0` and `pi-heif==1.4.0`, and no OCR, telemetry, cloud service, export, or PR-009 behavior is authorized by this change.
