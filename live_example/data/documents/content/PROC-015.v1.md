---
{
  "access_scope": "analytics",
  "category": "procedures",
  "document_id": "PROC-015",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-INV-001",
    "sample_table": "invoices"
  },
  "owner_employee_id": "EMP-004",
  "record_links": {
    "department_id": "DEP-ANALYTICS"
  },
  "status": "current",
  "version": 1
}
---
# Monthly sales comparison

## Purpose and starting evidence

Choose the same customer scope and complete calendar months. Name the posted-sales-less-credit basis and cite the aggregate's contributing records.

## Review sequence

Open the invoices record and follow its linked records. A concrete baseline reference is `DEMO-INV-001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Compute current minus previous and divide by previous for percentage change. A zero denominator is undefined; a numerical decline alone does not establish a cause.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
