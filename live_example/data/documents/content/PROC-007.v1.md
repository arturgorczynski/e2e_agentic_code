---
{
  "access_scope": "operations",
  "category": "procedures",
  "document_id": "PROC-007",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-PO-003",
    "sample_table": "purchase_orders"
  },
  "owner_employee_id": "EMP-002",
  "record_links": {
    "department_id": "DEP-LOGISTICS"
  },
  "status": "current",
  "version": 1
}
---
# Purchase-order follow-up

## Purpose and starting evidence

Read the supplier, expected date and purchase-order lines. Sum linked goods receipts rather than assuming that an expected date proves receipt.

## Review sequence

Open the purchase_orders record and follow its linked records. A concrete baseline reference is `DEMO-PO-003`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

An open line remains inbound. Escalate a missed ETA with the line ID and quantity; the assistant cannot place or accelerate a purchase order.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
