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

**Question:** Минимальные readability/resolution thresholds после пилота.

**Status:** DEFERRED
**Owner:** Product owner and pilot/test owner.
**Reason for deferral:** Final thresholds require image-stage implementation and pilot evidence.
**Target:** PR-009/PR-011 and pilot.
**Current gate impact:** Does not block M0 or PR-004.

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
