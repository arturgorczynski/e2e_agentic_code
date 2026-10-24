---
{
  "access_scope": "general",
  "category": "procedures",
  "document_id": "PROC-014",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "sample_id": "PRICE-DEMO-ORD-001:L001",
    "sample_table": "price_history"
  },
  "owner_employee_id": "EMP-003",
  "record_links": {
    "department_id": "DEP-SALES"
  },
  "status": "current",
  "version": 1
}
---
# Historical-price explanation

## Purpose and starting evidence

Show the product, observation date and original source-row identifier for each selected price. Multiple prices on one date can represent different baskets.

## Review sequence

Open the price_history record and follow its linked records. A concrete baseline reference is `PRICE-DEMO-ORD-001:L001`. Check identity and the fixed business date before interpreting its state. Keep identifiers in the answer so another employee can reproduce the lookup.

## Decision and escalation

Retain the exact decimal string. Do not silently turn an observed price into a current price list; posted lines use the documented half-up rounding rule.

If evidence is missing, describe the missing record and stop at that uncertainty. Do not fill the gap with a likely date, amount or status. Preserve the distinction between reading evidence, proposing a change and completing an authorized change.

## Handoff evidence

Record the actor, business date, reviewed IDs and unresolved discrepancy. Include source versions when drafting a report; its review and save are separate from this business operation.

Business reference: 2011-12-09. Dataset: acme-company-v8.
