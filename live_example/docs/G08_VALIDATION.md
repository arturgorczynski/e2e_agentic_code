# G08: inspectable execution validation

Validated on **2026-10-15**, Windows PowerShell, Python **3.12.12**, SQLite **3.50.4**,
LangChain **1.4.6**, LangGraph **1.2.15**, `langgraph-checkpoint-sqlite` **3.1.2** and
Ruff **0.17.1**. G08 adds no dependency and requires no Docker, cloud credentials or
external tracing account.

## Requirement-by-requirement evidence

| Requirement | Implementation and observed evidence |
| --- | --- |
| Acceptance, attempts, tools, context, approvals, checkpoints and outcomes | `tracing.py`, `trace_hooks.py`, `agent.py`, `runtime.py` and company-tool events; the live export and deterministic multi-tool test contain the corresponding executed events. |
| Correlation, ordering, timing, parentage and usage | Version-2 event columns carry thread/run/execution/span/parent IDs, append sequence, UTC timestamps, measured durations and redaction metadata. The real export contains six provider results with usage. |
| Effective instructions, messages, tool schemas, settings and outputs | Main `model_request` snapshots include system text, messages, eight described tools and generation settings; responses link by request event ID. Provider/helper callbacks retain actual message batches, available invocation parameters, output metadata and tool calls. The named-profile regression test verifies constructor settings remain available when a model has a friendly name. |
| Before/after transformations | Exact before/after lists and edits are recorded for native message updates, effective request transformations and consecutive main inputs. Tests execute built-in summarization and PII middleware plus explicit message removal. Tool/document output is linked by tool-call ID. Unassigned summary IDs stay null until their observed content is matched to the assigned message. |
| Retries and helper calls | Actual `ModelRetryMiddleware` execution with one injected failure produces distinct attempts, an error, and a link to the previous failed provider span. Built-in `SummarizationMiddleware` calls produce separate `purpose=summarization` provider events. Failed application runs resume with the same run ID and a new execution ID. |
| Search and durable exports | Owned `chat trace`, `chat diff` and `chat export` commands; a new CLI process reads and exports persisted evidence. Tests cover pagination/search and denied cross-owner export. Markdown and JSON exports contain timeline, payloads, context provenance and diffs. |
| Explicit observability boundary | The [trace guide](execution_traces.md), export header and machine-readable flags state that this is observable application/LangChain data, not hidden reasoning or an HTTP wire dump. |

## Trace-only reconstruction

The [real export](examples/g08_invoice_trace.json) contains **136 events**, **six
main-model requests**, **five consecutive-input diffs**, and **six provider results
with token usage**. It comes from three separate CLI processes using installed local
Ollama **`qwen3-coder:30b`** on the full company dataset. No fake model was used for
that export. The separate [live-runtime receipt](g08_live_runtime.json) records process
IDs, responses, actual prepared queries, restart continuity and submission deduplication.

```powershell
uv run --locked python scripts/verify_trace_export.py docs/examples/g08_invoice_trace.json
```

This verifier reads **only the exported JSON**. It reconstructs **70,000 pence owed**,
**45,000 pence allocated** and a **5,000-pence credit** from recorded tool results,
requires executed SQL in the corresponding tool spans, and finds the model's answer.
It checks event IDs/order, source references and durations, then independently applies
each recorded edit list to reproduce the next input exactly. All five comparisons
match. No company database, transcript, checkpoint file, model or network is consulted.
See the [trace-only audit](g08_trace_audit.json) and [readable export](examples/g08_invoice_trace.md).

The export correctly declares `redacted=false`: this synthetic invoice investigation
did not contain a credential payload requiring masking. Redaction itself is verified
separately with planted credentials; the absence of secrets in one ordinary run is
not treated as a redaction test.

## Deterministic failure and transformation checks

[test_tracing.py](../tests/test_tracing.py) uses explicitly labeled fake models while
executing real LangChain middleware, callbacks, tools and the official persistent saver:

- A multi-tool investigation reads invoice data, searches documents and reads an exact
  policy version. Input diffs and provenance connect returned facts to tool/document
  evidence. A separate process exports the saved thread without inference.
- An injected provider failure is retried once through `ModelRetryMiddleware`; both
  attempts and the failed-attempt link are preserved. A separate failed submission
  resumes without changing its application run ID.
- Built-in summarization makes an observable helper call; its message replacement is
  attributed to the summarization node. PII middleware masks an email, and another
  middleware removes context while the independent transcript remains intact.
- A pending report is approved in a new CLI process. Decision events retain its
  original run ID and the new decision execution ID; repeated approval records a
  replay without another write. Tool errors remain explicit events.
- Environment and `.env` secret values, the session token, a credential dictionary
  field, an Authorization header and a secret in an exception are absent from stored
  trace bytes and exports. Redacted events include paths and inherited-redaction flags.
- An actual old seven-column event table gains the new columns without rewriting
  its historical payload. Those rows are labeled `legacy`, not asserted to have
  metadata that was never captured.

## Reproduction and remaining limits

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked ruff check .
uv run --locked python scripts/verify_trace_export.py docs/examples/g08_invoice_trace.json
uv run --locked python scripts/verify_live_runtime.py --output artifacts/new-g08-live
uv run --locked python scripts/verify_independence.py
```

The clean copy at `C:\Users\Komputer\AppData\Local\Temp\acme-g01-hg_gwwr0` installed
offline from the existing lockfile using the warmed cache. Source-data verification,
full company verification, preserving initialization, trace-only reconstruction,
**55 offline tests** (86.773 seconds), Ruff and isolated import-path checks passed.
The final protection for shadowed `.env` credentials was then applied to that copy;
all **seven affected trace tests** passed again there (17.784 seconds) and in the
working project (18.188 seconds). Ruff passed again. Hash comparison confirmed all
**31 Python files** under `acme/`, `tests/` and `scripts/` match the working source.
All 16 current guides/README files passed the local-link check.

Parent course import-layout checks were rerun. Python module checks pass. The
previously recorded first-cell function/`@register_cell_magic` problem in
`notebooks/06_middlewares/01_summarization.ipynb` still causes one failed check and
two execution errors outside IPython. That notebook was not modified.

Current approval continuation means the persisted G06/G07 operation workflow;
edited decisions and graph interrupts remain G09. The graphical inspector remains
G11. Tests establish deterministic tracing behavior, not the semantic quality of a
provider's summaries. SDK-internal HTTP retries, helpers that explicitly discard
callbacks, and events that a forcibly killed process could not commit are not
claimed as observed. Old traces retain their explicit legacy limitations. macOS/Linux
and cloud-provider inference remain unverified.
