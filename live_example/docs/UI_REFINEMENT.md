# Chat, executions and playground refinement — 2026-10-17

Implemented in `acme/ui.py`, `ui_assets.py`, `ui_service.py`, `execution_view.py`,
`tool_catalog.py` and `web_search.py`. See [the updated walkthrough](learning_app.md).

- Accepted prompts render from the persisted queue before the worker produces a transcript.
  Once the human transcript arrives, the queued preview is replaced without duplication.
- New-chat and mode navigation use virtual drafts. No conversation row is created until
  a valid first submission. Rejected submissions roll back their empty allocation.
  Existing empty rows are hidden, not deleted. Populated chats and artifacts are retained.
- History actions use Gradio custom events with `preventDefault`, not document navigation.
  The sidebar has a bounded flex stack, a contained history scroller, bounded settings and
  a collapsible company-tool accordion. Chat bubbles have horizontal gutters.
- Executions offers word, mode and date filters, a larger clickable conversation, direct
  timeline-row selection, and an expandable conversation graph. Arrows indicate recorded
  event order, not a claim about parallel execution dependencies. Input/output/raw-event
  inspection remains available for every selected step.
- The tool catalog uses the actual model-facing schemas and offers editable examples.
  Each account has one durable private playground, excluded from chat history. Documents,
  record pages, aggregates, file previews, CSV jobs and saved reports are accessible there.
  Chat approvals remain in the originating conversation; playground approvals remain in Tools.
- Both modes and the playground can use free public web search. DDGS 9.9.x is constrained
  with compatible primp 0.15.x; this avoids the incompatible browser profiles in primp 2.x.
  No API key or paid service is required. External availability is not guaranteed.

## Verification

- 11 regression tests pass, covering draft persistence, first-message visibility, replay,
  transcript deduplication, playground isolation and restart, catalog/schema parity,
  document access, owned graph output, word/date/mode filters, search success/failure,
  report approval/browsing, mounted Gradio configuration, in-page history callbacks
  and cross-account HTTP denial.
- The two repository notebook/module import-layout checks pass. Ruff passes for the changed
  application and tests. No teaching notebooks, historical execution artifacts or model
  configuration were rewritten.
- Isolated real-tool acceptance: 148 accessible document versions for the test super-user;
  customer preview; full customer-order aggregate; document read; CSV preview and completed
  group-sum worker; live public web results with source links; no playground entries in chat history.
- The configured `qwen3-coder:30b` completed a real Free-chat web search, returned two
  source links and produced inspectable graph nodes. The prompt appeared before the answer
  and remained a single transcript entry. Initial trials exposed the model's missing
  opening tool-call tag; instructing it to invoke tools before commentary made the tested
  call native. This is a successful journey, not a claim that every model output is reliable.
- Browser visual acceptance is **not verified** in this session: the browser controller
  reported no available browser, and Windows Computer Use reported an unavailable native pipe.
  Backend, HTTP and component checks do not establish rendered layout or physical click behavior.

Reproduce:

```powershell
cd live_example
uv sync --locked
uv run python -B -m unittest discover -s tests -v
uv run ruff check acme tests scripts/check_ui_revision.py
uv run python -B scripts/check_ui_revision.py --search
# Optional real configured-model + web-tool check on isolated sample state:
uv run python -B scripts/check_ui_revision.py --model
uv run acme serve
```

Restart the server and reload an already-open browser once to load the new UI code.
Subsequent conversation switches do not reload the document.
