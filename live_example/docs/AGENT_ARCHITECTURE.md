# Acme agent architecture and demonstration guide

This page describes the **current** local React/FastAPI portal. The visible
customer, employee and superuser selector is a scenario control, not a
production login. It maps a selected demo identity to a stable local account
in `state/app.sqlite`. A prompt cannot change that mapping. The default site
binds to `127.0.0.1`; Docker is unnecessary for the portal and agent runtime.

## One agent, three modes

`acme/agent.py` creates the same LangChain `create_agent` graph with a different
system prompt and tool list per mode:

| Mode | Main tools | Identity boundary |
| --- | --- | --- |
| Customer | `my_profile`, `my_account_terms`, `my_orders`, `my_order`, `my_invoices`, `my_invoice`, permitted document search/version list/read, preference notes | Customer ID comes from the selected server persona; tools reject another customer's records. |
| Company | Bounded record queries, summaries, dated cash activity, documents, calculator, workspace, report/ticket proposals, memory and web search | Employee scope follows the selected department; superuser has the full demo scope. |
| Free chat | Public web search and preference notes | No company database tools. |

The model chooses among *offered* tools. `RuntimeContextMiddleware` filters
the visible list, including the superuser-only `simulate_delete`. The company
service checks the actor again on every invocation, including direct Workbench
calls; tool hiding by itself is not an access boundary.

The same middleware narrows the model-visible `entity` enum on
`lookup_record` and `list_records` to the selected profile's permitted
projections. It derives that set from `company_queries.QUERIES`, the fixed
SQL query registry. Tool names and backend implementations stay the same.
The finance scope also offers `cash_activity` and `company_expenses` records.
The former logs fixed invoice, credit, payment, expense and category queries with their
bound dates. The 2026 expense ledger is fictional and incomplete; its recorded
cash difference is never labeled company profit. The website's Insights page
uses a separate read-only service over the same SQLite records, so browsing
the dashboard does not run the agent.
The [schema walkthrough](SCOPED_TOOL_SCHEMA_WALKTHROUGH.md) follows the
LangChain request override, an actual recorded model schema, and the
independent SQL authorization that still runs at execution time.

For the selected customer's **current account terms**, `my_account_terms`
resolves the customer ID from the trusted session, chooses the document version
effective today and invokes the same validated `read_document` service used by
the generic agent tool. This produces a `customer_terms_lookup`,
`document_read` and `tool_result` trail. General policy or historical-date
questions still use `search_documents` followed by `read_document`. A search
excerpt is discovery evidence; the account-terms tool returns the complete
current Markdown body for the customer's own record.

The prompt and runtime describe this actor as a **selected local demo profile**.
It controls scenario scope but is not verified authentication. For document
questions, `search_documents` uses an explicit effective date, defaulting to
today. The runtime injects today's local calendar date into the effective
model request; the model should omit `effective_on` for a current question
and pass an event date only when the user supplied one. **Knowledge** defaults
to the same date and can expose older or future
versions when the date filter is changed or cleared. The catalog's `current`
status means latest registered version; it can become effective later than the
day it was registered.

For a policy question about an earlier event, the agent searches with that
event date and must read the complete returned policy version before applying
its rule. The [return-case trace](RETURN_CASE_WALKTHROUGH.md) shows a first
run that used a search excerpt and a later run that opened the full v2 policy.
The employee's selected scope still applies to record tools: a Support
employee may read the ticket and case document while shipment and finance
queries are denied. The answer must identify which claims came from the
document rather than from those restricted tables.
The final scoped run offered the Support agent only permitted record
entities, so it did not attempt those out-of-scope queries.
The [partial-dispatch walkthrough](PARTIAL_DISPATCH_WALKTHROUGH.md) gives
another dated example: Support verified order lines and ticket events through
permitted SQL projections, then attributed restricted shipment and invoice
facts to a fully read case document. A customer run used only `my_order` and
left delivery and the next dispatch date unresolved. Both runs and their
event streams are saved for inspection.
That case also exposed an invoice-reference error: `orders.source_invoice_no`
is the archived source invoice number, not an Acme invoice relationship.
The order tools now state this in their returned facts, and the agent prompt
requires an invoice-by-order lookup under `finance.read` or a clearly labeled
document report when that scope is unavailable.
The [r13 partial-dispatch revision](PARTIAL_DISPATCH_WALKTHROUGH.md#reproduce-the-r13-correction-and-handoff)
adds a second, Operations-scoped document for the same case. The Warehouse
agent can inspect the shipment-item and stock-movement chain in SQL; Support
can inspect its ticket and order lines but relies on its case document for
physical and Finance claims. Both scopes see the inventory reservation only
as a product-and-warehouse aggregate, not an allocation to the order. The
saved r13 runs show which claims came from SQL and which came from documents.
The [r14 settlement case](SETTLEMENT_WALKTHROUGH.md) shows a different
boundary: a Finance agent can read the scoped reconciliation and SQL payment
rows, while the customer sees only its own invoice ledger. The Finance
payment tool returns allocation totals across all invoices for each payment;
an allocation page for one invoice alone cannot establish that another
customer payment is unallocated. The customer ledger exposes credits but no
refund register, so absence of a credit note is not proof of no refund.

When a record ID is known, `search_documents` can require a complete ID
mention in a permitted document body. This narrows discovery without treating
the document as proof of the record. The [supplier review discovery case](DOCUMENT_DISCOVERY_CASE.md)
follows a live model call through retrieval, full-version reading and SQL
checks.
For a known document ID, `list_document_versions` reveals only the permitted
catalog metadata: version, status and effective dates. It does not read the
Markdown body. The agent then calls `read_document` for the exact versions it
needs. This matters when two reviews share one calendar date: date search
selects the latest version, while the version list preserves the earlier one.
The [supplier completion case](SPLIT_COMPLETION_WALKTHROUGH.md) follows this
revision history alongside the linked SQL receipts and stock movements.

The agent-facing modules `agent.py`, `runtime.py`, `customer_tools.py` and
`company_tools.py` use `demo_identity.py` to resolve the selected actor. They
do not import FastAPI or the portal's page/data modules. `portal_identity.py`
only re-exports that shared identity API for the website. Selecting a customer
reads the customer's name by ID; the selector no longer loads up to 100 orders
and 100 invoices just to establish a session. **My account** fetches those
records separately when the page needs them, in independent 25-row order and
invoice pages.

Importing the FastAPI portal does not import `acme.agent` or `acme.runtime`.
The **Tools** page obtains its argument schemas from the same Pydantic models
used by the direct service (`tool_schemas.py`, `workspace_tools.py` and
`web_search.py`). Its examples are checked against both those service schemas
and the LangChain model tool schemas. The chat worker imports the agent graph
when a message is actually run; the website handles browsing and editing
without constructing it. This import boundary has an isolated-process test.
The superuser's **Check links** view calls the deterministic, read-only
`audit_contemporary_history` service directly from FastAPI. Its 50 SQL and
planning checks do not ask the model to judge database consistency.
The [live import-boundary probe](../artifacts/portal-agent-import-boundary-2026-10-21.json)
also records the Tools API schema and a successful post-change chat with an
actual `sales_targets` SQL event. It checks startup and one chat, not sustained
runtime isolation or load.

`my_orders` returns an exact lifetime count, earliest/latest order IDs and
dates from the whole owned history, and at most 50 orders per call.
`next_offset` lets the agent inspect older orders without treating the first
page as the full history. The account page similarly lets a customer browse
every owned order and invoice, rather than stopping at the latest 100.
The [customer history paging case](CUSTOMER_HISTORY_PAGING_CASE.md) shows a
wrong one-page model answer, the SQL correction, and a later three-page run.

`my_order` reads at most 100 order lines per call. It reports `total_lines` and
`total_pence` for the whole owned order, plus `returned_lines`, `has_more` and
`next_offset` for the current page. A customer order with more than 100 lines
therefore needs another call to inspect every product; the first page is not
the whole basket. Each line also reports dispatched and still unshipped units.
The tool resolves ownership from the selected server persona on every page.

`my_invoices` returns one bounded page plus the exact whole-account invoice
count, billed total and outstanding balance. `my_invoice` reads one owned
invoice and pages through its linked payment allocations and credit notes.
The balance alone does not identify an individual payment or prove a refund.
The [current invoice walkthrough](CUSTOMER_INVOICE_AGENT_WALKTHROUGH.md)
separates the model's native call, Python ownership check, SQLite rows and
final answer using actual 2026 event IDs. The clickable website invoice view
uses separate read-only portal data code, so React does not call an agent tool.

## Three different kinds of persistence

| File | Key | Meaning |
| --- | --- | --- |
| `state/checkpoints.sqlite` | Conversation thread ID | LangGraph checkpoint: graph state and message continuity within one chat. |
| `state/app.sqlite` | Persona, conversation, run and operation IDs | Selected personas, accepted messages, readable transcript, proposed operations and decisions. |
| `state/memory.sqlite` | Stable persona account ID plus topic | LangGraph `SqliteStore`: explicitly requested preference notes shared across that persona's chats. |

`acme/runtime.py` opens the SQLite checkpointer and store during a run and
passes both to `create_agent`. `acme/memory_tools.py` uses `runtime.store` in
model tools; the direct Workbench opens the same file. A note is stored only
when the user explicitly asks the agent to remember a non-sensitive
preference, or when a tester runs `remember_note` directly. It is not an
automatic summary of chats. It rejects email addresses and Acme record IDs;
the system prompt directs the model to get current business facts from tools.
`recall_notes` retrieves only the selected persona's namespace. Resetting the
company exercise database does not erase conversation or preference memory;
start a new thread after a reset because old chat evidence may describe the
previous company state.

LangChain distinguishes thread-scoped checkpointers from cross-thread stores
in its [long-term memory guide](https://docs.langchain.com/oss/python/langchain/long-term-memory).
Acme uses local SQLite for both, with separate files and purposes. There is no
embedding index for preference notes.

## Input, tool, output and trace path

1. FastAPI binds a browser cookie to the chosen demo persona. `ui_service.py`
   accepts a message once using a submission ID and persists it before
   inference. A completed duplicate returns its saved result.
2. `runtime.py` loads the checkpoint, builds middleware, and streams the agent
   with `stream_mode=["messages", "values"]`. The first channel provides model
   output previews; the second keeps graph state and transcript in sync.
3. `RuntimeContextMiddleware` injects server-derived identity, filters offered
   tools, and rejects hidden writes in read-only mode. Built-in LangChain
   middleware applies configured model/tool limits, transient model retry,
   optional email redaction and optional context summarization.
4. `VisibilityMiddleware` records the effective model request and tool results.
   `company_queries.py` uses fixed query templates and bound values; the agent
   cannot supply SQL syntax or a table name. The separate superuser SQL console
   in `portal_data.py` is read-only and bounded.
5. `state/events.sqlite` records actual SQL, retrieval, provider, tool and
   decision events. The **Execution** view compares these with the agent's
   answer. An answer alone is a claim, not evidence that a tool ran.

In **Execution**, `model_response` records what the model requested.
`tool_attempt_started` records that LangChain began handling the call;
`sql`, `retrieval` and `tool_result` record the application work and its
structured outcome. `tool_message` is the value handed back to the model.
For structured service errors, the adapter also marks that LangChain
`ToolMessage` as `error`; its complete content and call ID remain available.
The key-events view also shows `tool_error`, `native_tool_error`, failed
attempts and `run_failed`, so a rejected or failed call cannot look like a
successful lookup just because the model asked for it.

The standard preset limits a run to 12 model calls, 20 tool calls and 120 graph
steps, with one retry for classified transient model failures. The `summary`
preset replaces older *model context* after six messages while retaining two
recent messages; it does not delete the readable transcript. The `pii` preset
redacts email addresses in incoming model input. These are configurable in
`models.toml` and inspected with `acme doctor`. Redaction is not a privacy
guarantee for stored transcripts, all tool results or exports; use fictional
details for demonstrations. See the [middleware lesson](middleware.md).

Tool arguments are validated by strict Pydantic models, permissions are
rechecked, query values are bound, and result sizes are capped. Tool errors
return structured errors rather than fabricated facts. Provider retries do
not replay company writes. The owned CSV workspace in
`acme/workspace_tools.py` persists bounded local files and job state for
longer calculations; it does not expose arbitrary host filesystem access to
the model. Its fixed worker has deadlines and cancellation. Optional Docker
code execution in older lessons is outside the normal site path.

The fixed company query catalog distinguishes a forecast from its commercial
target. `forecasts` contains model output and frozen training facts;
`forecast_runs` records the method, cutoff and assumptions; `sales_targets`
links a separate Sales decision to one forecast. An analytics employee can
read the exact target row, while a customer cannot. The agent uses a planning
document for the decision narrative and checks its numerical target against
that SQL row. The [planning trace](../artifacts/planning-target-agent-2026-10-21.json)
shows the tool calls before and after this query was added. The
[step-by-step planning walkthrough](PLANNING_AGENT_WALKTHROUGH.md) connects
those events to the three SQL rows, the exact Markdown version and the
agent's final answer.

Forecast accuracy has a separate time boundary. `business_summary` counts
invoice-line units only through the forecast's business reference date. For
an unfinished target period it returns the partial count and `null` error
fields; the agent should not score a full-month forecast against that partial
count. The [open-period trace](../artifacts/forecast-open-period-agent-2026-10-21.json)
shows the earlier misleading direct tool result and a later successful agent
call with the corrected contract.

Supplier receipts have a pagination boundary too. A purchase-order item now
reports the count and total quantity of all linked goods receipts and its
remaining ordered quantity. The [partial receipt walkthrough](PURCHASE_RECEIPT_AGGREGATE_CASE.md)
shows why the first receipt page is insufficient, plus a model run that checks
the exact stock movement separately.

## Human decision for destructive-looking actions

`save_report` and `update_ticket` create durable pending operations. The
superuser-only `simulate_delete` does the same for either an allowlisted SQL
record or one exact document version. It validates that the target currently
exists, then saves the proposal in `app.sqlite`. The model cannot approve it.

In **Execution**, a person inspects the payload and approves or rejects it.
The application rechecks ownership, current permissions and any edited
arguments. A repeated decision returns the recorded outcome. For
`simulate_delete`, approval records `simulated=true` and `deleted=false`;
there is **no SQL DELETE and no file removal**. The target remains readable
after approval. This is Acme's application-level human decision workflow,
not LangChain's graph `interrupt()` or `HumanInTheLoopMiddleware`. That
distinction matters when teaching the example. LangChain's native
[human-in-the-loop guide](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
shows how a graph interrupt pauses and resumes inside the agent; Acme's
persisted proposal ends the agent run and handles the decision separately.

## Five useful live demonstrations

For a concrete model/tool/SQL/answer sequence with exact event IDs, read
[one recorded agent run](ONE_AGENT_RUN.md) before changing the agent code.
For a counterexample where two plausible answers were wrong before the tool
contract was corrected, read [the customer invoice failure case](AGENT_FAILURE_CASE.md).
For a provider response that *looked* like a tool call but executed nothing,
read [the native tool-call failure](NATIVE_TOOL_CALL_FAILURE.md).
For a live failure caused by an invented document date and a confused account
contact, read [the current account-terms case](BOT_SCENARIOS.md#7-current-account-terms-after-the-directory-release).
For a current Finance invoice/document question and the local model comparison,
read [the Finance agent case](FINANCE_AGENT_MODEL_COMPARISON.md).
For a current customer invoice with a credit note, read
[the customer invoice walkthrough](CUSTOMER_INVOICE_AGENT_WALKTHROUGH.md).
For an employee forecast and target comparison backed by both SQL and
Markdown, read [the planning walkthrough](PLANNING_AGENT_WALKTHROUGH.md).
For a customer access boundary and the difference between an unrecorded
delivery and a known physical state, read
[the boundary and fulfillment case](AGENT_BOUNDARY_AND_FULFILLMENT_CASE.md).

1. Select `DEMO-CUST-001`, open **My account**, read the address, then ask the
   customer assistant to call `my_profile`. Compare the answer with the tool
   event. A prior audited address edit appears in both views.
2. Select customer `UCI-CUST-12748` (145 historical orders in the current
   full bundle). Ask for total orders and most recent order. `my_orders` returns
   the lifetime count and at most 50 records per page; **My account** shows 25
   per page. Page through both and compare their 145-order lifetime count. The
   earlier incorrect live answer and its correction are in
   [bot scenarios](BOT_SCENARIOS.md).
3. Select customer `UCI-CUST-17850` (last recorded order on 2010-12-01).
   Ask when the account last ordered. The record supports a lapse, not an
   invented reason for it. See [bot scenarios](BOT_SCENARIOS.md).
4. In **Tools**, run `remember_note` with topic `answer style` and note
   `Prefer concise bullet points`; start another conversation as the same
   persona and call `recall_notes`. Switch persona and observe an empty result.
5. As superuser, run `simulate_delete` for customer `DEMO-CUST-001` with a
   training reason. Inspect the pending operation in **Execution**, approve
   it, then open the customer in **Database** again. Its row still exists and
   the decision event says `deleted=false`.

These demonstrations require a configured tool-capable model only when using
the chatbot. Catalog, account, knowledge, database and direct tool checks work
without a model. `acme doctor --inference` verifies a model separately.

## Code and checks

- `acme/agent.py`: prompts, model tool schemas, `create_agent`.
- `acme/runtime.py`: accepted submissions, checkpoint/store lifetime,
  streaming and transcript persistence.
- `acme/demo_identity.py`: shared persona selection and trusted actor lookup;
  `acme/portal_identity.py` is the website compatibility entry point.
- `acme/customer_tools.py`: customer-bound SQL profile, orders, invoices,
  settlement ledger and exact current account-terms lookup; the model cannot
  supply a different customer ID.
- `acme/middleware.py`: identity injection, selection, limits, retry,
  optional summarization and PII transformation.
- `acme/company_tools.py`, `acme/tool_schemas.py`, `acme/company_queries.py`:
  strict company service, prepared SQL and proposal decisions.
- `acme/memory_tools.py`: explicit persona-scoped LangGraph store access.

```powershell
uv run python -m unittest tests.test_portal tests.test_memory_tools tests.test_data_quality -v
uv run python -m unittest tests.test_ui_revision.UIRevision.test_ui_build_callbacks_and_import_layout -v
uv run acme doctor
```

For future document retrieval beyond lexical search, see the
[RAG roadmap](RAG_ROADMAP.md). The current corpus is versioned Markdown, not
an embedding database.
