# PR-S001-F1 — Windows cleanup and ACL evidence correction

Status: CURRENT CORRECTION.

PR #9 merged PR-S001 as an isolated synthetic Windows encryption feasibility research harness. PR-S001 remains not accepted as final feasibility evidence, Gate 1 remains NOT ACCEPTED, M2 remains NOT COMPLETED, and PR-005/PR-006 remain UNAUTHORIZED.

This follow-up is limited to deterministic evidence defects from the Windows harness run:

- explicitly close the ordinary SQLite connection used to prove SQLCipher rejection;
- replace generic ACL evidence with specific current user, SYSTEM, Administrators, broad-write and directory-cleanup checks;
- preserve safe-report privacy boundaries and keep the final research recommendation unchanged until corrected Windows evidence is available.

Non-goals: WAL evidence, rollback-journal evidence, recommendation policy, production persistence/storage, CI workflow changes, and PR-005/PR-006 authorization.
