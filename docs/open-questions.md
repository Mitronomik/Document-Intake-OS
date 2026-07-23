# Открытые вопросы

Ответ становится требованием только после явного решения, записи ADR and обновления документов/тестов. Q-001 through Q-020 are retained for decision continuity.

Statuses: `OPEN`, `ACCEPTED`, `DEFERRED`, `EXTERNAL_CONFIRMATION_REQUIRED`, `LOCAL_EVIDENCE_REQUIRED`, `SUPERSEDED`.

## Excel и терминалы

### Q-001

**Question:** Официальное название терминала `visitors_example.xlsx`.

**Status:** EXTERNAL_CONFIRMATION_REQUIRED
**Owner:** Product owner with terminal/operator confirmation.
**Required evidence:** Official operator-facing terminal name for the template currently identified internally as `VISITORS`.
**Target:** Before PR-020 operator-facing/adapter naming.
**Current gate impact:** Does not block M0 or PR-004 under ADR-016 staging rules.
**Implementation block:** Visitors operator-facing labels and adapter naming remain blocked until confirmation exists.
**Placeholder rule:** Do not invent an official display name.

### Q-002

**Question:** Обязан ли TSP принимать именно `.xls`?

**Status:** EXTERNAL_CONFIRMATION_REQUIRED
**Owner:** Product owner with terminal/operator confirmation.
**Required evidence:** Written confirmation whether TSP requires `.xls` output or accepts a separately confirmed `.xlsx` equivalent.
**Target:** Before PR-022.
**Current gate impact:** Does not block M0 or PR-004 under ADR-016 staging rules.
**Implementation block:** TSP output-format strategy remains blocked until confirmation exists.
**Placeholder rule:** Do not choose `.xls` or `.xlsx` silently.

### Q-003

**Question:** Максимальное количество водителей для каждого терминала. Пометка «не более 10» пока не формализована.

**Status:** EXTERNAL_CONFIRMATION_REQUIRED
**Owner:** Product owner with terminal/operator confirmation.
**Required evidence:** Per-terminal maximum participant counts and any terminal-specific enforcement notes.
**Target:** Before applicable terminal adapter/export enforcement.
**Current gate impact:** Does not block M0 or PR-004. Generic terminal-limit and terminal-restriction checks already exist as product capabilities.
**Implementation block:** Adapter/export enforcement of concrete limits remains blocked until confirmation exists.
**Placeholder rule:** Do not formalize “не более 10” without confirmation.

### Q-004

**Question:** Нужно ли вставлять изображения в Excel или достаточно папки рядом? Текущая гипотеза: достаточно папки.

**Status:** EXTERNAL_CONFIRMATION_REQUIRED
**Owner:** Product owner with terminal/operator confirmation.
**Required evidence:** Confirmation whether each terminal accepts adjacent document folders or requires images embedded in the workbook.
**Target:** Before PR-023.
**Current gate impact:** Does not block M0 or PR-004 under ADR-016 staging rules.
**Implementation block:** Export packaging behavior depending on this answer remains blocked until confirmation exists.
**Placeholder rule:** Do not implement image embedding or final folder-only terminal policy from the hypothesis alone.

### Q-005

**Question:** Матрица обязательных документов по терминалу, гражданству, типу пропуска и транспорту.

**Status:** EXTERNAL_CONFIRMATION_REQUIRED
**Owner:** Product owner with terminal/operator confirmation.
**Required evidence:** Terminal-specific required-document matrix by terminal, citizenship, pass type and transport configuration.
**Target:** Before PR-019–PR-023 terminal rules.
**Current gate impact:** Does not block M0 or PR-004. Generic domain responsibility for completeness already exists.
**Implementation block:** Terminal-specific completeness rules remain blocked until confirmation exists.
**Placeholder rule:** Do not invent required-document matrices.

## Изображения

### Q-006

**Question:** Правило склейки: vertical/horizontal, порядок, поля and terminal differences.

**Status:** DEFERRED
**Owner:** Product owner and image/export implementer.
**Reason for deferral:** PR-004 does not render images; merge layout belongs to image workflow.
**Target:** PR-013.
**Current gate impact:** Does not block M0 or PR-004.

### Q-007

**Question:** Минимальные prepared-JPEG readability and post-compression resolution thresholds после пилота.

**Status:** DEFERRED
**Owner:** Product owner and pilot/test owner.
**Reason for deferral:** Final prepared-artifact readability and post-compression resolution thresholds require image-stage implementation and pilot evidence. Scope clarification: Q-007 controls PR-011 prepared-JPEG readability and post-compression resolution thresholds. The PR-009 whole-frame source-quality threshold portion was separated into Q-021. Q-007 no longer blocks PR-009 algorithm or persistence implementation. This preserves historical continuity and does not mark Q-007 accepted.
**Target:** PR-011 and pilot.
**Current gate impact:** Does not block M0 or PR-004, and does not block PR-009 deterministic algorithm or persistence implementation.

## Эксплуатация и безопасность

### Q-008

**Question:** Один ПК, несколько пользователей на одном ПК или несколько ПК?

**Status:** ACCEPTED
**Decision reference:** ADR-017.
**Accepted answer:** First MVP topology is one Windows 11 x64 workstation with one active operator session at a time.
**Owner:** Product owner.
**Target:** M0 / PR-004 topology boundary.
**Current gate impact:** Resolves the M0 topology conflict for PR-004 after the GATE-M0 PR is merged and accepted.

### Q-009

**Question:** Срок хранения originals, artifacts, snapshots, exports, backups and audit.

**Status:** DEFERRED
**Owner:** Product owner with operations/legal input when needed.
**Reason for deferral:** Retention periods and deletion policy are not part of domain-only PR-004.
**Target:** Revisit before storage/audit/backup policy is implemented.
**Current gate impact:** Does not block M0 or PR-004.

### Q-010

**Question:** Encryption and key storage.

**Status:** ACCEPTED
**Owner:** Product owner and security/architecture owner.
**Resolution:** ADR-018 accepted after merge of GitHub PR #7.
**Accepted direction:** Option C — Encryption-first application architecture.
**Decision reference:** ADR-018
**Target:** Resolved before PR-005; PR-005 and PR-006 authorization remain blocked by later gates.
**Current gate impact:** The encryption staging conflict is resolved at the architecture and sequencing level. Production plaintext persistence is prohibited. PR-S001 is authorized, not started. Exact packages, bindings, versions and implementation details remain subject to PR-S001 evidence. PR-005 and PR-006 remain unauthorized, PR-007 and later work remain unauthorized, and no encryption technology has yet been implemented.
**Resolved conflict:** The technical specification requires encrypted database and filesystem storage, while persistence/storage were planned before PR-030 encryption; ADR-018 resolves sequencing by requiring encryption-first architecture before production persistence or storage.
**Placeholder rule:** ADR-018 accepts the architecture direction and candidate technology classes, but does not finally select a package, edition, binding, version or production implementation. Final selection remains blocked until PR-S001 evidence and later explicit authorization.

### Q-011

**Question:** Local accounts, password policy, timeout and recovery.

**Status:** DEFERRED
**Owner:** Product owner and security/implementation owner.
**Reason for deferral:** Actor fields already exist for verification and audit; authentication implementation is not part of PR-004.
**Target:** PR-031.
**Current gate impact:** Does not block M0 or PR-004.

## OCR

### Q-012

**Question:** Обезличенные примеры водительских удостоверений по приоритетным странам.

**Status:** LOCAL_EVIDENCE_REQUIRED
**Owner:** Product owner and local acceptance/test owner.
**Required evidence:** Local-only driver-license evidence by priority country and variant.
**Target:** M6 local OCR evidence.
**Current gate impact:** Does not block M0 or PR-004.
**Privacy rule:** Evidence files remain outside Git, Codex and CI; repository records only non-sensitive summaries.

### Q-013

**Question:** Типы и примеры work permits/patents.

**Status:** LOCAL_EVIDENCE_REQUIRED
**Owner:** Product owner and local acceptance/test owner.
**Required evidence:** Local-only catalog of work permit/patent types and examples sufficient for OCR planning.
**Target:** M6 local OCR evidence.
**Current gate impact:** Does not block M0 or PR-004.
**Privacy rule:** Evidence files remain outside Git, Codex and CI; repository records only non-sensitive summaries.

### Q-014

**Question:** Частотность country/type/version для приоритизации OCR.

**Status:** LOCAL_EVIDENCE_REQUIRED
**Owner:** Product owner and local acceptance/test owner.
**Required evidence:** Local-only aggregate frequencies by country, document type and version for OCR prioritization.
**Target:** M6 local OCR evidence.
**Current gate impact:** Does not block M0 or PR-004.
**Privacy rule:** Evidence files remain outside Git, Codex and CI; repository records only non-sensitive summaries.

## Эксплуатация

### Q-015

**Question:** Будет ли Microsoft Excel установлен на всех рабочих ПК?

**Status:** LOCAL_EVIDENCE_REQUIRED
**Owner:** Product owner and local IT/acceptance owner.
**Required evidence:** Local Windows 11 / Microsoft Excel availability and version evidence for Excel adapter acceptance.
**Target:** Before PR-022/PR-023 and installer acceptance.
**Current gate impact:** Does not block M0 or PR-004.
**Privacy rule:** Local Microsoft Excel availability evidence remains local. Approved PII-free terminal workbooks may be stored in Git after the repository-policy enforcement update and technical privacy inspection. Real application workbooks remain prohibited.

### Q-016

**Question:** Куда сохранять export: local folder, network disk or removable drive?

**Status:** DEFERRED
**Owner:** Product owner and export/package implementer.
**Reason for deferral:** Export destination policy is not part of domain-only PR-004.
**Target:** PR-023.
**Current gate impact:** Does not block M0 or PR-004.

### Q-017

**Question:** Backup destination, owner, frequency and external copy.

**Status:** DEFERRED
**Owner:** Product owner and storage/operations owner.
**Reason for deferral:** Backup policy is not implemented in PR-004.
**Target:** Revisit before PR-006 if it changes storage layout, no later than PR-032.
**Current gate impact:** Does not block M0 or PR-004.

### Q-018

**Question:** Offline update process for application and models.

**Status:** DEFERRED
**Owner:** Product owner and release/installer owner.
**Reason for deferral:** Offline update process belongs to installer/security hardening, not PR-004.
**Target:** PR-033/PR-034.
**Current gate impact:** Does not block M0 or PR-004.

## Future

### Q-019

**Question:** Нужна ли macOS сразу после Windows MVP?

**Status:** SUPERSEDED
**Decision reference:** ADR-002 and NFR-02.
**Accepted answer:** Windows 11 x64 is first; macOS follows Windows stabilization as a separate future build.
**Owner:** Product owner.
**Target:** Future platform planning after Windows stabilization.
**Current gate impact:** Does not block M0 or PR-004.

### Q-020

**Question:** Существует ли официальный согласованный API «Конверсты»? До подтверждения integration не проектируется.

**Status:** DEFERRED
**Decision reference:** ADR-007.
**Owner:** Product owner.
**Reason for deferral:** Direct integration remains outside MVP.
**Target:** Future.
**Current gate impact:** Does not block M0 or PR-004.

## Historical PR-006 lifecycle note

PR-005: `COMPLETED AND HUMAN ACCEPTED`. PR-006: `COMPLETED AND HUMAN ACCEPTED`. PR-007: `COMPLETED AND HUMAN ACCEPTED`. PR-008: `COMPLETED AND HUMAN ACCEPTED WITH DOCUMENTED RESIDUAL RISK`; RISK-PR008-W11-SMOKE: `ACCEPTED FOR PR-008; DEFERRED TO INSTALLER/PILOT/RELEASE`; PR-009: `AUTHORIZED, NOT STARTED`; PR-010 AND LATER: `UNAUTHORIZED`; Gate 1: `COMPLETED AND HUMAN ACCEPTED`. M2: `COMPLETED AND HUMAN ACCEPTED`; Gate 2: `NOT ACCEPTED`; M3: `IN PROGRESS`. Q-009: `DEFERRED`; PR-006 implements immutable stored final artifacts and no retention, deletion or secure-deletion policy. Q-017: `DEFERRED`; PR-006 storage layout is backup-neutral and PR-032 remains responsible for encrypted backup/restore. Real documents and personal data remain prohibited in Git, Codex and CI.

## Lifecycle clarification — PR-007 audit and deferred questions

Q-009: `DEFERRED`. PR-007 may implement immutable append-only audit persistence without implementing retention, deletion or secure deletion. Q-009 still governs future retention and deletion policy. No audit-event deletion API or automatic purge is authorized.

Q-017: `DEFERRED`. PR-006 storage remains backup-neutral. Q-017 remains assigned to the later backup/recovery boundary, no later than PR-032. No backup destination, recovery procedure or recovery ceremony is selected here.

### Q-021

**Question:** PR-009 whole-frame diagnostic policy thresholds.

**Status:** DEFERRED
**Owner:** Product owner.
**Decision:** DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
**Historical acceptance requirement:** Q-021 required explicit product-owner acceptance of a production `policy_id`, `policy_version`, thresholds and severity mapping. That requirement was not met: no candidate, production policy identity, threshold set or severity mapping was accepted.
**Controlled scope:** minimum source-image dimensions for PR-009 diagnostics; blur threshold; contrast threshold; glare cutoff/fraction; exposure cutoffs/fractions; severity mapping; production policy identity and version; and activation of the default PR-009 policy.
**Completed aggregate evidence:** The accepted local calibration contour processed 60 samples, calculated 60 metric sets and had zero failures or failure stages. It used 43 calibration samples, 17 held-out validation samples, 54 Pareto candidates and a `CALIBRATION_ONLY` search scope. No policy was accepted or selected.
**Accepted narrow conclusion:** The current PR-009 V1 whole-frame metrics, current candidate search space and tested severity combinations did not produce an acceptable production quality policy on the completed local Q-021 calibration and validation set. This result does not establish universal failure of the algorithms.
**Aggregate observations:** Maximum listed validation exact was `0.411765`. Candidates with zero calibration missed RETAKE still had at least one validation missed RETAKE and between six and nine validation false RETAKE results. UNDEREXPOSED recall was zero for all listed candidate roles; BLUR_DETECTED and OVEREXPOSED were more promising; GLARE_DETECTED, LOW_CONTRAST and LOW_RESOLUTION remained insufficiently reliable.
**Reason for deferral:** The V1 metrics and searched policies were not sufficiently reliable on the local validation set, so no production default may be activated. Future resolution requires a separate versioned metric-separability improvement, local recalibration and explicit product-owner acceptance. V1 formulas and persisted algorithm identities must not be changed silently.
**Current gate impact:** PR-009 was later completed and human accepted through PR-009-D4 after GitHub PR #24 merged on 2026-07-22 from reviewed head `72c01662031f73985f8715d6c3c87abf7aa5c4db` at merge commit `b491226878cabfc87c484f6a4d41bc2969851273`. Q-021 no longer blocks human acceptance or merge of the explicit-policy PR-009 infrastructure. It continues to block selection or activation of a production default quality policy, assignment of production `policy_id`, assignment of production `policy_version`, automatic quality-based blocking, automatic production `RETAKE_REQUIRED` enforcement and any claim that PR-009 thresholds are calibrated for production.
**Residual limitation:** `RISK-PR009-NO-PRODUCTION-QUALITY-POLICY` is open and accepted for the PR-009 infrastructure and human-acceptance boundary. Production composition must fail closed when no accepted policy is configured, and no document may be automatically rejected, deleted, suppressed or blocked using an unaccepted PR-009 policy. Explicit synthetic policies remain allowed in tests and verifiers.
**Placeholder rule:** Do not silently select final production thresholds or use real-document fixtures.
**MPO compatibility clarification:** The 2026-07-22 product-owner decision accepts Pillow-detected MPO as JPEG with only primary frame 0 decoded, immutable original bytes and ignored secondary frames. It resolves only a JPEG input-compatibility gap and does not accept any Q-021 threshold, severity mapping, policy activation or final PR-009 human acceptance.


## PR-009 calibration lifecycle update — 2026-07-22

ADR-023: ACCEPTED.
PR-009: IMPLEMENTED AND READY FOR HUMAN ACCEPTANCE WITH DOCUMENTED RESIDUAL LIMITATION.
Q-021: DEFERRED — NEGATIVE CALIBRATION EVIDENCE ACCEPTED; NO PRODUCTION POLICY SELECTED.
Production default PR-009 quality policy: NOT ACTIVE.
RISK-PR009-NO-PRODUCTION-QUALITY-POLICY: OPEN AND ACCEPTED FOR THE PR-009 INFRASTRUCTURE MERGE BOUNDARY.
PR-010 AND LATER: UNAUTHORIZED.
Gate 2: NOT ACCEPTED.
M3: IN PROGRESS.

Human acceptance and merge remain separate product-owner actions after review and exact-head CI. PR-010 and later remain unauthorized until a separate post-merge product-owner decision.

## PR-009 human acceptance lifecycle state — 2026-07-22

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

GitHub PR: #24.
Final reviewed head: `72c01662031f73985f8715d6c3c87abf7aa5c4db`.
Merge commit: `b491226878cabfc87c484f6a4d41bc2969851273`.
Merge date: 2026-07-22.

This current PR-009-D4-backed section supersedes earlier historical lifecycle snapshots for current status only. It does not rewrite those historical records and does not authorize PR-010 production implementation or PR-011 and later work. FR-04 remains incomplete because geometry, document regions and later image-preparation work remain future scope.
