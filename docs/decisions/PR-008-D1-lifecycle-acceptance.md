# PR-008-D1 — PR-008 lifecycle acceptance and Windows 11 smoke residual risk

## Status

ACCEPTED

## Decision date

2026-07-21

## Context

PR #21 — PR-008: Add encrypted source import and advisory duplicate detection — was merged on 2026-07-20. The final exact-head CI #106 was green with workflow database ID `29776664038`, and both Ubuntu AMD64 and hosted Windows AMD64 jobs passed. The production-component PR-008 verifier passed on hosted Windows with `PR008_VERIFY result=PASS`.

The required deterministic hash, duplicate-detection, audit, privacy and persistence evidence passed for the PR-008 acceptance boundary. The frozen larger-image DHASH64 is `1810111f39f11131`.

No physical Windows 11 x64 acceptance workstation was available from the current MacBook development environment. A MacBook cannot provide a physical Windows 11 production smoke. The missing physical smoke is an environment-evidence limitation, not a hidden claim that PR-008 was executed on a physical Windows 11 x64 production workstation.

## Decision

PR-008 is COMPLETED AND HUMAN ACCEPTED.

RISK-PR008-W11-SMOKE is accepted by the product owner for the PR-008
development acceptance boundary.

PR-009 is AUTHORIZED and NOT STARTED.

Gate 2 remains NOT ACCEPTED.

PR-010 and later implementation work remain UNAUTHORIZED.

## Evidence

- GitHub PR: #21 — PR-008: Add encrypted source import and advisory duplicate detection.
- Final reviewed head: `99dfefe467762e241f0584c2ca1a81bc662c1ab0`.
- Merge commit: `bf7af9617d33a205f27eb9a4734fea6ecee18b58`.
- Merge date: 2026-07-20.
- Final exact-head CI: CI #106; workflow database ID `29776664038`; conclusion: success.
- Required successful CI jobs:
  - Python checks (ubuntu-latest): success.
  - Python checks (windows-latest): success.
  - PR-S001 Windows encryption spike: success.
  - PR-S001 DPAPI cross-runner negative: success.
- Final test evidence recorded by the merged PR:
  - macOS: 465 passed, 3 skipped.
  - Ubuntu: 465 passed, 3 skipped.
  - Windows: 467 passed, 1 skipped.
- Final PR-008 verifier on supported Windows CI: `PR008_VERIFY result=PASS`.
- Frozen larger-image DHASH64: `1810111f39f11131`.

## Residual risk

`RISK-PR008-W11-SMOKE` status: ACCEPTED FOR THE PR-008 DEVELOPMENT ACCEPTANCE BOUNDARY; DEFERRED TO WINDOWS INSTALLER, PILOT, OR FINAL RELEASE ACCEPTANCE.

Hosted Windows Server AMD64 is not identical to a physical Windows 11 x64 workstation. Driver, shell, filesystem policy, installer, antivirus, codec packaging and workstation-specific behavior may still differ. This risk remains open for PR-033, pilot, or release acceptance. Acceptance of this risk does not claim final production readiness and must not be reused to claim that the complete Windows 11 production release has been accepted.

The final Windows 11 release-validation requirement, Windows installer verification requirement, real-photo quality validation, native codec redistribution and legal-notice work, sensitive-data/private-contour gate, real-document local acceptance requirements and existing SQLCipher release risks remain open where already applicable.

## Consequences

- PR-008 lifecycle is closed.
- PR-009 may begin after this documentation PR is merged.
- Gate 2 remains open through PR-009–PR-013.
- No OCR or later-stage work is authorized by this decision.
- No physical Windows 11 result may be fabricated or inferred.

## Non-goals

- No code changes.
- No PR-009 implementation.
- No Gate 2 acceptance.
- No Windows installer acceptance.
- No real-document or real-photo validation.
- No closure of native codec packaging obligations.
