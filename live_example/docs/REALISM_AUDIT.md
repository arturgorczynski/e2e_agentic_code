# Realism audit and revision contract

This is a working audit of the fictional Acme company, not a claim that the realism
pass is complete. The fixed baseline is `acme-company-v8` with 35 tables, 3 views,
147 document IDs and 148 Markdown versions. The active exercise database can contain
user edits and must not be replaced during a content revision. The installed
document release is `acme-documents-2026-r15`: 174 IDs and 461 versions, including
the superseded historical versions. It lives under `state/documents`; the v8
source bundle remains unchanged under `data/documents`.

## What the current records actually show

| Area | Tables inspected | v8 baseline finding | Revision direction |
| --- | --- | --- | --- |
| Organisation | `departments`, `locations`, `employees`, `employee_assignments` | Ten departments, three locations and 200 authored employees have current assignments; names and contact details remain visibly formulaic. | Give roles, contact identity and reporting context more natural variation while retaining stable IDs and scope mapping. |
| Partners | `addresses`, `customers`, `customer_contacts`, `suppliers` | 3,832 fictional accounts and contacts have deterministic names and synthetic addresses. Seven suppliers are assigned by product category. | Improve address/contact presentation and add a credible partner history without implying the public source contained identities. |
| Catalog | `categories`, `products`, `price_history` | 3,585 products and 259,652 source-linked price observations preserve source codes and price strings. | Keep observed descriptions/prices traceable; improve classification labels, catalog display and item-specific imagery. |
| Sales | `orders`, `order_items`, `order_status_history` | 15,213 orders, 259,652 lines and 35,526 status events are linked, but 15,061 orders are fulfilled and most event reasons repeat. | Add a small, clearly authored set of open, partial, cancelled and exception histories with distinct causes. Preserve observed baskets. |
| Purchasing and stock | `warehouses`, `inventory`, `purchase_orders`, `purchase_order_items`, `goods_receipts`, `shipments`, `shipment_items`, `stock_movements` | Dispatch, receipt and movement links reconcile. Only one of 379 purchase orders is open, so the current business view has little varied work in progress. | Add bounded supplier delay and shortage cases with coherent receipt, reservation and movement timelines. |
| Finance | `invoices`, `invoice_items`, `payments`, `payment_allocations`, `credit_notes` | 15,212 invoices and 13,309 payments are connected; the baseline contains only one credit note. | Add explicit, reconciled partial-payment and credit cases; never infer refunds from credit notes or rewrite observed prices. |
| Service | `tickets`, `ticket_events` | Of 1,663 tickets, 1,224 are split-consignment queries, 438 invoice-copy requests and one is a damaged-goods case. | Add distinct case types, owners, evidence and resolutions tied to real orders and invoices in the fictional model. |
| Planning | `forecast_runs`, `forecasts`, `sales_targets` | Seven runs and 73 forecasts have reproducible inputs, but all use one method family. | Add review decisions, assumption changes and target comparison without retroactively using future data. |
| Knowledge | `documents`, `document_versions`, `document_links` | All versions have links and checksums. The 148 Markdown versions are short and heavily template-driven by category. | Rewrite each category for its business purpose, retain effective intervals, and validate prose against linked SQL facts. |

Counts above are from the shipped v8 manifest except the order-status, ticket-topic and
purchase-order-status distributions, which were read from the local exercise database on
20 October 2026. Those distributions can change after portal edits.

## Document review

| Category | Versions | Current length and structure | Required editorial pass |
| --- | ---: | --- | --- |
| Policies | 10 | 229–266 words, two sections | Decision rule, applicability, owner, exception path, version change and evidence. |
| Procedures | 18 | 167–181 words, four sections | Trigger, accountable role, ordered steps, required records and escalation. |
| Product guides | 40 | 209–216 words, four sections | Product-specific handling, stock and sourcing facts, caveats and substitution checks. |
| Customer terms | 25 | 206–209 words, four sections | Account-specific terms, coverage, contact route and service/finance boundaries. |
| Department instructions | 10 | 202–205 words, four sections | Distinct remit, daily work, handoffs and records owned by that department. |
| Incident notes | 25 | 191–219 words, four sections | Case chronology, evidence considered, decision, owner and next action. |
| Planning commentary | 20 | 202 words each, four sections | Forecast assumptions, input cutoff, decision impact and post-period review. |

The editorial target is varied, useful working material, not a minimum word count.
Shared document control can be consistent while each case's action and evidence must
remain specific. Keep the original source data and authored assumptions visibly distinct.

## Contemporary fictional history now in the local exercise state

On 20 October 2026, eight explicitly fictional contemporary customer accounts were
added to the active exercise database. They contain 44 orders spread across January
through October 2026, 25 linked invoices and shipments, 8 service cases with distinct
topics and outcomes, and one linked damage credit note. Invoices have a mixture of
settled, partly paid and unpaid balances. Each account has a contact, address,
account manager and status history. The rows carry `fictional_contemporary_seed` provenance; a user
created account carries `fictional_contemporary_scenario`. The customer picker can
filter the 2011 archive and contemporary histories separately. The original source
orders retain their 2011 dates and source identifiers.

The account seed, date distribution and service-case seed each created a full SQLite
snapshot under `state/backups`. These state rows are an additive exercise layer,
not part of the immutable v8 baseline. Because the installed release includes eight
case documents linked to contemporary tickets, reset retains those cases and their
required customer histories automatically. The seed can also be replayed in a
fresh v8 state with `python -m acme company seed-modern`, then
`python -m acme company seed-modern-cases`. The linked-record audit is
`python -m acme company audit-modern`. An additive purchasing seed adds three
supplier orders: North Quay received 12 of 12,
Maple received 6 of 18 four days after the expected date, and Fable has an
overdue open order with no receipt. Goods receipts, stock movements and current
inventory reconcile. Run `python -m acme company seed-modern-purchasing` in a
freshly seeded state, then `python -m acme company audit-modern`; the audit checks
supplier, quantity, status, chronology, receipt movement and stock balance links.
The same audit checks that contemporary shipment lines belong to their stated
orders, never exceed ordered quantities, dispatch after order placement and
have matching product and warehouse stock movements. A corrupted fixture in
`tests/test_portal.py` proves that over-shipment, a cross-order shipment line
and a shipment dated before its order are detected. The active 2026-10-20
exercise database passed these checks with zero violations.
On 21 October the same `audit-modern` gained six further checks for linked
finance records and chronology: an invoice posted before its order, an invoice
line from another order, a payment allocated to another customer's invoice, an
allocation before receipt or beyond the payment amount, a credit issued before
its invoice. Delivery before dispatch is already rejected by a SQLite table
constraint. Deliberately corrupted isolated
records in `tests/test_portal.py` prove each new check detects its target.
On 21 October, four further checks covered invoices with no lines, invoice
lines billing more units than the linked order line, a current order status
that disagrees with the latest status event, and a status event dated before
its order. Deliberate fixture corruptions in `tests/test_portal.py` trigger
each check, while a fresh modern seed and a user-created scenario still pass.
Four more controls now require a contemporary invoice due date to match the
customer's payment terms, a fulfilled order to have an invoice and shipment,
and a shipment to have at least one line. Isolated corruptions prove that the
new checks fire. The active database passed all 35 violation checks with zero
findings;
the audit is read-only and left the 2011 source transactions unchanged. Its
[saved result](../artifacts/modern-link-audit-2026-10-21-r3.json) also records
15,201 source-derived orders dated 2010-11-25 through 2011-12-08 and 15,201
source-derived invoices dated 2010-12-01 through 2011-12-09, alongside the
separate contemporary cohort.
Four October 2026 forecast records now compare three-month and two-month
lookbacks for two fictional products. Each run freezes billed invoice lines
before 1 October, stores the input fingerprint and connects to a Sales target.
The short lookback for Cedar & Stone has no billed units; its two-unit target
is explicitly marked as a planner override, not a model prediction. The
contemporary planning data is generated with
`python -m acme company seed-modern-planning` and verified by `audit-modern`.

The read-only `audit-modern` also checks the boundary between the two data
eras: source-linked orders and invoices must stay on or before 2011-12-09,
and contemporary orders cannot be dated in the source era. Each contemporary
forecast must have a Sales target. Its target ID must point to the matching
forecast ID and the Sales department; a blank assumption is rejected. For
the seeded 125% and 110% targets, the audit recalculates the rounded value
from the forecast. The two-unit override is checked against a zero-unit
forecast. A nonblank custom assumption can describe another planner judgment;
the audit cannot recalculate its amount without a stated formula. This checks
the declared seed formulas without forcing every commercial target to use a
fixed markup. The active exercise
copy passed all 41 checks on 21 October 2026 with zero violations. An isolated
mutation test changes a target, its department and the cohort dates to prove
these new checks can fail.

The r2 release contains 147 revised current documents and eight new case documents.
Its 148 older versions remain available by exact version and effective date. Nine
core policy sources and eight individually written case sources live under
`data/document_sources/revision_v9`; the remaining categories are rendered from
the original catalog facts by `acme/document_revision.py`. The verified candidate
is `artifacts/document-release-2026-r2`. Its r3 successor adds eight account-specific
terms linked to the contemporary customers, generated from their actual account,
order and service facts by `acme/document_extension.py`. The installed r3 candidate
is `artifacts/document-release-2026-r3`. The installed r4 successor adds three
supplier order reviews and four forecast decision records, each linked to live
product, warehouse or forecast IDs and generated by `acme/document_business.py`.
The installed r5 successor reviews all 170 current documents and issues editorial
corrections for 114. It removes template and exercise phrasing while preserving
the linked IDs, dates, quantities and original Markdown versions. The per-document
review is `artifacts/document-release-2026-r5/editorial_review.json`; its builder
is `scripts/build_document_polish.py`. Revised versions take effect on 21 October
2026. Historical queries for 20 October retain the preceding wording. Each
installation made a full database backup. Check the installed candidate with
`python -m acme company docs-bundle-audit --output-dir artifacts/document-release-2026-r5`.

The catalog now maps all eight contemporary scenario SKUs to six product-specific
illustrative concepts. Repeated generic names share one concept per product type.
Fifty-five source-SKU concepts are mapped; other catalog rows retain clearly
labelled category illustrations. See [catalog image notes](IMAGE_ASSETS.md).

### Installed contemporary directory correction

A check of the active database on 20 October 2026 found that the eight
contemporary seed accounts use only four distinct contact names, six Leeds
addresses and one account manager. The source rows from 2011 are unaffected.
`acme/contemporary_identities.py` now defines eight distinct fictional contacts,
UK addresses and email addresses, four active Sales account managers and four
account segments. Fresh contemporary seeds use these details.

On 21 October 2026, `artifacts/directory-release-2026-r2` was installed in
the active exercise state. It corrected the eight seeded accounts and added
version 3 of their account-specific terms. The r6 catalog has 170 document
IDs and 440 versions. Installation staged the SQL and document changes,
checked the facts, text, register, foreign keys and source archive, then made
a full database and document backup under `state/backups`. A post-install
audit found zero contemporary business-link violations; all eight directory
entries now match their intended identities. The installer remains date-gated
and can be used for a fresh, eligible exercise state:

```powershell
python scripts/install_directory_release.py
```

The installer checks the r5 parent hash and refuses unrecognized edits to the
eight directory records. Same-day document versions are resolved by choosing
the highest eligible version for an effective-date query; an exact version
remains available in the catalog. To prepare a later candidate, use a new
output directory and leave r2 intact:

```powershell
python scripts/prepare_directory_release.py --output-dir artifacts/directory-release-2026-r3
```

The installed release can be checked with:

```powershell
python -m acme company docs-bundle-audit --output-dir state/documents
```

### Department instruction release r7

On 21 October 2026, `artifacts/department-release-2026-r7/documents` was
installed as `acme-documents-2026-r7`. Ten department instructions gained
distinct daily controls, handoffs, and information-handling guidance. The
previous version 3 of each remains available; current version 4 takes effect
on the same day. The catalog now contains 170 document IDs and 450 versions.
The authored sections are in `data/document_sources/revision_r7/departments`;
`acme/department_release.py` builds and checks the candidate against current
department names, responsibilities, headcounts, and SQLite relationships.

Installation preserved the 2011 source transactions and made a full state
backup at `state/backups/document-release-20261021T063404Z-2963f2`.
The installed bundle audit and the contemporary business-link audit both
passed. To prepare a new r7 candidate from an eligible r6 state, or install
that candidate, use `scripts/prepare_department_release.py` and
`scripts/install_department_release.py` respectively. These scripts check the
parent revision and installation date; an already installed r7 state should
not be passed through them again.

### Procedure provenance correction r8

The installed r8 release adds version 4 of `PROC-009`, `PROC-011` and `PROC-014`.
Their earlier current versions called authored `DEMO-*` movement, ticket and
price records historical source references. The price example also has
`price_kind=fixture` and no `source_row_id`, so the procedure now distinguishes
fixture prices from observed source rows. The stock procedure compares a
reconstructed balance with `inventory.on_hand` only at `inventory.as_of`.

The authored bodies live in `data/document_sources/revision_r8/procedures`.
`acme/procedure_release.py` validates their controlled sample IDs against the
active SQL rows, checks the release lineage and preserves the preceding
versions. `scripts/prepare_procedure_release.py` creates a new immutable
candidate from an audited r7 bundle; `scripts/install_procedure_release.py`
stages the SQLite/document update with a full backup. The installed candidate
is `artifacts/procedure-release-2026-r8/documents`, and the backup is
`state/backups/document-release-20261021T073951Z-4aa6a8`.

Post-install checks found 170 IDs, 453 versions, zero foreign-key errors and
zero violations in the contemporary business-link audit. The website returns
the new version 4 for 21 October 2026 while version 3 remains available by
exact version. Source-derived orders remain at 15,201.
In a fresh website chat, the superuser agent searched current documents,
received `PROC-014:v4` in retrieval event 5955, read all 1,882 characters in
event 5993 and correctly identified the sample price as a fixture with no
source-row ID. The [portable run extract](../artifacts/procedure-r8-agent-check-2026-10-21.json)
contains the native calls, answer and independent price-row SQL values. This
checks one question, not general answer reliability.

Five further historical SKU concepts now depict frequently observed unmapped
items: the hanging heart tealight holder, three-tier cake stand, Red Retrospot
jumbo bag, party bunting and assorted bird ornaments. They are
illustrative generated product photos, not evidence of the exact 2011 stock.
Three more concepts cover the high-activity small wicker heart, Victorian
hanging glass tealight holder and doily-print jumbo bag. The website continues
to label every SKU concept as illustrative.
Three additional concepts cover spotted bunting, a small popcorn holder and a
1950s-style Christmas paper-chain kit. Their product descriptions informed
fictional images; they do not verify the appearance of the source stock. Prompt
and checksum details are in `artifacts/image-assets-2026-10-21-r2.json`.
The later [r3](../artifacts/image-assets-2026-10-21-r3.json) and
[r4](../artifacts/image-assets-2026-10-21-r4.json) selections extend this to
27 historical SKU concepts, including distinct kitchen, frame and clock forms.

### Supplier quantity wording correction r9

The original fictional purchasing seed said a supplier "short shipped six of
eighteen units" while the linked records show **six received and twelve still
outstanding**. That phrase could describe either quantity. The authored
[supplier review](../data/document_sources/revision_r9/procurement/PROCURE-79511D9988BA.md)
now states both numbers explicitly. Release `acme-documents-2026-r9` adds
`PROCURE-79511D9988BA:v3`, retains versions 1 and 2, and updates the matching
purchase-order provenance. The seed wording in `acme/scenarios.py` is also
corrected for new exercise databases. The [release builder](../acme/procurement_release.py)
checks the purchase line, receipt and movement against SQLite; the shared
installer stages the update with a full backup at
`state/backups/document-release-20261021T093054Z-8e5806`.

The installed bundle audit reports 170 document IDs, 454 versions and no
issues. SQLite foreign-key checks and all 35 contemporary business-link checks
report zero violations. The website returns v3 for the operations employee.
In a fresh [agent run](../artifacts/procurement-r9-agent-2026-10-21.json),
`read_document` read all 1,869 characters of v3, and `lookup_record` read the
matching stock movement. The answer correctly separated the six received from
the twelve outstanding. This run checks one question.

### Two separate supplier receipts r10

The r10 release added a fourth fictional 2026 purchase order,
`SCN-PO-SPLIT-75F3A546B17E`. Its 15-unit line has two dated goods receipts
of five and four units. Each receipt links to its own positive stock movement.
At that review, the order remained open for six outstanding units. The operations
[review](../data/document_sources/revision_r10/procurement/PROCURE-SPLIT-75F3A546B17E.md)
is `PROCURE-SPLIT-75F3A546B17E:v1`. It describes the recorded arrivals and
does not treat the unfulfilled balance as physical stock or a customer promise.

The [r10 builder](../acme/split_receipt_release.py) checked its parent r9
catalog and the product, supplier and warehouse in SQLite. The installer
staged the SQL and Markdown together, audited both, and backed up the former
active state under
`state/backups/document-release-20261021T171643Z-f281aa`. The installed
catalog has 171 IDs and 455 versions; the contemporary-link and document
audits report no issues. The archived 15,201 source-derived orders were
unchanged.

A fresh [employee agent run](../artifacts/split-receipt-r10-agent-2026-10-21.json)
looked up the order and line, listed both receipts and their movements,
queried inventory, and read the current document. Its answer separated the
six unfulfilled units, nine recorded arrivals and 29 units on hand at the
time of the run. This proves one traced question, not general reliability.
The [walkthrough](SPLIT_RECEIPT_WALKTHROUGH.md) shows how to inspect each
connection in the website and database.

### Return request reviewed against the delivery-date policy r11

The Lantern Trade Studio return ticket opened on 26 August 2026 after a
shipment recorded delivered on 24 August. The earlier case file was v1 and
the ticket remained open without a later event. The r11 release adds a
21 October review event and makes the ticket `in_progress`. The reviewer
checked the **30-day request window in `POL-RETURNS-001:v2`**, which was
effective on the August delivery date; current v3 began only on 20 October.
Two one-unit order lines share a SKU, so the affected line and condition
evidence still need confirmation. The review does not create a warehouse
return, credit note or refund.

The [revised case file](../data/document_sources/revision_r11/support/CASE-75F3A546B17E.md)
is `CASE-75F3A546B17E:v2`. The [r11 builder](../acme/return_case_release.py)
preserves v1 as a superseded version and stages the ticket event with the
document. An isolated rehearsal checked the SQL and document audits,
idempotence, 15,201 archived source-derived orders and zero credit notes
for the linked invoice. The active install backed up its prior state under
`state/backups/document-release-20261021T172831Z-8c7af7`. Post-install
audits report 171 document IDs, 456 versions, zero contemporary-link
violations and zero broken foreign keys. The
[walkthrough](RETURN_CASE_WALKTHROUGH.md) explains the different evidence
and access scopes.

In the first employee-agent question, the model applied policy v2 after only
a search excerpt. After a prompt correction, a
[fresh run](../artifacts/return-case-employee-guided-2026-10-21.json) read
the full policy v2 and case v2 and labeled shipment and invoice claims as
document-reported. Two out-of-scope reads were still attempted and denied.
The [before trace](../artifacts/return-case-employee-before-guidance-2026-10-21.json)
is retained to show the difference. These are two specific runs, not a broad
accuracy claim.

A further [scoped-tool run](../artifacts/return-case-employee-scoped-2026-10-21.json)
used model-visible `entity` enums limited to the seven record types permitted
to Support. It still read both full documents and made no out-of-scope calls.
The backend authorization was not removed. The
[schema walkthrough](SCOPED_TOOL_SCHEMA_WALKTHROUGH.md) traces this boundary.

### Contemporary invoice-line reconciliation check

At the r4 audit stage, the read-only `company audit-modern` checked 44 rules. Three additions
compare each contemporary invoice item's quantity and pence amount with its
linked order line, and require every line of a fulfilled contemporary order
to be invoiced. The previous total and upper-quantity checks could miss a
short invoice line or an omitted line while the invoice header still appeared
credible. Isolated tests deliberately changed the quantity and amount and
removed a fulfilled line; each relevant check reported a violation. The
active 2026 exercise returned zero violations across all 44 checks on
21 October 2026; the [saved audit](../artifacts/modern-link-audit-2026-10-21-r4.json)
is a point-in-time result. The 2011 source transactions were not rewritten.

### Contemporary order fulfillment checks r5

At the r5 release, the audit had 47 rules. It rejected a contemporary order with no
lines, checks whether each active order's `confirmed`, `partial` or `fulfilled`
status matches the quantities in `order_fulfillment`, and flags a cancelled
order that still has an invoice or dispatch. The status check deliberately
excludes cancellations: five legitimate cancelled orders have unshipped
lines, and `cancelled` is a business decision rather than a fulfillment
quantity derived from those lines. The separate cancellation check covers
their billing and dispatch boundary.

An isolated test made the status and its latest history event agree on
`partial` while every line remained unshipped; the new quantity check found
that inconsistency. It also caught a cancelled invoiced order and an empty
order. The active exercise returned zero violations across all 47 checks on
21 October 2026. The [r5 snapshot](../artifacts/modern-link-audit-2026-10-21-r5.json)
records the full result; it does not change the 2011 source rows.

### Partial dispatch with open Support follow-up r12

The fictional Fable Home Merchants order `SCN-ORD-83DAA020DE34-03` has four
distinct one-unit lines for the same product. On 17 October, a shipment and
two linked stock movements dispatched the first two lines. The order status
became `partial`; the other two lines remain unshipped. Stock
for the SKU moved from 20 on hand and 4 reserved to 18 and 2. Reservation is
an aggregate for the product and warehouse, with no order allocation link. The shipment
has no recorded delivery date, and this order has no invoice.

Support opened `SCN-TKT-83DAA020DE34-R12` on 19 October and reviewed it on
21 October. It is an internal follow-up with no recorded buyer statement,
delivery proof or approved ETA. The [controlled case](../data/document_sources/revision_r12/support/CASE-PARTIAL-83DAA020DE34.md)
is `CASE-PARTIAL-83DAA020DE34:v1`; the
[walkthrough](PARTIAL_DISPATCH_WALKTHROUGH.md) follows its order, shipment,
stock, ticket and document links. The [r12 builder](../acme/partial_dispatch_release.py)
staged all business rows and the document together. Its isolated rehearsal
checked idempotence, all 47 contemporary rules and the unchanged 15,201
source-derived orders. The r12 installation had 172 document IDs and 457
versions, 26 contemporary shipments and 9 contemporary tickets. The full
backup is `state/backups/document-release-20261021T180950Z-92882d`.
The [r12 post-install audit](../artifacts/modern-link-audit-2026-10-21-r12.json)
records the 47 zero-violation checks and the clean document register.

### Corrected Support evidence and Operations handoff r13

The r12 Support case incorrectly attributed the warehouse's two reserved
units to the Fable order. The database records a product-and-warehouse total,
not an allocation by order. The [r13 Support source](../data/document_sources/revision_r13/support/CASE-PARTIAL-83DAA020DE34.md)
corrects that claim in case v2 and labels the stock and no-invoice statements
as observations made on 21 October. The
[Operations handoff](../data/document_sources/revision_r13/operations/OPS-DISPATCH-83DAA020DE34.md)
lists both order-line, shipment-item and dispatch-movement chains and marks
the same reservation limit. Operations employee `EMP-041` sees the handoff,
Support employee `EMP-138` sees the revised case, and a superuser sees both.

The [r13 builder](../acme/dispatch_handoff_release.py) packages one new
Operations document and one new version of the Support case. Its isolated
rehearsal verifies idempotence, 47 zero-violation business checks and 15,201
preserved source-derived orders. The r13 installation had 173 document IDs and
459 versions. The installer backup is
`state/backups/document-release-20261021T182905Z-bb02b1`. The
[post-install audit](../artifacts/modern-link-audit-2026-10-21-r13.json)
confirms the active document register and unchanged business checks.
The [live Warehouse trace](../artifacts/partial-dispatch-warehouse-agent-r13-v3.json)
and [live Support trace](../artifacts/partial-dispatch-support-agent-r13-v1.json)
show the current documents and role-specific SQL calls in actual model runs.

### Two-receipt invoice settlement and Finance review r14

Fable invoice `SCN-BILL-83DAA020DE34-01` totals GBP 240.00. A first GBP 120.00
receipt was allocated on 12 October. A second GBP 120.00 receipt on 20 October
was allocated on 21 October, leaving zero recorded balance. This preserves
the older Support case's mid-October GBP 120.00 balance statement as a
correct dated observation. The new [Finance review](../data/document_sources/revision_r14/finance/FIN-SETTLE-83DAA020DE34-01.md)
explains the chain without changing the order, shipment or Support case.

The [r14 release](../acme/settlement_release.py) adds one payment, one
allocation and one Finance-scoped document to the fictional 2026 layer. Its
isolated rehearsal checked idempotence, 47 zero-violation business rules,
15,201 preserved source-derived orders, 174 document IDs and 460 versions.
The full backup is `state/backups/document-release-20261021T184539Z-e0b760`;
the [post-install audit](../artifacts/modern-link-audit-2026-10-21-r14.json)
records the active state. The [settlement walkthrough](SETTLEMENT_WALKTHROUGH.md)
includes the SQL links, role-specific views, live Finance and customer agent
traces, and the payment-tool correction prompted by an observed model error.

### Supplier order completion and Purchasing review r15

The earlier split supplier order retained its two September receipts of five
and four units. A final six-unit receipt and its own +6 warehouse movement were
recorded on 21 October 2026. The 15-unit line is fully received, the order is
now `received`, and inventory is 35 on hand with four reserved. The original
expected date and the first two receipts remain unchanged. Purchasing's v1
open review is superseded, and its [v2 closeout](../data/document_sources/revision_r15/procurement/PROCURE-SPLIT-75F3A546B17E.md)
is current. See the [walkthrough](SPLIT_COMPLETION_WALKTHROUGH.md) for IDs and
the historical-versus-current distinction.

The [r15 release](../acme/split_completion_release.py) was checked on an
isolated r14 copy before installation. Its 47 business checks had zero
violations, 15,201 source-derived orders were preserved, and the document
corpus has 174 IDs and 461 versions. The active-state
[audit](../artifacts/modern-link-audit-2026-10-21-r15.json) is clean. The full
backup is `state/backups/document-release-20261021T185725Z-070091`.

## External examples and adaptation

The [McDonald's Supplier Code of Conduct](https://corporate.mcdonalds.com/content/dam/sites/corp/nfl/pdf/HUMAN%20RIGHTS_Supplier_Code_of_Conduct.pdf)
shows explicit scope, operational obligations, assessment and revision information.
The [adidas policy library](https://www.adidas-group.com/en/sustainability/transparency/policies?tag=Supply+Chain)
separates a core standard from supporting procedures and topic-specific guidance.
The [Nike Code Leadership Standards resource](https://about.nike.com/en/resources/nike-code-leadership-standards-translations-2/)
describes implementation requirements, documentation and training. Acme should adopt
these structural patterns for its own fictional workflows. Brand wording, logos and
claims from those companies must not appear as Acme content.

## Release rule for a new baseline

Changing generated rows or Markdown changes the fixed hashes. A new dataset version
must be built and validated in a fresh directory. The active `state/company.sqlite`
and its `baseline.json` receipt must be migrated explicitly, with a backup and with
the learner's current edits preserved. Do not silently reset the active exercise DB.
