# Learn middleware through one conversation

For the current website, see [agent architecture](AGENT_ARCHITECTURE.md).
The optional summary and email-redaction presets below remain available; the
default `standard` preset leaves both off. The portal uses visible demo personas.
The step-by-step trace exercise later on this page describes the older CLI/UI
lesson, whose screen labels and account flow differ from the current portal.

For a current-site check, choose a persona in the header, start a new chat in
**My account** or **Workspace**, send a message, then open **Execution**. Inspect
the saved transcript and its model, tool, SQL and memory events. Change the
`models.toml` preset before a new submission and use `acme doctor` to confirm
its resolved settings. The [live demo script](LIVE_DEMO_SCRIPT.md) gives an
end-to-end presentation sequence.

The CLI and UI use the same configured middleware stack. Open `models.toml` in
the independent `live_example/` project and change only this setting:

```toml
[middleware]
preset = "combined"
```

Run `uv run acme doctor`, then start a **new chat** in the UI. New submissions read
the configuration automatically; restarting the server is unnecessary for a preset
change. Start a new chat to keep each experiment's model context understandable.
Return the setting to `standard` when the experiment is finished.

| Preset | What it demonstrates |
| --- | --- |
| `standard` | Selected demo persona context, tracing, bounded model/tool calls and transient model retries. |
| `summary` | Summarization at six messages, retaining two recent messages. |
| `pii` | Email redaction in the incoming user message before model invocation. |
| `read_only` | Offers record and document reads (including document-version discovery), fixed calculations, public web search, preference recall and the selected customer's own profile, orders, terms and invoices. Write/proposal tools are hidden. |
| `combined` | Summary, email redaction and read-only tool selection together. |

Every preset inherits the defaults in `acme/middleware.py`; preset tables override
those defaults, **not** the `standard` table. Unknown keys and invalid limits are
rejected before a new message is accepted. `doctor` validates the selected preset.

## Historical G09 trace exercise

1. Select `combined`, create a new **Free chat**, and send: “Remember ORCHID.
   October sales were GBP 10000. My email is person@example.com.”
2. Send: “November sales were GBP 7500.” Then: “Explain how to compare two months.”
3. Send: “What was my case label, and what is the sales percentage change?”
   These values are user-supplied exercise facts; they are not retrieved company data.
4. Open **Executions**, choose this conversation, then select a message/execution.
   Choose a **Middleware settings** step to see the resolved preset and actual order.
   **Identity and tools** records the server-derived actor and offered tool names.
5. Select **Model input** and inspect its Input tab: the new email is replaced with
   `[REDACTED_EMAIL]`. After enough messages, a summary replaces earlier context.
   **Context changed** steps show transformations. Open **Compare model inputs**
   and choose two calls to see their exact difference. The full exported trace also
   records `provider_started` with purpose `summarization` for helper calls.
6. Return to Chat: all four original user messages remain in the transcript.
   The generated summary is not displayed as a message written by you.
7. Create a **Company assistant** chat. Ask for `DEMO-CUST-005` and the sales
   comparison policy. Inspect the offered tool schemas: `save_report`,
   `update_ticket` and `analyze_workspace` are absent in `read_only`/`combined`.
   A model that nevertheless requests a disabled tool receives an error; no
   proposal is created. Server-side role checks still apply to every company tool.

For a current customer example with `read_only`, select a customer and ask for
their invoices. The model still receives `my_invoices` and `my_invoice` because
they only read records owned by the selected persona. It does not receive
`remember_note`, which writes a preference. Tool selection is a model-facing
learning control; ownership and company permissions remain server-side checks.

The exact summary and answer depend on the selected model. The saved trace is the
evidence for what was sent and returned. No hidden reasoning is exposed.

## Order and boundaries

`RuntimeContextMiddleware` and `VisibilityMiddleware` are **project-local** helpers.
The other classes below are LangChain built-ins. Their wrappers run outer to inner:

1. Runtime context: revalidate the session, inject its identity and filter tools.
2. Optional email PII input transformation.
3. Optional summarization with the same selected model.
4. Model-call limit.
5. Tool-call limit.
6. Transient model retry.
7. Visibility: capture each actual main-model attempt and tool result.

The PII and summary transformations use LangChain's `before_model` hooks; their
listed order ensures new input is redacted before summarization. Provider callbacks
also capture helper calls. A retry wraps visibility so attempts remain separately
inspectable. See [the trace lesson](execution_traces.md) for event contracts.

The default budget is 12 main model calls and 20 tool calls per execution, one
transient retry per main call, and a 120-step graph backstop. Retries can therefore
produce up to 24 main provider attempts. Summary helper calls have their own
LangChain retry behavior and are not counted as main calls. A new submission or
explicit resume starts a new execution budget. These are **not lifetime quotas**.

Transport failures and provider-classified retryable errors are retried; invalid
arguments and permission failures are not. Arbitrary tool calls and business
writes are not automatically retried. Limits end an execution with a visible
budget message; they do not promise to stop a running tool. CSV worker deadlines,
cancellation and optional Docker limits are explained in
[local execution](local_execution.md). Graph-step limits are separate from those
execution deadlines and the model request timeout.

PII mode demonstrates an **input transformation**, not a privacy guarantee: the
original transcript is retained, traces can include pre-transformation context,
and tool results and model outputs are not covered by this email-only setting.
Do not use real confidential data for the exercise. Credential redaction in trace
exports is a separate mechanism described in the trace lesson.

## Durable settings and approvals

The accepted run's resolved middleware settings are stored in `run_configurations`
in `app.sqlite`. Explicit resume restores them even if `models.toml` has changed.
A completed duplicate submission returns its saved result without another model
call. Model selection/settings are captured in each effective model request;
the middleware snapshot does not freeze an external model's implementation.

Business approval is a **persisted application operation**, rather than a suspended
LangGraph node. With `standard`, a company write tool creates a pending proposal.
Open **Tools > Review changes**, inspect/edit its arguments, and approve or
reject. Pending operations survive restart. The server revalidates ownership,
permissions and edited arguments; repeated approval returns the original result
instead of writing again. The agent cannot approve its own proposal. Follow the
[UI walkthrough](learning_app.md) for a complete report exercise.

The Python `submit(..., middleware=[...])` argument is an expert/test extension:
it replaces the configured stack and records class names, not serialized custom
objects. Resuming such a run requires supplying the custom objects again. Learner
CLI/UI runs use the persisted named configuration above.

## Verify and read the implementation

```powershell
uv run python -m unittest discover -s tests -p test_middleware.py -v
uv run python -m unittest discover -s tests -p test_tracing.py -v
```

The checks inject one transient failure, distinguish permanent errors, terminate
an endless tool loop, verify summary/transcript separation, redact input, deny a
hallucinated hidden write, and resume with persisted settings. They use explicit
scripted models for deterministic failure injection. Real-model validation is
separate, because a model cannot reliably be prompted to produce a network error.

Read `acme/middleware.py` (configuration/order), `acme/runtime.py` (acceptance and
resume), `acme/agent.py` (one `create_agent`), and `acme/trace_hooks.py` (callbacks).
Compare the course's middleware notebooks with these ordinary Python modules.

Official API references: [LangChain middleware](https://reference.langchain.com/python/langchain/middleware),
[model call limit](https://reference.langchain.com/python/langchain/agents/middleware/model_call_limit/ModelCallLimitMiddleware),
and [summarization](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware).
