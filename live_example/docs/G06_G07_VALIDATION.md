# G06 and G07 validation

Validated on **2026-10-15**, Windows PowerShell, Python **3.12.12**, SQLite **3.50.4**,
uv **0.10.2**, Ruff **0.17.1**. Locked dependencies include LangChain **1.4.6**,
LangGraph **1.2.15**, `langgraph-checkpoint-sqlite` **3.1.2** and
`langchain-ollama` **1.1.0**. No Docker, cloud credentials, external database or model
download was needed for these checks.

## G06: bounded company tools

- Eight implemented tools, 20 fixed record projections, strict service input models
  and a shared result envelope. See [tool contracts](company_tools.md).
- Permission checks precede company reads. Model tool schemas exclude user identity,
  runtime context, session tokens and operation IDs.
- Deterministic, scope-filtered mock retrieval returns exact document versions and
  excerpts. SQL/retrieval events are emitted by actual executed code.
- Report and ticket writes remain pending until an authenticated owner decision.
  Stable operation IDs, compare-and-set ticket transitions and transaction-backed
  decisions prevent duplicate effects on retry. Current permissions are rechecked.

`python scripts/verify_company_tools.py` passed **75 direct tool calls** on a temporary
copy of the full baseline, with **zero model calls**. It exercised all eight tools and
all 20 entity projections, pagination, filtering, invalid arguments, role denial,
source validation, version selection, arithmetic, approval, rejection and retries.
The largest serialized response was **16,839 bytes**. The sales summary returned one
facts object for **15,212 invoices** and **742,604,410 pence**, reconciled independently
against gross invoices less credits. Lists covered **15,213 orders** and **259,652
order items** while returning at most 50 records per page.

The small fixture is exercised by `tests/test_tools_runtime.py`, including all eight
tools, deterministic fake-model tool execution, version/scoping checks, invalid and
oversized inputs, SQL-injection-shaped values, separate roles, source permissions
changing before approval, expired sessions, failed-run recovery and write deduplication.

Full-data measured evidence is saved in [g06_full_tools.json](g06_full_tools.json).
Timings are observations on this machine, not performance guarantees.

## G07: durable runtime

[agent.py](../acme/agent.py) visibly constructs the single agent with model, system
prompt, tools, immutable runtime context, project-local middleware and the official
SQLite saver. [runtime.py](../acme/runtime.py) owns acceptance, submission deduplication,
serialization and checkpoint continuation. [Runtime walkthrough](agent_runtime.md)
documents local login, threads, inspection, approval and recovery.

Offline runtime checks demonstrate:

- A real LangChain ToolNode and official `SqliteSaver` with a clearly labeled fake
  model; no provider integration is inferred from these tests.
- An accepted message survives model failure and resumes from its checkpoint without
  a duplicate human message. Reusing an ID for different text is rejected.
- A completed submission returns its prior result without constructing an agent.
- A model-context message removal preserves the append-only application transcript.
- Cross-owner transcript, trace, run, resume and operation access are denied.
- An overlapping runner is rejected by the execution lock.

Actual provider validation uses installed local **Ollama `qwen3-coder:30b`**
(30.5B, Q4_K_M). The script starts three separate CLI processes against the full
company dataset and the same owned thread. It checks invoice facts through real tool
calls, follows up about payment allocations and credit notes, then recalls the first
turn's case label from persisted context. The request is repeated to verify no new
model event or accepted message, and another account is denied history access.
See [g07_live_runtime.json](g07_live_runtime.json) for actual process IDs, answers,
executed SQL, model-request count and the checks performed.

An earlier live run exposed a pounds/pence confusion. The tools now retain exact
`*_pence` integers and also supply formatted `*_gbp` strings, and the prompt explicitly
distinguishes the two. The final live check additionally asserts **GBP 700.00**
outstanding, **GBP 450.00** allocated payment and **GBP 50.00** credit, rejects observed
unit-label errors, and verifies the remembered balance in the third process. All pass.

The provider still emitted a stray `<tool_call>` marker in its first natural-language
answer. This is retained in the raw answer and flagged in the evidence. Persistence
and the selected factual checks do not certify perfect output formatting or general
answer quality; G13's broader release evaluation remains necessary.

## Verification commands and outcomes

Run from `live_example/`:

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked ruff check .
uv run --locked python scripts/verify_company_tools.py
uv run --locked python scripts/verify_live_runtime.py --output artifacts/new-live-check
uv run --locked python scripts/verify_independence.py
```

- **48 offline tests passed** in 79.610 seconds in the working project.
- **Ruff passed** with the existing E/F/I rules and 100-character line limit.
- The final clean copy at `C:\Users\Komputer\AppData\Local\Temp\acme-g01-67ir243v`
  installed from the unchanged lockfile using the warmed cache and no network.
  Data verification, full company verification, repeated preserving initialization,
  all **48 tests** (81.694 seconds), Ruff and isolated import-path verification passed.
  No parent imports, source credentials, original workbook, source virtual environment
  or runtime state were copied.
- All 14 current Markdown guides/README files passed a local-link existence check.
- Parent course import-layout checks were rerun. The previously recorded issue in
  `notebooks/06_middlewares/01_summarization.ipynb` remains: a first-cell function and
  `@register_cell_magic` fail the layout check and execution outside IPython. That
  notebook was not changed. Python module import-layout checks passed.

## Remaining boundaries

These goals deliver the CLI and initial events, not the graphical UI or complete
G08 inspection experience. G09 adds edited approvals, durable graph interrupts and
the teaching middleware configurations. General code execution is absent; the local
analysis tool performs only bounded arithmetic. The checkpoint library depends on
`sqlite-vec`, but this application creates no vector index and performs no vector search.

The concurrency policy is a single local runner with rejection of overlap, not a
distributed queue. Authentication assumes trusted access to the machine and files.
macOS/Linux, cloud-model inference and Docker execution remain unverified. The full
release is not yet complete; **G08 is the next goal**.
