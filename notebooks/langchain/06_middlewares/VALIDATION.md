# Custom middleware: current verification

Lesson `16_custom_middleware.ipynb` has been rewritten as a Polish notebook with 24 worked cases. All middleware definitions live beside their explanations in the notebook. It covers contracts, lifecycle, decorator/class implementations, ordering, state/context/reducers, bounded revision, request overrides, authorization, dynamic registration, cache, retry/idempotency, Command composition, async/cancellation, stream projections and integrated real-model execution.

The current notebook executed completely in a fresh Jupyter kernel with its final case using the configured model. The 16 current regression tests execute the same notebook definitions with a controlled model in place of that final model call, and check middleware behavior, imports and UTF-8 text. Ruff passes for the notebook, verifier and test module. The verifier accepts native notebook top-level await; no background-thread bridge is used to hide async execution.

- [Executed notebook](artifacts/verification/20261017T104925Z-aa2771c4/16_custom_middleware.ipynb)
- [Execution report and source hash](artifacts/verification/20261017T104925Z-aa2771c4/16_custom_middleware.execution.json)

```powershell
uv run --group middleware python -m unittest discover -s tests -v
uv run --group middleware python notebooks/langchain/06_middlewares/verify_notebooks.py --execute "16*"
```

The broader curriculum evidence below describes the earlier full run. Its original lesson-16 copy and source hash are superseded by the verification above.

# Curriculum validation

Validated on 17 October 2026 using the project Python environment, LangChain 1.4.6, LangGraph 1.2.15 and Deep Agents 0.7.25.

All **22 remaining notebooks** executed in fresh Jupyter kernels: five foundation notebooks and 17 middleware notebooks numbered `00`–`16`. There were **no skipped integrations** in the successful runs. Ordinary model examples used the configured local Ollama profile. Scripted examples controlled tool requests and negative paths while exercising real middleware and tools. This is local-model evidence, not cloud-provider validation.

HITL verification supplied explicit simulated answers only in executed copies. The live-model runs exercised approve and edit, conditional reject, human response, ordered batch decisions, per-call schemas, invalid-answer rejection, partial resume and streaming resume. The source notebook continues to ask for human input. Regression tests separately cover approve, edit, reject and respond and check which actions actually execute.

The Docker engine and pre-existing `python:3.12-slim` image were used. Containerized workers completed or reached real deadlines; shell execution and timeout cleanup ran. No containers with the lesson label remained after testing. Docker Desktop remains running.

The rubric run demonstrated revision followed by satisfaction; independent Python checks confirmed handbook/laptop content and exactly two non-empty lines. Filesystem checks covered all seven tools, read-only exposure, thread isolation and cross-thread sharing. The regression for reading notes after running the shared-store example remains covered.

The earlier curriculum suite passed **34 tests**, including notebook/module imports, all four model factories, compact display, numbering, index links, lesson Markdown content and HITL decision branches. Ruff and locked dependency sync pass. Lesson Markdown contains functionality explanations and documentation links; setup, display guidance and validation are outside lesson cells.

| Notebook | Result | Seconds | Evidence |
|---|---|---:|---|
| [01_create_agent.ipynb](../01_create_agent.ipynb) | Passed | 4.91 | [Executed copy](artifacts/verification/20261017T102301Z-818a59f4/01_create_agent.ipynb) |
| [02_opening_loop.ipynb](../02_opening_loop.ipynb) | Passed | 4.16 | [Executed copy](artifacts/verification/20261017T102301Z-818a59f4/02_opening_loop.ipynb) |
| [03_adding_memory.ipynb](../04_adding_memory.ipynb) | Passed | 4.7 | [Executed copy](artifacts/verification/20261017T102301Z-818a59f4/03_adding_memory.ipynb) |
| [04_tools.ipynb](../05_tools.ipynb) | Passed | 5.88 | [Executed copy](artifacts/verification/20261017T102301Z-818a59f4/04_tools.ipynb) |
| [05_streaming_structured_output.ipynb](../08_streaming.ipynb) | Passed | 27.21 | [Executed copy](artifacts/verification/20261017T102301Z-818a59f4/05_streaming_structured_output.ipynb) |
| [00_preparation.ipynb](00_preparation.ipynb) | Passed | 5.39 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/00_preparation.ipynb) |
| [01_summarization.ipynb](01_summarization.ipynb) | Passed | 12.07 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/01_summarization.ipynb) |
| [02_tool_errors_retries.ipynb](02_tool_errors_retries.ipynb) | Passed | 7.16 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/02_tool_errors_retries.ipynb) |
| [03_model_retries_fallback.ipynb](03_model_retries_fallback.ipynb) | Passed | 5.28 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/03_model_retries_fallback.ipynb) |
| [04_call_limits.ipynb](04_call_limits.ipynb) | Passed | 4.44 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/04_call_limits.ipynb) |
| [05_human_in_the_loop.ipynb](05_human_in_the_loop.ipynb) | Passed | 11.11 | [Executed copy](artifacts/verification/20261017T102702Z-4ed4a7b4/05_human_in_the_loop.ipynb) |
| [06_pii.ipynb](06_pii.ipynb) | Passed | 5.56 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/06_pii.ipynb) |
| [07_todo.ipynb](07_todo.ipynb) | Passed | 10.01 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/07_todo.ipynb) |
| [08_tool_selection.ipynb](08_tool_selection.ipynb) | Passed | 6.39 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/08_tool_selection.ipynb) |
| [09_local_execution.ipynb](09_local_execution.ipynb) | Passed | 10.67 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/09_local_execution.ipynb) |
| [10_docker_sandbox.ipynb](10_docker_sandbox.ipynb) | Passed | 36.87 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/10_docker_sandbox.ipynb) |
| [11_filesystem.ipynb](11_filesystem.ipynb) | Passed | 9.91 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/11_filesystem.ipynb) |
| [12_subagents.ipynb](12_subagents.ipynb) | Passed | 10.35 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/12_subagents.ipynb) |
| [13_rubric_grading.ipynb](13_rubric_grading.ipynb) | Passed | 8.73 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/13_rubric_grading.ipynb) |
| [14_file_search.ipynb](14_file_search.ipynb) | Passed | 6.55 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/14_file_search.ipynb) |
| [15_context_editing.ipynb](15_context_editing.ipynb) | Passed | 5.42 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/15_context_editing.ipynb) |
| [16_custom_middleware.ipynb](16_custom_middleware.ipynb) | Passed | 5.84 | [Executed copy](artifacts/verification/20261017T102501Z-fb8e77ce/16_custom_middleware.ipynb) |

[Machine-readable execution manifest](artifacts/verification/curriculum-7f827bfb.json) records the source hashes and matching execution copies from that full run. Foundation copies were checked for Python equivalence after removing verifier-only input and storage isolation. Older logs and executed notebooks were preserved.
