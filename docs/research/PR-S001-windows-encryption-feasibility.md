# PR-S001 Windows encryption feasibility and packaging

## 1. Scope

PR-S001 is an isolated feasibility spike for Windows 11 x64 and Python 3.12. It uses fictional synthetic data only, creates no production persistence or storage API, and does not select a final production package automatically.

## 2. Accepted ADR-018 boundaries

ADR-018 is accepted. PR-S001 may gather evidence for SQLCipher, DPAPI Current User, key hierarchy, authenticated encrypted-object envelopes, rollback anchors, crash consistency, offline packaging, safe diagnostics, licensing and performance. PR-005 and PR-006 remain unauthorized.

## 3. Environment and evidence date

External package and platform evidence was checked on 2026-07-17 against primary sources: Microsoft Learn DPAPI `CryptProtectData` and `CryptUnprotectData`, Zetetic SQLCipher API and licensing pages, PyPI project metadata for `sqlcipher3` and `pysqlcipher3`, PyCA `cryptography` documentation, Astral `uv` documentation, and official GitHub Actions action repositories. Committed local evidence does not fabricate GitHub Actions results. Where CI-only evidence is required, see the sanitized PR-S001 Windows CI evidence and GitHub step summary.

## 4. Candidate matrix

| Candidate | Evaluation | Technical | Security | Packaging | Licensing/support | Production risk |
|---|---|---|---|---|---|---|
| A `sqlcipher3==0.6.2` | Executable Windows probe candidate | Technically executable only when Windows wheel imports and reports SQLCipher capabilities in CI | Must prove `cipher_status`, integrity, wrong-key, tamper and plaintext absence | PyPI metadata lists Windows CPython 3.12 x64 wheel; wheelhouse job proves or fails offline install | Binding metadata and SQLCipher Community obligations require legal/product-owner review | SQL-string raw-key PRAGMA is marked a risk unless binding-safe raw-key API is demonstrated |
| B official Zetetic Windows package | Metadata-only, commercial-not-tested | Not executable in this PR | Security properties depend on licensed package docs and future supplied binaries | Offline delivery/support appear commercially available but not downloaded here | Commercial/Enterprise terms, trial limits and redistribution remain subject to approval | No trial code, purchase, commercial binary or secret is used |
| C `pysqlcipher3==1.2.0` | Legacy control metadata only | Not added to lockfile and no CI source build attempted | Not demonstrated for Python 3.12 Windows | Older release/build route appears source-build oriented | Support model appears weaker than maintained candidates | Not selected by this spike |
| D custom binding/build | Design route only | Possible through custom SQLCipher Community build, official DLL binding, or separately validated APSW route | Requires independent validation | More complex reproducibility and redistribution | Support model depends on chosen route | Not implemented or selected |

## 5. SQLCipher executable evidence

Candidate A is the selected executable candidate for the automated spike. The Windows job records installed package version, embedded SQLCipher version, SQLite version, exposed cryptographic provider information when available, `cipher_status`, `cipher_integrity_check`, compile/options evidence, journal/temp-store posture, wheel metadata and raw-key API assessment. See the sanitized PR-S001 Windows CI evidence and GitHub step summary.

## 6. DPAPI evidence

The spike implements Current User DPAPI with `ctypes`, `CryptProtectData`, `CryptUnprotectData`, `CRYPTPROTECT_UI_FORBIDDEN`, null prompt/description, no Local Machine flag, application wrapper validation and `LocalFree`. Same-runner and process-restart evidence is generated only on Windows. Cross-runner negative evidence uses a one-day protected-blob artifact and claims only current-profile non-portability, not every roaming-profile/domain configuration.

## 7. Key-hierarchy comparison

Strategy A derives purpose keys with HKDF-SHA-256 labels for `database-key`, `file-key-encryption-key` and `future-backup-key`. It is operationally simple but rotation and blast-radius analysis remain production risks. Strategy B wraps independent database and object DEKs under a root-derived KEK using standardized key wrapping from `cryptography`; it adds per-object overhead and recovery complexity but improves independence and rotation options. No final strategy is selected.

## 8. Encrypted-envelope evidence

`SPIKE ENVELOPE VERSION 0` is experimental and not an accepted production format. The executable experiment uses AES-256-GCM, 96-bit nonces and deterministic canonical JSON AAD binding synthetic artifact ID, kind, length, generation, key version, storage format version and plaintext digest. It does not claim guaranteed global nonce uniqueness beyond the tested generator and process boundary.

## 9. Independent rollback-anchor evidence

The probe keeps expected state separate from the replaceable encrypted object. Old valid envelope replacement, key-version rollback, ciphertext replacement and copied-object substitution fail against the current authoritative record. A coordinated rollback of both the object and authoritative record, or of the full encrypted database, encrypted storage and every local authoritative-state copy, is explicitly not claimed as detected.

## 10. Crash-consistency comparison

The report compares database-record-first, object-publication-first and staged-pending recovery. Only the staged-pending sequence is prototyped as a spike model: pending expected state, encrypted temp object, flush/fsync, atomic replace, active finalization and reconciliation. Outcomes are limited to ACTIVE, SAFE_TO_RETRY or QUARANTINED. Windows directory fsync limitations and final production transaction design remain unresolved.

## 11. Offline wheelhouse-install evidence

The Windows workflow downloads binary wheels to `RUNNER_TEMP`, records filenames/tags/SHA-256/sizes in sanitized summary, creates a clean venv, installs with `--no-index --find-links`, and runs an offline smoke probe. This proves only wheelhouse-based offline dependency installation and does not prove the final Windows installer.

## 12. Performance evidence

The spike measures DPAPI protect/unprotect, SQLCipher startup/read/write operations and AES-GCM payloads of 1 KiB, 100 KiB, 1 MiB and 1,992,294 bytes with bounded samples. GitHub-hosted runner measurements are not production performance claims.

## 13. Licensing and attribution obligations

Python binding license metadata, SQLCipher Community license/attribution requirements, cryptographic-provider notices, official Commercial/Enterprise implications, trial restrictions and redistribution approval needs are recorded separately. Redistribution terms remain subject to legal and product-owner approval; this report provides no legal conclusion beyond published requirements.

## 14. Supply-chain observations

Spike dependencies are confined to the `encryption-spike` dependency group and are not production dependencies. Wheels are acquired from PyPI during CI only and are not committed or uploaded except as transient package installation inputs.

## 15. Security limitations

DPAPI Current User does not isolate against same-user malware. SQLCipher package import is not production suitability. The raw-key SQL PRAGMA route is a production-selection risk if no binding-safe raw-key API is demonstrated. No final KDF, envelope format, crash-consistency design, backup/recovery design or full-system rollback anchor is selected.

## 16. Failed or unsupported checks

Local Linux execution reports Windows-only DPAPI, ACL and SQLCipher checks as UNSUPPORTED or NOT_DEMONSTRATED. See the sanitized PR-S001 Windows CI evidence and GitHub step summary for Windows-only results.

## 17. Recommendation

CONDITIONALLY FEASIBLE. The spike can support product review if CI demonstrates Candidate A runtime capabilities and offline wheelhouse install, but production selection remains blocked on raw-key API risk, licensing/legal approval, final transaction design, and human acceptance.

## 18. Remaining blockers

Unresolved blockers: final SQLCipher edition/binding/version, legal redistribution approval, final key hierarchy, production envelope format, production storage/database transaction boundary, backup/recovery design, installer ACL design and full-system rollback strategy.

## 19. Explicit non-authorization of PR-005 and PR-006

PR-S001 is in review only. PR-S001 merge does not authorize PR-005 or PR-006. Human acceptance and separate authorization are required before any production persistence or storage work.
