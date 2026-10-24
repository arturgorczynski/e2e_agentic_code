# Company dataset

`company.json` defines the G02 organization, fixed business clock, role/account
design and operative policy contracts. It contains authored fictional facts.

`prepared/` contains the complete normalized UCI transaction staging dataset from
G03, its profile, invoice membership and checksums. It is usable locally without
source downloads. See [source attribution](../sources/ATTRIBUTION.md).

`baseline/` contains the v8 compressed, validated 35-table company database, its logical
content manifest, preparation report and validation report. It includes all 200
employees and the authored operational scenarios. `acme company init` creates a
separate writable exercise copy; installation and module imports do not seed anything.
The v8 bundle pairs non-numbered fictional trading names and plausible billing
labels with varied authored supplier and employee records, distributed sales
portfolios, weekday order and dispatch histories, grouped account remittances,
sampled support histories, and weekly supplier replenishment. See
[data quality](../../docs/DATA_QUALITY.md)
for provenance and the non-destructive migration of an existing exercise copy.

See the [data guide](../../docs/company_data.md) and
[dictionary](../../docs/data_dictionary.md). Public transaction staging, reconstructed
operational history and authored scenario records remain distinct sources of evidence.
