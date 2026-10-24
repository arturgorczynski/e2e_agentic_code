# Public data preparation and field mapping

## Source selection

Use **UCI Online Retail**, dataset 352, donated by Daqing Chen in 2015,
DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33). It describes a UK online
retailer selling gift items, with many wholesale customers, during 2010–2011.
See the [official source](https://archive.ics.uci.edu/dataset/352/online%2Bretail).

Wide World Importers is a design reference for purchasing, stock, partial fulfillment,
invoicing and settlement. Its transactions, people and geography are **not imported**
or joined to UCI. Microsoft identifies the sample-code license as MIT; no code, backup,
data or documentation text from that sample is redistributed in this milestone.

## Reproduce the preparation

From `live_example/`, after `uv sync --locked`:

```powershell
uv run --locked acme data fetch
uv run --locked acme data prepare
uv run --locked acme data verify
```

Only `fetch` uses the network. It downloads the official archive to the ignored
`data/sources/raw/online_retail.zip`. The versioned download receipt pins the archive
hash; both an existing cache and a re-download must match it. An upstream change
requires deliberate source/version review rather than silently replacing the pin.
The first acquisition was HTTPS from UCI, with no upstream published checksum available;
the recorded hash is a locally measured content identity, not a publisher signature.

`prepare` checks that hash before reading the fixed `Online Retail.xlsx` member.
It uses a small standard-library XML reader for the known eight-column worksheet;
it does not execute formulas, alter the workbook, or extract arbitrary archive paths.
Unexpected headers or a different Excel date system fail preparation.

The prepared files are already included under `data/company/prepared/`. Learners
only need `acme data verify`; they need neither the raw workbook nor spreadsheet
libraries, downloads, a model, Docker, or an application database.

To prove reproducibility without replacing the shipped artifacts:

```powershell
uv run --locked acme data prepare --output-dir artifacts/reproduced
uv run --locked acme data verify --output-dir artifacts/reproduced
```

Compare the two `manifest.json` files: identical file hashes prove that the profile,
normalized rows and group manifest match. Preparation writes only its requested
output directory; it does not initialize or reset an application database. `prepare`
intentionally replaces its generated staging artifacts, so use an alternate output
directory when inspecting an older version.

## Source-to-Acme mapping

| Source | Prepared field | Interpretation and future G04 mapping |
| --- | --- | --- |
| Workbook sheet and row | `source_row_id` | `UCI352:Sheet1:<Excel row>`, header excluded; stable audit identity independent of business ID |
| `InvoiceNo` | `invoice_no` | Preserve string including `C`/`A` prefixes; invoice-group key, not proof of an original order ID |
| `StockCode` | `stock_code` | Preserve string, letters and special codes; future source product key |
| `Description` | `description` | Preserve the row's text; empty remains empty; never invent a product name during staging |
| `Quantity` | `quantity` | Signed integer; negative values remain visible; fractional quantities fail instead of truncating |
| `InvoiceDate` | `invoice_date_local` | Excel 1900 serial converted to ISO wall time, rounded to nearest second; original minute-level history retained |
| `UnitPrice` | `unit_price_gbp` | Exact decimal string from XLSX numeric text; preserve unusual values and serialization residuals |
| `CustomerID` | `customer_id` | Integral identifier string; absent IDs remain empty, not merged into one invented customer |
| `Country` | `country` | Preserve source labels, including Unspecified; no silent geographic standardization |
| Derived | `transaction_kind` | `C*` = cancellation, digit-only invoice = sale group, other prefixes = adjustment; this is lexical classification, not final accounting treatment |
| Derived | `duplicate_of` | First prior source row with the same eight normalized business fields; duplicates are marked, never deleted |
| Derived | `issues` | Missing fields, nonpositive values, nonstandard stock codes and duplicates; pipe-delimited diagnostic tags |

Customer names, employee identities and supplier relationships are absent from the
source. Future IDs should preserve a mapping such as `UCI-CUST-<CustomerID>` while
clearly labeling generated names and contacts. `DEMO-*` scenario records form a
separate synthetic namespace; they are never described as observed UCI customers.

## Complete baskets and eligibility

G03 ships **every source row**, including duplicates, cancellations and adjustments.
No row-level selection or cleaning is applied to the staging dataset. The second file,
`invoice_groups.csv.gz`, records every invoice's full row count and diagnostics.

For a conservative baseline, an eligible sale invoice has a numeric ID, positive
quantity and price on every row, complete customer/description/country/stock fields,
one consistent customer and country, standard stock codes (`five digits + optional
letters`), and no exact duplicate rows. If any line fails, the **whole invoice** is
ineligible. Rows remain in the full prepared file. Eligibility is an Acme baseline
selection rule, not a declaration that every other source transaction is wrong.

This gives G04 an already profiled set of complete baskets. If G04 selects a smaller
baseline, it must select invoice IDs and include every associated source row. Retain
the complete source staging data for audit. The source does not reliably link every
cancellation to its original invoice; do not manufacture such links or call matching
product/quantity pairs definitive refunds.

## Dates, money and provenance

Historical dates remain unchanged. Business time is fixed at 9 December 2011 at
18:00 Europe/London; importing at a later date does not make these current trades.
The source gives no explicit timezone, so UK local time is an interpretation recorded
in the company contract. Source XML timestamps and prices remain recoverable from the
hash-pinned raw archive; prepared IDs identify their precise row.

Some raw Excel numeric strings have binary serialization tails, such as
`2.5499999999999998`. Profiling distinguishes a residual within `1e-10` GBP of a whole
penny from materially finer precision. **Neither is silently rounded in G03.** G04
must explicitly document any business-price normalization and retain the raw value.
Posted amount rounding follows the company contract after that interpretation.

`source_signed_value_gbp` is the exact sum of signed quantity times the raw unit-price
decimal. It is not claimed to be cash, net revenue, VAT, profit or an audited financial
balance. Operational orders, supplier ETAs, payments, tax assumptions and forecast
values will be separate modeled extensions with their own provenance.

## Artifacts and validation

- `download_receipt.json`: actual acquisition UTC timestamp, URL, byte count and ZIP hash.
- `manifest.json` under `data/sources/`: source identity, rights, transformation and use decisions.
- `transactions.csv.gz`: all prepared source lines in original row order.
- `invoice_groups.csv.gz`: every group, row count, eligibility and signed value.
- `profile.json`: measured data-quality and coverage statistics.
- Prepared `manifest.json`: recipe version, source ZIP/XLSX hashes, output byte counts and hashes.

The gzip metadata uses an empty filename and zero modification time. The profile
contains no current timestamp. Reproduction therefore compares bytes, not just counts.
The local verifier checks hashes, continuous source row IDs, complete group membership
and profile row totals without reading the raw source. Acquisition timestamps stay
in the receipt and do not alter deterministic dataset content.
