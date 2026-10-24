# Follow a planning answer across SQL, a document and the agent

This is one recorded website run from 21 October 2026. The selected demo
employee was `EMP-004` (analytics), using `qwen3.8:latest`. The question asked
for the October linen-cover desk notebook forecast, its linked Sales target,
the two-month input window, and whether the target was a model prediction or a
planning decision. The compact [before/after extract](../artifacts/planning-target-agent-2026-10-21.json)
preserves the question, answers, tool calls and independent SQLite rows. The
full local event stream is in `state/events.sqlite`, thread
`thread-cf67f06f56c5499f8bf93b6f74b7f718` for the successful run.

The 2011 retail transactions remain a separate source cohort. This example
uses authored, clearly fictional 2026 business history; its forecast inputs
exclude the 2011 archive and October target-month invoices.

## Start with the data, before asking the model

The four identifiers in this example mean different things:

| Identifier | Where it lives | What it proves |
| --- | --- | --- |
| `SCN-FC-79511D9988BA-2026-10-v2` | `forecasts` | Recorded model output: **6 units**; 12 training units and last qualifying invoice date 2026-09-24. |
| `SCN-FCRUN-79511D9988BA-2026-10-v2` | `forecast_runs` | Method: trailing calendar-month mean; two-month lookback; input cutoff 2026-09-30; target period 1–31 October. |
| `SCN-TARGET-79511D9988BA-2026-10-v2` | `sales_targets` | A **7-unit** commercial target linked to that forecast by `forecast_id`, with a 110% uplift assumption. |
| `PLAN-79511D9988BA-2026-10-v2`, version 2 | Registered Markdown document | The decision narrative, input assumptions and interpretation. It is not the SQL target row. |

The arithmetic is 12 billed units ÷ 2 preceding complete months = 6 forecast
units. Sales chose 110% of 6 and rounded 6.6 half up to 7 target units. The
forecast record and the target record are distinct; one does not overwrite the
other. The saved extract contains independently queried rows for all three
tables, so the answer is not being checked only against its own wording.

## What happened in the agent run

The browser sent a company-chat request. `acme/portal.py` and
`acme/ui_service.py` bound the selected employee to the request, queued it and
handed it to `acme/runtime.py`. The runtime opened the conversation checkpoint,
created the company agent and streamed its steps. `acme/agent.py` builds that
agent with LangChain `create_agent` and model-visible `@tool` definitions.
The employee identity is injected through `ToolRuntime[RunContext]`; it is not
an argument the model may edit.

| Event | What the trace shows | Who owns that step |
| --- | --- | --- |
| `7368 request_accepted` → `7371 checkpoint_loaded` | Submission, run setup and conversation state were recorded. | Acme runtime and LangGraph checkpoint |
| `7383 model_request` → `7388 model_response` | The model received permitted tool schemas and requested three native calls: `lookup_record` for `forecasts`, `lookup_record` for `sales_targets`, and `search_documents`. | Model chooses calls and arguments; no SQL has run yet. |
| `7404 native_tool_started` → `7406 sql` → `7407 tool_result` | Python ran `SELECT ... FROM forecasts WHERE id=?` with the exact forecast ID; one row returned `units=6`. | Acme company tool and SQLite |
| `7415 native_tool_started` → `7421 sql` → `7422 tool_result` | Python ran the fixed `sales_targets` lookup with the exact target ID; one row returned `target_units=7` and the matching `forecast_id`. | Acme company tool and SQLite |
| `7418 native_tool_started` → `7429 retrieval` → `7430 tool_result` | Keyword search on permitted Markdown returned ranked excerpts; the matching planning document was first. | Acme document service; this is lexical search, not vector RAG |
| `7451 model_response` → `7466 native_tool_started` → `7468 document_read` → `7469 tool_result` | The model selected document `PLAN-79511D9988BA-2026-10-v2`, version 2. Python returned its complete 1,883-character body. | Model chooses exact version; service checks access and file hash |
| `7510 model_response` → `7526 run_completed` | With tool messages in context, the model wrote the final answer and the runtime saved it. | Model wording, then Acme persistence |

Some of the first three tool calls overlapped: `search_documents` started
before the target SQL event was written. Read the sequence numbers as the order
of recorded events, not as a claim that all calls executed one after another.
`model_response` records a *request* to call a tool; `sql`, `retrieval` and
`document_read` show what the application actually did. `tool_result` is the
structured result; `tool_message` is what LangChain passed back to the model.
The trace cannot reveal hidden model reasoning.

`acme/company_queries.py` owns the allowlisted SQL templates and checks the
employee's `analytics.read` permission. Values are bound as parameters. The
model cannot submit its own SQL through `lookup_record`, switch the database
path, or grant itself another scope. `acme/company_tools.py` validates tool
inputs and returns bounded record envelopes. The separate website **Database**
page has its own browsing routes and a superuser read-only SQL console; opening
a row there does not run this agent.

The document search in `acme/company_tools.py` tokenizes permitted Markdown,
scores literal word matches, and returns excerpts and version references. The
agent then called `read_document` for the exact version. The registered file's
SHA-256 is checked before its body is returned. The document provides why the
target was chosen; the `sales_targets` row is the separate evidence that the
number was actually recorded in the company database.

## Why the earlier answer was weaker

The extract also contains an earlier run of the same question, thread
`thread-34cdd9ebb8744acbac1fb25255237499`. At that point
`sales_targets` was not in the agent's bounded query catalog. The model looked
for the target ID under `forecasts` (`7207` → `7209`), got zero rows, and
correctly limited its claim: the 7-unit target appeared in the planning
document, but it could not verify a separate database target record. The row
did exist in SQLite; it was the agent's **tool access** that was missing.

After `sales_targets` was added to the schema and allowlisted query, the later
run fetched both exact rows and could cite the target as a stored record. This
is why a plausible answer and even a relevant document are not sufficient
proof of a database fact. It also demonstrates the distinct roles of data,
documents, tools and the language model in this example.

## Reproduce it in the website

1. Start the local site as described in the [portal guide](PORTAL_GUIDE.md).
   A configured tool-capable model is needed for chat; Database and Knowledge
   browsing work without one.
2. Select **Employee**, find `EMP-004`, and open **Workspace**. Ask: “For the
   October 2026 linen-cover desk notebook planning review v2, compare forecast
   `SCN-FC-79511D9988BA-2026-10-v2` with target
   `SCN-TARGET-79511D9988BA-2026-10-v2`. Verify both records, explain the
   two-month lookback and cutoff, and cite the document version.”
3. Open **Execution** for the new conversation. Inspect **Model response**,
   **Tool call**, **SQL**, **Retrieval**, **Document read**, **Tool result** and
   the final response. A fresh run may choose a different valid path and will
   have different event IDs.
4. Open **Database** and browse `forecast_runs`, `forecasts` and
   `sales_targets`; then open the versioned planning document in **Knowledge**.
   Compare the linked IDs, figures and dates yourself.

This evidence covers two runs of one question. It verifies the observed
after-run answer and the data path, not the reliability of every future model
response or the truth of the fictional company's plan.
