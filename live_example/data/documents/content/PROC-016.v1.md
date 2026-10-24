---
{
  "access_scope": "analytics",
  "category": "procedures",
  "document_id": "PROC-016",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "DEMO-FC-006",
    "sample_table": "forecasts"
  },
  "owner_employee_id": "EMP-004",
  "record_links": {
    "department_id": "DEP-ANALYTICS"
  },
  "status": "current",
  "version": 1
}
---
# Forecast version comparison

## Purpose and starting evidence

Choose forecasts for the same product and target period. Compare method versions, lookback windows and training input fingerprints before comparing their numbers.

## Review sequence

Open the forecasts record and follow its linked records. A concrete baseline reference is `DEMO-FC-006`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Recompute from invoices posted before the cutoff. Keep target actuals outside generation and flag incomplete actual periods when evaluating accuracy.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
