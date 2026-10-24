# Supplier order review: two partial garland receipts

## Scope and owner

Purchasing owns this fictional working review of purchase order
`SCN-PO-SPLIT-75F3A546B17E` and its line
`SCN-POITEM-SPLIT-75F3A546B17E`. The product is Winter garland display set
(`SCN-SKU-75F3A546B17E`) from Solstice Seasonal Goods Ltd (`SUP-03`) for
Coventry distribution (`WH-CVT`). This is an Acme training record, not a
supplier acknowledgement or a commitment to a customer.

## Order and receipt timeline

The order was placed on 2026-08-26 for **15 units**, with an original expected
date of 2026-09-05. Its database status remains **open**. The supplier sent
two partial deliveries rather than one complete delivery:

| Event | Recorded date | Units | Linked stock movement |
| --- | --- | ---: | --- |
| `SCN-GR-SPLIT-75F3A546B17E-01` | 2026-09-08 | 5 | `SCN-STOCK-SPLIT-75F3A546B17E-01`, +5 |
| `SCN-GR-SPLIT-75F3A546B17E-02` | 2026-09-16 | 4 | `SCN-STOCK-SPLIT-75F3A546B17E-02`, +4 |

The first receipt was three calendar days after the original expected date;
the second was eleven days after it. The two recorded receipts total **9
units**, leaving **6 units outstanding** against the 15-unit line. Each stock
movement names its own goods receipt and adds the same quantity to `WH-CVT`.
The order quantity itself is a request to the supplier: only the two receipts
and matching stock movements establish the recorded physical arrival of nine
units. Current on-hand and available stock must be read from inventory because
later dispatches or reservations can change them.

## Purchasing decision and handoff

Keep the PO open for six outstanding units. Ask the supplier for a dated
commitment for the remainder. Record any later receipt as another event with
its own ID and movement; do not overwrite either partial receipt or the
original expected date. Sales may inspect the customer order history for this
product, but a customer order sharing the SKU does not allocate this supplier
line or promise delivery. Warehouse Operations should compare both receipts
with their movement rows and physical count before changing any stock claim.
