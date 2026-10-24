---
{
  "access_scope": "operations",
  "category": "procedures",
  "document_id": "PROC-006",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-STOCK-003",
    "sample_table": "inventory"
  },
  "owner_employee_id": "EMP-002",
  "record_links": {
    "department_id": "DEP-LOGISTICS"
  },
  "status": "current",
  "version": 1
}
---
# Available-stock check

## Purpose and starting evidence

Select the warehouse and product together. Subtract reservations from on-hand units before comparing the result with a new request.

## Review sequence

Open the inventory record and follow its linked records. A concrete baseline reference is `DEMO-STOCK-003`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Use purchase orders to explain possible replenishment, keeping their future quantities out of current availability. Route the quantified shortage to purchasing.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
