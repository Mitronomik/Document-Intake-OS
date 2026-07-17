# PR-S001 — Windows encryption feasibility and packaging spike

Required base SHA: `edc895ffaf26f496bd8f60dbcbb87f3d5cfb09f4`.

Authorization source: GATE-S1 completed and human accepted; ADR-018 accepted; Q-010 accepted.

PR-S001 is an isolated feasibility spike. PR-S001 does not create production persistence or storage. PR-S001 does not select the final production package automatically. PR-S001 merge does not authorize PR-005 or PR-006. Human acceptance and separate authorization are required.

Goal: produce reproducible evidence for SQLCipher packaging/encryption, DPAPI Current User, key hierarchy alternatives, authenticated encrypted-object envelope behavior, independent rollback anchors, crash consistency, safe diagnostics, licensing and performance.

Candidate matrix: A `sqlcipher3==0.6.2` executable Windows candidate; B official Zetetic Windows package metadata-only/commercial-not-tested; C `pysqlcipher3==1.2.0` legacy metadata control; D custom binding/build route documented only.

Exact modules: `spikes/windows_encryption/dpapi_probe.py`, `key_strategy_probe.py`, `sqlcipher_probe.py`, `envelope_probe.py`, `safe_report.py`, `run.py`, and their spike tests.

Inputs: runtime-generated fictional synthetic bytes and scalar labels only. Outputs: sanitized JSON evidence in CI, GitHub step summary, one short-lived DPAPI-protected blob artifact for cross-runner negative testing, and this research report.

Synthetic-data policy: no real/anonymized documents, personal data, document images, OCR/MRZ, database files, WAL/journal files, key blobs, ciphertext, wheels or benchmark output are committed.

Security boundaries: no Local Machine DPAPI, no interactive prompts, no production repository/storage/application interfaces, no production migrations, no UI integration, no telemetry, no external runtime service.

Acceptance criteria: isolated under `spikes/`; no `src/` changes; spike dependencies only in `encryption-spike`; Windows spike CI demonstrates or honestly fails SQLCipher, DPAPI, ACL, offline wheelhouse, envelope, rollback, crash model and safe-report checks; PR-005/PR-006 remain unauthorized.

Tests: documentation baseline tests, repository policy, Ruff, mypy, pytest, build, and dedicated Windows spike tests.

CI: add `windows-encryption-spike` and dependent `windows-dpapi-cross-runner-negative` jobs without changing the existing checks matrix.

Manual verification: review changed file scope, sanitized report, lifecycle wording and absence of generated artifacts.

Evidence report: `docs/research/PR-S001-windows-encryption-feasibility.md`.

Licensing review: binding license, SQLCipher Community attribution, cryptographic-provider notices, official commercial/enterprise implications, trial restrictions and redistribution approval remain subject to legal/product-owner review.

Risks: raw-key API availability, package support, Windows-only behavior, offline installer gap, ACL installer design, final transaction design, full-system rollback non-claim.

Non-goals: production persistence/storage, production encryption APIs, backup/recovery, authentication, UI integration, final package/KDF/envelope/crash-design selection, PR-005 authorization, PR-006 authorization.

Final-report requirements: report branch, base SHA, commit/PR metadata, changed files, candidate matrix, runtime versions where demonstrated, results, blockers, verification, CI status and lifecycle authorization states.
