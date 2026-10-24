# Two partial supplier receipts: inspect the evidence

This is a dated walkthrough of the r10 state, before the r15 final receipt.
For the current position, see [supplier completion](SPLIT_COMPLETION_WALKTHROUGH.md).
The exercise uses fictional Acme records dated 2026. The source-derived
retail transactions remain dated 2010–11. The purpose is to follow a
purchase request through deliveries, stock and a controlled document, then
check what the agent actually read.

## The five different things

| Thing | Exact record | What it establishes |
| --- | --- | --- |
| Supplier order | `SCN-PO-SPLIT-75F3A546B17E` | Acme requested 15 units from `SUP-03` for `WH-CVT`; status is open. |
| Order line | `SCN-POITEM-SPLIT-75F3A546B17E` | The 15-unit request is for `SCN-SKU-75F3A546B17E`. |
| Goods receipts | `SCN-GR-SPLIT-75F3A546B17E-01` and `-02` | Five units were recorded on 8 September 2026 and four on 16 September. |
| Stock movements | `SCN-STOCK-SPLIT-75F3A546B17E-01` and `-02` | Each receipt has a matching positive warehouse ledger entry of five or four. |
| Controlled review | `PROCURE-SPLIT-75F3A546B17E:v1` | Purchasing's authored assessment of the order and next action; it is not itself a physical stock event. |

The calculation is **15 ordered − (5 + 4 received) = 6 outstanding**.
The nine recorded arrivals are supported by the two stock movements. Current
on-hand stock comes from `inventory`, which also includes other stock activity;
it is not the same quantity as either outstanding or this order's arrivals.
The [authored Markdown](../data/document_sources/revision_r10/procurement/PROCURE-SPLIT-75F3A546B17E.md)
states these distinctions and directs Purchasing to seek a date for the
remaining six units.

## Inspect without the agent

1. Select **Superuser** and open **Database → Browse**. Open
   `purchase_orders` and find `SCN-PO-SPLIT-75F3A546B17E`. Follow its line to
   `purchase_order_items`. Then filter `goods_receipts` by that line ID.
2. Open each receipt and follow `goods_receipt_id` into `stock_movements`.
   Check the warehouse, product, date and signed quantity of each movement.
   In `inventory`, inspect `SCN-INV-75F3A546B17E` for the current warehouse
   position. Its on-hand value was 29 when this walkthrough was recorded.
3. Open **Table connections** and select `purchase_order_items` or
   `goods_receipts` to see the foreign-key relationships. The graph explains
   the schema; the row links above establish this particular order's facts.
4. Open **Knowledge**, search `partial garland receipts`, and read archived
   `PROCURE-SPLIT-75F3A546B17E:v1`. Compare its claims with the first two rows.
   The document is restricted to Operations access.

**Tools** can run the same bounded backend lookups directly: use
`lookup_record` for the order or line, `list_records` for the line's
`goods_receipts`, and `list_records` for each receipt's `stock_movements`.
The current database also contains a third receipt from r15. To reproduce the
two-receipt state exactly, use the r10 release backup or the saved trace.
The tool result is a database observation. The review document is a separate
human-authored interpretation. Database Browse also permits local demo edits;
if you change these records, rerun the audit and treat this walkthrough's
numbers as a dated snapshot.

## Ask the agent and inspect its work

Select **Employee → `EMP-002`**, with `operations.read` enabled, then ask:

> Verify `SCN-PO-SPLIT-75F3A546B17E` from exact company records. Show every
> goods receipt and linked stock movement, units outstanding, current on-hand
> stock, and the current supplier review's exact version.

Open **Execution** for that conversation. The
[recorded 21 October run](../artifacts/split-receipt-r10-agent-2026-10-21.json)
contains eight completed tool calls and 11 SQL events. It shows
`lookup_record(purchase_orders)`, `list_records(purchase_order_items)`,
`list_records(goods_receipts)`, a separate `list_records(stock_movements)` for
each receipt, `list_records(inventory)`, `search_documents` and
`read_document(version=1)`. The actual `document_read` event confirms the
full version was opened. The answer gave six outstanding, nine arrivals and
29 on hand, with their different meanings. One recorded run demonstrates
these calls for this question; it does not prove every future answer correct.

## Where the exercise came from

The r10 [release builder](../acme/split_receipt_release.py) copied the
audited r9 document corpus, added the controlled review, and staged the
purchase order, receipts, movements and inventory adjustment in SQLite.
The [release command](../scripts/split_receipt_release.py) installed the
bundle in `state/documents` and `state/company.sqlite` after validation and
a full backup. The immutable release candidate is under
`artifacts/split-receipt-release-2026-r10/documents`.
The [isolated rehearsal](../scripts/verify_split_receipt_release.py) applies
the same release to an online database copy and checks idempotence, links,
ledger reconciliation and document audit. Do not run **prepare** against the
already installed state: the builder expects the r9 parent and unoccupied
record IDs. A new exercise copy can use the candidate and installer.
