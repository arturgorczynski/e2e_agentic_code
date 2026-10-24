# Case review: Fable Home Merchants partial dispatch

## Scope and source records

This fictional contemporary case concerns Fable Home Merchants account
`SCN-CUST-83DAA020DE34` and order `SCN-ORD-83DAA020DE34-03`, accepted on
10 October 2026. The order contains four distinct, one-unit lines for the
same Assorted homewares pack SKU. Each line is GBP 60.00, so the four lines
total GBP 240.00. The separate line IDs matter even though the SKU repeats:

| Order line | Ordered | Dispatched | Open |
| --- | ---: | ---: | ---: |
| `SCN-ITEM-83DAA020DE34-009` | 1 | 1 | 0 |
| `SCN-ITEM-83DAA020DE34-010` | 1 | 1 | 0 |
| `SCN-ITEM-83DAA020DE34-011` | 1 | 0 | 1 |
| `SCN-ITEM-83DAA020DE34-012` | 1 | 0 | 1 |

## Dispatch and stock evidence

Shipment `SCN-SHIP-83DAA020DE34-03-PARTIAL` was recorded as dispatched
from Coventry warehouse `WH-CVT` on 17 October with the first two lines.
Each shipment line has its own one-unit dispatch movement. The two other
order lines have no shipment line. The order moved from confirmed to partial
on that date. This shipment has **no recorded delivery date or proof of
delivery**; dispatched does not mean delivered.

The modeled stock position for `SCN-SKU-83DAA020DE34` after dispatch is 18
on hand and 2 reserved, hence 16 available. Two one-unit dispatch movements
reduce the previous 20 on hand to 18. The remaining two units stay reserved
for this order. This local position is a fictional scenario record, not a
guarantee of a subsequent dispatch or customer delivery date.

## Support review

Support opened internal follow-up ticket `SCN-TKT-83DAA020DE34-R12` on
19 October. On 21 October, Support confirmed the four-to-two quantity split
from the linked order and shipment records. The ticket remains in progress.
The recorded description is an internal task; there is no buyer statement
in this case. Support should ask Logistics for delivery confirmation and
Warehouse Operations for the next two-line dispatch plan. No delivery ETA
has been approved or promised.

There is no invoice for this order, no payment allocation and no credit
note. Finance must assess any future invoice separately from the dispatch
record. The case itself neither posts an invoice nor moves stock.

## Handoff and interpretation

When explaining this case, cite the exact order, shipment, line and ticket
IDs. Distinguish recorded dispatch from delivery, and outstanding quantity
from a confirmed restock or fulfilment date. The source-derived 2011 trade
history belongs to a separate historical cohort; this 2026 case is entirely
fictional.
