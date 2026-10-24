# Warehouse dispatch reconciliation: Fable Home Merchants

## Scope and source records

This Operations handoff records the fictional warehouse position reviewed
on 21 October 2026 for order `SCN-ORD-83DAA020DE34-03`, product
`SCN-SKU-83DAA020DE34` and Coventry warehouse `WH-CVT`. It is a dated
working record. Check current inventory and shipment rows again before
promising availability or dispatch.

The order has four one-unit lines. Shipment
`SCN-SHIP-83DAA020DE34-03-PARTIAL` was dispatched on 17 October with
the first two lines. The exact physical ledger chain is:

| Order line | Shipment item | Dispatch movement | Units |
| --- | --- | --- | ---: |
| `SCN-ITEM-83DAA020DE34-009` | `SCN-SHIPITEM-83DAA020DE34-R12-1` | `SCN-STOCK-83DAA020DE34-R12-1` | −1 |
| `SCN-ITEM-83DAA020DE34-010` | `SCN-SHIPITEM-83DAA020DE34-R12-2` | `SCN-STOCK-83DAA020DE34-R12-2` | −1 |

Order lines `SCN-ITEM-83DAA020DE34-011` and
`SCN-ITEM-83DAA020DE34-012` each remain one unit unshipped. They have
no shipment item in this review. The order's recorded status is `partial`.
The shipment has no recorded delivery date; ask Logistics for carrier proof
before describing it as delivered.

## Inventory and reservation boundary

The 21 October modeled inventory row `SCN-INV-83DAA020DE34` shows 18
units on hand and 2 reserved, leaving 16 available. The stock movement
ledger totals 18 after the two dispatches above. The **2 reserved units
are a product-and-warehouse aggregate**. There is no allocation record
that ties that reserved quantity to the two unshipped lines of this order.
Order demand and warehouse reservation happen to have equal quantities
here, but equality does not establish ownership of a particular unit.

## Next controlled actions

Warehouse Operations should check the present stock position, pick status
and any later stock movements before planning shipment of the two open
lines. Logistics should obtain a delivery event or carrier evidence for
the dispatched parcel. Support owns customer communication under ticket
`SCN-TKT-83DAA020DE34-R12`. An internal plan is not a buyer promise;
no dispatch or delivery ETA is recorded in this review. Finance should
check its own invoice records if a billing question arises. This document
does not create another shipment, movement, invoice or reservation.
