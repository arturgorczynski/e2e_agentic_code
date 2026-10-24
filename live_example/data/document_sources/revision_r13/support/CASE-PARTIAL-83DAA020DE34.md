# Case review: Fable Home Merchants partial dispatch

## Scope and source records

This fictional contemporary case concerns Fable Home Merchants account
`SCN-CUST-83DAA020DE34` and order `SCN-ORD-83DAA020DE34-03`, accepted on
10 October 2026. Four separate, one-unit lines share product
`SCN-SKU-83DAA020DE34`. Each line is GBP 60.00, for an order-line total of
GBP 240.00. The line IDs matter even though the product is the same:

| Order line | Ordered | Dispatched | Unshipped |
| --- | ---: | ---: | ---: |
| `SCN-ITEM-83DAA020DE34-009` | 1 | 1 | 0 |
| `SCN-ITEM-83DAA020DE34-010` | 1 | 1 | 0 |
| `SCN-ITEM-83DAA020DE34-011` | 1 | 0 | 1 |
| `SCN-ITEM-83DAA020DE34-012` | 1 | 0 | 1 |

## Dispatch and stock evidence at the 21 October review

Shipment `SCN-SHIP-83DAA020DE34-03-PARTIAL` was recorded as dispatched
from Coventry warehouse `WH-CVT` on 17 October with the first two lines.
Each has a linked one-unit dispatch movement. The other two order lines
have no shipment line. The order status changed from confirmed to partial
on 17 October. The shipment has **no recorded delivery date or proof of
delivery**. Dispatch is not proof that the buyer received the goods.

For product `SCN-SKU-83DAA020DE34`, the warehouse snapshot on 21 October
shows 18 units on hand and 2 reserved, hence 16 available. Two one-unit
dispatch movements reconcile the previous 20 on hand to 18. **Reserved is
an aggregate for this product and warehouse. The database has no link
allocating those two reserved units to this particular order.** This
corrects the earlier case wording, which assigned the reservation to the
order without an allocation record. The two unshipped order units are an
order-line fact; their next pick and dispatch remain unconfirmed.

## Support review and handoff

Support opened internal ticket `SCN-TKT-83DAA020DE34-R12` on 19 October
and reviewed the four-to-two split on 21 October. The ticket is in progress.
Its description is an internal follow-up, not a buyer statement. Support
should ask Logistics for delivery confirmation and Warehouse Operations for
the remaining two-line dispatch plan. There is no approved or promised ETA.

At this 21 October review, no invoice was linked to the order, and no
payment allocation or credit note was linked through one. This dated case
observation is not a live Finance query. Finance owns any later invoice or
settlement decision. The case document itself posts no financial or stock
transaction.

## Record control

When discussing this case, cite the order, shipment, exact line IDs and
ticket. Distinguish a dated case statement from a fresh SQL check, and
distinguish the 2026 fictional cohort from source-derived 2011 trade.
