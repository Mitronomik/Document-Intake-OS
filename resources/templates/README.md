# Terminal template directory policy

This repository is temporarily public under ADR-014. While it remains public, this directory may contain only this `README.md` policy marker.

Terminal templates are prohibited here, including cleaned, anonymized, empty, and sample templates. Template-derived golden files are also prohibited.

Checksums, manifests, screenshots, exports, and sidecar files derived from real terminal templates are prohibited. Real file names, sheet structures, mappings, or template-derived examples must not be added merely as placeholders.

Before any template-related file is introduced:

1. repository visibility must be reviewed;
2. a private development contour must be approved;
3. the exact files must receive separate approval;
4. golden-file handling must be defined.

Adapters must never modify source templates in place.
