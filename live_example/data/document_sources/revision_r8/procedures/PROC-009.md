# Stock-ledger reconciliation

## Use and owner

Logistics (`DEP-LOGISTICS`) owns this procedure when a warehouse balance or dispatch movement is questioned. Start with the warehouse, product and date range. Movement `MOVE-DEMO-SHIP-001:DEMO-ORD-001:L001` is an authored scenario record for practice, not an observed UCI transaction. Its ID is a traceable example; select the movement belonging to the case being reviewed.

## Review steps

1. Read the movement's `kind`, signed `quantity`, `occurred_on`, product and warehouse. A dispatch must be negative; a receipt or opening movement must be positive.
2. For a dispatch, follow `shipment_item_id` to its shipment and order line. Compare the absolute movement quantity with the shipped quantity, and check product, warehouse and dispatch date on the linked records.
3. For a receipt, follow `goods_receipt_id` to the purchase-order line. Check the supplier, ordered and received quantities, warehouse and receipt date. Opening stock has neither a shipment nor receipt link.
4. Sum signed movements for the product and warehouse from the opening position through the reference date. Compare the result with `inventory.on_hand` only when that date matches `inventory.as_of`; otherwise label it a dated reconstruction. Check `inventory.reserved` separately: a reservation is not a stock movement and cannot be subtracted again from on-hand stock.

## Decision and exception

Do not describe a missing movement as a completed dispatch or receipt. If a link, date, quantity or ending balance disagrees, record both IDs and the difference, then ask the responsible inventory or purchasing owner to resolve it. A proposed correction is not a posted movement. A negative running balance needs investigation before anyone relies on an availability figure.

## Handoff record

Record reviewer, reference date, warehouse, product, movement IDs, linked shipment or purchase-order IDs, calculated balance, recorded on-hand and unresolved difference. Keep the 2011 source cohort and authored scenarios separate when they appear in the same report.
