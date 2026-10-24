---
{
  "access_scope": "general",
  "category": "procedures",
  "document_id": "PROC-017",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-ORD-001",
    "sample_table": "orders"
  },
  "owner_employee_id": "EMP-003",
  "record_links": {
    "department_id": "DEP-SALES"
  },
  "status": "current",
  "version": 1
}
---
# Owned report review

## Purpose and starting evidence

Show the concrete report title, contents, source versions and operation ID to the conversation owner. Wait for a decision before claiming a saved result.

## Review sequence

Open the orders record and follow its linked records. A concrete baseline reference is `DEMO-ORD-001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

After edits or restart, revalidate scope and ownership. Repeated approval must return one saved artifact; rejection must leave no report behind.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
