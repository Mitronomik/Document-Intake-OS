# AGENTS.md

## Project

Document Intake OS is an offline Windows desktop application for importing driver and vehicle document photographs, non-destructive image preparation, local OCR/MRZ/barcode recognition, operator verification, local persistence, JPEG generation under 1.90 MiB, and Excel export for three real terminal templates.

## Authoritative sources

Read before changing code:

1. `docs/technical-specification.md`
2. `docs/decisions.md`
3. `docs/product-spec.md`
4. `docs/architecture.md`
5. `docs/domain-model.md`
6. `docs/security.md`
7. `docs/testing-strategy.md`

If documents conflict, stop and report the conflict.

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

While the repository is public, allowed fixtures are limited to:

- synthetic source-code tests that contain no document-derived layout or personal data;
- fictional scalar values only when they contain no document-derived layout or personal data.

While the repository is public, forbidden fixtures and artifacts include:

- real passports, migration cards, licenses and vehicle documents;
- scans, photographs or screenshots derived from real documents;
- real names, phones, addresses and identifiers;
- birth dates belonging to real people;
- VINs, vehicle registration numbers and trailer registration numbers;
- production databases, database journals, backups and screenshots;
- OCR outputs and MRZ payloads;
- logs containing operational data;
- secrets, keys, passwords, certificates and tokens;
- private fixtures and local acceptance fixtures;
- cleaned terminal templates;
- anonymized terminal templates;
- template-derived golden Excel files.

Cleaned or anonymized terminal templates may be allowed only after:

1. the repository is moved into an approved private contour;
2. repository visibility is reviewed;
3. the security decision is recorded;
4. the files are separately approved.

## Required checks

```bash
uv sync --locked --all-extras --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src
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
