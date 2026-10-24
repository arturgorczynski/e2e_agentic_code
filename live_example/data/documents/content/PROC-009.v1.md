---
{
  "access_scope": "operations",
  "category": "procedures",
  "document_id": "PROC-009",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "MOVE-DEMO-SHIP-001:DEMO-ORD-001:L001",
    "sample_table": "stock_movements"
  },
  "owner_employee_id": "EMP-002",
  "record_links": {
    "department_id": "DEP-LOGISTICS"
  },
  "status": "current",
  "version": 1
}
---
# Stock-ledger reconciliation

## Purpose and starting evidence

Start with the opening movement, add receipts and subtract dispatches by warehouse and product. Order events by date, treating receipts before dispatches on the same day.

## Review sequence

Open the stock_movements record and follow its linked records. A concrete baseline reference is `MOVE-DEMO-SHIP-001:DEMO-ORD-001:L001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

The running balance may never be negative. Compare the ending balance with on-hand stock and separately verify reservations against outstanding order lines.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
