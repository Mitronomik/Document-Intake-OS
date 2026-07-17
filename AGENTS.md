# AGENTS.md

## Project

Document Intake OS is an offline Windows desktop application for importing driver and vehicle document photographs, non-destructive image preparation, local OCR/MRZ/barcode recognition, operator verification, local persistence, JPEG generation under 1.90 MiB, and Excel export for three real terminal templates.

## Authoritative sources

Read before changing code. Canonical source priority is:

1. `docs/technical-specification.md`
2. `docs/decisions.md`
3. `docs/product-spec.md`
4. `docs/architecture.md`
5. `docs/domain-model.md`
6. `docs/security.md`
7. `docs/testing-strategy.md`
8. current PR task under `docs/tasks/`

A lower-priority document must not override a higher-priority source. If documents conflict, stop and report the conflict instead of resolving it silently.

## Hard constraints

1. No real personal documents or personal data may be committed.
2. No runtime feature may upload documents or extracted data to an external service.
3. OCR, image processing, persistence and export must work offline.
4. Original source files must never be modified or overwritten.
5. OCR values remain drafts until explicitly verified.
6. Passport numbers, birth dates, validity dates, VINs, vehicle registrations and trailer registrations are critical fields.
7. Unverified or conflicting critical fields may not be exported.
8. Prepared documents must be RGB JPEG files no larger than 1.90 MiB.
9. Preserve exact Excel sheet names, headers, comments, validations, formatting, workbook structure and required file format.
10. Do not add telemetry, analytics, cloud OCR, cloud storage, external AI APIs or external error reporting.
11. Do not implement direct Konversta submission or browser automation in MVP.
12. Export must use an immutable application snapshot.
13. Never log complete identity numbers, phones, addresses, OCR payloads or MRZ.
14. Excel adapter changes require golden-file tests.
15. Security or data-integrity architecture changes require an accepted ADR.

## Architecture

- `domain`: entities, value objects, policies and invariants.
- `application`: use cases, DTOs and ports.
- `persistence`, `storage`, `recognition`, `image_pipeline`, `terminal_adapters`: port implementations.
- `ui`: invokes application services and contains no domain rules.

Forbidden:

- UI direct SQLite access;
- UI direct OCR calls;
- UI direct workbook editing;
- domain imports of PySide6/OpenCV/OCR/database libraries;
- OCR mutating verified data;
- export reading mutable records after snapshot creation.

## Coding standards

- Python 3.12.
- Public APIs require type annotations.
- Prefer immutable domain value objects.
- Use `pathlib.Path`.
- Use UTC internally.
- Store dates as typed dates or ISO values.
- Store passport numbers, VINs, phones and registrations as strings.
- Preserve leading zeros.
- Use explicit enums.
- Database changes require migrations.
- File writes must be atomic where practical.
- Every stored file has SHA-256.
- Errors must be typed and actionable.

## Fixtures and public repository rules

While the repository is public, fixture rules have two states.

### Current enforcement state

Until the repository-policy enforcement PR is merged, tracked fixtures remain limited by the current scanner and `.gitignore`:

- synthetic source-code tests that contain no document-derived layout or personal data;
- fictional scalar values only when they contain no document-derived layout or personal data;
- synthetic document fixtures only in currently permitted paths.

No Excel template or template-derived binary artifact may be committed yet.

### Product-policy state after enforcement update

After technical privacy inspection and the repository-policy enforcement PR:

- the three approved source templates may be tracked;
- approved structural template fixtures may be tracked;
- PII-free binary golden files may be tracked;
- synthetic output workbooks may be tracked;
- PII-free structural screenshots, manifests and mappings may be tracked.

While the repository is public, forbidden fixtures and artifacts include:

- real passports, migration cards, licenses and vehicle documents;
- scans, photographs or screenshots derived from real documents;
- real names, phones, addresses and identifiers;
- birth dates belonging to real people;
- VINs, vehicle registration numbers and trailer registration numbers;
- production databases, database journals, backups and screenshots;
- OCR outputs and MRZ payloads from real documents;
- logs containing operational data;
- secrets, keys, passwords, certificates and tokens;
- private fixtures and local acceptance fixtures;
- terminal templates or template-derived artifacts outside the three product-owner-approved templates and their PII-free technical derivatives.

ADR-016 permits the three approved terminal templates (`TSPMAINFILE.xls`, `visitors_example.xlsx`, `MGSMAINFILE.xlsx`) and PII-free technical derivatives after repository-policy enforcement is updated and technical privacy inspection passes. Permitted derivatives may include cleaned, anonymized or empty structural copies, binary golden files and synthetic output workbooks with fully fictional values, structural screenshots, real checksums, extracted manifests, mappings and workbook structural metadata. These artifacts must not contain real personal data, real application rows, real document images, OCR/MRZ payloads from real documents, secrets, credentials, confidential connection strings or confidential paths.

## Repository policy guardrail

Before submitting a change, run:

```bash
python scripts/check_repository_policy.py
```

Do not bypass or weaken policy checks. Do not add allowlist exceptions without an accepted ADR when privacy or data boundaries are affected. No real documents, private fixtures, PII-bearing workbooks or secret-bearing files may be used to make a test pass. Product policy permits the three approved PII-free terminal templates and technical derivatives, but the current scanner and `.gitignore` remain temporarily more restrictive; before the first permitted binary artifact is committed, a separate repository-policy enforcement PR must update the scanner, `.gitignore` and related tests.

## Required checks

```bash
python scripts/check_repository_policy.py
uv sync --locked --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src scripts/check_repository_policy.py
uv run pytest -ra
uv build
```

Image tests prove immutable originals, EXIF handling, RGB JPEG, ≤1.90 MiB and determinism.

Recognition tests prove source/confidence, versioned runs, MRZ conflicts and no mutation of confirmed values.

Export tests prove snapshot creation, exact template preservation and safe failure behavior.

## Pull requests

Each PR must:

- solve one coherent task;
- state scope and non-goals;
- list changed modules;
- include tests and manual verification;
- update docs and `docs/progress.md`;
- avoid unrelated refactors.

Before implementation report understanding, planned files, risks and test plan.

After implementation report files changed, decisions, commands, exact test results, manual steps and limitations.
