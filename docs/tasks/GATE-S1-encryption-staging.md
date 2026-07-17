# GATE-S1 — Encryption staging proposal

## Base SHA

`6f3021a38305cb92d733a46426cde427828bac04`

## Context

GATE-M0 is completed. M0 and M1 are accepted. PR-004 is completed through GitHub PR #6 at merge commit `6f3021a38305cb92d733a46426cde427828bac04` and is human accepted. Gate 1 is not accepted. M2 is not completed. Q-010 remains open. PR-005, PR-006, PR-007 and later work remain unauthorized.

GATE-S1 prepares a proposal. GATE-S1 does not accept ADR-018 automatically. GATE-S1 does not resolve Q-010 until human acceptance.

## Problem statement

The technical specification requires encrypted database and filesystem storage, but PR-005 and PR-006 were scheduled before PR-030 encryption. Production personal data must never be persisted in plaintext, raw key material must not be stored beside protected content, and later backup portability and recovery must remain possible.

## Authoritative sources

- `AGENTS.md`
- `docs/technical-specification.md`
- `docs/decisions.md`
- `docs/product-spec.md`
- `docs/architecture.md`
- `docs/domain-model.md`
- `docs/security.md`
- `docs/testing-strategy.md`
- `docs/open-questions.md`
- `docs/acceptance-criteria.md`
- `docs/traceability-matrix.md`
- `docs/roadmap.md`
- `docs/implementation-plan.md`
- `docs/progress.md`
- `docs/handoff.md`
- `docs/tasks/PR-004-core-domain.md`
- `tests/test_documentation_baseline.py`

## Exact proposal

Propose ADR-018 with an encryption-first invariant: no production-capable database or document storage may write personal data to disk in plaintext, and no startup may continue after key-protection failure. Propose an explicit threat model, a locally generated application root/master key protected by a versioned DPAPI current-user key blob, mandatory key hierarchy and purpose separation, full-database encryption with integrity authentication through SQLCipher or a validated equivalent, application-level authenticated file encryption with a versioned encrypted object envelope, BitLocker as defense in depth, strict temporary-plaintext boundaries, and a future backup/recovery wrapper separate from the DPAPI blob.

## Threat model and protection boundary

The proposal protects data at rest against offline disk theft/copying, another Windows user, copying protected data without the required Windows profile, accidental disclosure of encrypted files or later encrypted backups, and tampering detectable by authenticated encryption or database integrity checks. It does not fully protect against malicious code under the same Windows credentials, a malicious administrator, an already unlocked operator session, process-memory inspection, screen capture or operator-authorized plaintext access, or compromised application binaries. DPAPI Current User does not provide application-to-application isolation.

## Key hierarchy and purpose separation

The DPAPI-protected root/master key is not directly a database key, file AEAD key or backup recovery key. Database, file-storage and future backup purposes require independent key material, purpose/domain separation, versioned key and envelope formats, no derivation from predictable identifiers alone, no claim of guaranteed Python zeroization for immutable bytes/strings, and minimized key copies/lifetimes. PR-S001 must compare purpose-derived keys with wrapped per-database/per-object data-encryption keys.

## SQLCipher hardening requirements

PR-S001 must verify active encryption for every production connection, fail closed when encryption is inactive, keep HMAC/integrity authentication enabled, prove ordinary SQLite cannot open the database, test wrong-key/tamper/corruption behavior, verify WAL and rollback-journal pages are encrypted, prevent plaintext file-based SQLite temporary stores, constrain SQLCipher logging, keep keys out of logs/exceptions/diagnostics, compare binding-safe keying against SQL-string key injection, test offline Windows packaging, document licensing, and verify no security feature is silently disabled for performance.

## Encrypted object envelope

File encryption requires a versioned envelope containing format magic/version, algorithm identifier, key version or key identifier, nonce/IV, ciphertext, authentication tag and canonical authenticated metadata. Metadata binds artifact ID, artifact kind, plaintext length, storage format version, and expected content checksum or another accepted rollback/replay control. Nonce reuse is prohibited, partial writes fail authentication, writes use encrypted temporary output and atomic replacement, plaintext temporary files are forbidden by default, historical ciphertext replacement for the same immutable artifact is detectable, and errors contain no PII.

## Compared options

- Option A — Plaintext persistence until PR-030: REJECT.
- Option B — BitLocker-only protection: REJECT AS SOLE CONTROL.
- Option C — Encryption-first application architecture: PREFERRED, but not accepted until human review.

## Recommendation

Recommend Option C for product-owner review only.

## Assumptions

- First MVP topology remains one Windows 11 x64 workstation with one active operator session.
- PR-004 contains no persistence.
- Q-010 remains open until a human accepts ADR-018.

## Risks

- SQLCipher or equivalent packaging may be difficult on Windows 11 x64.
- DPAPI current-user scope affects backup and future local-user design.
- External image or Excel libraries may later require temporary path-based integration.
- Backup recovery ceremony remains unresolved under Q-017.

## Decision boundaries

This gate may propose security architecture and documentation tests only. It may not implement encryption, database, storage, backup or dependency changes.

## Non-decisions

Final SQLCipher edition or distribution, final Python database binding, exact cryptography package and version, FIPS requirement, backup recovery password policy, backup destination, retention and deletion periods, secure deletion guarantees, local application users, authentication, idle timeout, administrator recovery ceremony, key rotation UI, multi-workstation key sharing and macOS keychain implementation remain unresolved.

## Lifecycle state

- GATE-M0: COMPLETED
- M0: ACCEPTED
- M1: ACCEPTED
- PR-004: COMPLETED AND HUMAN ACCEPTED
- GATE-S1: IN REVIEW
- ADR-018: PROPOSED
- Q-010: OPEN
- PR-S001: PROPOSED, NOT AUTHORIZED
- PR-005: UNAUTHORIZED
- PR-006: UNAUTHORIZED
- PR-007 AND LATER: UNAUTHORIZED
- Gate 1: NOT ACCEPTED
- M2: NOT COMPLETED

The next safe step is review and product-owner decision on GATE-S1 / ADR-018.

## Affected future PRs

PR-S001 is proposed as a Windows encryption feasibility and packaging spike. PR-005 remains unauthorized until ADR-018 acceptance, PR-S001 review and acceptance, and explicit PR-005 authorization. PR-006 remains unauthorized until its own task review. PR-007 and later work remain unauthorized.

## Acceptance criteria

- ADR-018 exists once and is PROPOSED.
- Q-010 remains OPEN and references ADR-018 as a proposal.
- PR-004 closure records GitHub PR #6, the exact merge commit, and product-owner acceptance.
- Lifecycle documents state GATE-S1 is in review and remove stale PR-004 in-review state.
- Documentation tests cover the proposal and authorization boundaries.
- No runtime implementation, dependency, fixture, template, PII or binary artifact is added.

## Documentation tests

`tests/test_documentation_baseline.py` must prove the PR-004 closure, ADR-018 proposal status, Q-010 status, PR-S001 proposed-but-unauthorized state, PR-005/PR-006/PR-007 authorization boundaries, Gate 1 and M2 status, option recommendations, encryption-first invariant, no silent fallback, raw-key storage prohibition, threat-model boundary, key hierarchy and purpose separation, SQLCipher hardening requirements, encrypted object envelope requirements, backup boundary, non-decisions and absence of stale lifecycle state. Permanent pytest tests must not depend on fixed historical Git diff ranges.

## Manual review checklist

- Run the PR review/manual verification command `git diff --name-only 6f3021a38305cb92d733a46426cde427828bac04...HEAD` outside pytest to confirm GATE-S1 correction file scope.
- Confirm ADR-018 remains PROPOSED.
- Confirm Q-010 remains OPEN.
- Confirm PR-S001, PR-005, PR-006, PR-007 and later work remain unauthorized.
- Confirm no dependency or runtime implementation was added.
- Confirm no real documents, PII, templates or binary fixtures were added.
- Confirm fixed-base Git diff checks remain manual PR review checks only and are not permanent pytest invariants.

## Prohibited implementation

Do not implement SQLite, SQLCipher, database libraries, migrations, repository interfaces, DPAPI, AES-GCM, cryptography dependencies, filesystem storage, database fixtures, encrypted fixtures, document fixtures, personal data, secrets, keys, backup, recovery or later implementation tasks.

## Final report requirements

Report actual branch, base SHA, commit SHA, final head SHA, changed files, ADR-018 status, proposal summary, Q-010 final status, lifecycle updates, verification results, blocked commands, GitHub Actions status if known, PR number, PR title, PR body, and confirmations that no dependency, encryption code, database/storage code, PII, template or binary fixture was added and PR-005 and later remain unauthorized.
