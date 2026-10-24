# Agent walkthrough: partial supplier receipts

An order line may have many goods receipts. `list_records` returns at most 50
rows and defaults to 10, so summing its first page can understate what arrived
and overstate what remains outstanding. The model should read the exact totals
from the purchase-order line, then inspect receipt and stock evidence as needed.

## Where the numbers come from

The fixed SQL projection in [`company_queries.py`](../acme/company_queries.py)
reads a `purchase_order_items` row and, using its ID, counts and sums **all**
linked `goods_receipts` rows. It returns:

| Field | Meaning |
| --- | --- |
| `quantity` | Units ordered on this line. |
| `receipt_count` | Number of linked goods-receipt rows. |
| `received_quantity` | Sum of the quantities on all those receipts. |
| `outstanding_quantity` | Ordered minus received; a negative value exposes an over-receipt. |

The SQL template is fixed in Python and uses a bound record ID. The model
cannot supply SQL or choose a table name. Both `lookup_record` and
`list_records` use this projection, and the service checks `operations.read`.
The totals do not depend on the page size of `goods_receipts`.

An isolated test inserted **12 one-unit receipts** against a 20-unit line.
The ordinary receipt list returned 10 rows on its first page; the line still
reported `receipt_count=12`, `received_quantity=12` and
`outstanding_quantity=8`. Another line with no receipts reported 0 received
and 5 outstanding. A customer persona could not read the supplier line.
An intentionally inconsistent third line, with 3 received against 2 ordered,
reported `outstanding_quantity=-1` so the data problem stays visible.

## What one real agent run showed

The [evidence record](../artifacts/purchase-line-receipt-aggregate-2026-10-21.json)
points to run `run-3282c88b4fed4cd18cc88b73906d3b24` in
`state/events.sqlite`. The user asked about fictional PO
`SCN-PO-79511D9988BA`.

1. At event 8865, the model requested the PO header and its line list.
2. At event 8896, the service returned the line with 18 ordered, one receipt,
   6 received and 12 outstanding.
3. At event 8918, the model requested the actual receipt row, rather than
   inventing its ID or date from the aggregate.
4. At event 8956, it filtered stock movements by the receipt's exact ID. The
   result at 8976 contained the matching `+6` movement into `WH-CVT`.
5. The final answer distinguished the 12 units still owed by the supplier
   from stock that had physically arrived.

The goods-receipt aggregate establishes what the receiving records say. A
matching stock movement is separate evidence of arrival in the stock ledger.
Neither one alone establishes today's on-hand or available balance; a later
dispatch can change that balance. Use `inventory` for a current stock question.
