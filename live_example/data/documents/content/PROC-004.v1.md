---
{
  "access_scope": "finance",
  "category": "procedures",
  "document_id": "PROC-004",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-CN-001",
    "sample_table": "credit_notes"
  },
  "owner_employee_id": "EMP-001",
  "record_links": {
    "department_id": "DEP-FINANCE"
  },
  "status": "current",
  "version": 1
}
---
# Credit-note explanation

## Purpose and starting evidence

Read the reason and issue date on the credit note. Confirm that the related invoice was already posted and belongs to the account under discussion.

## Review sequence

Open the credit_notes record and follow its linked records. A concrete baseline reference is `DEMO-CN-001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Distinguish the reduction of a receivable from a cash refund and from returned physical goods. Require separate evidence for either of those events.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
