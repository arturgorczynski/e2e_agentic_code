# G13 release validation

Status: **complete for the tested local release journeys, 2026-10-16**. All eight
journeys have evidence. G09 remains a separate unfinished middleware milestone.
This does not certify other operating systems, cloud inference or production use.

The [release evidence](g13_release_evidence.json), [test log](g13_test_results.txt),
[independent-install log](g13_independence.txt), [company checks](g13_company_validation.json)
and [tool measurements](g13_tool_measurements.json) travel with this project.
Earlier UI checks are detailed in [G10-G12 validation](G10_G12_VALIDATION.md).

## Required journeys

| Journey | Observed result |
| --- | --- |
| 1. Install, configure, log in, choose a scenario, answer with evidence | A fresh copy outside the course installed from the unchanged lockfile and cached packages. Setup created its own model configuration and account. Doctor passed an actual tool-call probe. Chrome login on port 7864, Company assistant selection and the built-in sales CSV example completed with the real model. Workspace showed input CSV, result JSON and report Markdown. Authenticated download returned the exact 742,604,410 pence total. |
| 2. Follow-up, switch, refresh, restart, retain history | The company conversation and two pending operations survived stopping server PID 2428, starting PID 5008 with the same state and browser refresh. Switching to the astronomy chat displayed its own history; switching back restored the company chat. The next model response recalled MAPLE-13, DEMO-CUST-005 and -25.00%. Exactly five human messages persisted. Earlier G11 checks also covered streaming and logout/login. |
| 3. Structured records and policy into a report | Real business_summary calls returned October GBP 10,000 and November GBP 7,500 for DEMO-CUST-005. read_document read POL-METRICS-001 v1. Two proposals referenced both executed queries and that policy, the 25% decline and uncertainty about its cause. [Approved report](examples/g13_approved_report.md). |
| 4. Inspect every step and context changes | Chrome rendered model requests and the comparison before/after the policy read. The [portable trace](examples/g13_sales_trace.json.gz) contains 400 events, 15 model calls, 10 tool calls, 19 context changes and 14 exactly reconstructed input diffs. Every model/tool span finishes and every model-input message has a recorded origin. [Trace-only audit](g13_trace_audit.json). |
| 5. Edit, approve, reject, persist, deduplicate | After restart, the UI edited the first proposal's title/body, approved it and rejected the second. Replaying both authenticated decisions returned stored outcomes. Exactly one report exists, with the edited title and reviewer note; rejection created none. |
| 6. Isolated users and artifacts | G11 used two simultaneous browser cookie sessions with separate identities/history. G13 repeated boundary checks on the new thread: owner downloads succeeded; another authenticated account received 403 for transcript, trace, workspace file and approved report. Web tests cover Gradio session/event ownership and logout. |
| 7. Transient error, runaway loop and timeout | Final tests inject a transient provider failure and check separate retry spans and persisted failure/resume. An endless tool model stops at the recorded graph-step budget, leaves a failed run and releases the lock. Real local-worker deadline tests terminate the child and assert no late artifacts. These are injected failures, not naturally occurring browser/provider failures. |
| 8. Explicit reset and baseline reproduction | A disposable full-data rehearsal changed a ticket, refused reset without --yes while preserving the mutation, then confirmed reset and compared all twelve baseline scenario facts. A fresh thread reproduced one approved transition; replay produced no extra write. [Reset record](g13_company_validation.json). |

## Validation gates

- Final working-copy suite: **80 tests passed in 126.191 seconds**, plus Ruff. Four
  are optional real Docker tests; the remaining 76 cover application behavior,
  tools, local workers, authentication, persistence, setup, traces and import layout.
- Independent installation: **80 tests passed in 127.322 seconds**, plus Ruff.
  Imports resolved inside that external copy. The copy then received the final
  prompt wording and completed the browser/model scenario. The final working-copy
  suite includes that prompt change. The trace auditor also passed against the
  shipped compressed evidence without an app, database or model.
  Final [copy parity](g13_copy_parity.json) confirms all 54 application, script,
  test and configuration files match the independently installed copy.
- Full integrity: 35 populated tables, 200 employees, 3,832 customers, 15,213 orders,
  259,652 order items, 15,212 invoices, 73 forecasts and 147 documents / 148 versions.
  Checks recompute finance relationships, forecast inputs/cutoffs and all twelve
  scenario assertions. Integrity took 21.089 seconds; the reset rehearsal took
  32.54 seconds. Seventy-five direct full-data calls checked 20 projections,
  bounded output, ownership, sources, versions and independent sales reconciliation.
- All **47 teaching-source SHA-256 fingerprints matched** after validation. The root
  model factory, configuration and notebook source were not changed. The parent
  import suite was run and retains one pre-existing summarization notebook failure
  and two IPython-context errors. The app's separate import checks pass. This is
  not a claim that every root-course test is green.
  The raw [parent check log](g13_parent_imports.txt) preserves those failures.

## Tested environment and timings

Windows 11 build 26200, AMD64, Python 3.12.12, Chrome extension automation. G11
layout checks used 1280 x 900 and 390 x 844 viewports, not physical mobile devices.
Dataset: acme-company-v1, full profile, business date 2011-12-09, currency GBP.
Local Ollama: qwen3-coder:30b, temperature 0, context setting 16,384 tokens.

| Dependency | Tested version |
| --- | --- |
| LangChain / core | 1.4.6 / 1.6.10 |
| LangGraph / SQLite checkpointer | 1.2.15 / 3.1.2 |
| LangChain Ollama | 1.1.0 |
| Gradio | 6.30.0 |
| FastAPI / Uvicorn | 0.143.2 / 0.54.0 |
| HTTPX / Ruff | 0.28.1 / 0.17.1 |

Independent-copy startup to login-page HTTP readiness: **7.96 seconds**, including
Python/UI startup and polling overhead, excluding installation/model warmup. This
is one observation, not a benchmark. An initial measurement attempt had a missing
log directory and was discarded; the recorded run used the corrected launcher.
Normal serving used the prepared database without regeneration.

Representative direct full-data tool timings include local tracing, exclude model
inference, and are not load tests. Largest measured tool result: 16,839 bytes.

| Tool | Calls | Median ms | Maximum ms |
| --- | ---: | ---: | ---: |
| list_records | 40 | 31.3 | 40.8 |
| lookup_record | 22 | 21.6 | 23.8 |
| business_summary | 2 | 27.3 | 32.7 |
| search_documents | 3 | 24.2 | 41.6 |
| read_document | 2 | 22.6 | 22.9 |
| save_report | 3 | 25.9 | 26.2 |

## Default path and optional results

Real-model browser scenarios used local Ollama and fixed host CSV operations, with
no Docker execution or cloud credentials. A suitable local model was installed.
Docker was available on the machine; default execution did not invoke it.

Four separate real-container tests passed: read-only CSV/no network/no provider
secret, timeout removal, cancellation removal and oversized-output rejection.
These are optional evidence, not prerequisites for default acceptance. Cloud
inference, uncached installation, macOS/Linux, physical mobile devices, production
hosting and sustained multi-user load were not verified.

## Observed limits

- Model prose is not a calculation validator. The first answer converted values to
  GBP but called the column pence. A follow-up corrected it. After tighter guidance,
  the independent run used correct GBP cells/column and total, but retained an
  ambiguous section heading, `Sales Summary by Month (GBP pence)`, and omitted the
  requested file ID in prose. Exact files remained in Workspace. These observations
  remain in the raw evidence; prompt wording does not guarantee correct citations.
- Asking for two proposals initially produced chat drafts. An explicit follow-up
  invoking save_report created the actual operations. The pending-review status
  distinguishes prose from an operation that can be approved.
- The browser download observer stalled and lost its automation attachment. The
  file/link had already been observed; authenticated HTTP download later passed.
  A completed browser save-dialog journey is not claimed.
- The graph-step budget stops repeated cycles, not a currently executing tool.
  Worker deadlines provide the termination boundary. Host workspaces organize files;
  they do not sandbox arbitrary host code.
- Company reset preserves accounts, transcripts and historical approvals. Stop the
  server and start a **new chat** after reset. Old reports describe their old state.
- Traces show recorded application/provider inputs and outputs, not hidden reasoning,
  an HTTP wire dump, or events lost before commit during abrupt process termination.

## Reproduce

Run from this project after [README setup](../README.md):

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked ruff check .
uv run --locked python scripts/verify_release_state.py
uv run --locked python scripts/verify_company_tools.py --output artifacts/g13_full_tools.json
uv run --locked python scripts/verify_release_trace.py docs/examples/g13_sales_trace.json.gz
uv run --locked python scripts/verify_independence.py
uv run --locked acme doctor --inference
uv run --locked acme serve
```

For the browser rehearsal: sign in, choose Company assistant and select the sales
CSV exercise under Learn & tools. In the same chat, compare DEMO-CUST-005 sales for
October/November 2011 and read POL-METRICS-001 v1. Request two save_report proposals
with query/document sources. Restart with the same state, refresh, edit/approve one,
reject the other, switch chats, then ask for the remembered customer and change.
Inspect model requests and compare those before/after read_document. Download the
report and trace. Use a separate local account/session for ownership-denial checks.
Validation credentials are disposable and are not shipped application defaults.
