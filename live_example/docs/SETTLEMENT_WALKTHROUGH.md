# Follow a two-payment invoice settlement

This fictional 2026 case shows why **payment received**, **payment allocated**
and **invoice settled** are different statements. It adds records to the
contemporary Fable Home Merchants history; the 2010–11 source-derived
transactions retain their original dates and values.

## The business record chain

| Date | Record | What it establishes |
| --- | --- | --- |
| 9 October | Invoice `SCN-BILL-83DAA020DE34-01` for order `SCN-ORD-83DAA020DE34-01` | GBP 240.00 billed; due 8 November. |
| 12 October | Payment `SCN-PAY-83DAA020DE34-01` | GBP 120.00 received from account `SCN-CUST-83DAA020DE34`. |
| 12 October | Allocation `SCN-ALLOC-83DAA020DE34-01` | The first GBP 120.00 assigned to this invoice; GBP 120.00 remained open. |
| 20 October | Payment `SCN-PAY-83DAA020DE34-R14` | Another GBP 120.00 received. It was not yet allocated to the invoice on this date. |
| 21 October | Allocation `SCN-ALLOC-83DAA020DE34-R14` | The second GBP 120.00 assigned to this invoice; recorded balance GBP 0.00. |

The [Finance review](../data/document_sources/revision_r14/finance/FIN-SETTLE-83DAA020DE34-01.md)
is `FIN-SETTLE-83DAA020DE34-01:v1`, effective 21 October and visible to
Finance and superusers. It reports the dated chain and links to the account,
order and invoice. Its payment and allocation IDs are in the body and facts;
the `document_links` table has no columns for direct payment or allocation
links. Follow `payment_allocations.payment_id` and `.invoice_id` in SQLite
to verify the money path.

An [older Support case](../data/document_sources/revision_v9/cases/SCN-TKT-83DAA020DE34.md)
said GBP 120.00 remained outstanding at its mid-October delivery review.
That was correct after the first allocation. Its historical wording remains
in the installed case version; the later Finance record explains the new
balance without rewriting the Support document. Invoice settlement does not
change the delivered shipment, Support ticket or order.

## Inspect in the local website

1. Select customer `SCN-CUST-83DAA020DE34` and open **My account** → invoice
   `SCN-BILL-83DAA020DE34-01`. The detail shows GBP 0.00 outstanding and
   two allocation entries with both receipt and application dates.
2. Select Finance employee `EMP-120` and search **Knowledge** for
   `FIN-SETTLE-83DAA020DE34-01`. Open v1 and compare its IDs and dates
   with the invoice and payment rows. Support employee `EMP-138` and the
   customer cannot read this Finance document; superuser can.
3. As superuser, use **Database** → **Browse** on `invoices`, `payments` and
   `payment_allocations`. The foreign-key path is
   `orders → invoices ← payment_allocations → payments`. Check that the two
   allocations sum to 24,000 pence and that each payment belongs to the
   invoice's customer. **Check links** should show 47 zero-violation controls.

The customer invoice ledger lists allocations and credit notes for this
invoice. It does not expose a refund register. Here no credit note is linked
to this invoice; the ledger alone cannot establish whether a refund occurred
somewhere else.

## What the agents actually did

The [Finance probe](../scripts/verify_settlement_agent.py) uses the selected
`EMP-120` profile. Its [current trace](../artifacts/settlement-finance-agent-r14-v2.json)
read the full Finance document v1, looked up the invoice and both payment
rows, and listed this invoice's two allocation rows. It separated the
20 October receipt from the 21 October allocation, identified the older
GBP 120.00 balance as document-reported, and made no refund claim. No
out-of-scope tool call was denied.

The [earlier Finance trace](../artifacts/settlement-finance-agent-r14-v1.json)
exposed an agentic mistake: a customer-wide payment list contained a third
payment, absent from *this invoice's* allocation page. The model labelled
that payment unallocated overall. It actually belongs to another invoice.
The bounded `payments` tool now returns `allocation_count`,
`allocated_pence` and `unallocated_pence` over **all** invoices for each
payment. A [regression test](../tests/test_portal.py) creates two invoices
and verifies that a payment missing from one invoice's allocation list can
still be fully allocated to the other. The agent instruction explicitly
forbids the old inference. The current Finance run used the exact payment
IDs and did not repeat it.

The [customer trace](../artifacts/settlement-customer-agent-r14-v2.json) used
only `my_invoice`. It reported the two allocations, zero balance and no
linked credit note, while saying the customer ledger cannot establish that
no refund occurred elsewhere. Its [first run](../artifacts/settlement-customer-agent-r14-v1.json)
overclaimed that no refund was involved. The customer prompt and tool
description now state the narrower evidence boundary. Both current runs
passed mechanical source-path checks; their wording was also reviewed
against the rows above. Future model answers still require inspection.

## Reproduce the controlled release

From a prepared r13 state in `live_example`:

```powershell
.\.venv\Scripts\python.exe scripts/settlement_release.py prepare
.\.venv\Scripts\python.exe scripts/verify_settlement_release.py
.\.venv\Scripts\python.exe scripts/settlement_release.py install
```

The immutable candidate is
`artifacts/settlement-release-2026-r14/documents`. Its isolated verifier
installs twice on a copy, checks the two receipts and allocations, 174
document IDs, 460 versions, 47 zero-violation business rules and 15,201
unchanged source-derived orders. The installer makes a full backup and
validates the staged database plus documents before replacing active state.
The [post-install audit](../artifacts/modern-link-audit-2026-10-21-r14.json)
records the active result. To capture new model traces against the running
server, use fresh filenames:

```powershell
.\.venv\Scripts\python.exe scripts/verify_settlement_agent.py --persona finance --output artifacts/my-finance-settlement.json
.\.venv\Scripts\python.exe scripts/verify_settlement_agent.py --persona customer --output artifacts/my-customer-settlement.json
```
