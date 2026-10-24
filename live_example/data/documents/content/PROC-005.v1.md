---
{
  "access_scope": "operations",
  "category": "procedures",
  "document_id": "PROC-005",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-SHIP-001",
    "sample_table": "shipments"
  },
  "owner_employee_id": "EMP-002",
  "record_links": {
    "department_id": "DEP-LOGISTICS"
  },
  "status": "current",
  "version": 1
}
---
# Split dispatch review

## Purpose and starting evidence

Read every shipment for the order, then group shipment items by order-item identifier. One shipment can complete one line and leave another partially supplied.

## Review sequence

Open the shipments record and follow its linked records. A concrete baseline reference is `DEMO-SHIP-001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Compare dispatched and ordered units line by line. Do not infer carrier delivery from warehouse dispatch or quote a purchase-order ETA as a delivery guarantee.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
