## Agentic AI

The independent [Live Example](live_example/README.md) application has its own package,
configuration, lockfile, and tests. Run its commands from `live_example/`.
The course's test discovery excludes that project.

To start Acme from this repository root:

```powershell
cd live_example
uv sync --locked
uv run acme setup
uv run acme doctor --inference
uv run acme serve
```

Setup lets you choose your own local username, name and role. Open
`http://127.0.0.1:7860`, then choose an existing user or create a new one.
The `acme` command belongs to this independent project, so it is not available
through the course-root environment.

The 27 notebooks live under [notebooks/langchain](notebooks/langchain/) and use one root `.env`, one [models.toml](models.toml), and one [model_config.py](model_config.py) factory for examples that call a real model. Lessons 09 and 10 use scripted models so their contracts run offline.

The separate [RAG course](notebooks/rag/README.md) has nine standalone notebooks covering chunking, tables and images, embeddings, exact and approximate neighbors, index maintenance, BM25 hybrid search, Clef System One reranking, and the full retrieval-to-answer flow. It uses the shipped Acme finance and research documents. Install its optional packages with `uv sync --group rag` and run the notebooks from the repository root with the project kernel.

The introductory sequence is [Create Agent](notebooks/langchain/01_create_agent.ipynb), [Opening Loop](notebooks/langchain/02_opening_loop.ipynb), [simple memory for one conversation](notebooks/langchain/03_simple_memory.ipynb), [memory with saved conversations](notebooks/langchain/04_adding_memory.ipynb), [Tools](notebooks/langchain/05_tools.ipynb), [structured output and agent state](notebooks/langchain/06_structured_output_agent_state.ipynb), [runtime context](notebooks/langchain/07_context.ipynb), [Streaming](notebooks/langchain/08_streaming.ipynb), [Context versus State](notebooks/langchain/09_context_and_state.ipynb), and [custom middleware end to end](notebooks/langchain/10_custom_middleware.ipynb).

Every notebook keeps all imports in a dedicated first code cell (with only minimal project-path setup). Model creation and examples start below it. Python modules keep imports at the top level; no imports inside functions or example cells. Automated tests enforce this convention.

1. Fill provider values and credentials in the root `.env` using [.env.example](.env.example) as a template. Preserve existing keys.
2. Select `[selection].main` in `models.toml`: `local` (Ollama), `openai`, `claude` (Anthropic), or `azure` (Azure OpenAI). Middleware roles can select their own profiles in that same file.
3. Open any notebook in VS Code, select the project `.venv` kernel, and run from the top.

Model names, endpoints, Azure deployment/API version and keys all live in `.env`. TOML stores profile selection and model/runtime options. Unused providers can remain blank. No notebook-local environment file is loaded. Explicit process environment variables take precedence over `.env`.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv sync --group middleware
# For local execution, install the exact OLLAMA_MODEL selected in .env:
# ollama pull <your-model>
```

Python code uses `from model_config import get_model` followed by `model = get_model()`. A specialized role can use `get_model("grader")`, for example. Recreate models/agents after changing configuration. Restart notebook kernels opened before the shared-configuration migration.

You can always override the model for a single call without editing configuration:

```python
model = get_model()  # Selected profile + default model from .env.
model = get_model(model="my-local-model")  # Same provider, different model.
model = get_model("grader", model="my-grading-model")
model = get_model(profile="azure", model="my-deployment")
```

`model=` takes precedence over the configured model name; that default may be blank when an explicit name is supplied. The profile still selects the provider, endpoint and credentials. For Azure, `model=` is the deployment name. The first positional argument remains the role. `get_json_model` and `get_model_name` accept the same `model=` argument.

Models must support the lesson's tools/structured-output features. Lesson 06 uses one Pydantic schema and LangChain's `ToolStrategy` to show structured output in the agent state.

The advanced middleware curriculum starts at [notebooks/langchain/06_middlewares/README.md](notebooks/langchain/06_middlewares/README.md). API key handling follows the [official OpenAI Python guidance](https://developers.openai.com/api/reference/python).

Checks without paid API calls:

```powershell
uv run --group middleware python -m unittest discover -s tests -v
```
