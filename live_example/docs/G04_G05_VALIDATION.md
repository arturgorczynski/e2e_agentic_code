# G04 and G05 validation

Completed on **2026-10-15**, Windows PowerShell, Python **3.12.12**, SQLite **3.50.4**,
uv **0.10.2**, Ruff **0.17.1**, with the existing lockfile. No Docker, external database,
model inference, cloud credential or original source-workbook download was required.

## Delivered artifacts

- [Schema](../acme/schema.sql), [dictionary](data_dictionary.md) and
  [operational rules](../acme/company_data.py): 35 linked, populated tables.
- [Compressed baseline](../data/company/baseline/company.sqlite.gz),
  [content manifest](../data/company/baseline/manifest.json),
  [preparation report](../data/company/baseline/preparation_report.json) and
  [validation report](../data/company/baseline/validation_report.json).
- [Document catalog](../data/documents/catalog.json), 148 fixed Markdown versions
  under `data/documents/content/`, and nine hand-authored core policy sources.
- [Source-and-answer map](../evals/source_answer_map.json), outside company search.
- [Build/verify/init/reset guide](company_data.md) and
  [document guide](company_documents.md).

The compressed database is **46,971,445 bytes**, expanding to **310,202,368 bytes**.
The baseline is a distinct immutable distribution artifact; exercise initialization
creates a writable copy. This is not OS-level protection against repository edits.

## Full dataset scale

| Records | Count |
| --- | ---: |
| Departments / locations / warehouses | 10 / 3 / 2 |
| Employees / effective assignments | 200 / 200 |
| Customers / customer contacts | 3,832 / 3,832 |
| Addresses / suppliers | 3,839 / 7 |
| Products / categories | 3,585 / 7 |
| Price observations | 259,652 |
| Orders / order items | 15,213 / 259,652 |
| Order status events | 35,526 |
| Invoices / invoice items | 15,212 / 259,651 |
| Payments / payment allocations | 18,736 / 18,736 |
| Credit notes | 1 authored goodwill-credit scenario |
| Shipments / shipment items | 20,312 / 275,203 |
| Inventory positions / stock movements | 3,586 / 306,188 |
| Purchase orders / purchase lines / goods receipts | 92 / 27,400 / 27,399 |
| Tickets / ticket events | 5,464 / 16,290 |
| Forecast runs / forecasts / simulated sales targets | 7 / 73 / 73 |
| Documents / versions / record links | 147 / 148 / 192 |

The validator compared **all 259,639 selected public source lines** with G03, preserving
all **15,201 complete eligible baskets** and their invoice, customer, product, quantity,
raw price and posting-day identities. The other 12 orders and 13 order lines are in the
authored DEMO namespace. Unselected public anomalies/cancellations remain intact in G03.
No unrelated public dataset was joined to manufacture customer relationships.

## Reconciliation and lifecycle evidence

`acme company verify` recomputed the checks on the shipped database rather than trusting
the saved report. Its successful report records 267 named checks, including per-forecast
and scenario checks. Whole-table queries establish:

- SQLite integrity and no foreign-key orphans; all 35 tables populated.
- Exactly 200 employees and the prescribed headcount in each of ten departments.
- Invoice headers equal lines; billed lines match their orders; every posted amount
  independently recomputes from exact Decimal prices with half-up line rounding.
- Payment allocations conserve each payment, belong to the right customer, follow
  valid dates, and do not over-settle an invoice after credit notes.
- Shipment quantities never exceed orders; every dispatched line and received purchase
  line has its matching stock movement, warehouse, product, date and signed quantity.
- Inventory ending balances reconcile, chronological balances never go negative, and
  reservations equal outstanding uncancelled Coventry order quantities.
- Purchase-line suppliers match the catalog and receipt totals agree with open/received
  status. Monthly supplier batches have multiple linked product lines.
- Order and ticket histories reach their current states through valid dates. Partial
  dispatch, incomplete delivery confirmation, outstanding balances and a pre-billing
  cancellation are represented explicitly.

The small fixture uses the identical schema/rules/validators, the first 40 eligible
source baskets, all DEMO business scenarios, 20 employees and a reduced 66-document
collection. It is a separate profile, not a different business implementation.

## Forecast information boundary

Forecast versions average the preceding three or two full months of billed units.
Generation records include reconstructed UTC time, cutoff, target period, method,
version, training totals, last input date and a hash of exact ordered input records.
The 12 source-product subjects are chosen only from activity before 2011-10-01.

Two negative/sensitivity tests establish the boundary:

1. Changing November actual quantities leaves the November forecast and its input
   fingerprint unchanged. Changing October training quantities changes both.
2. Increasing future source activity dramatically does not change the earlier selected
   forecast product cohort.

Every stored forecast was regenerated from its bounded inputs and compared with the
saved value/fingerprint. Sales targets remain labeled simulated stretch targets.
Retrospective inventory reconstruction is explicitly distinguished from forecasting.

## Scenario evidence

The private source map resolves all twelve scenarios to existing records, computed-view
aliases, document versions or explicitly later application fixtures. Recomputed facts
include GBP 700 / nine days overdue (S01), 20 and zero outstanding units (S02), 15
available / 15 short / 80 inbound units (S03), an open complaint (S04), GBP -2,500 /
-25% sales change (S05), and 1,000 forecast versus 850 actual units (S06).

Both return-policy versions exist with the correct effective intervals and 14/30-day
text (S11); the requested nonexistent order is absent (S12). S07/S08 report inputs,
S09 role definitions and S10 private-record ownership fixtures are available. Actual
report writes, approvals, restarts, role denial and owner isolation remain explicit
G06–G11 runtime acceptance gates. A proposed report is not falsely seeded as already saved.

## Document review

The full corpus has nine policies, 18 procedures, 40 product guides, 25 customer terms,
ten department instructions, 25 incident notes and 20 planning notes. All 148 versions
were validated for content hashes, metadata, effective intervals, real FK links, owner,
scope, record-derived facts, and corresponding factual statements in the prose.

Representative content was read from every category:

| Reviewed document | Substance checked |
| --- | --- |
| `POL-RETURNS-001:v1` and `:v2` | Superseded 14-day rule versus current 30-day rule; dates, evidence requirements and no retroactive selection |
| `PROC-008:v1` | Receiving sequence, actual goods-receipt ID, purchase-line/stock-movement reconciliation and escalation |
| `PROD-001:v1` | Real source product 85123A, 1,518 selected lines / 33,585 units, modeled stock 53/41/12, category handling and source-price limitations |
| `TERMS-001:v1` and `TERMS-002:v1` | Account-specific purchasing coverage; UK versus EIRE 30/45-day modeled terms; no leaked payment balances |
| `DEPT-001:v1` | Eight actual analytics assignments, department remit, handoffs and ownership boundaries |
| `INC-001:v1` | Actual open damaged-goods case, order/customer links, one-event timeline and approval boundary |
| `PLAN-001:v1` and `PLAN-002:v1` | Same product/period with 684 versus 834 forecast units, three/two-month inputs, exact fingerprints and partial-December caveat |

Review corrected product-guide scope to **operations**, because those documents expose
stock and supplier facts. Forecast subjects were selected from pre-cutoff activity to
make the planning examples useful while preserving the information boundary. Snapshot
documents use the as-of date; incident notes cannot precede their latest included event.

All documents have a specific record, policy or workflow purpose. Category-specific
templates contribute usable instructions; repeated common language is not counted as
additional documents. No model-drafted text or PDF/DOCX generation is needed at startup.

## Reproduction and checksums

Two final full builds, `artifacts/g04-release` and
`artifacts/g04-release-reproduced`, produced the same 35 table hashes, document catalog
hash and logical content hash. After publishing the first bundle under `data/`, every
baseline file also matched the reproduced file byte for byte: database archive,
manifest, preparation report and validation report.

Logical content SHA-256:
`4106def0585c2d0f40bc31e87bc597f798f4ef009a3571777ee5ad8f8c89d755`

Compressed archive SHA-256:
`bafe1c6fdd31955f6fa0a442fb66cacec973b1e70c6506d252d334fc535250bb`

Document catalog SHA-256:
`b42c883d0b89bb7e5a34f9f97039f63c456663c72770c938fdaab2d846e03723`

Use a new output directory to repeat:

```powershell
uv run --locked acme company build --profile full --output-dir artifacts/my-rebuild
uv run --locked acme company verify --data-dir artifacts/my-rebuild
```

Reproducibility was exercised on this Windows/Python/SQLite runtime. Other operating
systems were not tested; canonical logical rows, rather than SQLite file layout, are
the portable identity criterion.

## Installation, state preservation and tests

A clean copy outside the repository installed with `uv sync --locked --offline` using
the warmed cache. It had no parent imports, `.env`, prior environment or raw UCI workbook.
CLI help/version, G03 source verification and full G04/G05 verification passed. Company
initialization returned `initialized`, then `preserved` on the second call. All **34
tests** and Ruff passed. Lockfile identity and package import location were checked.

Retained copy:
`C:\Users\Komputer\AppData\Local\Temp\acme-g01-c815ne9j`.
The G01-named prefix is the existing standalone verifier's directory convention.

The suite also modifies an exercise ticket, proves another initialization preserves
the exact database bytes, rejects CLI reset without `--yes`, and proves an explicitly
requested reset restores logical baseline records while preserving an unrelated file.
Unknown existing state without a receipt is preserved with an error. Deliberate orphan,
invalid-quantity, finance, stock, source-line and document-fact corruptions are rejected.

After the standalone run, verification additionally gained direct schema/source-pin
checks; the final shipped full dataset passed that updated `company verify` command.
All 34 tests were rerun successfully on that final worktree, and Ruff passed. Local
documentation links and dictionary coverage of all 35 tables were also checked.
Windows temporary-directory checks required access
outside the execution sandbox; cached dependency installation copied files across drives.

Required parent import-layout checks were run. Teaching-source discovery and Python
module layout passed. The unchanged existing summarization notebook still has one
failing subtest and two execution errors from a function/`@register_cell_magic` in its
import cell. This is the previously recorded G01/G03 issue, not a new data-module failure.

No parent model factory, root `.env`, teaching notebook or historical execution artifact
was changed. G04 and G05 are complete; the next milestone is company tools and mock
integrations. This release does not claim a running agent, retrieval engine, login or UI.
