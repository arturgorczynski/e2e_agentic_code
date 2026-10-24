# Company tools

The current React/FastAPI portal also exposes two preference-memory tools and
one superuser deletion **simulation**. The original G06 CLI lesson below uses
historical role language; current portal personas are described in the
[portal guide](PORTAL_GUIDE.md) and [agent architecture](AGENT_ARCHITECTURE.md).

## Original G06 service contract

Eight core tools and a workspace tool give one agent bounded access to the company. These are project-local
integrations. The company service is simulated over real SQLite; document retrieval
is deterministic mock RAG. No remote ERP, arbitrary SQL, embeddings or vector index
is involved. Direct tool calls need no model, Docker or network.

| Tool | Behavior | Result limit |
| --- | --- | --- |
| `lookup_record` | One authorized record by entity and ID | One record, exact source ID |
| `list_records` | Fixed filters and stable ID ordering | 1–50 rows, total and next cursor |
| `business_summary` | Sales, receivables, forecast or customer order ranking | One facts object; ranking includes up to 10 customer records |
| `cash_activity` | Finance-scoped, dated invoice, credit, customer cash and fictional expense measures | One facts object, expense-category records and the IDs of its executed SQL events |
| `search_documents` | Scope/date filtering, then deterministic text ranking | 1–10 excerpts of up to 600 characters |
| `list_document_versions` | List permitted revision metadata for one exact document ID | 1–50 versions per page, no body text |
| `read_document` | Read a permitted document ID and exact version | Up to 6,000 characters, next offset |
| `run_analysis` | Sum, difference, percentage change or available stock | Up to 100 decimal operands; one answer |
| `save_report` | Propose title, body and verified sources | Up to 6,000 body characters, 12 sources |
| `update_ticket` | Propose `open` → `in_progress` with a reason | One ticket transition |
| `analyze_workspace` | Prepare sales CSV, analyze a file or read a result | Bounded owned files; see [local execution](local_execution.md) |
| `remember_note` | Save an explicitly requested non-sensitive preference for this persona | One note per topic, 500 characters |
| `recall_notes` | Read this persona's preferences across chats | Up to 20 notes |
| `simulate_delete` | Superuser-only proposal for a record or exact document version; approval only records a simulation | One target; `deleted=false` |

Read [tool_schemas.py](../acme/tool_schemas.py) for strict service input models and
the shared `ToolResult` envelope. [agent.py](../acme/agent.py) contains the small
LangChain wrappers; their model-facing schemas omit runtime identity. Service
validation is authoritative, including bounds that are described in wrapper docstrings.
Unknown fields are rejected. Each invocation accepts at most 32,000 UTF-8 bytes of
JSON arguments and returns at most 48,000 bytes of compact result JSON. Oversized
arguments are omitted from the tool-result event and recorded by size instead.

Every result identifies its integration and has `status`, `records`, `facts`,
`sources`, `page`, `error` and `operation_id` fields. Empty lookups return
`status="empty"` and `found=false`; empty lists have zero records and a page summary.
Unavailable private documents return a generic access error without disclosing
whether the requested version exists. Errors never become invented business facts.
`list_document_versions` uses the same selected persona and document visibility
as `read_document`. It returns effective dates and status for discovery; call
`read_document` before quoting any version. A date-based search selects the
highest version effective that day when two revisions share one calendar date.

## Prepared queries and permissions

[company_queries.py](../acme/company_queries.py) defines every projection and filter
column in code. Only values become bound SQL parameters. The model cannot supply a
table name, column name, SQL statement or arbitrary expression. Text search treats
`%` and `_` literally. Unsupported filters return an error.

| Entities | Required permission | `parent_id` means |
| --- | --- | --- |
| customers, employees | commercial.read | Not supported |
| products | commercial.read | Category |
| orders | commercial.read | Customer |
| order_items | commercial.read | Order |
| invoices | finance.read | Order |
| invoice_items, payment_allocations, credit_notes | finance.read | Invoice |
| payments | finance.read | Customer |
| company_expenses | finance.read | Purchase order (`status` filters expense category; `query` searches payee) |
| shipments | operations.read | Order |
| shipment_items | operations.read | Shipment |
| stock_movements | operations.read | Product (`status` filters movement kind); exact `goods_receipt_id` or `shipment_item_id` link |
| inventory | operations.read | Product |
| purchase_orders | operations.read | Supplier |
| purchase_order_items | operations.read | Purchase order |
| goods_receipts | operations.read | Purchase-order item |
| tickets | support.read | Order |
| ticket_events | support.read | Ticket |
| forecasts | analytics.read | Forecast run |
| forecast_runs | analytics.read | Not supported |
| sales_targets | analytics.read | Forecast |

`customer_id` is an explicit filter for orders, invoices and payments. It
selects invoices through their linked orders. For invoices, `parent_id` means
one **order ID**; passing a known customer ID there returns an argument error
with guidance instead of an empty page. This matters because an empty page
under the wrong relationship must not be interpreted as "this customer has no
invoices." For a customer's aggregate invoice balance, call
`business_summary(report="receivables", customer_id=..., start_date=...,
end_date=...)`. For the count of **all** customer orders, including cancelled
and unbilled orders, call `business_summary(report="customer_orders",
customer_id=..., start_date=..., end_date=...)` or use the `total` in a
customer-filtered order page. An invoice count is not an order count.

`status` filtering is available for orders, purchase orders, tickets and ticket
events, and expense categories. `query` matches customer/product/employee names,
expense payees or ticket descriptions.
Pass a returned `next_cursor` as `after` for the next record page.

`purchase_order_items` returns the ordered `quantity`, plus `receipt_count`,
`received_quantity` and `outstanding_quantity` calculated from **all** linked
goods receipts in SQLite. These totals remain exact when a receipt list has
more rows than one page. They describe recorded goods receipts; inspect the
linked stock movements separately before claiming that units reached a
warehouse or are currently on hand. A negative outstanding value would expose
an over-receipt rather than being silently clamped to zero.

For a known goods receipt, find its recorded stock movement directly:

```text
list_records(entity="stock_movements", goods_receipt_id="SCN-GR-79511D9988BA")
```

For a known shipment line, use `shipment_item_id` instead. These exact filters
are available only on `stock_movements` and cannot be combined in one call.
`parent_id` can additionally restrict the search to a product. Compare the
returned movement's product, warehouse and signed quantity with the receipt or
shipment line. A reference in a document is not proof of a database movement.

To discover a document about a known business record, combine a short topic
with an exact complete ID mention:

```text
search_documents(query="supplier order review", mentions_record_id="SCN-PO-79511D9988BA")
```

The ID filter scans only documents permitted to the selected persona and
effective on the requested date. It matches a complete ID in the Markdown
body, not a substring of another ID. A mention helps find the document; read
the returned exact version and verify its factual claims against SQL records.

Sales and forecast summaries require `analytics.read`; receivables require
`finance.read`. Sales means posted invoice totals less associated credits for the
selected invoice-date cohort, evaluated at the fixed business date, **2011-12-09**.
It is not cash receipts or a tax-adjusted accounting statement. Dates are inclusive;
money is integer GBP pence. Results retain `*_pence` integers and add exact `*_gbp`
strings for display, so the model can quote pounds without guessing a conversion.
`cash_activity(start_date=..., end_date=..., cohort=...)` requires `finance.read`
and explicit dates. It executes fixed SQL for the same dated measures defined in
[business insights](BUSINESS_INSIGHTS.md); its query event IDs permit inspection
in **Execution**. Historical outflows are unavailable. The 2026 ledger covers
selected authored payments only, and the cash difference is **not profit**.
Contemporary `expense_category` records give the count and exact pence amount
for each category in the date range; their sum matches the recorded outflow.
`lookup_record` and `list_records` can inspect individual `company_expenses`
rows, including a purchase-order link; such a link does not establish that a
supplier order was fully paid.
Forecast summaries expose training cutoff, target period, observed billed units,
`observed_through` and `period_complete`. Before the target period ends,
`actual_units` is a **partial count through the business reference date**;
`error_units` and `error_percent` are `null`. The query excludes invoices dated
after that reference. Only a completed target period has a final error against
the forecast. Historical 2011 forecasts use the fixed 2011-12-09 reference;
contemporary forecasts use today's local date.

`business_summary(report="customer_orders")` requires `commercial.read` and ranks
all orders in the selected period by customer, rather than counting sampled pages.
It defaults to the earliest recorded order date (currently **2010-11-25**) through
**2011-12-09**, includes every order status and
returns the first ten customers, with ties sorted by customer ID. Optional
`customer_id` restricts the cohort. The result includes its date range and metric
basis. Sales and receivables retain their default November 2011 period when dates
are omitted. `forecast_id` is required for the forecast report.

In the original CLI account flow, authentication and ownership are checked in application code before company reads.
The session resolves the user and current permissions on each call; model arguments
cannot override them. The five role definitions live in
[company.json](../data/company/company.json). That original role set has no
all-company superuser. The current local website additionally exposes an
explicit **Superuser** demo persona; see the [portal guide](PORTAL_GUIDE.md).

## Mock retrieval

The search first excludes unauthorized scopes and versions outside `effective_on`.
It verifies each selected document against its catalog checksum. Lowercase word
tokens score by occurrence count capped at five, plus four for a title match.
Results sort by descending score, then document ID and version. Equal inputs against
the same corpus and role return equal results. This teaches retrieval mechanics,
version selection and source attribution; it does not demonstrate semantic search.

Search results include IDs, versions, excerpts and effective dates. Read a source
with `read_document`; use the returned next offset for more content. An explicit
read can inspect an authorized historical version, which remains labeled superseded.
Evaluation answers under `evals/` are never part of this search corpus.

## Write proposals and retry behavior

Report and ticket tools create pending operations. They do not apply the proposed
business change. The stable operation ID hashes the thread, application run, tool
kind and canonical validated arguments. Repeating the same proposal in the same run
returns the existing operation, including after approval. Changing arguments creates
a distinct proposal. A genuinely new run may intentionally propose the same content.

Only the separate authenticated application command can approve or reject. It shows
the persisted payload, rechecks ownership and current permissions, verifies report
sources and compares the ticket's expected status. Approval and its report/ticket
effect commit in one SQLite transaction across the attached local databases using
rollback journals. Do not switch these databases to WAL without revisiting that
cross-database atomicity assumption. A repeated decision returns the stored outcome;
rejection produces no business effect. SQLite uniqueness constraints back the deduplication.

Report sources must be permitted records, exact document versions, or SQL event IDs
from this thread. Reading a report rechecks source access. References establish where
the proposed content came from; they do not prove every natural-language claim in its
body. Review the body before approval. The UI supports editing the pending arguments
before approval and retains both the original and decided payloads. Current role and
source permissions are validated again before the write.

## Inspect and verify

Actual executed queries produce SQL events containing the template, bound values,
permission and row count. Actual retrieval produces its own event. No query evidence
is fabricated for a role-denied call. CLI results and model-request traces identify
the simulated integrations. The graphical inspector is under **Executions**.

```powershell
uv run --locked python -m unittest discover -s tests -p test_tools_runtime.py -v
uv run --locked python scripts/verify_company_tools.py
```

The first uses a small fixture and a deterministic fake model where needed. The
second exercises all eight tools on a temporary full company copy with no model
calls, checks all 20 entity projections and reconciles full-cohort sales independently.
It writes `artifacts/g06-full-tools.json`; normal exercise state is preserved.
