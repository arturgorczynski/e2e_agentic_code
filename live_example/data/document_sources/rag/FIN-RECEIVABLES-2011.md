# Acme Wholesale: receivables aging study and reconciliation protocol

## Question

Which amounts are billed, which are paid, and which are actually overdue at the fixed 9 December 2011 reference date? This internal study sets out a repeatable method. It is a fictional company exercise built around a historical retail source, not a published account of the source retailer. Payment schedules, due dates and allocations are authored Acme data. The report intentionally separates an arithmetic balance from an aging conclusion.

## Units and dates

All amounts are integer pence in storage and GBP when displayed. An invoice's `posted_on` date places it in a billing cohort. Its `due_on` date determines whether an unpaid balance is past due at a chosen reference date. A payment's `received_on` date describes the receipt event. An allocation's `allocated_on` date describes application of that payment to an invoice. A credit note has its own `issued_on` date and links to an invoice. Moving any one of these dates into another column would change the question being answered.

At the cutoff, the shipped baseline contains GBP 7,426,094.10 in posted invoice headers, GBP 6,026,454.15 in allocations and GBP 50.00 in issued credits. The broad residual is GBP 1,399,589.95. That number includes invoices not yet due and therefore cannot be called overdue debt. A correct aging table starts from each invoice, joins only its eligible allocations and credits, and computes its remaining balance before testing `due_on < reference_date`. If the amount is zero, days overdue is zero even when the due date is in the past.

## Cohort construction

For each invoice, retain the stable invoice ID, customer ID through its linked order, posted date, due date, header amount, all linked allocation IDs and credit-note IDs. Sum allocations with `allocated_on <= reference_date`, and sum valid credits with `issued_on <= reference_date`. Subtract from the invoice header amount, but investigate a negative result rather than silently flooring it. The invoice balance view is a convenient prepared projection; the raw joins are the independent reconciliation path. If a receipt exists but is unallocated at the selected date, it is not yet a reduction of that invoice's balance.

An aging classification can use `not_due`, `1-30`, `31-60`, `61-90` and `over_90` days, but the bucket labels are a reporting choice. They do not alter the accounting arithmetic. State whether the due date itself is day zero or day one; this exercise treats calendar days after due date as overdue. A leap day and weekend still count as calendar days. The model should not infer that a customer disputed an invoice merely from a late allocation.

## Reconciliation matrix

| Evidence | Key field | What it supports | What it does not support |
|---|---|---|---|
| Invoice header | `total_pence`, `posted_on` | Billed amount and posting cohort | Collection or profit |
| Payment receipt | `amount_pence`, `received_on` | Cash receipt in modeled history | Which invoice was settled |
| Payment allocation | `invoice_id`, `allocated_on` | Amount applied to a specific invoice | Independent new cash |
| Credit note | `invoice_id`, `issued_on` | Reduction of linked invoice claim | Customer refund unless separate evidence exists |
| Invoice balance view | `outstanding_pence` | Prepared point-in-time balance | Cause of nonpayment |

The matrix matters because a lexical search for “paid invoice” can return both a payment receipt and an allocation. A RAG system should cite the exact row or document version that establishes the requested relation. If it only finds a receipt with a matching customer, it must not claim that a particular invoice was settled.

## Procedure for an analyst

First choose an effective date and validate that it falls within the exercise's available history. Then select the invoice population: all posted invoices through the date, a complete posting month, one customer, or a named invoice list. Keep customer filters in the SQL predicate rather than in natural-language memory. Next compute balances per invoice. Compare the sum of those balances with the broad invoice less allocations less credits orientation, noting any excluded or post-cutoff events. Only then group positive balances by due-date bucket. Save the SQL predicate, source IDs, dataset version and business reference with the report.

For an invoice questioned by a customer, read that invoice directly and list linked allocations and credits. A source invoice number imported from the retail archive is not the Acme invoice relationship. The Acme relation is the `order_id` and the modeled `invoice_id`. Reconstructed orders can be split, and an order's status does not certify that its invoice is paid. Finance access is required for invoice and payment detail; a general document reader must not receive these amounts through an unrestricted snippet.

## Failure examples

“November receipts equal November sales” is unsupported because receipts may pay older invoices and November invoices may be paid later. “The GBP 1.40 million residual is delinquent” is unsupported because it contains not-yet-due invoices. “A credit note proves cash was refunded” is unsupported because crediting a receivable and transferring money are distinct operations. “A late invoice caused a support case” is unsupported without a linked case and timeline. A good answer gives the exact measure it can prove and names the missing join or event for the stronger claim.

## Review and reproducibility

Run the reconciliation against the immutable baseline for teaching comparisons. The local `state/company.sqlite` is mutable and may include contemporary fictional records. When a user's question concerns today's exercise state, query that state and state its reference date instead. Keep those two populations separate. If a new document edition changes a policy, retain the older version and its effective interval; historical analysis must use the policy effective on the event date.

The report is designed to produce several distinct retrieval targets: a query for “overdue” should find the due-date rule, “settled” should find allocation linkage, and “cash” should find the receipt distinction. The snippets must remain finance-scoped. A high search score is no substitute for invoice-level evidence.
