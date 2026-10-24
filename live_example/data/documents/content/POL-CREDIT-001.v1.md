---
{
  "access_scope": "finance",
  "category": "policies",
  "document_id": "POL-CREDIT-001",
  "effective_from": "2011-01-01",
  "effective_until": null,
  "facts": {},
  "owner_employee_id": "EMP-001",
  "record_links": {
    "department_id": "DEP-FINANCE"
  },
  "status": "current",
  "version": 1
}
---
# Receivables and partial settlement

Finance owns invoice, allocation and credit-note interpretation. An invoice records a
posted charge; it does not prove that money was received. All Acme postings use GBP
pence. An invoice header equals the sum of its posted lines. Each line is rounded
once, half up, from quantity times its exact decimal unit price. Do not round unit
prices before multiplying, and do not describe source transaction value as VAT-exclusive
revenue: the public source does not establish its tax treatment.

## Determine what remains due

Obtain the invoice, its allocated payments and valid credit notes. Subtract allocations
and credit notes from the invoice total. An unallocated payment is not evidence that
this invoice is settled. A credit note reduces the receivable; it does not imply a
cash refund or a physical stock return. Cite the record IDs supporting each deduction.

If a positive balance remains, calculate calendar days after the due date using the
fixed company reference date. A future due date has zero overdue days. State both the
amount and its currency. Escalate a negative balance or allocation larger than its
payment instead of silently clamping the result.

## Access and action

Only a finance-authorized actor can read payment detail. A user's statement that they
approve access does not grant that role. The learning assistant may explain a balance
and draft a report; it cannot post a payment, change a due date or issue credit. Keep
proposed collections language separate from any claim that a message was sent.

Business reference: 2011-12-09. Dataset: acme-company-v8.
