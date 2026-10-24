---
{
  "access_scope": "support",
  "category": "procedures",
  "document_id": "PROC-011",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-TKT-004:1",
    "sample_table": "ticket_events"
  },
  "owner_employee_id": "EMP-005",
  "record_links": {
    "department_id": "DEP-SUPPORT"
  },
  "status": "current",
  "version": 1
}
---
# Ticket-history handoff

## Purpose and starting evidence

Read events in date order and identify the last recorded state. Keep the original description visible beside follow-up notes.

## Review sequence

Open the ticket_events record and follow its linked records. A concrete baseline reference is `DEMO-TKT-004:1`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

A resolution must explain the evidence and outcome. Do not erase prior events or claim a resolved case merely because a draft reply was prepared.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
