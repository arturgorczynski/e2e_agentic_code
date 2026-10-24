# Use Acme: chat, inspect and try tools

Run all commands from `live_example/`. The [quick start](../README.md#quick-start)
installs the locked dependencies, sets up prepared data and starts the server.
The normal path needs Ollama with a tool-capable model; Docker is optional.

## Choose or create your local user

`uv run acme setup` asks you to choose an existing username or create your own.
For a new local profile, enter a display name and select an access profile.
Existing configuration and exercises are preserved.

The browser opens **Choose your space**. Select a local profile, or expand
**Create a new user**. New profiles choose a name, username and one of four access
profiles; **Custom scope** exposes the individual tool/data scopes. The expandable
help explains the difference. Successful creation opens its own chat workspace.
Use **Switch user / sign out** at the bottom of the sidebar to change users.

| Role | Useful work |
| --- | --- |
| Analyst | Sales, forecasts, CSV analysis and reports |
| Finance | Invoices, allocations, credit notes and receivables |
| Sales | Customers, orders and commercial documents |
| Operations | Stock, purchasing and shipments |
| Support | Tickets, customer-facing order status and approved ticket changes |

Each new profile gets its own user ID, private conversations, files and traces.
It does not claim to be a company employee or rewrite the baseline dataset. Access
profiles control scopes on the server; they do not grant access to another profile's
private conversations. Create one from the terminal with
`uv run acme setup --username learner.one --access-profile employee`.

These are local learning accounts. Anyone with direct access to the SQLite files
controls their contents. The server binds to loopback; this is not enterprise identity.

## Chat and history

**Free chat** has no company tools. **Company assistant** can read company records,
search the fixed document corpus, calculate and propose changes. Select a mode in
the sidebar. Its **Chat history** shows only conversations in that mode, including
that mode's Trash. The history has a fixed scroll area, leaving room for tools and
Settings. **New chat** opens an unsaved draft in the selected mode. It enters history
only after the first accepted message. Older empty conversations are hidden.

Switching mode opens an existing conversation in the destination mode or an unsaved
draft if none exists. Selecting a history entry updates the view without page navigation.
Existing accepted conversations keep their mode and checkpoints. An empty chat can
change mode directly. Mode switching does not alter or erase earlier conversations.

Assistant messages are labeled on the left; your messages are on the right.
Enter sends; Shift+Enter adds a line. Your accepted prompt appears immediately, including
while the model worker is starting. Bubbles have space on both sides. Chat shows the final answer for each user
message, plus the current streamed preview while the agent is working. Intermediate
assistant narration that accompanies tool calls is preserved in **Executions**, so
repeated tool-loop announcements do not fill the conversation.

A chat's **...** menu contains Rename and Delete. Delete moves it into recoverable
Trash. Refresh and server restart retain saved conversations. Closing the browser
disconnects the viewer; the queued agent process continues. Use **Resume interrupted
response** after fixing the cause of an interrupted execution. It reuses the accepted
message rather than appending it again.
The Company tools accordion can be opened and closed. Chat requests awaiting approval
appear under **Review requested changes** in that same chat.
Both modes can use **web_search**, a free public search tool without an API key.

## Executions: follow a particular answer

1. Open **Executions**. Filter by words in the title or conversation, Free/Company,
   recent activity or an explicit UTC date range. Choose an owned conversation,
   or select **Inspect current chat** to open the current conversation.
2. The enlarged saved conversation appears below the selectors. Click a user or
   assistant bubble to select its execution, or use **Message / execution** above it.
3. Read its status and model/tool/context counts. The timeline lists what happened
   in order. Click a row directly; there is no separate step selector.
4. **Input** shows what entered that step; **Output** shows its result. A model-input
   step includes instructions, messages, offered tool schemas and settings. A tool
   result contains validated arguments and the recorded result.
5. Use **Raw event** for IDs and correlation metadata. Open **Compare model inputs**
   to choose two model calls and compare the exact context. No event IDs need to be
   copied manually.
6. **Conversation graph** shows each message/run and expands the selected run into
   clickable model, tool, database, context and approval nodes. Arrows show recorded
   event order. Select a node to read its input, output and raw event below the graph.

Intermediate model messages, prepared SQL, retrieval evidence, middleware settings
and context changes are retained here. These are observable execution records, not
hidden reasoning or an HTTP wire dump. `VisibilityMiddleware`, `RuntimeContextMiddleware`
and the execution viewer are project-local helpers. The [trace lesson](execution_traces.md)
explains the event contracts and CLI exports.

The viewer lists the latest 200 executions in a conversation. CLI/export commands
retain access to the complete persisted history and trace.

## Tools: run an action without the model

Open **Tools**. A private playground is created for your account automatically.
It has its own durable files, approvals and evidence and never appears in chat history.
No chat needs to exist or be selected. Switching chats does not change the playground.
Direct actions apply server-side role and ownership checks. Agent middleware tool
selection affects agent calls; direct exercises remain separate authenticated actions.

- **Tool catalog:** every model tool has a description, exact public input schema,
  editable example and a **Run tool** action. Inspect its result without calling a model.
- **Web search:** enter public search terms and get linked titles and snippets for free.
  DDGS uses public providers; rate limits and availability can vary. Queries leave the
  application, so use public terms. No search API key is required.
- **Documents:** browse all accessible document versions or search with an effective date,
  click a library row or choose a document/version and read
  the rendered content. Expand details to inspect exact sources and result fields.
  Retrieval is mock RAG text ranking, not vector search.
- **Calculator:** choose an operation and enter one number per line. For percentage
  change, `10000` followed by `7500` produces **-25%**. No model call is made.
- **Files & CSV:** select a playground file to preview its content. Prepare monthly sales
  CSV with Analytics access, choose the numeric/group
  columns, run analysis and download the result. Upload CSV opens an owned form.
  Worker deadlines and cancellation are real. Optional generated Python requires
  Docker and is described in [local execution](local_execution.md).
- **Database:** browse a permitted table/projection, search supported names, look up
  an ID or filter by a parent ID. **Next page** advances through bounded pages.
  Aggregates calculate sales, receivables or the customers with the most orders.
- **Review changes:** select a pending operation, inspect/edit its arguments and
  approve or reject. The server rechecks arguments, sources and permissions.
  Repeated approval returns the saved outcome. The advanced proposal form exposes
  `save_report` and `update_ticket` directly, without a model.
- **Reports:** browse and read reports saved by your account, including those from chats.
  Refresh the report list after approving a new report.

Company tools are also described in the sidebar while Company assistant is selected.
A role may read some projections and be denied others. The full contracts are in
[Company tools](company_tools.md).

## Connect to the database yourself

Open **Tools > Database > Connect to SQLite from Python**. It displays the exact
company database path used by the running server and a working read-only connection
example. There is no separate database server, port or database password.

For the default state, run this from `live_example/`:

```python
import sqlite3
from pathlib import Path

path = Path("state/company.sqlite").resolve()
connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
print(connection.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall())
print(connection.execute("SELECT id, name FROM customers LIMIT 10").fetchall())
connection.close()
```

Use the actual path shown by the app if it was started with `--state-dir`. Direct
file access is a developer capability and bypasses application role filtering.
Read-only mode protects exercise data while exploring. The [35-table dictionary](data_dictionary.md)
explains the physical schema; in-app exploration offers focused permitted projections.

## First company exercise

As Analyst, create a Company assistant chat and ask:

> Which customer placed the most orders? Use the complete company history, give
> the count and cite the evidence.

The agent should call `business_summary(report="customer_orders")` instead of
paging through sampled orders. The report ranks all matching orders, includes every
status, and defaults to the earliest order date through 2011-12-09. In the full
baseline, the leading customer is **Orchard & Finch Living (`UCI-CUST-12748`),
145 orders**. Confirm the exact record/query
in Executions. Then try the same aggregate directly in Tools > Database.

Other exercises and expected facts are in [Learning scenarios](learning_scenarios.md).

## Settings and diagnostics

Sidebar **Settings** shows your role, selected model profile, middleware preset and
call budgets. **Response refresh** adjusts how often this page displays new progress;
it does not change the underlying agent execution. Model connection values live in
this project's `.env`; profiles and middleware presets live in `models.toml`.
See the [middleware walkthrough](middleware.md). Start a new chat after changing presets.

```powershell
uv run acme doctor --inference
uv run acme doctor --full-data
uv run acme data verify
uv run acme company verify
uv run python -m unittest discover -s tests -v
uv run ruff check .
```

If a port is occupied, use `uv run acme serve --port 7861` and diagnose that port
with `uv run acme doctor --port 7861`. If Ollama is unavailable, start it and check
`OLLAMA_BASE_URL`. For a missing model, install the tag set in `OLLAMA_MODEL` and
repeat the inference probe. A text-only probe response is not verified tool support.

`uv run acme company reset --yes` replaces only company exercise data. Conversations,
reports, approvals and checkpoints remain and may refer to the old exercise. Start
a new conversation after reset. Normal setup and startup do not regenerate the company.
