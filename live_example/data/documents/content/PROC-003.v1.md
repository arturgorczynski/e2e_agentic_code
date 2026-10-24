---
{
  "access_scope": "finance",
  "category": "procedures",
  "document_id": "PROC-003",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-PAY-001",
    "sample_table": "payments"
  },
  "owner_employee_id": "EMP-001",
  "record_links": {
    "department_id": "DEP-FINANCE"
  },
  "status": "current",
  "version": 1
}
---
# Payment allocation review

## Purpose and starting evidence

Find the payment's customer and compare it with the customer on the destination invoice. Check receipt and allocation dates before accepting the link.

## Review sequence

Open the payments record and follow its linked records. A concrete baseline reference is `DEMO-PAY-001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Allocated amounts cannot exceed the payment. An unallocated balance is not a settled invoice. The assistant reads evidence but cannot allocate or move money.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
