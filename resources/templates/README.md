# Terminal template policy marker

This directory is intentionally empty in the current tracked tree except for this policy marker.

ADR-016 permits the three approved source templates — `TSPMAINFILE.xls`, `visitors_example.xlsx` and `MGSMAINFILE.xlsx` — and their PII-free technical derivatives after a repository-policy enforcement PR updates scanner and `.gitignore` rules and after each artifact passes technical privacy inspection.

Do not add the actual Excel templates, screenshots, manifests, mappings or binary golden files in GATE-M0 / PR #5.

Before the first approved template artifact is committed, the enforcement PR must define approved paths, provenance rules, synthetic-data-only golden-file rules and continued blocking of real documents, PII, databases, logs, backups, OCR/MRZ payloads from real documents and secrets.

Adapters must never modify source templates in place.
