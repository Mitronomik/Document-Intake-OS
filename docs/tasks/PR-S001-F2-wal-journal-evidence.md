# PR-S001-F2 — WAL and rollback-journal evidence correction

**Status:** CURRENT CORRECTION

## Scope

Create a synthetic-only research-harness correction for SQLCipher auxiliary-file evidence:

- demonstrate WAL mode activation using a dedicated `wal-probe.db` lifecycle;
- demonstrate rollback-journal activation using a dedicated `journal-probe.db` lifecycle;
- use ordinary SQLite control databases to prove marker scanning is non-vacuous;
- inspect exact expected `-wal` and `-journal` files while the relevant connection or transaction remains active;
- keep safe reports sanitized with stable reason codes only.

## Lifecycle boundaries

- PR #9 / PR-S001 was merged as a synthetic-only research harness.
- PR-S001 final acceptance is **NOT ACCEPTED**.
- PR #10 / PR-S001-F1 completed and merged connection cleanup and ACL evidence correction at merge commit `b9c07a0c2b152bdad21e5d50126917c55b349e12`.
- PR-S001-F2 is the current correction.
- Gate 1 remains **NOT ACCEPTED**.
- M2 remains **NOT COMPLETED**.
- PR-005 remains **UNAUTHORIZED**.
- PR-006 remains **UNAUTHORIZED**.

## Non-goals

This task does not implement production persistence, storage, migrations, backup/recovery, authentication, final key hierarchy, OCR, image processing, Excel adapters, Windows installer, final SQLCipher licensing approval, or Windows 11 x64 acceptance.

## Verification expectation

Local platform-independent tests cover decision semantics and report sanitization. Actual SQLCipher auxiliary-file evidence remains a Windows CI/integration concern. Windows 11 x64 remains `NOT_DEMONSTRATED` until separately accepted.
