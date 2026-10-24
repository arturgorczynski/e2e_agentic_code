# Acme Wholesale local demo website

A fictional wholesale company website backed by the existing Acme SQLite data, document corpus, Python tools, agent runtime, approvals and execution traces. The current UI is React + TypeScript served by FastAPI. Older Gradio learning material remains in the repository for reference; `acme serve` opens this website.

## Start locally (no Docker)

From PowerShell in `live_example`:

```powershell
uv sync --locked
npm --prefix frontend install
npm --prefix frontend run build
uv run acme setup
uv run acme doctor
uv run acme serve
```

Open <http://127.0.0.1:7860>. If `state/` already exists, setup preserves it. If your existing `.env` is configured, it is preserved as well. The public catalog and database views work without a running model. For chat, start the configured model provider and run `uv run acme doctor --inference` to check tool calling. The tested local model path uses Ollama; Docker is not part of normal startup.

For frontend development, keep `uv run acme serve` running in one terminal, then run `npm --prefix frontend run dev` in another. Open <http://127.0.0.1:5173>; Vite proxies `/api` to FastAPI. Rebuild with `npm --prefix frontend run build` before using the single-server port 7860.

See the [live presentation script](docs/LIVE_DEMO_SCRIPT.md) for a guided
15–20 minute demonstration and the [portal guide](docs/PORTAL_GUIDE.md) for
data boundaries, editing, agent trace inspection and troubleshooting.
See [data quality and provenance](docs/DATA_QUALITY.md) for the v8 fictional
identities and business histories, [bot scenarios](docs/BOT_SCENARIOS.md)
for demonstrable customer cases, and [retrieval roadmap](docs/RAG_ROADMAP.md)
for the current document search boundary and future RAG design. Fifty-five
historical stock codes have individual [AI concept images](docs/IMAGE_ASSETS.md);
eight contemporary scenario SKUs share six more concepts. Other catalog
images are category assortments. Neither is verified stock photography.

The document catalog also includes six [authored long-form finance and research
documents](data/document_sources/rag/README.md) for later RAG lessons. They are
versioned, scope-controlled Acme exercise material; the current search remains
lexical.

The [business insights guide](docs/BUSINESS_INSIGHTS.md) explains the order
history, monthly billing and cash measures, and the explicitly fictional 2026
expense ledger. Its installer is needed when preparing a fresh exercise state
with the contemporary purchase orders; the current demo state already has it.

## Verify

```powershell
uv run python -m unittest tests.test_portal -v
uv run python -m unittest tests.test_ui_revision.UIRevision.test_ui_build_callbacks_and_import_layout -v
uv run ruff check acme serve.py tests/test_portal.py
npm --prefix frontend run build
```

The first test builds a small temporary company database and checks customer isolation, employee scopes, direct tools, read-only SQL, audited row creation and editing, foreign-key relationships, conflict handling and a customer tool reading an address edit after restart. The second check preserves the repository's Python import convention. Existing CLI and historical lessons have their own tests and documentation.

## Existing learning material

- [Agent runtime and CLI](docs/agent_runtime.md)
- [Current portal agent architecture](docs/AGENT_ARCHITECTURE.md)
- [One current customer invoice agent run](docs/CUSTOMER_INVOICE_AGENT_WALKTHROUGH.md)
- [Employee planning run across SQL and a document](docs/PLANNING_AGENT_WALKTHROUGH.md)
- [Fictional cash activity agent run](docs/CASH_ACTIVITY_AGENT_WALKTHROUGH.md)
- [Supplier receipt completion and live Operations trace](docs/SPLIT_COMPLETION_WALKTHROUGH.md)
- [Native tool-call failure and verified CLI comparison](docs/NATIVE_TOOL_CALL_FAILURE.md)
- [Company tool contracts](docs/company_tools.md)
- [Execution traces](docs/execution_traces.md)
- [Middleware lesson](docs/middleware.md)
- [Original Gradio UI notes](docs/learning_app.md)

This is a local learning application with fictional company identities. Persona switching is deliberately visible and is not production authentication. The default server binds to `127.0.0.1`.
