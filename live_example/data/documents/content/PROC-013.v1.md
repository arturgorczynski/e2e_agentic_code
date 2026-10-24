---
{
  "access_scope": "general",
  "category": "procedures",
  "document_id": "PROC-013",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-SKU-A",
    "sample_table": "products"
  },
  "owner_employee_id": "EMP-003",
  "record_links": {
    "department_id": "DEP-SALES"
  },
  "status": "current",
  "version": 1
}
---
# Product substitution review

## Purpose and starting evidence

Compare exact stock codes, descriptions and product guides. Similar names or categories do not establish compatible dimensions, materials or safety properties.

## Review sequence

Open the products record and follow its linked records. A concrete baseline reference is `DEMO-SKU-A`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Historical prices are observations, not an approved quotation. Escalate a substitution to a human product owner rather than promising equivalence.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
