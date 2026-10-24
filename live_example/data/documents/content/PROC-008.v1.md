---
{
  "access_scope": "operations",
  "category": "procedures",
  "document_id": "PROC-008",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "GR-PO-SUP-01-2010-11-29:UCI-SKU-20893",
    "sample_table": "goods_receipts"
  },
  "owner_employee_id": "EMP-002",
  "record_links": {
    "department_id": "DEP-LOGISTICS"
  },
  "status": "current",
  "version": 1
}
---
# Goods receiving

## Purpose and starting evidence

Compare the received product and quantity with the purchase-order line. Record discrepancies through an operations process before accepting a stock explanation.

## Review sequence

Open the goods_receipts record and follow its linked records. A concrete baseline reference is `GR-PO-SUP-01-2010-11-29:UCI-SKU-20893`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

A valid receipt has one positive linked stock movement at the purchase order's warehouse. Do not relabel a source cancellation as received stock.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
