# Acme Wholesale: 2011 year-to-date billing and cash evidence

## Purpose and status

This is an internal analytical report for a fictional wholesale distributor. It is a teaching document, not audited accounts, a statutory filing, a tax return, or a measure of profit. The business reference is 9 December 2011. The underlying retail transaction values are drawn from the UCI Online Retail source used by the Acme exercise; Acme customers, payment events, due dates, suppliers, staff and operational explanations are modeled. Amounts below use GBP and integer pence in the fixed `acme-company-v8` baseline. A later mutable exercise database may contain additional records, so reproduce the figures from the shipped baseline before comparing.

## Executive reading

The 2011 posting cohort through the reference date contains 14,048 invoices totaling GBP 6,943,759.54. The wider baseline also contains December 2010: all 15,212 posted invoices through the reference date total GBP 7,426,094.10. Payment allocations dated through that date total GBP 6,026,454.15 across the wider history. One credit note contributes GBP 50.00. Subtracting allocations and credits from the **wider** invoice total yields GBP 1,399,589.95 at this broad aggregate level. This arithmetic is a receivables orientation, not a claim that every invoice is overdue. The invoice balance view and due dates must be used for an overdue analysis. Payment receipts and allocations are different event sets: a receipt can fund more than one invoice, and payment timing does not change an invoice posting month.

The 2011 source spans January through the first nine days of December. November is the last complete month in the fixed business calendar. October header billing was GBP 823,436.00 across 1,516 invoices; November was GBP 892,184.17 across 2,030 invoices. The difference is GBP 68,748.17, around 8.35 percent of October's amount. That comparison establishes a change in this defined measure, but cannot establish a cause. December's GBP 452,128.89 is a partial-period figure across 635 invoices and must not be compared as if it were a completed month.

## Measurement contract

An invoice is included in the 2011 cohort when `posted_on BETWEEN '2011-01-01' AND '2011-12-09'`. The header amount is the stored `total_pence`, assembled from line-rounded values under the dataset's explicit rounding rule. The broader 15,212 invoice count includes December 2010. Keep those populations separate when quoting a number. The older December 2010 cohort explains why the all-history orientation and calendar-year subtotal are not interchangeable.

The receipt measure uses `payments.received_on`. The allocated measure uses `payment_allocations.allocated_on`. Neither is equivalent to recognized revenue or cash on hand. The baseline does not contain a complete general ledger, VAT treatment, cost of goods sold, payroll, depreciation, or balance-sheet reconciliation. Therefore this report does not estimate gross margin, operating income, net income, or free cash flow. The occasional synthetic expense entries in a contemporary exercise state must not be netted against 2011 billing; their dates and provenance differ.

## Monthly evidence table

| Posting month | Invoice count | Header billing GBP | Interpretation |
|---|---:|---:|---|
| 2011-09 | 1,453 | 797,214.15 | Complete month in fixed history |
| 2011-10 | 1,516 | 823,436.00 | Complete month in fixed history |
| 2011-11 | 2,030 | 892,184.17 | Complete month in fixed history |
| 2011-12 to the 9th | 635 | 452,128.89 | Partial month only |

Receipt amounts for the same calendar months are GBP 539,360.21 in September, GBP 651,903.15 in October, GBP 845,371.10 in November and GBP 307,372.88 in the first nine days of December. Those values are grouped by receipt date, not by the posting month of the invoices eventually paid. A lower receipt amount in one month does not by itself show a deterioration in collections; invoice age, due dates, allocation lags and cohort mix would be needed. Likewise, an increase in posted billing is not proof of increased product demand without examining quantities, pricing and eligibility.

## Reconciliation workflow

1. Verify the `acme-company-v8` baseline manifest and its database hash. Record the business reference date.
2. Query `invoices` by `posted_on`, count rows and sum `total_pence`. Keep integer pence until display.
3. Query `payments` by `received_on` for receipt timing and `payment_allocations` by `allocated_on` for allocations. Do not add both to one total.
4. Query `credit_notes` by `issued_on`, then inspect the linked invoices. The aggregate credit above contains one GBP 50.00 note at the cutoff.
5. For receivables, use invoice-linked allocations and credits as of the selected date and check individual invoice balances. An invoice existing in the database does not prove payment or nonpayment.
6. Compare complete periods on the same basis. If a document or cached answer quotes a different version, identify the source version before explaining a discrepancy.

An illustrative SQL query for the billing table is `SELECT substr(posted_on,1,7) AS month, COUNT(*), SUM(total_pence) FROM invoices WHERE posted_on <= '2011-12-09' GROUP BY month ORDER BY month`. The query is evidence of a calculation method. It does not explain why a month changed.

## Interpretation limits and open questions

The reconstructed company invoices follow the exercise's eligibility and modeling rules. Excluded source baskets remain outside these measures. Product categories and supplier assignments are fictional extensions, and some order acceptance dates are modeled relative to observed posting. A customer ranking may be useful for exploration but cannot establish profitability because margin and service costs are absent. A large invoice can dominate an amount-weighted result while a count-weighted result tells a different story. Both should be named before use.

For a collections investigation, ask which invoice cohorts have passed their due dates, whether partial allocations are common, and how much of the broad residual remains for invoices not yet due. For a demand investigation, compare product quantities and customer populations over matching complete months. For an operational investigation, inspect linked dispatch and return records. These are questions for additional evidence, not conclusions supplied by this report.

## Retrieval exercises

This document deliberately includes overlapping terms such as billing, receipts, allocations, credits and outstanding balance. A good retrieval answer should choose the section matching the user's question and cite this document's ID and version. It should distinguish the all-history aggregate from a 2011-only subtotal and should identify December as partial. It should not quote the modeled cash history as observed UCI payment behavior. A search for “November profit” should retrieve the limitation that profit is unavailable, even though the report contains a November billing amount.
