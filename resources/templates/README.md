# Terminal templates

Only approved and cleaned terminal templates may be committed here.

Required paths:

- `tsp/TSPMAINFILE.xls`
- `visitors/visitors_example.xlsx`
- `mgs/MGSMAINFILE.xlsx`

Before commit verify:

1. no real names, phones, passport numbers, addresses, VINs or registrations;
2. sheet names are unchanged;
3. exact headers are unchanged;
4. comments, validations, formatting and service sheets remain intact;
5. the workbook opens without repair;
6. the SHA-256 checksum is recorded in `template-checksums.sha256`.

Do not edit templates directly during export. Adapters must work with copies.
