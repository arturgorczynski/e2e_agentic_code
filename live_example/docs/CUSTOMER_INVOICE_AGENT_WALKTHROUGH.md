# Follow one customer invoice answer through the agent

This is a recorded run from 21 October 2026 through the local website API,
using the selected customer `SCN-CUST-A12C4F10C352` and `qwen3.8:latest`.
The customer asked about `SCN-BILL-A12C4F10C352-02`: its original amount,
outstanding balance, linked payments or credits, and whether a credit proves
a cash refund. The compact [run extract](../artifacts/customer-invoice-ledger-2026-10-21.json)
contains the question, model call, SQL event IDs, independent database check
and final answer. The complete machine-local stream is in `state/events.sqlite`
under thread `thread-5b7d952f9c0a4047b49fc49ae27d1ac5`.

## Before the model runs

The React chat submits text to `POST /api/chat` in `acme/portal.py`. FastAPI
gets the selected demo persona from the browser's session cookie and passes
the message to `LearningService.submit_chat` in `acme/ui_service.py`. That
service saves one queued request with a submission ID. The worker calls
`acme/runtime.py`, which records the accepted user message, opens the
LangGraph SQLite checkpointer and preference store, and builds the agent.
The browser polls `/api/conversations/{thread_id}` for its readable answer.

The actor is a **selected fictional demo profile**, not verified login. The
server bound the actor to customer `SCN-CUST-A12C4F10C352` before the model
chose any tool. The customer ID was not a model argument.

`build_agent` in `acme/agent.py` uses LangChain `create_agent` with the customer
prompt, customer tool list, `RunContext`, middleware, checkpointer and store.
The `my_invoice` function is a LangChain `@tool`. Its model-visible input is
`invoice_id` (plus optional page size and offset); LangChain injects
`ToolRuntime[RunContext]` when the tool executes. `RuntimeContextMiddleware`
in `acme/middleware.py` adds the selected profile to the model request and
filters offered tools. Python still checks the selected customer in
`acme/customer_tools.py` before querying SQLite.

These are the [documented `create_agent` pattern](https://docs.langchain.com/oss/python/langchain/agents),
[hidden `ToolRuntime` injection](https://docs.langchain.com/oss/python/langchain/tools),
and [model/tool middleware hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom).
The application-specific queue, identity checks and event recorder are Acme
code around those LangChain interfaces.

## What the recorded events show

| Event sequence | Observation | Which component decided or executed it |
| --- | --- | --- |
| `6267 request_accepted`, `6268 run_started` | The user text became one application run. | Acme queue and runtime |
| `6269 middleware_configured`, `6270 checkpoint_loaded` | The run selected middleware and loaded its conversation state. | Acme runtime and LangGraph checkpointer |
| `6280 runtime_context` | The effective model step offered customer tools including `my_invoice` for the selected client profile. | Acme identity middleware |
| `6282 model_request`, `6285 model_response` | The model requested native `my_invoice(invoice_id='SCN-BILL-A12C4F10C352-02')`. No SQL had executed at the model-response step. | Model choice |
| `6300 tool_attempt_started` | LangChain began handling that requested tool call. | Agent tool runner and visibility middleware |
| `6302 sql` | Fixed query `portal:my_invoice` used parameters `[selected customer ID, requested invoice ID]` and returned one owned invoice. | Python and SQLite |
| `6303 sql` | Fixed query `portal:my_invoice_settlements` returned one linked ledger row with pagination limit 20, offset 0. | Python and SQLite |
| `6305 tool_message` | The tool handed structured facts and the credit row back to the model. | Acme customer tool and LangChain tool message |
| `6318 model_request`, `6333 model_response` | A second model call used those facts to write the final answer; it requested no more tools. | Model wording |
| `6348 run_completed` | The completed run and transcript became inspectable. | Acme runtime |

The first SQL query joins `invoice_balances` to the order and filters by the
**server-selected** customer. An unknown or another customer's invoice yields
an empty tool result. The second query fetches payment allocations and credit
notes for that owned invoice. `invoice_balances` is a local SQLite view: it
subtracts allocated payments and credit notes from the original invoice total.
The customer tool reports whether the visible entries reconcile with that
balance, and offers `next_offset` if the ledger spans more than one page.

The `tool_message` in this run reported `total_pence=18000`,
`allocated_pence=0`, `credited_pence=1000`, `outstanding_pence=17000`,
`ledger_reconciles=true` and `has_more=false`. Its one row was credit note
`SCN-CREDIT-A12C4F10C352`, dated 2026-05-22, for 1,000 pence. An independent
query in the saved extract found the same row and no payment allocation.
The model converted the integer pence to GBP 180.00, GBP 10.00 and GBP 170.00.
It correctly said that this credit reduces the invoice balance but **does not
establish a cash refund**.

## Read the boundary correctly

- The model chose the tool and supplied an invoice ID. It did not choose a
  customer ID, SQL statement, database path or permission.
- LangChain executed the native tool call. The app's Python function selected
  the account, ran bound SQL and returned factual data. The model then wrote
  the answer from that result.
- The customer tool emitted `tool_message` and `sql` events; company tools also
  emit a separate structured `tool_result`. Look at the events present in this
  run rather than assuming every tool has identical trace kinds.
- The website's clickable **My account** invoice detail uses a separate
  read-only FastAPI route in `acme/portal_data.py`. It does not invoke the
  agent. The [website probe](../artifacts/customer-invoice-website-2026-10-21.json)
  confirms the same balance and a 404 for another customer's invoice.
- The financial records are authored fictional 2026 scenario data. This run
  verifies one response and its recorded execution, not the accuracy of every
  future model answer. It does not expose hidden model reasoning.

Two later website runs checked the boundary after `my_invoice` was added.
When the question named another customer and its invoice, the model called
`my_profile` for the selected account and refused; its only SQL parameters
belonged to `SCN-CUST-A12C4F10C352`. When the question named only the other
invoice ID, `my_invoice` ran its owner-bound query and returned zero rows.
The model then listed the selected account's own invoices and declined to
provide the requested balance. The [boundary extract](../artifacts/customer-invoice-boundary-after-ledger-2026-10-21.json)
records the two prompts, native calls, SQL labels, parameters and answers.
Those two observed refusals do not turn the demo persona picker into verified
authentication; the ownership filter in Python is the data boundary here.

To repeat the exercise, run the portal, select customer
`SCN-CUST-A12C4F10C352`, ask about invoice
`SCN-BILL-A12C4F10C352-02`, then open **Execution**. Compare the agent's
answer with `model_response`, `tool_attempt_started`, both `sql` events and
`tool_message`. The event IDs above refer to the saved run; a new run gets
new IDs and may take a different model path.
