# Company data dictionary

The executable source of truth is [`acme/schema.sql`](../acme/schema.sql). It creates
35 `STRICT` SQLite tables, foreign keys, row-level checks, uniqueness constraints,
indexes and three readable views. Connections through `acme.dataset.connect` always
enable foreign keys. This is a teaching operational model, not an accounting product.

The prepared exercise state can add `company_expenses` through the explicit
[fictional ledger installer](../scripts/install_expense_ledger.py). It is an
extension to the mutable `state/company.sqlite`, not a 36th table in the
verified 2010–11 baseline. Each row has an authored 2026 payment date, category,
payee, positive integer GBP pence, description and provenance. Optional
`supplier_id` and `purchase_order_id` foreign keys connect selected payments
to fictional suppliers and purchase orders. No supplier invoice or payable
balance is modeled; the link alone does not prove full settlement.
On the exercise database, triggers keep the supplier of a linked expense
equal to the supplier of its purchase order. The verified baseline schema
and its hash stay unchanged.

## Shared conventions

- `id`: stable text primary key. `UCI-CUST-*` and `UCI-SKU-*` retain public identifiers;
  `ORD-*` and `INV-*` retain source invoice numbers. `DEMO-*` identifies authored cases.
  Source row keys remain `UCI352:Sheet1:<row>`. They are never independently reshuffled.
- Fields ending `_id` reference the named parent, except original `source_*` identifiers
  that refer to G03 staging. The schema spells out every foreign-key target.
- All posted money uses integer **GBP pence**. `raw_unit_price_gbp` preserves the exact
  source decimal string, including Excel serialization residues. Calculate with Decimal:
  `quantity * raw price * 100`, rounded once half up to integer pence. No unit-price
  rounding precedes multiplication. Never infer VAT, audited revenue or profit.
- Operational dates use ISO `YYYY-MM-DD`. This dataset models daily operations; original
  intraday source timestamps remain in G03 and are reachable through row IDs. Source
  civil time is interpreted as Europe/London. The as-of date is 2011-12-09.
- Forecast `generated_at` is a reconstructed, timezone-aware UTC timestamp. Actual
  preparation/execution time is not substituted for historical business time.
- `provenance` explains observed, reconstructed or authored content. No employee,
  customer name, supplier, payment, shipment or support event is claimed to identify
  a real person or observed operational event from the unnamed source retailer.
- Missing source customers, special stock codes and anomalous baskets remain in G03.
  G04 uses only its complete eligible basket set. It does not invent cancellation links.

## Organization: four tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `departments` | `id`, `name`, `responsibility`: authored function and remit | Ten departments own workflows and document responsibilities |
| `locations` | `id`, `name`, `purpose`: Bristol office, Coventry distribution, Leeds returns | Physical operating context for assignments and warehouses |
| `employees` | `id`, `name`, `job_title`, `hired_on`, `email`, `provenance` | 200 authored full-profile employees; reserved `.example` addresses; no private HR information |
| `employee_assignments` | `id`, `employee_id`, `department_id`, `location_id`, `valid_from`, nullable `valid_until` | Effective assignment intervals; at most one current assignment, no overlaps; supports directory and departmental instructions |

The fixture has two employees per department, including the five account-linked design
identities. The full profile follows company.json's exact department allocations. Account
passwords and authentication belong to the later application database, not this baseline.

## Business partners: four tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `addresses` | `id`, `label`, `country`, `provenance` | Fictional customer billing labels may include generated street and postal details; none came from the public transaction source |
| `customers` | `id`, nullable unique `source_customer_id`, fictional `name`, `address_id`, `account_manager_id`, `payment_terms_days`, `settlement_delay_days`, `segment`, `provenance` | Source-linked purchasing identity, modeled commercial terms and employee handoff |
| `customer_contacts` | `id`, `customer_id`, `name`, `email`, `responsibility` | Synthetic account contact, never a discovered source identity or live delivery address |
| `suppliers` | `id`, `name`, `address_id`, positive `lead_days`, `provenance` | Seven fictional category suppliers support multi-line monthly purchasing batches |

The customer country is the first selected source observation, interpreted as an account
country; it does not establish a real billing address. Source invoice-country differences
remain visible in staging. UK accounts receive 30-day terms, others 45. A stable account
sequence assigns a 0–18-day settlement delay. Labels do not determine purchasing behavior.

## Catalog: three tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `categories` | `id`, `name`, `classification_rule`, `handling_note` | Explicit description-keyword grouping and authored handling guidance; no manufacturer claims |
| `products` | `id`, nullable unique `source_stock_code`, `name`, `category_id`, `supplier_id`, `provenance` | First selected source description, classified category and modeled supplier |
| `price_history` | `id`, `product_id`, `observed_at`, `raw_unit_price_gbp`, nullable unique `source_row_id`, `price_kind` | One price observation per order line. These are transaction observations, including repeated prices, not effective list-price intervals |

## Sales: three tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `orders` | `id`, nullable unique `source_invoice_no`, `customer_id`, `ordered_at`, `status`, GBP `currency`, `provenance` | One reconstructed order per complete eligible invoice, with modeled weekday acceptance before posting |
| `order_items` | `id`, `order_id`, `product_id`, positive `quantity`, `raw_unit_price_gbp`, nonnegative `line_pence`, unique nullable `source_row_id` | Preserve all basket lines, quantities and prices; header/line comparisons and source audit |
| `order_status_history` | `id`, `order_id`, `occurred_at`, `status`, `reason` | Confirmed → partial → fulfilled history; authored cancellation occurs before billing/dispatch |

Every source order preserves its entire eligible basket. `DEMO-ORD-CANCELLED` represents
an explicit operational cancellation with no invoice, shipment or reservation. The public
dataset's cancellation lines stay in staging because reliable original-sale links are absent.

## Logistics: five tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `warehouses` | `id`, `location_id`, `name` | Separate Coventry dispatch and Leeds inspection-supply stock |
| `inventory` | `id`, `warehouse_id`, `product_id`, nonnegative `on_hand`, `reserved`, `as_of` | Unique warehouse/product snapshot; reserved is physical stock held, available = on_hand - reserved |
| `stock_movements` | `id`, `warehouse_id`, `product_id`, `occurred_on`, `kind`, signed nonzero `quantity`, nullable unique `shipment_item_id` / `goods_receipt_id` | Opening and receipt positive, dispatch negative; exactly the correct operational link for each kind |
| `shipments` | `id`, `order_id`, `warehouse_id`, `dispatched_on`, nullable `delivered_on`, `carrier`, `provenance` | Actual simulated dispatch versus delivery evidence; future delivery is not recorded as completed |
| `shipment_items` | `id`, `shipment_id`, `order_item_id`, positive `quantity` | Split fulfillment without double-counting order headers; each dispatch has a matching negative stock movement |

For source baskets, order acceptance is modeled one to four working days before the
observed invoice date. Domestic first dispatch follows one to three working days
after posting; export follows two to five. Lines of at least 48 units ship three
quarters first (rounded down), then the remainder after another two to five
working days when the second shipment existed by the reference date. Dispatches
are weekdays; carrier names and transit intervals are fictional. The generated
as-of shipment set is retained, so dates near the 2011-12-09 cutoff may be
clamped to that date. Explicit DEMO cases use their authored scenario schedule.

Products with dispatch history receive a modeled 24–72-unit opening stock; a
source-linked product with only pending demand may start at zero. S03 retains
its authored 50-unit opening. Weekly supplier receipts are carton-rounded and
include a buffer derived from the preceding four calendar weeks of dispatches.
The reconstruction still uses each week's known dispatch units to guarantee
fulfillment, so it is **not a genuine forecast or observed procurement record**.
Within a day, opening and receipt movements precede dispatch for balance checks.
Every running balance remains nonnegative. Coventry reservations are limited
to physical on-hand stock. Outstanding order demand beyond that amount remains
visible in `order_fulfillment`; the inventory agent tool reports it as
`backordered`. Leeds holds 20 units of demonstration inspection packaging.

## Purchasing: three tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `purchase_orders` | `id`, `supplier_id`, `warehouse_id`, `placed_on`, `expected_on`, `status`, `provenance` | Retrospective weekly supplier batch with varied modeled lead, or explicit open replenishment |
| `purchase_order_items` | `id`, `purchase_order_id`, `product_id`, positive `quantity` | Multiple products per supplier batch; outstanding inbound quantity |
| `goods_receipts` | `id`, `purchase_order_item_id`, `received_on`, positive `quantity` | Received quantity reconciles to the order line and positive movement; future inbound is not on-hand |

## Finance: five tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `invoices` | `id`, unique `order_id`, `posted_on`, `due_on`, `total_pence`, GBP `currency`, `provenance` | Posted header equals the sum of line amounts; due date follows modeled account terms |
| `invoice_items` | `id`, `invoice_id`, unique `order_item_id`, `quantity`, `amount_pence` | The billed line has the same order, quantity and rounded amount as its order item |
| `payments` | `id`, `customer_id`, `received_on`, positive `amount_pence`, GBP `currency`, `provenance` | Separate simulated receipt; not inferred just because an invoice exists |
| `payment_allocations` | `id`, `payment_id`, `invoice_id`, `allocated_on`, positive `amount_pence` | Same customer, valid chronology, no over-allocation; baseline payments are fully allocated |
| `credit_notes` | `id`, `invoice_id`, `issued_on`, positive `amount_pence`, `reason`, `provenance` | S01's goodwill credit reduces its receivable without implying refund or returned stock |

Source-derived invoices receive modeled payments on recurring customer weekdays,
with invoice-level timing around the account delay. Some invoices above GBP 300
receive unequal installments; one remittance can allocate to several invoices.
Only receipts at/before the reference date exist. DEMO finance records are
explicitly authored. No invoice is over-settled.

## Support: two tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `tickets` | `id`, `order_id`, `assigned_employee_id`, `opened_on`, `status`, `topic`, `description`, `provenance` | Split-consignment enquiries, invoice-copy requests, or authored damaged-goods complaint |
| `ticket_events` | `id`, `ticket_id`, `occurred_on`, `status`, `note` | Open → in_progress → resolved chronology; last event matches current state |

A sample of split consignments triggers quantity enquiries after first dispatch.
Another stable sample asks for invoice copies after posting. Source cases rotate
across support staff and have varied working-day review and resolution intervals.
Open, in-progress and resolved states coexist at the business cutoff. Tickets
are simulated, not imported messages or evidence of actual customer contact.

## Planning: three tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `forecast_runs` | `id`, `generated_at`, `training_cutoff`, `target_start`, `target_end`, `method`, `method_version`, `lookback_months`, `assumption` | Reconstructed frozen run and information boundary |
| `forecasts` | `id`, `run_id`, `product_id`, `units`, `training_units`, nullable `training_last_date`, `input_sha256` | Versioned product prediction and exact input fingerprint |
| `sales_targets` | `id`, `department_id`, unique `forecast_id`, `target_units`, `assumption` | Explicit simulated 10% stretch target, separate from actuals and training evidence |

Version 1 averages three preceding full months; version 2 averages two. Missing months
count as zero. Forecast inputs select billed quantities only where posting is before
the target start; no target-period actuals enter the query. Generation is reconstructed
at target-start midnight after the prior-day cutoff. Values round half up to units.
Input hashes cover ordered invoice ID/date/line/quantity tuples. Tests mutate November
actuals and prove the November forecast is unchanged, then mutate October training
quantities and prove it changes. December actuals remain incomplete.
The 12 source-product forecast subjects are selected by cumulative billed units before
2011-10-01, the earliest target start. Later outcomes cannot influence cohort selection.

## Documents: three tables

| Table | Fields and meaning | Relationship / learning purpose |
| --- | --- | --- |
| `documents` | `id`, `title`, `category`, `owner_employee_id`, `access_scope` | Stable company document identity and permission scope |
| `document_versions` | `id`, `document_id`, positive `version`, `effective_from`, nullable `effective_until`, `status`, `relative_path`, `sha256` | Fixed Markdown content, nonoverlapping validity, one current version and retained superseded policy |
| `document_links` | `id`, `document_id`, exactly one of `customer_id`, `product_id`, `department_id`, `warehouse_id`, `ticket_id`, `forecast_id`, `invoice_id`, `order_id` | Real foreign keys to relevant company evidence, avoiding unenforced generic entity strings |

## Views and indexed queries

- `invoice_balances`: header less allocated payments and related credits; exposes
  `outstanding_pence`. Finance authorization must be enforced by future tools.
- `order_fulfillment`: each order item plus `shipped_quantity`, supporting per-line
  outstanding quantities. Cancellation is checked on the parent order.
- `monthly_customer_sales`: `customer_id`, `month`, `sales_pence`. Credits are attributed
  to the original invoice cohort as of the reference date, not their issue month.
  It is neither cash revenue nor a credit-posting-period ledger.

Indexes support customer/date orders, order/product lines, invoice due/posting dates,
allocations per invoice, warehouse/product/date movements, purchase receipts, shipment
items, ticket timelines, forecasts and document scopes. The schema names each index.
Validators check totals and cross-parent constraints that a simple foreign key cannot
express, such as an allocation's customer and a shipment item's order.

Example read after `acme company init`:

```python
from acme.dataset import connect

db = connect("state/company.sqlite", readonly=True)
try:
    rows = db.execute(
        "SELECT id, total_pence, outstanding_pence FROM invoice_balances WHERE id=?",
        ("DEMO-INV-001",),
    ).fetchall()
    print([dict(row) for row in rows])
finally:
    db.close()
```

This is a maintainer read example, not an agent SQL tool. Future model-facing tools
use prepared operations and enforce actor permissions in application code.
