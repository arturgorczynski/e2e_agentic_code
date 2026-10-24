# Fictional company data quality and provenance

## What is observed and what is authored

The prepared UCI retail transaction files supply customer IDs and country,
stock codes and descriptions, invoice membership, quantities, prices and dates.
Acme's company name, staff, suppliers, customer trading names, billing address
labels, categories, account terms, reconstructed order workflow and `DEMO-*`
scenarios are fictional. A plausible address in the portal is **not** an
observed delivery address. Customer and staff email addresses use reserved
`.example` domains. The application should never present these as verified
real-world contact details.

The transaction descriptions are retained as source evidence, including their
capitalization, odd spelling and occasionally vague product wording. A polished
catalog presentation may format that text, but must not silently replace the
underlying observed description with an invented product specification.

## Historical and contemporary timelines

The observed transaction archive spans late 2010 through 2011. Its dates stay
where they were recorded; the portal's 2011-12-09 historical reference date is
an analysis cutoff, not the first date in the archive. Some linked company
workflow records in that period, such as shipments and supplier receipts, are
fictional reconstructions and must not be described as observed source events.

The separate contemporary cohort is explicitly fictional. Seeded 2026 orders,
invoices, payments, stock events and documents form a linked business history;
newly created scenario customers add their own dated records. The order and
invoice `provenance` columns distinguish source-derived records from
`fictional_contemporary_seed` and authored scenarios. The customer picker can
filter these cohorts without moving any archived transaction into 2026.

The installed r10 exercise adds one contemporary supplier case:
`SCN-PO-SPLIT-75F3A546B17E` has 15 ordered units, receipts of five and four
on separate dates, two corresponding inbound stock movements, and six units
still outstanding. These are authored 2026 training events, not observations
from the 2010–11 retail archive. The [source review](../data/document_sources/revision_r10/procurement/PROCURE-SPLIT-75F3A546B17E.md)
and [walkthrough](SPLIT_RECEIPT_WALKTHROUGH.md) show the exact links.

The later r11 release adds a dated Support review to a fictional August
return request. It preserves the earlier case document and uses the policy
version effective on the delivery date. The window calculation does not
create a physical return or change the invoice. See the
[case walkthrough](RETURN_CASE_WALKTHROUGH.md) for the record boundaries.

The r12 release adds a fictional October partial dispatch for Fable Home
Merchants: four distinct one-unit order lines, two shipped lines, two
one-unit stock movements and a warehouse snapshot of two units reserved for
the product and warehouse in aggregate. The database has no allocation record
that assigns those reserved units to this order. Its Support ticket
records an internal follow-up, not a buyer claim; dispatch has no recorded
delivery proof or promised completion date. See the
[partial-dispatch walkthrough](PARTIAL_DISPATCH_WALKTHROUGH.md).

The r13 editorial release corrects the earlier Support case's attribution of
the aggregate reservation to this order. It adds an Operations handoff with
the exact shipment-item and stock-movement links. These are controlled,
scoped documents; r13 changes no business transaction rows.

The r14 release adds a second GBP 120.00 receipt to one Fable invoice. Cash
arrived on 20 October; a separate allocation on 21 October brought that
invoice's recorded balance to zero. A Finance-scoped review explains why an
earlier Support case correctly reported GBP 120.00 outstanding at its own
review date. The [settlement walkthrough](SETTLEMENT_WALKTHROUGH.md) follows
the payment, allocation and invoice links. This is fictional 2026 history;
the source-derived 2011 records remain in their original period.

The r15 release completes the separate fictional split supplier order. Its
earlier receipts of five and four remain unchanged; the final receipt of six
has a matching positive stock movement. The 15-unit order is now `received`,
with zero outstanding. Inventory is 35 on hand and four reserved as of 21
October. The [Purchasing walkthrough](SPLIT_COMPLETION_WALKTHROUGH.md)
distinguishes that current balance from the superseded two-receipt review.

In the mutable exercise database checked on 2026-10-21, orders by calendar
year were 1,212 in 2010, 14,001 in 2011 and 44 in 2026. Of those, 15,201
orders were reconstructed from complete UCI invoices; 44 were contemporary
seeds, and 12 were authored scenarios. These counts are a dated snapshot and
can change when learners edit or create records.

Run `python -m acme company audit-modern` after changing linked 2026 records
in **Browse**. This read-only audit checks 50 relationships and chronology
rules. In particular, an invoiced line must retain its order-line quantity
and amount, and every line on a fulfilled contemporary order must appear on
its invoice. It also compares active order status with shipped line quantities,
rejects empty contemporary orders, and detects cancelled orders with billing
or dispatch records. These checks catch an edit that keeps the invoice header total
plausible while breaking a link underneath it. A zero-violation result is a
consistency check on the fictional exercise state, not evidence that the
historical supplier, payment or shipment events were observed.
When the optional expense ledger is installed, the audit also checks that a
linked payment names its purchase order's supplier, follows the purchase
order date, and is not dated in the future. An absent ledger contributes zero
expense violations; the historical baseline remains unchanged.

## v2 identity and catalog refinements

`acme/company_data.py` now assigns deterministic, non-numbered fictional
customer trading names from a permutation of name components. They remain
stable for a given build and unique across the full observed customer set.
Eight demo customers have individually authored names. Billing address labels
are generated from a building/street/locality template, with UK-style postal
labels for UK customers and city-level international business locations for
other countries. Those labels are useful for exercises, not shipping.

Product categories preserve the established classifier for ambiguous source
phrasing, with narrow overrides for clear errors. Examples: a Christmas gift
bag is packaging, a beaker is tableware, a tea towel is textile, and a pen is
stationery. Source stock codes and descriptions do not change. Supplier links
follow the fictional category sourcing rule, so a category correction also
updates the product's supplier assignment.

## Existing exercise state

`scripts/enrich_demo_data.py` previews proposed changes without writing. With
`--apply`, it creates an online SQLite backup under `state/backups/`, then
applies all changes in one transaction. It changes a customer name only if it
still matches the v1 formula and an address only if it still contains the v1
placeholder and remains linked to its original generated address ID. It
changes a product category only when the current value matches the v1
classifier. Manually changed address records and other user exercises are
preserved. A second dry run should report zero remaining candidates.

The fixed v2 baseline and document corpus are generated together from the
prepared source files. The corpus includes product guides and customer terms,
so its catalog, Markdown content and SQLite metadata must match. The reviewed
v2 bundle passed `acme company verify`; `scripts/install_company_v2.py` then
installed it alongside the enriched mutable copy while preserving the prior
bundle and state in `state/backups/`. Existing portal address edits remain in
the mutable copy. Historic validation artifacts for v1 are left untouched.

## v3 supplier and employee refinements

The v3 baseline replaces the seven numbered supplier offices with distinct
fictional business locations and category-appropriate trading names. These are
location labels, not verified or deliverable addresses. Typical supplier lead
times are varied independently of the retrospective purchase-order history.

Generated employees now have department-specific roles and deterministic hire
dates spread across 2007–2011. The five individually authored staff records
keep their original roles and dates. Their assignment start dates match their
hire dates. In the full installed exercise copy, 200 employees have 42 distinct
job titles and 185 distinct hire dates; the seven old supplier address
placeholders are gone.

`scripts/polish_authored_data.py` previews changes to an existing v2 exercise
database. It updates only original generated values and backs up the database
before `--apply`; manually edited rows are preserved. The reviewed full v3
bundle passed `acme company verify`. `scripts/install_company_v3.py` backed up
the mutable copy and fixed baseline, applied guarded changes, installed the
new compressed baseline and updated `state/baseline.json`. The document catalog
is byte-identical to v2, while only the suppliers, addresses, employees and
employee assignments baseline tables changed. The previous user-created
address row remained present in the exercise copy after installation.

## v4 customer ownership links

The v4 baseline assigns source-linked customers across the 35 active Sales
employees. The assignment is stable for a given customer ID but remains
fictional: the UCI source does not identify Acme staff or account ownership.
The eight `DEMO-CUST-*` accounts retain `EMP-003` for the guided scenarios.
`scripts/assign_account_managers.py` previews changes in an existing v3
exercise copy and updates only source-linked customers still pointing to the
original manager. `scripts/install_company_v4.py` verifies the reviewed bundle,
backs up the mutable database and fixed baseline, installs v4, and updates the
state receipt. Only the baseline `customers` table changed; the document
catalog did not. The installed exercise copy now uses all 35 sales managers,
with 83–130 source customers per manager. The earlier manually added address
remains present.

## v5 logistics and supplier history

The v5 baseline keeps observed invoice dates, basket membership, quantities
and prices unchanged. Source-linked shipments now use seven fictional carrier
labels chosen from parcel, pallet and export services. Their delivery dates
follow varied weekday transit intervals. The installed exercise copy has
twelve distinct calendar-day delivery lags among delivered source shipments;
the authored `DEMO-*` journeys retain their fixed teaching outcomes.

The 91 received supplier purchase orders use supplier-specific planned lead
times, with 14 distinct calendar-day lead values in the installed copy. Their
27,399 goods receipts now fall on days 21–31 of the preceding month, before
the modeled dispatch month. The matching stock-movement dates moved with the
receipts, so the stock ledger remains nonnegative and reconciled. These are
retrospective fictional records, not actual supplier confirmations.

`scripts/install_company_v5.py` compares every changed baseline row, previews
the field updates, and backs up the exercise database and old baseline before
installing. It also repaired 499 legacy purchase lines that still referenced
the wrong supplier batch after the v2 category corrections, together with
their linked receipt and stock-movement IDs. It checked the old quantities and
dates before reparenting them, then verified that every purchase line matches
its product's supplier. Two added addresses, one edited address and the
customer link using that address remain in the exercise copy. The fixed
document catalog and schema are byte-identical to v4.

## v6 order and dispatch workflow

The v6 baseline models source-linked order acceptance one to four working days
before the observed invoice posting date. This produces six calendar-day lag
values across 15,201 source-linked orders. Initial and split dispatches use
varied weekday schedules; none of the 20,302 source-linked shipment records
dispatches on a weekend. The shipment set and quantities remain intact.
Invoice dates, basket lines, observed prices and source row IDs are unchanged.
These order and dispatch dates remain fictional reconstructions.

The shifted dispatches change monthly stock demand. The rebuilt baseline has
56 additional purchase lines, goods receipts and linked stock movements, all
reconciled against the same final inventory positions. The 40 product guides
and 25 customer terms whose first or last modeled order dates changed were
regenerated with matching document metadata. The prior corpus and database
were backed up under `state/backups/`. `scripts/install_company_v6.py` checked
the exercise database against v5, carried forward its two added addresses,
one edited address and one customer address link, and validated the staged
database against the new corpus before installation.

## v7 account and service history

The v7 baseline replaces one-payment-per-invoice settlement with fictional
customer remittances on recurring weekdays. Invoice-level timing varies around
the account's modeled delay, and some larger invoices receive unequal
installments. One receipt can allocate to several invoices; the full baseline
has 1,299 such remittances, with up to 15 invoices in one receipt. It includes
early and late allocations and 178 partly paid source-linked invoices at the
business cutoff. These are simulated receipts, not bank transactions recovered
from UCI.

Source-linked service cases are now a sample of split consignments and
invoice-copy requests. Split cases open after the first modeled dispatch;
invoice-copy requests follow posting. Review and closure use varied working-day
intervals, with open and in-progress cases at the cutoff. The 1,662 source
cases are spread across 25 support employees. The authored `DEMO-*` cases keep
their teaching outcomes. The fixed corpus was regenerated so its footer and
catalog identify v7, and incident notes match the changed cases. The installer
in `scripts/install_company_v7.py` backed up v6 and carried forward two added
addresses, one edited address and one customer address link.

## v8 procurement and physical stock

The v7 stock model created one retrospective supplier order per supplier and
month, bought exactly that month's dispatch units, and kept the final stock
equal to an opening balance. It also treated all outstanding order quantities
as physically reserved stock. An observed 80,995-unit order accepted near the
business cutoff therefore appeared as 80,995 units of opening stock a year
earlier, even though none had shipped.

v8 groups retrospective purchase orders by supplier and dispatch week. Received
quantities are rounded to fictional carton sizes and include a buffer based on
the preceding four calendar weeks of dispatches. The full bundle has 378
received source-linked purchase orders and 147 distinct receipt dates, up from
91 orders and 58 receipt dates in v7. The stock ledger remains nonnegative and
matches the as-of inventory snapshot. These orders are still modeled from
known historical dispatches; they are not evidence of supplier transactions or
a genuine forecast.

Source-linked opening balances now range from 24 to 72 units for products with
dispatch history. A product with only pending demand may have zero on-hand.
`inventory.reserved` is capped by physical on-hand stock; the rest remains
unshipped demand in `order_fulfillment`. The 80,995-unit pending order is now
visible as outstanding demand with zero on-hand and zero reserved, rather than
as fictitious historical stock. `scripts/install_company_v8.py` reviews the
changed procurement and inventory tables, backs up v7, and replays the same
local address edits into the validated v8 database.

Individual carriers, customer addresses, staff ownership and supplier batch
dates remain modeled; plausible histories here do not establish what the
original retailer actually did. Further realism work should strengthen
account and service histories while keeping the observed transaction boundary
explicit.

The portal's **Order journey** makes existing links explorable for a superuser:
it joins an order to invoice balance, line fulfillment, shipments, payment
allocations, credits and ticket events. Its event labels state whether a date
is observed from the source invoice or reconstructed or authored. This view
does not change the modeled rows or make their timelines observed evidence.

## Remaining realism limits

This is a teaching company, not a reconstructed real merchant. Segments,
payment terms, names, hire dates, supplier sites and most employee assignments
are still authored or generated; none is an observed HR or supplier record.
Fifty-five historical stock codes have individually mapped AI concept images;
eight contemporary scenario SKUs share six more concepts. Remaining catalog
cards use category illustrations. The portal labels both kinds, and none
establishes the appearance of the actual historical stock. Future improvements
should add richer buyer histories without conflating authored data with the
observed transaction source.
