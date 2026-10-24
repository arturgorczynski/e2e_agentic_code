# Middleware workshop

The curriculum contains 17 notebooks, numbered `00` through `16`. Lesson Markdown explains behavior; setup, display controls and validation live here.

## Setup

```powershell
uv sync --group middleware --locked
```

Select the project `.venv` kernel. The single root `.env` supplies model names, endpoints and credentials; root `models.toml` selects profiles for the main model and specialized roles. All examples use the root `model_config.py` factory. Keep the configured Ollama service running for local profiles. LangChain 1.4.6 supplies per-call HITL interrupts.

The Docker lesson needs Docker Desktop's Linux engine and the image selected in `[sandbox]` of `models.toml`. The local shell uses Git Bash on Windows. Host execution is intended for the trusted fixture commands.

## Lessons and documented capabilities

| Lesson | Demonstrated behavior | Documentation |
|---|---|---|
| [00 Model and tool execution](00_preparation.ipynb) | Message roles, schemas, model/tool loop, permanent and transient errors | [Official page](https://docs.langchain.com/oss/python/langchain/agents) |
| [01 Summarization](01_summarization.ipynb) | Message/token/fraction thresholds, AND/OR triggers, retained tail, summary prompt and input cap | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#summarization) |
| [02 Tool errors and retries](02_tool_errors_retries.ipynb) | Sanitized errors, filtered handlers, correction, retries/backoff, exhaustion and propagation | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-error) |
| [03 Model retries and fallback](03_model_retries_fallback.ipynb) | Retry filters, backoff, fallback routing, exhausted exception and custom failure response | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-retry) |
| [04 Call limits](04_call_limits.ipynb) | Per-run/thread budgets, named/global tools, continue/end/error, alternate model/tool routing | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-call-limit) |
| [05 Human-in-the-loop](05_human_in_the_loop.ipynb) | Approve/edit/reject/respond, conditional gating, safe bypass, descriptions, batches, per-call IDs and schemas, streaming resume | [Official page](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) |
| [06 PII detection](06_pii.ipynb) | Redact/mask/hash/block, input/output/tool boundaries, regex and callable detectors | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#pii-detection) |
| [07 Task planning](07_todo.ipynb) | Planning state, pending/in-progress/completed, replacing plans, custom instructions | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#to-do-list) |
| [08 Tool selection](08_tool_selection.ipynb) | Separate selector, tool cap, always-include tools, parsing policy, exposed-tool comparison | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#llm-tool-selector) |
| [09 Host execution](09_local_execution.ipynb) | Workers, real timeouts, host shell, persistent state, lifecycle commands, output redaction | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#shell-tool) |
| [10 Container execution](10_docker_sandbox.ipynb) | Container workers/shell, network and resource restrictions, real timeout, exact-container cleanup | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#shell-tool) |
| [11 Filesystem backends](11_filesystem.ipynb) | Thread-local and cross-thread routes, seven file tools, read-only allowlist, namespaces and storage lifetime | [Official page](https://docs.langchain.com/oss/python/deepagents/backends) |
| [12 Subagents](12_subagents.ipynb) | Compiled and dictionary specialists, separate tools/models, task delegation, isolated parent context | [Official page](https://docs.langchain.com/oss/python/deepagents/subagents) |
| [13 Rubric grading](13_rubric_grading.ipynb) | Grader model/tools, criteria, revision feedback, iteration cap, callback and independent checks | [Official page](https://docs.langchain.com/oss/python/deepagents/rubric) |
| [14 File search](14_file_search.ipynb) | Glob, regex Grep, include filters, filename/content/count modes, size cap and ripgrep fallback | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#file-search) |
| [15 Context editing](15_context_editing.ipynb) | Clearing old results and inputs, retained tail, exclusions, placeholder and reclamation threshold | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/built-in#context-editing) |
| [16 Custom middleware](16_custom_middleware.ipynb) | 24 worked cases: contracts, lifecycle/order, state/context/reducers, prompt/model/tool overrides, authorization, bounded revision, cache, retry/idempotency, Command composition, async/cancellation, stream transformers and live integration | [Official page](https://docs.langchain.com/oss/python/langchain/middleware/custom) |

The main examples use the selected real models. Scripted model examples make requested tool calls and failure paths deterministic; they still execute the real middleware and tools. `InMemorySaver` and `InMemoryStore` retain data for their object's lifetime, not across kernel restarts.

## Output

Execution and output use separate cells. `show_messages(..., pretty=True)` renders bounded message and tool-call previews. Use `truncate=False` for full content or `pretty=False` for complete JSON. `TraceMiddleware` keeps complete payloads in unique `artifacts/` logs.

## Validation

```powershell
uv run --group middleware python -m unittest discover -s tests -v
uv run --group middleware python notebooks/langchain/06_middlewares/verify_notebooks.py
uv run --group middleware python notebooks/langchain/06_middlewares/verify_notebooks.py --execute "11*"
```

The verifier writes a new run directory under `artifacts/verification/`; existing executed notebooks and logs are preserved. The report distinguishes execution failures from skipped integrations.

Interactive teaching cells always use `input()`. For unattended verification, explicitly supply test answers; they are injected only into executed copies:

```powershell
uv run --group middleware python notebooks/langchain/06_middlewares/verify_notebooks.py --execute --input approve --input reject --input Friday --input approve --input reject --input approve --input reject
```

These answers exercise the HITL examples; they are simulated review decisions, not a human interaction test. [VALIDATION.md](VALIDATION.md) records the current evidence and any remaining limits.
