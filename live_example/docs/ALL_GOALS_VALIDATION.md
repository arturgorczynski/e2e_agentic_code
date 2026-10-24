# First-release completion audit

The subsequent [ten-item UI redesign](UX_REBUILD.md) has its own current acceptance
record and screenshots. Its updated account picker, Executions and Tools replace
the interface described in the historical first-release browser records below.

This is the current cross-goal audit for Acme Wholesale on Windows, 2026-10-16.
**Status: G01–G13 complete for the first-release scope below.**
Earlier milestone reports are historical evidence; their references to unfinished
later goals describe the state at that milestone. This audit supersedes those
status statements, without rewriting old traces or test logs.

## Requirement coverage

| Goal | Implementation and verification |
| --- | --- |
| G01 independent project | Own package, lockfile, config root, CLI, data and documentation. The external-copy check installs from cached locked packages, imports with isolated Python, verifies data, runs every application test and Ruff. No course or LangTutorial runtime imports. |
| G02 coherent company | [Company contract](company.md), fixed business clock/currency, five employee-linked identities and [12 scenarios](learning_scenarios.md). Expected facts live under `evals/`, outside searchable documents. |
| G03 public source | UCI attribution/license/checksums in `data/sources/manifest.json`; 541,909 source lines retained. [Mapping and reproducibility commands](source_mapping.md), stable prepared profiles and complete baskets. `data verify` passes in the independent copy. |
| G04 substantial data | 35 tables, 200 employees, 3,832 customers, 3,585 products, 15,213 orders, 259,652 items, 15,212 invoices and 73 forecasts. `company verify` recomputes relationships, money, lifecycle rules, forecast cutoffs and all scenario facts. [Dictionary](data_dictionary.md), [baseline/reset](company_data.md) and [full reset evidence](g13_company_validation.json). |
| G05 company documents | 147 documents / 148 versions across seven categories; IDs, scope, dates, owners and linked facts validated. Fixed hand-authored policies and fact-based templates; no generation call at startup. [Document guide](company_documents.md) and [representative review](G04_G05_VALIDATION.md). |
| G06 useful tools | Nine tools expose prepared SQL, bounded records/aggregates, versioned mock text retrieval and CSV workspaces. [Contracts](company_tools.md); tests cover filters, permissions, malformed input, pagination, source evidence and idempotency. [75 full-data calls](g13_tool_measurements.json) cover 20 projections; largest result 16,839 bytes. |
| G07 durable single agent | One `create_agent`, official SQLite checkpointer, separate account/thread/run/operation IDs, transcript and owned workspaces. Three fresh real-model CLI processes preserve case recall, exact invoice facts and duplicate-submission behavior. Cross-owner access is denied. |
| G08 visible execution | Persisted model inputs/results, tool schemas/arguments/results, context changes, SQL/document provenance, helper calls, retries, timings, checkpoints and approval decisions. [Portable release trace](examples/g13_sales_trace.json.gz) reconstructs 14 exact model-input changes; [trace audit](g13_trace_audit.json). No hidden reasoning or raw HTTP capture claimed. |
| G09 middleware and approval | Normal CLI/UI configured stack, persisted accepted settings and resume, transient-only model retries, model/tool budgets, summary, email input transformation and read-only selection. Seven deterministic tests plus actual Ollama combined-preset rehearsal. Pending edited approval/rejection/replay survives restart in [G13 evidence](G13_VALIDATION.md); permissions and edited arguments revalidated by current web tests. [Learner instructions](middleware.md). |
| G10 useful execution | Fixed local CSV operations work without Docker; owned files, limits, deadlines, cancellation and orphan recovery tested. Four optional real Docker tests verify mounts, no network/provider secrets, resource limits and cleanup. [Execution boundaries](local_execution.md). |
| G11 usable UI | Free chat by default, company mode, collapsible left history, per-chat rename/delete, Trash, focused composer, separate learning tools and visible identity. [Desktop/narrow/keyboard/two-user evidence](G10_G12_VALIDATION.md). Current browser rehearsal covers restart, new chat, company lookup, keyboard follow-up and middleware inspector. Current HTTP acceptance adds simultaneous same-account pages, approvals, context differences, CSV downloads and cross-account denial. |
| G12 install and learn | [Quick start](../README.md#quick-start), non-overwriting setup, doctor including middleware validation, model inference probe, serve, repository map, company guide and lesson links. Published commands exercised from an independent copy; diagnostics cover missing model/backend, wrong data version, busy port and absent optional Docker. |
| G13 complete journeys | [Eight release journeys](G13_VALIDATION.md), real Chrome/Ollama reports, persisted edit/approve/reject/replay, separate users, complete data checks and explicit reset. Current middleware and multi-page fixes close the remaining earlier gaps; deterministic failures are explicitly separate from real-provider/browser evidence. |

## What the final audit changed

- Added `models.toml` middleware presets used by both CLI and UI, validated by
  `doctor`, with immutable accepted-run snapshots for explicit resume.
- Fixed generated summary and redacted input messages being copied into the user
  transcript. Accepted original user messages remain the transcript authority.
- Fixed same-account pages freezing each other's updates by sharing a last-selected
  thread. Active view guards now use the authenticated identity and browser session;
  account-level last-opened selection is only the reload default. The view cache is
  bounded to 512 recently selected pages; this local teaching app does not target
  large concurrent deployments.
- Removed a startup race where hidden thread transport rejected an ID before its
  choices loaded. Every callback still checks ownership on the server.
- Strengthened invoice evidence instructions after a real model invented payment
  amounts without calling their tools. The fresh follow-up rehearsal retrieved the
  actual rows and passed. This improves behavior; it cannot guarantee factual prose
  from every model response. Review the cited records and trace.
- Moved the summary notebook's display-helper definition out of its import cell,
  and taught the source-layout test to inspect the Python body of its existing
  `%%tall` wrapper. All four parent import checks now pass. Existing cell IDs,
  outputs and execution counts were preserved; historical artifacts were untouched.
  The root model factory and root configuration were not changed.
- Finished the middleware walkthrough and removed stale future-tense UI/approval
  instructions. No embeddings, graph databases, custom graph workflow or multi-agent
  architecture was added.

## Reproduce the checks

From `live_example/`:

```powershell
uv sync --locked
uv run acme data verify
uv run acme company verify
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run python scripts/verify_independence.py
```

The independence script expects dependencies already cached by `uv sync`; it
copies an allowlisted project into a fresh system temporary directory and retains
it for inspection. It does not copy credentials, virtual environments or traces
from ignored runtime state. Shipped teaching trace examples are intentionally included.

With the tested tool-capable Ollama model installed, each output directory must be new:

```powershell
uv run python scripts/verify_live_runtime.py --model qwen3-coder:30b --output artifacts/my-runtime-check
uv run python scripts/verify_live_middleware.py --model qwen3-coder:30b --output artifacts/my-middleware-check
```

The first uses three fresh CLI processes; the second makes four free-chat turns
and a real company lookup using the normal `combined` preset. Both use disposable
state and local validation passwords. The second creates its own temporary project
configuration without copying the developer's `.env`. Neither modifies the learner's
normal `state/` directory.

From the course root, verify its import conventions separately:

```powershell
uv run python -m unittest discover -s tests -p test_import_layout.py -v
```

## Evidence and limits

- Final independent installation: **87 tests passed in 135.201 seconds**, Ruff,
  source data verification, company consistency, two non-destructive initializations,
  portable trace audit and isolated package import all passed. Four of the tests
  exercised optional real Docker execution; the other 83 do not require Docker.
  [Complete installation/test log](all_goals_independence.txt).
- The working-copy suite passed **87 tests in 127.819 seconds** before the final
  view-selection fix; the final independent suite above includes that fix. Its
  real Gradio regression additionally passes in [current UI API evidence](all_goals_ui_api.json).
- All **four parent import-layout checks passed in 3.719 seconds**:
  [log](all_goals_parent_imports.txt). [Source fingerprints](all_goals_teaching_source.json)
  show only the two intentional course fixes described above out of 47 tracked
  teaching source files. Root model factory and model configuration match.
- [Full doctor results](all_goals_doctor.json): data/version, writable state,
  authentication, middleware settings, real model/tool probe, available port and
  optional Docker availability all passed. The server occupies 7860; the separate
  port-availability probe used 7861.
- [Real three-process runtime](all_goals_live_runtime.json) and
  [portable invoice trace](examples/all_goals_invoice_trace.json.gz): invoice facts,
  context recall, three original user messages, duplicate submission and owner
  boundaries passed. [Unsuccessful earlier model answer](all_goals_model_failure.json)
  is retained separately rather than removed from the record.
- [Real combined middleware rehearsal](g09_live_middleware.json): four original
  messages retained, summary helper called, email removed from main inputs, ORCHID
  and -25% recalled, company lookup executed with read-only schemas.
  [Combined trace](examples/g09_combined_trace.json.gz) and
  [read-only company trace](examples/g09_read_only_trace.json.gz).
- Current Chrome UI: restored the persisted company chat after restart, completed
  the customer lookup and keyboard follow-up, displayed `middleware_configured`
  with limits 12/20 and the actual five-class standard stack. At **390 × 844**,
  document width and scroll width were both 390; drawer toggle, conversation and
  composer were readable. [Desktop screenshot](examples/final_chat.jpg),
  [narrow screenshot](examples/final_chat_mobile.jpg).
- [Final source/copy parity](all_goals_copy_parity.json) ties the running source to
  the clean installation. Local documentation links were checked for missing files.

Tested platform: Windows, Python 3.12.12, LangChain 1.4.6, LangGraph 1.2.15,
SQLite checkpoint package 3.1.2, Gradio 6.30.0, Ruff 0.17.1, local Ollama
`qwen3-coder:30b`. The lockfile is authoritative for the entire dependency set.
The prepared business clock is 9 December 2011; execution timestamps are actual UTC.

macOS/Linux, other browser engines, physical mobile devices and cloud-provider
inference are not certified by these checks. Desktop Chrome viewport emulation is
the narrow-screen evidence. Default operation needs no Docker or cloud credentials.
Docker results are optional and reported separately. Public-data preparation has
its own provenance; company identities, logistics, payments and forecasts are
explicitly simulated extensions. Mock RAG is text search, not semantic retrieval.

Model responses are not deterministic database reports. The unsuccessful invoice
answer and earlier CSV heading/proposal mistakes are retained in validation records;
the fixed follow-up runs are separate. The tool results and reviewed artifacts are
the factual baseline. PII mode does not erase the original transcript or protect
all traces; its precise boundary is documented in the middleware lesson.
