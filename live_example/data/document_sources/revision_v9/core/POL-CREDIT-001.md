# Receivables and partial settlement

## Purpose and responsibility

Finance maintains the invoice and settlement record. Account teams may discuss
the commercial context, but payment allocations and credit notes are reviewed
within the finance scope. An invoice is a posted charge, not evidence that cash
has arrived. All posted amounts in the Acme company database are stored as
integer GBP pence.

## Reconcile the invoice

1. Confirm the customer, order, invoice ID, posting date and currency. Compare
   the invoice header with the sum of its invoice lines. A line amount is
   calculated from quantity and the exact recorded unit price, then rounded
   once to pence; do not round the unit price first.
2. List every payment allocation to this invoice and its valid credit notes.
   Check the payment's customer, receipt date and allocated amount. An
   unallocated payment on the same account does not settle this invoice.
3. Calculate the outstanding balance as invoice total less allocations and
   credit notes. State the amount in GBP and retain each supporting record ID.
   A credit note reduces the receivable. It does not prove a cash refund or a
   physical return of stock.

## Due date and exceptions

Use the invoice due date and the relevant business reference date to calculate
calendar days overdue. A future due date is not overdue. If allocations exceed
the payment, the invoice header differs from its lines, or the outstanding
balance becomes negative, stop the reconciliation and assign an exception to
Finance. Do not silently adjust a posting to make the numbers agree.

## Communication and records

The reviewer records the invoice, allocation, payment and credit-note IDs, the
calculation date, the balance and unresolved differences. Collections language
must be reviewed before use. A draft report or proposed customer message is not
proof that a payment was posted, a due date changed or a message was sent.
Observed historical price lines retain their source precision; this document
does not interpret tax treatment or describe invoice value as audited profit.
