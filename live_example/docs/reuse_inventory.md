# Reuse inventory

`LangTutorial/` was a separate reference project and has been removed. Paths
below describe historical sources, not files to import now.

Paths below identify source material in the original teaching repository. They are
provenance references, not imports or installation requirements. Live Example must
remain usable when none of those source directories exist.

| Source | Decision | Changes / intended milestone |
| --- | --- | --- |
| Root `model_config.py` and `models.toml` | Adapted in G01 | One local factory; explicit configuration root, four provider profiles, environment precedence, model override, no construction/logging on import. Course-only settings are omitted. |
| `LangTutorial/src/tools/database_tools.py` | Candidate for G06 | Preserve focused business operations; fix `total_amount` versus `total_usd`, add typed results, pagination, permissions, and idempotent writes. |
| `LangTutorial/src/tools/kb_tools.py` | Candidate for G06 | Preserve simple search idea; add ranking, versions, metadata, and bounded source excerpts. |
| `LangTutorial/data/kb/` | Structural reference in G05 | Kept the idea of readable Markdown procedures. Authored Acme-specific policies and factual templates against the new database; no Zooplu company facts were copied. |
| `LangTutorial/db/models.py` | Conceptual reference in G04 | Replaced the four-table demo with an independent 35-table SQLite schema and explicit operational rules; no ORM dependency or old seed imported. |
| `LangTutorial/db/seed.py` | Do not copy wholesale | Destructive reseeding, moving dates, and tiny random data do not meet the dataset plan. |
| `LangTutorial/evals/` | Candidate for G02/G13 | Retain scenario format; check concrete facts and side effects, with meaningful failing exit codes. |
| `LangTutorial/src/utils/tracing.py` and `src/middleware/logging_middleware.py` | Candidate for G08 | Adapt event/timing patterns; persist correlated full inputs/results with documented redaction. |
| Current `notebooks/06_middlewares/lab/display.py` | Candidate for G08 | Adapt the project-local `TraceMiddleware`; explain its LangChain-level observation boundary. |
| Current `notebooks/06_middlewares/lab/custom.py` and middleware lessons | Candidate for G09 | Preserve explicit lifecycle/context examples and teach middleware order. |
| Current `notebooks/06_middlewares/lab/sandbox.py` | Candidate for G10 | Reuse bounded-worker and owned-container cleanup patterns after isolation review. Local processes are not security sandboxes. |
| `LangTutorial/src/agents/agent_high_level.py`, `src/graphs/` | Architecture reference only | Use current `create_agent` for G07. Custom graphs and multi-agent code stay deferred. |
| `LangTutorial/src/tools/utility_tools.py` | Replace unsafe calculator | Empty-builtins `eval` is not a sandbox; use limited operations in G10. |
| `LangTutorial/src/memory/`, CLI, provider configuration | Concepts only | Build explicit lifecycle, durable checkpoints, authentication context, and a single local configuration root. |

G01 copies no old credentials, company database, histories, traces, `.git`, `.venv`, or
caches. Future adaptations require their own tests; this inventory does not certify
those candidates as ready to use.
