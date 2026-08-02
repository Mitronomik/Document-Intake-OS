# PR-012-D1 — Lifecycle acceptance

**Status:** ACCEPTED
**Decision date:** 2026-08-01
**Nature:** append-only lifecycle evidence

## Decision

PR-012 is **COMPLETED AND HUMAN ACCEPTED**. ADR-026 and the PR-012 contract are
accepted. GitHub PR #32, `PR-012: Implement deterministic multiple-document
regions`, merged on 2026-08-01.

| Evidence | Verified value |
|---|---|
| Accepted implementation base | `e326ff30c9ab83615c97579c02e480e2497838ab` |
| Accepted and reviewed head | `9a6af1b72a064c47c66989b1e7dbc78d72768957` |
| Merge commit | `6a0f0df1e2d43e67395d4dee9415b6703181ab41` |
| Exact-head workflow | CI #203, run `30698992893`, SUCCESS |
| Ubuntu | 1177 passed, 14 skipped, 4 warnings; sdist PASS; wheel PASS |
| Windows | 1190 passed, 1 skipped, 4 warnings; sdist PASS; wheel PASS |
| Manual synthetic functional smoke | PASS at the reviewed head |
| Product-owner visual confirmation | PASS |

The private local smoke report remains outside Git. Only its approved evidence
fingerprint is recorded: `c28bd2b31ec227c9a5b6236a7fc108cd663cbee45616e934bec7be0ee051c53b`.
It must not be requested, copied, or committed.

## Schema freeze

Current schema version is **8**. Migration v0008 checksum is
`ff1d114954cf6a43cfe38ef8338a05b8bc11912fb51cd36dec2442d7ecee8f9b`.
Migrations v0001 through v0008 are frozen historical migrations and must remain
byte-for-byte unchanged. The earlier frozen v0007 checksum remains
`afad8ccc6de4ef81d73f137cbffa5a45fec1fdbb6940eabb0507cc9d6580a4a7`.

## Boundaries

Evidence uses only synthetic, non-sensitive material. Real documents and
personal data remain prohibited in Git, Codex, CI, logs, and test reports. The
offline/local-only, encrypted-storage, immutable-original, privacy-safe error
and audit boundaries remain unchanged. The private report is not repository
evidence.

This acceptance does not claim physical Windows 11 x64 installation, packaged
desktop startup, installer or upgrade behavior, final offline installed-app
verification, Microsoft Excel integration, terminal-template or real terminal
upload acceptance, or final workstation acceptance. Those remain deferred to
packaging, pilot, or release work.

The PR-012 merge does **not** authorize PR-013 production implementation.
ADR-027 is proposed, the PR-013 contract is proposed for human review, PR-013
production implementation is unauthorized, and PR-014 and later are
unauthorized. M3 remains in progress and Gate 2 is not accepted.
