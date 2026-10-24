# Order history and business activity

**Insights** is the company's read-only exploration page. It has separate
2010–11 and 2026 cohorts, filters for date, order status, customer ID and
customer/order text, an order detail panel, and monthly money activity.

## What the numbers mean

| Display | Source | Meaning |
| --- | --- | --- |
| Basket value | `order_items.line_pence` | Value of one order's lines. An order can be unbilled or cancelled; this is not revenue or cash. |
| Gross billed | `invoices.total_pence`, grouped by `posted_on` | Invoice postings in the chosen date range. Source-era invoice amounts reconstruct retail baskets; contemporary invoices are authored. |
| Credits issued | `credit_notes.amount_pence`, grouped by `issued_on` | Credit events dated in the range. A credit does not prove a cash refund. |
| Net billing activity | Gross billed minus credits issued in the same range | A dated activity measure, not audited revenue, profit, or an invoice cohort restatement. |
| Customer cash received | `payments.amount_pence`, grouped by `received_on` | Recorded customer remittances. The 2010–11 payments are modeled, not bank observations. |
| Current outstanding | `invoice_balances.outstanding_pence` for invoices posted in the range | Today's balance of that invoice cohort; later payments affect it. It is not a past month-end balance. |
| Recorded cash outflow | `company_expenses.amount_pence`, grouped by `paid_on` | Explicitly authored 2026 scenario payments. The ledger is incomplete as a company-wide cost statement. |
| Recorded cash difference | Customer cash received minus recorded cash outflow | Difference between two recorded demo cash streams. It is **not profit**. |

Months with no events remain visible as zero. Historical outflows are unavailable,
because the verified source and modeled historical database do not contain
supplier payments or operating expenses. Analytics employees see aggregate
billing. Finance employees and superusers also see cash, balances and expenses.
Other employees can browse commercial order history within their persona scope.

For a finance persona, **Money activity** also groups the selected-period
fictional outflows by expense category. Each bar gives the exact recorded GBP
amount and number of payments; the category amounts reconcile to the displayed
recorded cash outflow. This is a breakdown of the incomplete demo ledger, not
a company profit-and-loss statement. Select a category bar to open **Expense
ledger** with that category already filtered. The chosen dates and cohort stay
in place, so the ledger's all-page total can be checked against the bar.

The **Order history** panel pages customer orders 25 at a time. Its count covers
every match, not only the current page. Opening an order shows its status events
and up to 50 lines. Logistics events appear only with `operations.read`;
invoice amounts appear only with `finance.read` or superuser. Use Database Browse
for more than 50 lines and to inspect exact source rows.

## The fictional expense ledger

The verified historical baseline remains unchanged. The additive
`company_expenses` table lives in the exercise `state/company.sqlite`, so it is
visible in DBeaver and **Database → Browse**. Its 11 authored rows span January
through October 2026 and total **GBP 443.50** at installation. Three link to
fictional supplier purchase orders. A linked cash payment does not prove the
purchase order is fully paid: this demo has no supplier invoice or payable
balance ledger. Categories are supplier payment, logistics, packaging,
marketing and software. Every row carries the provenance value
`fictional_contemporary_expense`.

In **Insights → Expense ledger**, select a category or search by expense ID,
payee, description, supplier ID or linked purchase-order ID. The displayed
amount sums **all** matching rows in the chosen date range, including rows on
later pages. Search treats `%` and `_` as literal characters; it does not
accept SQL syntax. This is recorded fictional outflow for that filter, not a
complete company cost total.

The expense seed is [explicit code](../acme/expense_ledger.py). It is not
generated during website startup. Install it only after the contemporary
purchase orders exist:

```powershell
.\.venv\Scripts\python.exe -m scripts.install_expense_ledger
```

The installer makes a full online backup first and writes a manifest with row
count, sum and a logical hash. Running it again leaves existing rows and edits
alone. The Database reset preview identifies the fictional ledger separately;
reset keeps its rows and required linked purchase orders. The historical
baseline archive and its hash are untouched.

To add a test payment, select **Superuser → Database → Browse →
company_expenses → Add row**. Enter its 2026 payment date, one of the five
suggested categories, payee, amount in integer GBP pence and description.
The editor creates the ID and fills `GBP` and
`fictional_contemporary_expense` when left blank. If you select a purchase
order, its supplier is filled automatically. Database triggers reject an
expense linked to the wrong supplier and prevent a later supplier change on
that purchase order from breaking the link. **Check links** also reports
supplier mismatches, payments dated before their linked order and future
expense dates. These are consistency checks on fictional data, not evidence
of observed supplier transactions.

## Presentation path

1. Select **Superuser**, open **Insights → Order history** and choose
   **Fictional 2026**. Filter an order ID or customer and open a row to see
   status, lines, shipments and its invoice.
2. Switch to **Money activity**. Compare invoice postings, modeled customer
   cash and the smaller authored expense ledger by month. Read the definitions
   before interpreting the numbers.
3. Select `supplier payment` in the category breakdown to open **Expense
   ledger** with that filter. Inspect the three
   purchase order references. Open **Database → Browse → company_expenses** to
   inspect or edit the SQLite rows directly.
4. Switch to **2010–11 history**. Outflows are absent in that cohort. The
   source-era transaction and modeled-remittance labels remain explicit.

The website's read-only calculations are in
[business_insights.py](../acme/business_insights.py). The LangChain agent remains
a separate runtime. Its finance-scoped `cash_activity` tool computes the same
dated totals through fixed, logged SQL queries; `lookup_record` and
`list_records` can inspect individual fictional expenses. In **Tools**, run
`cash_activity` with `start_date`, `end_date` and `cohort` to compare its totals
with this page. Its `expense_category` records give the same category counts
and amounts; each query has an event ID in **Execution**. Neither path calls
the cash difference profit.
The [observed agent walkthrough](CASH_ACTIVITY_AGENT_WALKTHROUGH.md) follows
one local-model question through the tool, SQL events and final answer.
