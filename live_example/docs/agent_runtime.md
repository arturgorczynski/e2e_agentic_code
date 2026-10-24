# Run and inspect the single agent

**Current portal note (2026-10-20):** the website is React + TypeScript served
by FastAPI. Its persona switcher is password-free and deliberately visible for
local scenario testing. The CLI instructions below document the earlier lesson
and some terminology is historical. Use the [portal guide](PORTAL_GUIDE.md) to
operate today's site and [agent architecture](AGENT_ARCHITECTURE.md) for the
current checkpoint, memory-store and approval boundaries.

## Historical G07 CLI walkthrough

The runnable G07 interface is a CLI. It uses LangChain `create_agent`, hidden
`ToolRuntime` context injection and the official SQLite checkpointer. The eight
company tools are described in [Company tools](company_tools.md). No Docker is needed.
G08 adds [persisted trace search, input diffs and exports](execution_traces.md).
The [learning UI](learning_app.md) now provides the same owned conversations,
editable approvals and inspection views. The [middleware lesson](middleware.md)
configures retries, summaries, email redaction and tool selection. The ninth tool,
`analyze_workspace`, adds bounded local CSV analysis.

## First conversation

Run these commands from `live_example/`. Install dependencies and initialize the
shipped database:

```powershell
uv sync --locked
uv run --locked acme company init
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Select `main = "local"` in the `[selection]` section of `models.toml`. In this project's
`.env`, set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` to your running Ollama server and an
installed tool-capable model. This checkout currently uses `qwen3.8:latest` in
its local `.env` after the recorded [Finance comparison](FINANCE_AGENT_MODEL_COMPARISON.md).
Its hardware requirements are substantial. Other model choices need their own
capability check. `ollama list` shows installed models. To use this model on
another machine, install it with `ollama pull qwen3.8:latest` and set
`OLLAMA_MODEL=qwen3.8:latest`. Normal
application startup does not download models or silently switch to a cloud provider.

Create one of the five predefined local accounts. Passwords are entered through a
hidden terminal prompt; choose your own password of 12–200 characters:

```powershell
uv run --locked acme account --username morgan.finance
uv run --locked acme login --username morgan.finance
$created = uv run --locked acme threads create --title "Invoice investigation" | ConvertFrom-Json
$thread = $created.thread_id
uv run --locked acme chat send --thread $thread --submission-id invoice-1 --message "How much is still owed on DEMO-INV-001, and how many days overdue is it?"
uv run --locked acme chat send --thread $thread --submission-id invoice-2 --message "For that same invoice, show the allocated payment and credit-note IDs and amounts."
```

Every command is a new process. Expected company facts are £700 outstanding, nine
days overdue, £450 allocated payment and £50 credit, at business date 2011-12-09.
Verify the answer against the recorded tools. Provider wording can vary.

For another role, create and log in as `alex.sales`, `jamie.operations`,
`taylor.analyst` or `sam.support`. Roles expose different company records and document
scopes. Each account sees only its own threads, transcript, operations and reports.
The G02 contract's historical “design accounts” note means no passwords are shipped;
G07 now activates those identities through explicit local account provisioning.

Inspect or return to a conversation:

```powershell
uv run --locked acme threads list
uv run --locked acme chat history --thread $thread
uv run --locked acme chat events --thread $thread
```

After reopening your terminal, log in if necessary, run `threads list`, and set
`$thread` to the returned ID. History/events return up to 100 rows; pass the last
`seq` as `--after` to continue. `threads archive --thread $thread` preserves readable
history and events while preventing new execution. The learning UI also offers
rename and saved selection after refresh. The commands themselves are platform-neutral; the variable examples
above use PowerShell. macOS/Linux reproduction has not been verified.

## Pending report or ticket

Ask Morgan to prepare an invoice report and cite the invoice. The model should call
`save_report`, return `pending_approval` and provide an operation ID. Inspect the
concrete payload before making a decision:

```powershell
uv run --locked acme operation show --thread $thread --id OPERATION_ID
uv run --locked acme operation approve --thread $thread --id OPERATION_ID
uv run --locked acme report --thread $thread --id REPORT_ID
```

Replace the uppercase placeholders with returned IDs. Alternatively use `operation
reject` for a pending proposal. The model has no approval tool. You can exit and
restart before deciding: the proposal is in `app.sqlite`. The agent run itself
finishes with the pending proposal. Approval is a separate durable application
operation, rather than a suspended graph node. To discuss a decision, send a new
message with a new submission ID. The UI also supports editing arguments before approval.

To try a tool without any model, use the same login and thread:

```powershell
$arguments = '{"entity":"invoices","record_id":"DEMO-INV-001"}'
uv run --locked acme tool lookup_record --thread $thread --operation-key inspect-1 --args $arguments
```

Direct tool operation keys must be reused for retries. Use a new key for an
intentional new action. Within agent runs, the runtime supplies the operation scope.

## Persistence and retries

| File under `state/` | Responsibility |
| --- | --- |
| `company.sqlite` | Writable exercise company, initialized from immutable baseline |
| `app.sqlite` | Accounts, sessions, owned conversation catalog, runs, transcript, operations, reports |
| `checkpoints.sqlite` | Official LangGraph SQLite checkpoints for agent state |
| `events.sqlite` | Actual model, tool, query, retrieval and decision events |
| `runner.sqlite` | Cross-process SQLite execution lock |
| `client_session.json` | Local CLI client's current bearer session |

Conversation IDs, authenticated user IDs, application run IDs and tool operation IDs
have distinct roles. A client submission ID identifies one accepted message within
one thread. Retrying a completed submission returns the same run and result without
calling the model. Reusing that ID for different text is rejected. Accepted human
messages are committed before inference; graph messages use stable IDs and append
to a separate transcript. Removing messages from model context does not erase the
conversation transcript.

If the model fails or the process stops, resume the same submission explicitly:

```powershell
uv run --locked acme chat resume --thread $thread --submission-id invoice-1
```

Resume continues pending checkpoint work without adding another accepted human
message. An unfinished run blocks new messages in that thread until resumed. If no
checkpoint yet contains the accepted human message, it is supplied once to the
graph. The [configured middleware](middleware.md) retries only transient model failures,
records each attempt, and retains the accepted run's middleware settings during resume.

The initial policy is one active local runner. An exclusive SQLite transaction in
`runner.sqlite` serializes model execution and approval across CLI processes. A
second CLI invocation gets a busy error; the UI has its own persisted queue. The graph
uses two executor workers so streaming can wait for events while execution proceeds;
tool calls within a model response can therefore overlap. The outer lock still allows
only one agent run or approval at a time. A crashed process releases the SQLite lock. Read-only inspection
can continue while inference runs. The 30-step graph limit bounds graph progression;
it is not a deadline for an in-flight model call or tool.

## What the traces mean

`VisibilityMiddleware` in [agent.py](../acme/agent.py) is **our project-local helper**.
It records effective LangChain model inputs, exposed tool schemas and returned
messages. It is placed inside additional wrapping middleware so it sees their
effective model request. These records show observable inputs and outputs; they are
not hidden model reasoning or an HTTP wire dump. SQL and retrieval records come from
the corresponding executed code. G08 adds durations, parent relationships, context
diffs, retry/helper callbacks, checkpoint events and readable CLI exports. The
[trace walkthrough](execution_traces.md) explains both the evidence and its boundaries.

Passwords use salted scrypt hashes; server-side sessions store token hashes and
expire after eight hours. The CLI stores its bearer token in ignored
`state/client_session.json`, or accepts `ACME_TOKEN` from the environment. Tokens are
not model arguments or trace payloads. This is a trusted-machine learning application:
people who can read or modify its local files can bypass application-level controls.
Do not publish the state directory. The UI includes logout and isolated authenticated
sessions; active pages retain their own selected conversation.

`company reset --yes` resets **only company exercise data**. It preserves reports,
operations, history and checkpoints, which may describe the earlier exercise state.
Create a new thread after reset; retrying an already decided operation returns its
previous outcome and does not replay a company mutation.

## Verification

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked python scripts/verify_company_tools.py
uv run --locked python scripts/verify_live_runtime.py --output artifacts/my-live-check
```

The unit suite uses a labeled deterministic fake model. The live script actually
invokes local Ollama, creates an isolated full company state, runs three fresh CLI
processes, verifies context continuity, and checks duplicate submissions and denied
cross-owner reads. Its output directory must be new. No cloud backend is contacted.
Read [G06/G07 evidence](G06_G07_VALIDATION.md) for measured results and remaining limits.

Official API references: [LangChain tools and runtime context](https://docs.langchain.com/oss/python/langchain/tools),
[short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory),
and [SQLite checkpointer](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver).
