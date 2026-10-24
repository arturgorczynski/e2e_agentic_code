# Supplier order closeout: Winter garland display set

## Control and scope

Purchasing closes fictional supplier order `SCN-PO-SPLIT-75F3A546B17E`,
line `SCN-POITEM-SPLIT-75F3A546B17E`, for product
`SCN-SKU-75F3A546B17E` from `SUP-03` into warehouse `WH-CVT`.
This is a training company record. The original order date was 26 August 2026
and the expected date remains 5 September; a late receipt does not rewrite
either date.

## Receipt and stock evidence

| Receipt | Date | Units | Stock ledger entry |
| --- | --- | ---: | --- |
| `SCN-GR-SPLIT-75F3A546B17E-01` | 8 September 2026 | 5 | `SCN-STOCK-SPLIT-75F3A546B17E-01`, +5 |
| `SCN-GR-SPLIT-75F3A546B17E-02` | 16 September 2026 | 4 | `SCN-STOCK-SPLIT-75F3A546B17E-02`, +4 |
| `SCN-GR-SPLIT-75F3A546B17E-03` | 21 October 2026 | 6 | `SCN-STOCK-SPLIT-75F3A546B17E-03`, +6 |

The order line has **15 ordered** and **5 + 4 + 6 = 15 received**. It therefore
has **0 outstanding** recorded units. Each positive stock movement points to
its matching goods receipt. After the final six units, inventory row
`SCN-INV-75F3A546B17E` records **35 on hand**, four reserved and 31 available
as of 21 October 2026. On-hand includes opening stock and customer dispatches;
it is not the 15 units received against this one supplier order.

## Decision and history

The purchase order status is now `received`. Purchasing may close the
supplier follow-up for the missing six units after checking the physical count.
The earlier `PROCURE-SPLIT-75F3A546B17E:v1` review correctly recorded nine
received and six outstanding before this final receipt was posted. Keep that
version as the earlier review; this v2 records the later completed position.
Both reviews carry the same effective calendar date because this training
register stores dates, not times. Use the version and linked receipt IDs to
distinguish their sequence on 21 October.

This stock arrival does not by itself reserve stock to a customer order or
prove a shipment. Check `order_fulfillment` and `shipment_items` before
promising delivery against the new warehouse position.
