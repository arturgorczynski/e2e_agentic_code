# Follow an answer through its execution

The project-local trace recorder captures **observable application and LangChain
inputs and outputs**. It does not reveal hidden model reasoning or promise an HTTP
wire dump. It stores events in `state/events.sqlite`, separately from the conversation
transcript and official checkpoints. Reading, searching, comparing and exporting
requires the owner of the conversation. No running model or Docker is needed to
inspect a saved trace.

Start with the [agent CLI walkthrough](agent_runtime.md), then use its `$thread` ID.

## Search, compare and export

```powershell
uv run --locked acme chat trace --thread $thread --limit 20
uv run --locked acme chat trace --thread $thread --kind sql
uv run --locked acme chat trace --thread $thread --search DEMO-INV-001
```

Results contain `events`, `has_more` and `next_cursor`. Pass `next_cursor` as `--after`
to continue. `--run-id` filters to one application run. Filters combine; text search
is a literal case-insensitive substring of persisted JSON, limited to your thread.
It is a simple SQLite query, not a separate search service. Page size is 1–100.

Compare the first two main-model requests, including their system instructions,
messages, tool descriptions/schemas and recorded generation settings:

```powershell
$requests = uv run --locked acme chat trace --thread $thread --kind model_request --limit 2 | ConvertFrom-Json
$before = $requests.events[0].id
$after = $requests.events[1].id
$comparison = uv run --locked acme chat diff --thread $thread --before-event $before --after-event $after | ConvertFrom-Json
$comparison.unified_diff
```

The result also includes complete `before` and `after` snapshots and exact message
edits with source/destination ranges and inserted/removed values. A replaced message
retains both versions. Redacted comparisons are marked; they show differences in
the visible, redacted copies, not undisclosed secret values.

Export the entire thread, across all pages and process restarts:

```powershell
uv run --locked acme chat export --thread $thread --format markdown
uv run --locked acme chat export --thread $thread --format json
```

The commands return the written path under `state/exports/THREAD_ID/`. Markdown
contains a timeline, context-source map, consecutive-input diffs and full event
payloads. JSON contains the same evidence for scripts. Exports contain company and
conversation content; redaction is a credential filter, not a general privacy scrubber.

## Read the event hierarchy

| Field | Meaning |
| --- | --- |
| `seq`, `id` | Database append order and unique event ID |
| `thread_id` | Owned conversation |
| `run_id` | Logical accepted user submission, or direct tool-operation scope |
| `execution_id` | One execution/resume/approval invocation |
| `span_id`, `parent_id` | An operation and its containing operation |
| `created_at` | Actual UTC recording time; distinct from the 2011 business clock |
| `duration_ms` | Measured elapsed time for a completed operation, when applicable |
| `redacted`, `redaction_paths` | Whether recorded/displayed values were hidden and where |
| `capture` | `boundary-v2` for new instrumentation; `legacy` for older events |

The execution hierarchy has two useful layers. Application spans identify a main
model attempt, a tool attempt, the company-tool service and an approval. Native
LangChain spans identify graph nodes, provider invocations and helper-model chains.
Provider events retain `native_parent_id` as well as their enclosing application
attempt. These layers describe the same execution at different boundaries; adding
their event counts does **not** count independent model/tool calls.

`seq` is recording order. Background checkpoint commits may be observed alongside
node execution; use parent/checkpoint IDs for causal relationships rather than
assuming recording order alone explains causality. A hard process kill can leave a
started span without a finishing event. The recorder does not invent a completion.
An explicit resume gets a new execution ID while keeping the application run ID.

| Events | What they establish |
| --- | --- |
| `request_accepted`, `request_resumed` | Accepted input and stable message/submission identity |
| `run_started`, `run_completed`, `run_failed` | Run settings, outcome and elapsed time |
| `model_attempt_started/finished` | One passage through the main-model handler, including retries |
| `model_request`, `model_response`, `model_error` | Effective LangChain request and linked response/error |
| `provider_started/finished/error` | Actual LangChain model invocation, returned metadata and usage |
| `chain_started/finished/error` | Named native graph/middleware/helper node and parentage |
| `tool_attempt_started/finished`, `native_tool_*` | Model tool-call ID, validation/execution and outcome |
| `tool_started/finished`, `tool_result`, `tool_error` | Shared company-tool service, including direct CLI calls |
| `sql`, `retrieval`, `document_read` | Executed prepared query or selected document evidence |
| `context_change` | Before/after messages, changes, stage and available source references |
| `checkpoint_loaded/committed/writes` | Official saver state transitions, parent checkpoint and task IDs |
| `approval_requested`, `approval_started/finished`, `approval_replayed`, `business_decision` | Pending operation, owner continuation, outcome and replay |

## Explain an invoice answer

The saved [real local-model example](examples/g08_invoice_trace.md) answers an invoice
question, follows up about allocations/credits, then recalls the balance in a fresh
process. Its [JSON export](examples/g08_invoice_trace.json) can be verified without
the application state:

```powershell
uv run --locked python scripts/verify_trace_export.py docs/examples/g08_invoice_trace.json
```

Work backward from a `model_response`:

1. Its `request_event_id` identifies the exact effective model input.
2. Find the tool messages in that input. The export's `provenance` map connects their
   assigned message IDs to the earlier `tool_message` event by tool-call ID.
3. Follow that attempt's child company-tool span. `tool_result` supplies the invoice,
   allocation or credit fields; a sibling `sql` event gives the actual template,
   parameter values, required permission and returned row count.
4. The invoice result is **70,000 pence / GBP 700.00**, the allocation is **45,000
   pence / GBP 450.00**, and the credit is **5,000 pence / GBP 50.00**. They are not
   inferred from the model's prose.
5. Compare consecutive model inputs to see the tool requests/results enter context.
   Human input points to acceptance, AI messages to model responses, tool output to
   tool messages, and middleware replacements to their context-change stage.

Document investigations follow the same path: `retrieval` records the query, ranking
rule and selected versions; `tool_result` includes excerpts and source references;
`document_read` records the exact version and offset subsequently read. A denied
company query has no fabricated `sql` event.

An application service can return a structured `status="error"` result without
raising a Python exception. The agent adapter maps that result to a LangChain
`ToolMessage(status="error")` for company and web-search tools; workspace
errors use their top-level `error` field. The model receives the complete
error body, and `tool_message` records its error status. Check `tool_result`
or `workspace_error` for the service decision and `tool_message` for what was
actually handed back to the model. Older saved runs retain their original
messages; this mapping does not rewrite historical traces.

To reproduce the complete LangChain path without a provider call, run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent_tool_status.AgentToolStatusTests.test_full_agent_graph_keeps_structured_error_status -v
```

The scripted model requests `lookup_record` with an empty record ID. Python
returns `invalid_arguments`; the test inspects the graph's persisted transcript
and `tool_message` event and requires `status="error"` in both. It uses an
isolated temporary state and does not change the active exercise database.

## Summaries, masking, errors and approvals

Named native middleware nodes capture before/after state updates, including removed
messages and inserted summaries. The effective-request boundary also compares graph
state with the request actually passed to the main model, and successive main-model
inputs produce their own context-change events. The transcript remains separate.

Callbacks propagate into the built-in summarization model. Its `provider_started`
event has `purpose="summarization"`, its own input/output and native parent. Main-model
retries create distinct attempt/provider spans; a new provider invocation after an
error records `previous_failed_span_id` in the same execution/node/purpose. Native
retry notifications are retained when LangChain emits them. A provider SDK's internal
HTTP retries do not necessarily cross this boundary and are not claimed as captured.
New custom helper calls must inherit the runtime callback configuration.

Generation settings use an explicit allowlist; arbitrary client configuration,
headers and credentials are not serialized. Usage comes from returned LangChain
`usage_metadata`/provider metadata when available; missing usage stays missing.
Native callback `configuration_match` states whether a unique registered model
supplied constructor defaults. Callback-reported values override those defaults;
the main request snapshot also records the effective model's settings directly.

The test suite executes real `ModelRetryMiddleware`, `SummarizationMiddleware` and
`PIIMiddleware` with deterministic fake models. It verifies failure/retry links,
summary helper calls, email masking and message removal. These are actual middleware
executions, not evidence of provider summarization quality. They are validation
configurations; the default agent's teaching middleware presets arrive in G09.

Current approvals use an application-level operation workflow: proposal, end
the agent run, then let the selected demo persona approve or reject in the
portal or CLI. Decision events keep the **proposal's original run ID** and the
decision's execution ID. Repeated decisions emit a replay event and do not
repeat the business write. This is not a LangChain graph interrupt.

## Credential handling and compatibility

Before SQLite insertion, the recorder hides the current session token, configured
secret values from this project's `.env` and environment, sensitive dictionary fields,
and recognized inline credential/Bearer patterns. Model settings are allowlisted.
Tests inspect the database bytes, search results and exports for planted credentials.
Redaction happens on a copy, so it does not silently change the actual model input.
Consequently, a trace is not a replacement for the private transcript/checkpoint store.
Arbitrary undisclosed secrets in free-form prose cannot be reliably classified.

Existing event tables gain additive metadata columns. Old rows are preserved and
marked `legacy`; missing historical durations/parents/helper calls are not reconstructed
as if observed. Search/export applies the current credential filter to old payloads
too, but original capture policy and credentials no longer available locally cannot
be retroactively verified.

Implementation: [tracing.py](../acme/tracing.py) owns persistence/redaction/spans,
[trace_hooks.py](../acme/trace_hooks.py) owns LangChain callbacks and the thin
`SqliteSaver` subclass, and [trace_view.py](../acme/trace_view.py) owns inspection.
These are project-local helpers. Persistence itself still delegates to the official
saver. Official references: [middleware API](https://reference.langchain.com/python/langchain/agents/middleware),
[callback methods](https://reference.langchain.com/python/langchain-core/callbacks/base/AsyncCallbackHandler),
and [summarization](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware).
