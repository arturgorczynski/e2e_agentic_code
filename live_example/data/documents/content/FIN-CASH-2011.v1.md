---
{
  "access_scope": "finance",
  "category": "financial_reports",
  "document_id": "FIN-CASH-2011",
  "effective_from": "2011-12-09",
  "effective_until": null,
  "facts": {
    "provenance": "authored_acme_learning_document"
  },
  "owner_employee_id": "EMP-001",
  "record_links": {
    "department_id": "DEP-FINANCE"
  },
  "status": "current",
  "version": 1
}
---
# Acme Wholesale: billing versus receipt timing, autumn 2011

## Scope

This shorter finance note compares complete autumn months in the fixed `acme-company-v8` baseline. It examines posting and receipt **timing**, not profitability, cash flow statement categories or the behavior of the unidentified UCI retailer. Acme payment events are simulated. A separate report explains full receivables aging.

## Observations

September 2011 posted invoice headers total GBP 797,214.15; October totals GBP 823,436.00; November totals GBP 892,184.17. Receipts dated in those months total GBP 539,360.21, GBP 651,903.15 and GBP 845,371.10 respectively. The receipt series rises over these three complete months, but each month's receipts may relate to invoices from earlier cohorts. Subtracting November receipts from November billing produces a difference of GBP 46,813.07; that difference is **not** November's increase in outstanding receivables. To measure a balance change, reconcile opening and closing invoice balances with all invoice, allocation and credit events between the dates.

## Why the distinction matters

An invoice posting is a claim on a customer in this exercise. A receipt is a modeled cash arrival. An allocation connects a receipt to one or more invoice claims. Their counts differ because a single payment can be split, a partial payment can leave a balance, and timing crosses month boundaries. A credit note reduces a claim without being a payment. Consequently, a question about “how much was paid for October orders” needs order-to-invoice-to-allocation linkage; a month filter on `payments.received_on` alone answers a different question.

December contains only nine days through the business reference. Its GBP 452,128.89 posted headers and GBP 307,372.88 receipts are partial-period figures. Do not compare them with a full November total as evidence of a decline. The fixed source history also contains December 2010, so any “2011 total” needs an explicit lower date bound.

## Checks before explanation

For each reported amount, retain the SQL table, time column, date bounds, unit and dataset version. Verify that header totals use integer pence and are formatted only at the end. For payments, decide whether the report asks for receipts or invoice allocations. For credits, keep the issue date and invoice link. If a customer-specific report is needed, enforce customer scope in the database query before returning any result. Never use a prompt-supplied customer ID as authorization.

Possible explanations for timing changes include due-date distribution, partial payments, invoice mix and modeled remittance schedules. This note tests none of them. An analyst would inspect cohort-level due dates and allocation lags before attributing a change. The fictional exercise does not provide a complete general ledger or bank statement, so these rows should not be presented as audited cash flow.

## RAG questions this note should answer

“What were November receipts?” has a direct value here. “Were November invoices settled?” requires linked balances and cannot be answered from the month total. “Did profit increase?” cannot be answered from this corpus. A retrieval system should prefer a passage containing the needed definition over one containing a convenient but unrelated number.

Business reference: 2011-12-09. Dataset: acme-company-v8.
