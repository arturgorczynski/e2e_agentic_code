# G02 and G03 validation

Verified on **2026-10-15**, Windows PowerShell, Python **3.12.12**, uv **0.10.2**,
Ruff **0.17.1**, using the unchanged project lockfile. No Docker, model inference,
cloud credentials, application server or SQL server was required.

## G02: company and scenario contracts

- [Company brief](company.md) and [company.json](../data/company/company.json):
  product/customer assumptions, ten departments totaling a 200-person target, three
  locations, five named employee/account definitions and five business roles.
- GBP, exact decimal unit prices, future integer-pence postings, explicit rounding,
  Europe/London business time and a fixed 2011-12-09 reference. Execution timestamps
  remain current UTC. The source timezone interpretation is marked as an assumption.
- [Twelve scenario contracts](../evals/g02_scenarios.json) each include a prompt,
  records, policy IDs, inputs, facts, permissions, tools and objective acceptance.
- [Three paper walkthroughs](learning_scenarios.md) cover a receivable, split shipment
  and edited report approval. One agent and eight planned tools cover the inventory;
  private-conversation access is an application check before invoking the agent.
- Five contract tests validate links, role feasibility, organization totals, clock,
  independently recomputed scenario amounts, effective dates, negative cases and
  separation of expected answers from `data/documents/`.

These are executable **design checks**, not live-agent or authentication tests.
The remaining 195 employee records and operational scenario records belong to G04;
the versioned policy corpus belongs to G05. Tool enforcement, approval persistence,
conversation ownership and UI journeys remain G06–G13 requirements.

## G03: actual source acquisition and profile

Downloaded the official [UCI Online Retail archive](https://archive.ics.uci.edu/dataset/352/online%2Bretail).
The [source manifest](../data/sources/manifest.json),
[download receipt](../data/sources/download_receipt.json) and
[attribution](../data/sources/ATTRIBUTION.md) record origin, author, DOI, CC BY 4.0,
redistribution conditions, transformations and locally measured content identities.
Wide World Importers remains a design reference; no assets or records were copied.

| Measurement from the downloaded workbook | Result |
| --- | ---: |
| Source rows, all retained | 541,909 |
| Invoice groups, all retained | 25,900 |
| Identified customer IDs | 4,372 |
| Stock codes, including special codes | 4,070 |
| Missing customer IDs | 135,080 |
| Missing descriptions | 1,454 |
| Exact duplicate rows after first occurrence | 5,268 |
| Cancellation-prefixed lines | 9,288 |
| Other adjustment-prefixed lines | 3 |
| Negative quantities | 10,624 |
| Zero quantities | 0 |
| Negative prices | 2 |
| Zero prices | 2,515 |
| Absolute quantity above 1,000 | 174 |
| Price above GBP 1,000 | 120 |
| Near-penny serialization residuals, within 1e-10 GBP | 51,170 |
| Material fractional-penny prices | 4 |
| Eligible complete sale invoices | 15,201 |
| Rows in those complete invoices | 259,639 |

Dates span **2010-12-01 08:26:00 through 2011-12-09 12:50:00** in source wall time.
Signed quantity ranges from -80,995 to 80,995; raw unit price ranges from GBP -11,062.06
to 38,970. The [machine-readable profile](../data/company/prepared/profile.json)
also reports rows by country and month. December 2011 is partial.

Missing records and anomalies are flagged, not silently removed. An eligible invoice
must pass the rule with every line; one invalid line excludes its entire group from
that baseline selection. The shipped staging data still includes that group in full.
Cancellation-to-sale linkage is not inferred. [Field mapping](source_mapping.md)
distinguishes observed source facts from future reconstructed orders, fictional
identities, payments and forecasts.

## Content identity and reproduction

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Downloaded ZIP, ignored locally | 23,715,478 | `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b` |
| Original workbook inside ZIP | 23,715,344 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Shipped transactions.csv.gz | 9,793,573 | `cb6dd2fcfb8496aac2f5bd7a4c7c95fb3dc0260d71613596bfc76e8d87273fa4` |
| Shipped invoice_groups.csv.gz | 306,974 | `3798d828636246becc9100a1594b1900cb2ee61344a57a067fcf776f8278b76d` |
| Shipped profile.json | 3,112 | `bd5f58dd75df48fd33f342cb979e58ecaa987e033f9b6b03974bf9a84a382e72` |

Ran a full second preparation from the pinned raw archive into `artifacts/reproduced`.
**All four generated files matched byte for byte**, including the output manifest.
The second output also passed the data verifier: 541,909 rows and 25,900 complete groups.
This proves reproduction in the tested runtime; macOS/Linux and other Python/zlib
versions have not been exercised. JSON/CSV use UTF-8 and explicit LF, and gzip stores
neither a variable filename nor a current modification timestamp.

```powershell
uv run --locked acme data fetch
uv run --locked acme data prepare
uv run --locked acme data verify
uv run --locked acme data prepare --output-dir artifacts/reproduced
uv run --locked acme data verify --output-dir artifacts/reproduced
```

Six source-data tests cover date/price decoding, anomaly flags, duplicate retention,
whole-invoice eligibility, deterministic fixture output, rejected wrong workbook
formats, corrupted source/prepared checksums, missing manifest entries, and full
shipped-data integrity. Learners can verify the shipped files without the raw archive.

## Standalone installation and regression checks

| Check | Result |
| --- | --- |
| Independent project: `python -B -m unittest discover -s tests -v` | 22 tests passed |
| Independent project: `ruff check .` | Passed |
| Full second preparation and file-hash comparison | All four generated files identical |
| Clean external copy: `uv sync --locked --offline` | Passed using cached dependencies |
| External copy: CLI help, version and `acme data verify` | Passed |
| External copy: all 22 tests and Ruff | Passed |
| External copy: package import origin and unchanged lockfile | Passed |
| Parent: teaching-project discovery boundary and Python import layout | Passed |
| Parent: notebook import-cell checks | Existing summarization notebook failed; see below |

The reproducible standalone check is:

```powershell
uv run --locked python scripts/verify_independence.py
```

Retained verified copy:
`C:\Users\Komputer\AppData\Local\Temp\acme-g01-ga4f6zj7`.
The script excludes `.env`, `.venv`, caches and `data/sources/raw/`; it installed a new
environment and verified the prepared data without fetching anything. The original
`acme-g01-` prefix is just the verifier's temporary-directory naming convention.
Windows tests and the clean-copy check needed temporary-directory access outside the
execution sandbox. uv copied cached packages across drives after hardlink fallback.

The required parent command was also run from the course root:

```powershell
.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_import_layout.py -v
```

It reports one failing subtest and two errors, all in the existing
`notebooks/06_middlewares/01_summarization.ipynb`: its first code cell includes a
function definition with `@register_cell_magic`, and executing that cell outside an
IPython shell raises `NameError`. This was already recorded in G01. No notebook,
historical execution artifact, parent model factory or root `.env` was changed here.

G02 and G03 acceptance is complete. This does not claim a populated Acme ERP database,
running agent, full document corpus, authentication, UI or end-to-end release.
