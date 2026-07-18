# PR-S001-F3 — Windows ACL diagnostics correction

## Status

CURRENT CORRECTION.

## Scope

Repair the Windows encryption spike ACL evidence path by replacing generic ACL probe failures with deterministic, sanitized stage checks for SID lookup, ACL application, ACL reading, SID normalization, JSON serialization, JSON parsing and independent directory cleanup.

## Non-goals

Do not change SQLCipher, WAL, rollback-journal, DPAPI, key hierarchy, envelope format, crash consistency, offline packaging, production persistence, storage APIs, migrations, backup or recovery, authentication, OCR, image processing or Excel adapters.

## Lifecycle boundary

PR-S001 remains MERGED AS RESEARCH HARNESS and FINAL ACCEPTANCE NOT ACCEPTED. PR-S001-F1 is COMPLETED AND MERGED THROUGH PR #10. PR-S001-F2 is COMPLETED AND MERGED THROUGH PR #11 with merge commit `7559dbb6189f6e0181eec8a44a7de262cadf036f`. PR-S001-F3 is the CURRENT CORRECTION.

Gate 1 remains NOT ACCEPTED. M2 remains NOT COMPLETED. PR-005 and PR-006 remain UNAUTHORIZED. PR-007 AND LATER remain UNAUTHORIZED.

## Privacy and evidence requirements

Reports must contain only safe identifiers, statuses and reason codes. They must not expose SIDs, usernames, hostnames, paths, command lines, command output, ACL JSON, PowerShell output, icacls output or raw exception text.
