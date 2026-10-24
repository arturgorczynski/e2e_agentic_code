---
{
  "access_scope": "finance",
  "category": "procedures",
  "document_id": "PROC-002",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-INV-001",
    "sample_table": "invoices"
  },
  "owner_employee_id": "EMP-001",
  "record_links": {
    "department_id": "DEP-FINANCE"
  },
  "status": "current",
  "version": 1
}
---
# Invoice reconciliation

## Purpose and starting evidence

Read the invoice header and every invoice line. Sum posted integer-pence amounts and compare that total with the header before discussing settlement.

## Review sequence

Open the invoices record and follow its linked records. A concrete baseline reference is `DEMO-INV-001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Subtract only allocations to this invoice and its valid credit notes. Report an inconsistency with its record IDs; do not repair financial postings through a report.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
