# PR-S001 Windows encryption feasibility and packaging

## 1. Scope

Status: DEMONSTRATED for the repository-local evidence harness structure. PR-S001 remains an isolated feasibility spike. It uses fictional synthetic data only, creates no production persistence or storage API, and does not select a final production package automatically.

## 2. Accepted ADR-018 boundaries

Status: DEMONSTRATED. ADR-018 is accepted and remains authoritative. PR-S001 may gather evidence for SQLCipher, DPAPI Current User, key hierarchy, authenticated encrypted-object envelopes, rollback anchors, crash consistency, offline packaging, safe diagnostics, licensing and performance. PR-005 and PR-006 remain unauthorized.

## 3. Environment and evidence date

Status: DEMONSTRATED for source review date. External package and platform evidence was checked on 2026-07-17 against primary sources: Microsoft Learn DPAPI `CryptProtectData` and `CryptUnprotectData`, Zetetic SQLCipher API and licensing pages, PyPI project metadata for `sqlcipher3` and `pysqlcipher3`, PyCA `cryptography` documentation, Astral `uv` documentation, and official GitHub Actions action repositories.

GitHub Actions provides preliminary Windows x64 evidence on GitHub-hosted Windows Server. It does not prove Windows 11 compatibility. Windows 11 x64 result: NOT_DEMONSTRATED.

A sanitized run on Windows 11 x64 remains required before product-owner acceptance of PR-S001. No real documents or personal data are needed for that run.

```powershell
uv sync --locked --dev --group encryption-spike

uv run --group encryption-spike pytest -ra `
  spikes/windows_encryption/tests

uv run --group encryption-spike python -m spikes.windows_encryption.run `
  --output "$env:TEMP\pr-s001-windows11-evidence.json"

uv run --group encryption-spike python -m spikes.windows_encryption.run `
  --validate-report "$env:TEMP\pr-s001-windows11-evidence.json"
```

The sanitized report must not contain machine name, username or absolute path.

## 4. Candidate matrix

| Candidate | Evaluation | Technical | Security | Packaging | Licensing/support | Production risk |
|---|---|---|---|---|---|---|
| A `sqlcipher3==0.6.2` | Executable Windows probe candidate | NOT_DEMONSTRATED until Windows CI executes; source harness exists | NOT_DEMONSTRATED until `cipher_status`, integrity, wrong-key, tamper and plaintext absence checks run | NOT_DEMONSTRATED until wheelhouse job succeeds | NOT_DEMONSTRATED pending legal/product-owner review | Raw-key SQL PRAGMA remains a production-selection risk unless binding-safe raw-key API is demonstrated |
| B official Zetetic Windows package | Metadata-only, commercial-not-tested | NOT_DEMONSTRATED | NOT_DEMONSTRATED | NOT_DEMONSTRATED; no commercial binaries downloaded | NOT_DEMONSTRATED; redistribution subject to approval | No trial code, purchase, commercial binary or secret is used |
| C `pysqlcipher3==1.2.0` | Legacy control metadata only | NOT_DEMONSTRATED | NOT_DEMONSTRATED | NOT_DEMONSTRATED; not added to lockfile | NOT_DEMONSTRATED | Not selected by this spike |
| D custom binding/build | Design route only | NOT_DEMONSTRATED | NOT_DEMONSTRATED | NOT_DEMONSTRATED | NOT_DEMONSTRATED | Not implemented or selected |

## 5. SQLCipher executable evidence

Status: NOT_DEMONSTRATED locally on Linux; DEMONSTRATED only after Windows CI runs. The harness executes capability checks for installed binding version, embedded SQLCipher version, SQLite version, `cipher_status`, `cipher_integrity_check`, compile options, provider PRAGMAs when exposed, journal mode, temp-store mode, raw-key API inspection and logging status. Database checks execute encrypted creation, correct key, wrong key, ordinary SQLite rejection, encrypted header, marker scans, integrity, bit modification, truncation, WAL scan, rollback-journal scan, controlled temp scan and cleanup.

## 6. DPAPI evidence

Status: NOT_DEMONSTRATED locally on Linux; DEMONSTRATED only after Windows CI runs. The spike uses `ctypes` with `use_last_error=True`, explicit `argtypes`/`restype`, `CRYPTPROTECT_UI_FORBIDDEN`, no Local Machine scope, no prompt structure, application wrapper validation, and `LocalFree`. The upload step must first protect, unprotect in-process, unprotect in a fresh same-runner subprocess, and confirm the recovered key matches. The cross-runner job accepts only `ERR_DPAPI_UNPROTECT_FAILED`.

## 7. ACL evidence

Status: NOT_DEMONSTRATED locally on Linux; DEMONSTRATED only after Windows CI runs. The temporary ACL probe creates a temporary spike directory, obtains the current user SID without reporting it, disables inherited broad write access, grants required principals, checks broad groups, and deletes the directory. This is not a final installer ACL design.

## 8. Key-hierarchy comparison

Status: DEMONSTRATED by local tests when `cryptography` is available; otherwise UNSUPPORTED. Strategy A uses PyCA HKDF-SHA-256 with distinct database, file and backup labels. Strategy B wraps random DEKs under purpose-bound KEKs. No final key hierarchy is selected.

## 9. Encrypted-envelope evidence

Status: DEMONSTRATED by local tests when `cryptography` is available; otherwise UNSUPPORTED. `SPIKE ENVELOPE VERSION 0` is experimental and not an accepted production format. The envelope carries magic, format version, algorithm, key version, 96-bit nonce, canonical metadata, ciphertext and tag. InvalidTag is mapped to stable authentication failure only.

## 10. Independent rollback-anchor evidence

Status: DEMONSTRATED by local tests. Expected state remains outside the replaceable envelope. Old valid envelope, generation modification, digest modification, key rollback, ciphertext replacement and artifact-copy substitution fail. Coordinated rollback of both object and expected-state record remains explicitly undetected and is not claimed as detected.

## 11. Crash-consistency comparison

Status: DEMONSTRATED as an experimental state model. The staged sequence models pending expected state, encrypted temporary object write, file flush/fsync, atomic replace, active finalization and restart reconciliation. Results are limited to ACTIVE, SAFE_TO_RETRY or QUARANTINED. Windows directory fsync limitations remain unresolved. This is not a selected production transaction design.

## 12. Offline wheelhouse-install evidence

Status: NOT_DEMONSTRATED until Windows CI executes. The workflow downloads binary wheels into `RUNNER_TEMP`, records sanitized filename/tag/SHA-256/size evidence, installs with `--no-index --find-links` into a clean venv, and runs the offline smoke module. This proves only wheelhouse-based package-source independence, not the final Windows installer and not physical network disablement.

## 13. Performance evidence

Status: DEMONSTRATED for bounded standard SQLite and AES-GCM harness measurements when dependencies are available; SQLCipher and DPAPI performance remain NOT_DEMONSTRATED until Windows CI executes. GitHub-hosted runner measurements are not production performance claims.

## 14. Licensing and attribution obligations

Status: NOT_DEMONSTRATED for legal acceptance. The report records binding metadata, SQLCipher Community attribution requirements, cryptographic-provider notices, commercial/enterprise implications, trial restrictions and redistribution approval needs. Redistribution terms remain subject to legal and product-owner approval.

## 15. Supply-chain observations

Status: DEMONSTRATED for dependency isolation in `pyproject.toml`. Spike dependencies are confined to the `encryption-spike` dependency group and are not production dependencies. Wheels must not be committed or uploaded as general artifacts.

## 16. Security limitations

Status: DEMONSTRATED as documented limitations. DPAPI Current User does not isolate against same-user malware. SQLCipher import alone is not production suitability. Raw-key SQL PRAGMA remains a production-selection risk if no binding-safe raw-key API is demonstrated. No final KDF, envelope format, transaction design, backup/recovery design or full-system rollback anchor is selected.

## 17. Failed or unsupported checks

Status: UNSUPPORTED on local Linux for Windows-only DPAPI, ACL and SQLCipher runtime checks. Windows CI failures are evidence and must be reported as FAILED, UNSUPPORTED or NOT_DEMONSTRATED rather than converted into harness crashes unless the failure is an invalid lockfile, dependency failure, lint/type/test failure, unhandled exception, unsafe report, missing artifact, incorrect cross-runner semantics or cleanup failure.

## 18. Recommendation

CONDITIONALLY FEASIBLE. The recommendation is conditional because GitHub Windows Server evidence is preliminary, Windows 11 x64 result is NOT_DEMONSTRATED, legal redistribution is unresolved, raw-key API suitability is unresolved, and no final production design is selected.

## 19. Remaining blockers

Status: NOT_DEMONSTRATED for production acceptance. Blockers remain: final SQLCipher edition/binding/version, legal redistribution approval, final key hierarchy, production envelope format, production storage/database transaction boundary, backup/recovery design, installer ACL design, Windows 11 x64 sanitized run and full-system rollback strategy.

## 20. Explicit non-authorization of PR-005 and PR-006

Status: DEMONSTRATED. PR-S001 is in review only. PR-S001 merge does not authorize PR-005 or PR-006. Human acceptance and separate authorization are required before any production persistence or storage work.

coordinated rollback is not claimed as detected.
