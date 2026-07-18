# PR-S001-F4 — Windows 11 x64 target attestation

## Status

PR-S001-F4: CURRENT CORRECTION.

## Scope

Add a deterministic, privacy-safe target-platform probe to the PR-S001 Windows encryption research harness. The probe records sanitized Windows version and architecture evidence sufficient to distinguish Windows 11 x64 workstation from GitHub-hosted Windows Server environments.

## Lifecycle boundary

PR-S001: MERGED AS RESEARCH HARNESS; FINAL ACCEPTANCE NOT ACCEPTED.

PR-S001-F1: COMPLETED AND MERGED THROUGH PR #10.

PR-S001-F2: COMPLETED AND MERGED THROUGH PR #11.

PR-S001-F3: COMPLETED AND MERGED THROUGH PR #12; merge commit `ceb1e265a85a9af8374afa942fa7a68c7da492e7`.

PR-S001-F4: CURRENT CORRECTION.

Gate 1: NOT ACCEPTED.

M2: NOT COMPLETED.

PR-005: UNAUTHORIZED.

PR-006: UNAUTHORIZED.

PR-007 AND LATER: UNAUTHORIZED.

## Non-goals

This task does not perform the final Windows 11 run, fabricate target evidence, add target overrides, select the final SQLCipher edition, resolve licensing, create production persistence or storage APIs, authorize PR-005 or PR-006, accept Gate 1, or complete M2.

## Evidence safety

The probe may report only normalized OS version, build, product classification, native/process architecture classification, pointer width, check status and stable reason codes. It must not report hostnames, usernames, domains, SIDs, registry identifiers, raw API status values, exception text, paths, real documents or personal data.
