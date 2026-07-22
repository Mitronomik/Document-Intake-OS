# PR-009-D4 — PR-009 human acceptance and PR-010 contract authorization

## Status

ACCEPTED

## Date

2026-07-22

## Decision owner

Product owner

## Evidence

- GitHub PR: #24 (`PR-009: Implement orientation and quality assessment`).
- Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`.
- Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.
- Merge date: 2026-07-22.
- Human acceptance is based on the merged explicit-policy infrastructure, successful exact-head CI on the reviewed head, deterministic V1 metric implementation, typed caller-provided policy handling, immutable complete policy snapshots, append-only persistence, assessment and audit atomicity, controlled error boundaries, synthetic cross-platform verification, accepted MPO-as-JPEG compatibility and the accepted residual limitation that no production policy is active.

## Decision

PR-009: COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL LIMITATION.

Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.

Production default PR-009 quality policy: NOT ACTIVE.

Production policy_id: NOT ASSIGNED.

Production policy_version: NOT ASSIGNED.

Automatic PR-009 quality-based document blocking: NOT ACTIVE.

Automatic PR-009 production RETAKE_REQUIRED enforcement: NOT ACTIVE.

RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE AND HUMAN-ACCEPTANCE BOUNDARY.

PR-010 CONTRACT DEFINITION: AUTHORIZED, NOT STARTED.

PR-010 PRODUCTION IMPLEMENTATION: UNAUTHORIZED.

PR-011 AND LATER: UNAUTHORIZED.

Gate 2: NOT ACCEPTED.

M3: IN PROGRESS.

## Q-021 boundary preserved

The completed local calibration was technically valid: 60 samples were processed, 60 metric sets were calculated, no processing failures occurred, 43 samples were used for calibration, 17 held-out samples were used for validation, 54 Pareto candidates were evaluated and the search scope was `CALIBRATION_ONLY`.

No candidate policy was accepted, no production default was selected and the tested V1 whole-frame metrics, search space and severity combinations did not produce an acceptable production policy on that local set. This does not establish universal failure of the algorithms.

Q-021 continues to block production threshold selection, production severity mapping, assignment of production `policy_id`, assignment of production `policy_version`, activation of a production default policy, automatic quality-based blocking, automatic production `RETAKE_REQUIRED` enforcement and claims of production calibration.

Future production activation requires a separately versioned metric-separability task, local recalibration, legally and operationally permitted local evidence, explicit product-owner acceptance, explicit production `policy_id`, explicit production `policy_version`, accepted thresholds, accepted severity mapping and a separate lifecycle activation decision. This decision does not authorize that future metric-separability task.

## Residual limitation

`RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` remains open and accepted for the PR-009 infrastructure and human-acceptance boundary. No production default policy exists; production `policy_id` is not assigned; production `policy_version` is not assigned; no process-global or hidden policy is allowed; production composition must fail closed without a separately accepted policy; no unaccepted policy may automatically reject, delete, suppress or block a document; automatic production `RETAKE_REQUIRED` enforcement is inactive; explicit synthetic policies remain allowed in tests and verifiers; future production activation requires versioned metric-separability work, local recalibration and explicit product-owner acceptance; and V1 formulas and persisted algorithm identities must not be silently changed.

The risk does not block preparation of the PR-010 contract. The risk does not authorize PR-010 implementation. PR-010 must not depend on an active PR-009 production policy.

## PR-010 boundary

This decision authorizes preparation of the exact PR-010 documentation contract only. It does not authorize, start or implement PR-010 production code.

A later separate documentation-only pull request may define the exact PR-010 implementation contract. After that contract is merged and reviewed, another explicit product-owner lifecycle decision is required before PR-010 production implementation may start.

No PR-010 implementation architecture, runtime behavior, migration, dependency, DTO, repository, service, persistence schema, final UI control, automatic crop behavior, automatic perspective behavior, production policy identity or production policy version is accepted by this lifecycle decision.
