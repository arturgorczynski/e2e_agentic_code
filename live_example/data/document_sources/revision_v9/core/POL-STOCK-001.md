# Stock availability and replenishment

## Purpose and responsibility

Warehouse Operations owns the recorded stock position at each warehouse.
Purchasing owns supplier orders and their expected receipts. Sales and Support
may use the resulting availability to answer a customer request, but an
expected delivery from a supplier is not stock on hand.

## Availability check

Identify the warehouse and product together. Read on-hand units and reservations
for that exact pair. **Available units = on-hand units − reserved units.**
Reservations cover outstanding units on unfulfilled, uncancelled orders, up to
the physical stock available. Compare the new requested quantity with the
available amount and report any shortfall. Stock recorded at another warehouse
requires a separate transfer decision; it is not automatically available for
this dispatch location.

## Replenishment evidence

For a shortage, find the relevant purchase-order line, supplier and expected
date. Compare its ordered quantity with linked goods receipts. A purchase order
marked open remains inbound; a received status must be supported by receipt
lines. Each receipt increases stock through a linked movement. Each shipment
line reduces stock through a dispatch movement. Review those movements before
using the stock number in a promise or report.

## Exceptions and handoff

If movement totals do not reconcile to on-hand stock, if a receipt references
the wrong product or warehouse, or if reserved units exceed on-hand units,
record the conflicting IDs and ask Operations to investigate. Purchasing reviews
a missed supplier date with the outstanding quantity and supplier reference.
Do not add future receipts to today's available units or silently change stock
to resolve a discrepancy.

Acme's older source-linked fulfillment and replenishment events are modeled
from historical transaction baskets. Contemporary fictional cases carry their
own provenance. Report the evidence period and record origin when comparing
either history.
