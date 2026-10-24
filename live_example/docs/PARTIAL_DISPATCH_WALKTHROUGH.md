# Follow a partial dispatch across the company records

This is a fictional October 2026 business case. It shows a difference
between **confirmed**, **partially dispatched** and **delivered**, and keeps
the 2010–11 source-derived retail archive in its original period.

## The record chain

| Record | Recorded fact |
| --- | --- |
| Order `SCN-ORD-83DAA020DE34-03` | Fable Home Merchants placed four one-unit lines on 10 October. Each line is GBP 60.00; their total is GBP 240.00. |
| Status history | The order was confirmed on 10 October and changed to `partial` on 17 October. |
| Shipment `SCN-SHIP-83DAA020DE34-03-PARTIAL` | Two lines left Coventry on 17 October through Cedar Parcel Network. `delivered_on` is empty. |
| Shipment items | Lines `SCN-ITEM-83DAA020DE34-009` and `-010` each have one shipped unit. Lines `-011` and `-012` have no shipment item. |
| Stock movements | Each shipped line has its own `dispatch` movement of −1 for `SCN-SKU-83DAA020DE34` in `WH-CVT`. |
| Inventory | At the 21 October snapshot: 18 units on hand, 2 reserved and 16 available. The movement ledger also totals 18. Reserved is a product-and-warehouse aggregate; no row allocates it to this order. |
| Ticket `SCN-TKT-83DAA020DE34-R12` | Support opened an internal follow-up on 19 October, then marked it `in_progress` on 21 October. |
| Case `CASE-PARTIAL-83DAA020DE34:v2` | The current Support document corrects the reservation claim in v1 and dates its stock and invoice observations. |
| Handoff `OPS-DISPATCH-83DAA020DE34:v1` | An Operations document links each shipped order line to its shipment item and dispatch movement. |

At the 21 October review there was **no invoice** for this order. The shipment has **no recorded
delivery**. The ticket does **not** contain a statement from the buyer or an
approved date for the remaining dispatch. These absences are part of the
case, not blanks to fill by inference.

## Inspect in the local website

1. Select the Fable Home Merchants customer `SCN-CUST-83DAA020DE34` in the
   customer persona and open order `SCN-ORD-83DAA020DE34-03`. Compare its
   four lines and `partial` status with the account's other orders.
2. Switch to **Superuser → Database → Browse**. Open `orders`,
   `order_status_history`, `order_items`, `shipments`, `shipment_items`,
   `stock_movements`, `inventory`, `tickets` and `ticket_events`. Search
   each table by the IDs above. A shipment header is not proof that every
   order line was sent; follow its line rows.
3. In **Knowledge**, search `CASE-PARTIAL-83DAA020DE34` as Support and
   `OPS-DISPATCH-83DAA020DE34` as Operations. Open the full current versions
   and compare the cited IDs with the database. Superuser can read both.
4. Run **Database → Check links** as a superuser. The read-only audit should
   report zero violations across 47 controls. It verifies quantities,
   chronology and links, though it cannot prove a delivery that is not
   recorded.

The Support employee `EMP-138` can read commercial order and Support ticket
records and the corrected case v2. Shipment and stock tables require Operations
scope. Operations employee `EMP-041` can read the new handoff and physical
records, but not the Support case. A Support agent should attribute physical
facts to its case document unless it has another permitted source. In **Execution**, check
which tools the agent actually used before treating its answer as direct
database verification. A superuser can inspect every underlying row.

## What the two agents actually did

The repeatable [agent probe](../scripts/verify_partial_dispatch_agent.py) asks
the local model the same business question as Support and as the selected
customer, each in a new conversation. It saves the answer and the complete
application event stream without the session cookie. The
[historical corrected Support run](../artifacts/partial-dispatch-support-agent-r12-v4.json) used
`lookup_record` for the order and ticket, `list_records` for all four order
lines and both ticket events, then searched for and read the full case v1.
Its six SQL events were limited to commercial and Support projections. It
made no denied call. The answer labeled the shipment, delivery and invoice
statements as **case-document reports**, because Support cannot read the
Operations and Finance tables directly.

The [customer run](../artifacts/partial-dispatch-customer-agent-r12-v2.json)
called `my_order` once. Its two SQL events produced the order total and all
four owned lines, including `shipped_quantity` and `unshipped_quantity`.
The answer gave 4 ordered, 2 dispatched and 2 unshipped, and said that its
account record did not establish delivery or a next dispatch date. It did
not see the Support case. These traces demonstrate two particular model
answers and their source paths; inspect a new run before trusting its answer.

The script checks which tools and SQL projections ran and whether the full
case was read. Its mechanical result does not judge every sentence in the
answer, so the saved answers were also compared manually with the linked
database and document facts above.

The r12 traces remain historical evidence of v1 behavior. After the r13
installation, a fresh run must read Support case v2 or the Operations
handoff v1. The old trace cannot prove the agent used the corrected wording.

The [r13 Support run](../artifacts/partial-dispatch-support-agent-r13-v1.json)
read case v2 and checked the order, four order lines and ticket in SQL. It
reported delivery and invoice absence as dated statements from the case,
because its profile lacks Operations and Finance access. The
[r13 Warehouse run](../artifacts/partial-dispatch-warehouse-agent-r13-v3.json)
read the Operations handoff v1 and checked the order, shipment, shipment
items, stock movements and inventory in SQL. It explicitly said that it
could not independently verify an order-level reservation allocation from
its permitted tables. Both runs completed without denied calls; their
mechanical source-path checks passed. These are observed model runs, not a
guarantee that every future answer will use the same tools or wording.

An [earlier Support run](../artifacts/partial-dispatch-support-agent-r12-v3.json)
made a specific attribution mistake: it treated `orders.source_invoice_no =
NULL` as direct SQL proof that no Acme invoice existed. That column is the
archived retail source invoice reference, while Acme invoices are linked by
`invoices.order_id`. The order-tool result and agent instructions now explain
that distinction. In the corrected run, the model explicitly says that
`source_invoice_no` cannot establish invoice absence and attributes the
no-invoice statement to the case document. The isolated regression fixture
contains a NULL `source_invoice_no` **and** a linked invoice to keep this
boundary testable.

## Reproduce the release in a prepared r11 state

From `live_example`, the [builder](../scripts/partial_dispatch_release.py)
packages the [authored case](../data/document_sources/revision_r12/support/CASE-PARTIAL-83DAA020DE34.md)
against the audited r11 corpus:

```powershell
.\.venv\Scripts\python.exe scripts/partial_dispatch_release.py prepare
.\.venv\Scripts\python.exe scripts/verify_partial_dispatch_release.py
.\.venv\Scripts\python.exe scripts/partial_dispatch_release.py install
```

The package is immutable at `artifacts/partial-dispatch-release-2026-r12/documents`.
The isolated verifier installs it twice on a copy, checks the 4/2 quantity
split, the document register, all 47 business controls and the unchanged
15,201 source-derived orders. The installer creates a full database and
document backup, validates a staged replacement and records r12. If r12 is
already installed, the second install returns `already_installed`.

## Reproduce the r13 correction and handoff

From the r12 state, the [r13 builder](../scripts/dispatch_handoff_release.py)
packages the [corrected Support source](../data/document_sources/revision_r13/support/CASE-PARTIAL-83DAA020DE34.md)
and [Operations source](../data/document_sources/revision_r13/operations/OPS-DISPATCH-83DAA020DE34.md):

```powershell
.\.venv\Scripts\python.exe scripts/dispatch_handoff_release.py prepare
.\.venv\Scripts\python.exe scripts/verify_dispatch_handoff_release.py
.\.venv\Scripts\python.exe scripts/dispatch_handoff_release.py install
```

The bundle is immutable at
`artifacts/dispatch-handoff-release-2026-r13/documents`. The rehearsal
installs it twice on a copy, checks 173 document IDs, 459 versions, all 47
business controls and the preserved 15,201 source-derived orders. A new
agent run should compare its document version and SQL evidence with the
[r13 post-install audit](../artifacts/modern-link-audit-2026-10-21-r13.json).

To capture a new agent trace against the running local server:

```powershell
.\.venv\Scripts\python.exe scripts/verify_partial_dispatch_agent.py --persona warehouse --output artifacts/my-warehouse-check.json
.\.venv\Scripts\python.exe scripts/verify_partial_dispatch_agent.py --persona employee --output artifacts/my-support-check.json
```

The script requires a new output filename so historical evidence stays
unchanged. Its checker verifies document reads, permitted SQL paths and no
access-denied events; review the saved answer for wording and attribution.
