---
{
  "access_scope": "general",
  "category": "procedures",
  "document_id": "PROC-018",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "POL-ACCESS-001",
    "sample_table": "documents"
  },
  "owner_employee_id": "EMP-003",
  "record_links": {
    "department_id": "DEP-SALES"
  },
  "status": "current",
  "version": 1
}
---
# Policy version lookup

## Purpose and starting evidence

Extract the event date from the question and find the document version whose effective interval contains it. Use the business reference date for today.

## Review sequence

Open the documents record and follow its linked records. A concrete baseline reference is `POL-ACCESS-001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Cite historical and current versions separately when comparing them. A superseded version remains valid evidence for its historical interval.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
