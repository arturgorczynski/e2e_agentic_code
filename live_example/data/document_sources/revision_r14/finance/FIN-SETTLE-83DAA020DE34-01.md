# Receivables reconciliation: Fable invoice 01

## Scope and records

This is a fictional Finance review of Fable Home Merchants account
`SCN-CUST-83DAA020DE34`, order `SCN-ORD-83DAA020DE34-01` and invoice
`SCN-BILL-83DAA020DE34-01`. The review records the settlement position on
21 October 2026. The invoice was posted on 9 October for GBP 240.00 and is
due on 8 November. Check the current ledger before quoting its balance at a
later date.

## Dated receipt and allocation chain

| Date | Record | Meaning for this invoice |
| --- | --- | --- |
| 12 October | Payment `SCN-PAY-83DAA020DE34-01`, GBP 120.00 | Cash received from this customer. |
| 12 October | Allocation `SCN-ALLOC-83DAA020DE34-01`, GBP 120.00 | First payment assigned to this invoice; GBP 120.00 remained open. |
| 20 October | Payment `SCN-PAY-83DAA020DE34-R14`, GBP 120.00 | Second cash receipt. Receipt alone did not assign it to the invoice. |
| 21 October | Allocation `SCN-ALLOC-83DAA020DE34-R14`, GBP 120.00 | Second payment assigned to this invoice; the recorded balance became GBP 0.00. |

The two allocation rows total GBP 240.00, exactly the invoice total. Each
allocation points to a separate payment by the same customer. No credit note
is linked to this invoice. The zero balance means these recorded allocations
cover the billed amount; it does not imply a refund, a changed order or a new
stock movement.

## Historical statement and current answer

Support case `CASE-83DAA020DE34:v1` said GBP 120.00 remained outstanding
at its mid-October delivery review. That dated statement matched the ledger
before the second allocation. It must not be reused as the balance on
21 October. Finance should cite the two payment IDs, both allocation IDs,
the invoice ID and the date of the balance calculation when explaining the
change to the customer or Support. The delivery case remains a separate
service record; settling the invoice does not alter its resolved status.

## Control and handoff

Accounts Receivable owns the allocation decision. Confirm payment ownership,
currency, receipt date and amount before linking a payment to an invoice.
Use the `payment_allocations` rows to explain settlement and the `payments`
rows to explain cash receipt. If a later entry changes the balance, issue a
new dated review rather than rewriting this record.
