---
{
  "access_scope": "general",
  "category": "procedures",
  "document_id": "PROC-012",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-CUST-001",
    "sample_table": "customers"
  },
  "owner_employee_id": "EMP-003",
  "record_links": {
    "department_id": "DEP-SALES"
  },
  "status": "current",
  "version": 1
}
---
# Customer account handoff

## Purpose and starting evidence

Identify the account manager, billing-country assumption and payment terms. Verify the source customer identifier before combining purchasing history.

## Review sequence

Open the customers record and follow its linked records. A concrete baseline reference is `DEMO-CUST-001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Synthetic names and contact addresses are training labels, not discovered identities. Customer email addresses use reserved example domains and must not be contacted.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
