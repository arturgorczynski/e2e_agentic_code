# Acme Wholesale: company brief

Acme Wholesale is a fictional UK distributor of home accessories, stationery,
seasonal decorations, kitchenware, gift packaging, and small gift items. Its customers
include independent shops, online resellers, hospitality buyers, and occasional small
buyers. These segments are our design assumptions; the source customer IDs do not
establish a real customer's identity or industry.

The commercial history is adapted from UCI Online Retail. Acme is not a claim about
the real, unnamed retailer. Source product descriptions and transaction patterns
remain recognizable. Employee identities, commercial account names, suppliers,
fulfillment, payments, planning and policies are explicitly fictional extensions.

## Organization

The authoritative machine-readable design is [company.json](../data/company/company.json).
Its ten department allocations sum to the G04 target of 200 employees: sales 35,
warehouse 60, purchasing 18, finance 15, support 25, logistics 20, analytics 8,
people operations 7, IT 8, and leadership 4. G02 defines five representative employees;
the G04 full baseline now materializes all 200 and their effective assignments.

The Bristol office owns commercial activity, planning, finance, and administration.
Coventry is the main distribution centre. Leeds handles returns and regional dispatch.
These locations are fictional operating assignments, not source observations.

## Responsibilities and workflows

1. Sales receives an order and verifies the account and agreed terms. Source invoices
   can seed reconstructed orders; their earlier acceptance times are simulated.
2. Warehouse reserves available stock. Purchasing owns replenishment when available
   stock is insufficient. Logistics records dispatch and delivery exceptions.
3. An order may have multiple shipments. Fulfillment is tracked per item, so one
   shipped line does not imply the entire order is complete.
4. Finance posts invoices and allocates actual simulated payments separately. A credit
   note reduces the receivable; it is not automatically a cash refund.
5. Support investigates complaints and records approved ticket changes. The first
   agent cannot send email, refund money, buy stock, or change financial postings.
6. Analytics prepares evidence-based sales summaries and versioned forecasts. Forecast
   inputs stop at their recorded training cutoff; later actuals support evaluation.
7. An employee reviews any agent-generated report before it is saved in their workspace.

Every source-derived row retains its source identity. Company extensions use a distinct
namespace and provenance tag. Public transaction lines are observations; order and
warehouse events reconstructed around them are modeled assumptions.

## Business clock and amounts

- Fixed scenario reference: **2011-12-09 18:00:00 Europe/London**, represented as
  `2011-12-09T18:00:00+00:00` at that date. "Today" in business questions means this date.
- Preserve the original 2010–2011 transaction dates. Do not shift them to the system's
  current year. Source Excel timestamps lack an explicit timezone; interpreting them
  as UK local civil time is a documented Acme assumption, not a source guarantee.
- Actual runs, retries, approvals and log events use current timezone-aware UTC
  timestamps. Never overwrite business dates with execution time or vice versa.
- Primary currency: **GBP**. Keep source unit prices as exact decimal strings, including
  sub-penny values. Compute with `Decimal`, not binary floats.
- Future posted line amounts use integer pence: quantity times exact unit price,
  rounded once per line with `ROUND_HALF_UP`. Header totals sum posted lines. Keep the
  original unrounded source product alongside the posted interpretation.
- The source does not establish VAT treatment, payment receipts, profit or delivery.
  Do not describe quantity times unit price as audited net revenue or collected cash.
- "Days overdue" means the nonnegative difference between reference date and due
  date in calendar days, only when an outstanding balance remains.
- October/November are complete historical comparison months. December is partial;
  compare matching elapsed periods or explicitly label partial coverage.

## Initial access design

Five design accounts link to employee IDs in `company.json`. They have no shipped
passwords. G07 now provisions them explicitly through `acme account`; see the
[runtime walkthrough](agent_runtime.md). The browser login interface arrives in G11.

| Account | Employee | Business role | Additional permitted data |
| --- | --- | --- | --- |
| `morgan.finance` | EMP-001, Morgan Reed | Finance | Invoice, payment, credit-note detail and finance documents |
| `jamie.operations` | EMP-002, Jamie Patel | Operations | Stock, purchasing and shipment detail; operations documents |
| `alex.sales` | EMP-003, Alex Bennett | Sales | Basic customers, orders, products and general documents |
| `taylor.analyst` | EMP-004, Taylor Brooks | Analyst | Prepared sales aggregates, forecasts and analytics documents |
| `sam.support` | EMP-005, Sam Ellis | Support | Tickets, customer-service order summary and support documents |

All roles can use the non-sensitive employee directory and basic commercial data.
Detailed receipts and bank/payment information are finance-only. Support can see an
order's customer-facing status without obtaining warehouse movements or purchasing
costs. The analyst receives prepared metrics, not unrestricted access to finance or HR.

Each conversation belongs to one immutable authenticated `user_id`. Every read,
stream, resume, trace export and report download checks ownership. No role, including
IT, automatically gains access to another employee's private chat. Search applies
document permissions before ranking and excerpting. Tool schemas never ask the model
to choose the acting user or role.

Report saves and ticket changes require both permission and explicit approval by the
thread owner. Approval does not grant a missing role. Repeated approval uses the same
operation ID and must not repeat the write. G06/G07 enforce these checks in the CLI
and tool services, including browser callbacks and direct tool exercises.

Local learners can also create their own username and display name and choose one
of these five roles in setup or the browser. Each gets a separate application user
ID and private conversations. The selected role maps to the corresponding sample
employee; creating a login does not alter the 200-employee company baseline.

## One agent, eight tools

The implemented inventory in `company.json` contains lookup, bounded listing,
prepared business summaries, document search/read, predefined analysis, report save,
and ticket update. Each tool validates entity/report type and access scope. Tools do
not expose arbitrary SQL, shell commands, filesystem paths or unrestricted table names.

See [learning scenarios](learning_scenarios.md). The answer keys and small numeric
fixtures live in `evals/`, outside `data/documents/`. Later ingestion must explicitly
allowlist the company-document directory; it must not crawl the whole repository.
