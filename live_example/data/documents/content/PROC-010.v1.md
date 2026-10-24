---
{
  "access_scope": "support",
  "category": "procedures",
  "document_id": "PROC-010",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-TKT-004",
    "sample_table": "tickets"
  },
  "owner_employee_id": "EMP-005",
  "record_links": {
    "department_id": "DEP-SUPPORT"
  },
  "status": "current",
  "version": 1
}
---
# Complaint evidence review

## Purpose and starting evidence

Read the ticket and its linked order, then request missing product, quantity or photographic evidence. Separate what the buyer reports from what dispatch records establish.

## Review sequence

Open the tickets record and follow its linked records. A concrete baseline reference is `DEMO-TKT-004`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Show an explicit proposal before an open-to-in_progress change. Rejection preserves the ticket. Approval cannot authorize a refund or a credit note.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
