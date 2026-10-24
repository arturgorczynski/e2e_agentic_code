# G10–G12 validation

G10 execution, G11 learning UI and G12 setup are accepted on the evidence below.
G09 remains a separate outstanding milestone. Subsequent complete-journey evidence
is recorded in [G13 validation](G13_VALIDATION.md).

## Verified environment and checks

- Windows, Python 3.12.12, LangChain 1.4.6, Gradio 6.30.0 and SQLite checkpointer 3.1.2.
- The final independent copy installed from the unchanged lockfile, verified prepared
  data and company consistency, passed **76 tests in 127.217 seconds**, and passed Ruff.
  Imports resolved inside that copy, outside the parent course.
  Retained copy: `C:\Users\Komputer\AppData\Local\Temp\acme-g01-zjwnfb43`.
  Evidence: `artifacts/g12_final_independence.log`.
- Nine local-job checks cover useful CSV/report generation, malformed input, path/size
  limits, exact bounded decimal sums, deadlines, real cancellation, cross-owner denial,
  live-controller protection, orphan termination, reused-PID protection and shutdown.
  A shutdown deadline explicitly records unverified cleanup instead of claiming success.
- Eight web/setup checks cover owned downloads/history/traces, upload limits, logout,
  edited/replayed approvals, restored pending approvals, setup preservation, model/backend/
  data diagnostics, and Gradio session/event ownership. Foundation checks also verify
  quiet imports and module import layout.
- The root-course import checks were rerun. The pre-existing summarization notebook
  has one import-layout failure and two `get_ipython` errors. That notebook, root
  model factory and root `.env` were not modified.

## Default path: no Docker execution or cloud credentials

Interactive setup in a clean external copy prompted for the new account password,
preserved prepared company state, and created its own configuration. The installed
local model was `qwen3-coder:30b`; `doctor --inference` passed an actual tool-call probe.
The setup account and password were explicitly provisioned for disposable validation;
no default password is shipped.

The standalone `acme serve` journey passed through real Gradio HTTP callbacks:
login, streamed model output, disconnection/reconnection, restored selection, one
accepted human message, a sourced policy report, edited/idempotent approval, effective
input differences, full-company sales CSV analysis, report download, and another account's
denied access. It made four real model requests and recorded 112 events.
Evidence: `artifacts/g12_standalone_journey.json`.

The earlier in-repository journey independently passed the same sequence:
`artifacts/g11_api_validation.json`. These are API integration checks, not browser proof.
The final clean-copy suite followed the last recovery and precision changes; the real
model standalone journey used the preceding copy. Dependency installation used the local
uv cache; first-time uncached downloads were not tested.

## Optional Docker evidence

Four real container checks passed separately from the default path: generated Python
with a read-only CSV and no network/provider secrets; timeout removal; cancellation
with a terminated CLI; and oversized stdout rejection with container removal.
An initial cancellation/create race was corrected by separating create and start.

On the final UI server, a six-second Docker job visibly returned queued/running/complete
states through the polling callback, survived switching threads and disconnecting, and
retained its result. The same callback run verified create/rename/archive, restored
selection, clearing old thread editors, and suppressing stale thread polls.
Evidence: `artifacts/g11_final_callbacks.json`. This demonstrates callback state, not
rendered UI behavior or a slow agent tool's visual progress.

## G11 browser acceptance

The user waived browser-connection setup and supplied screenshots. Those screenshots
showed a crowded layout and broken banner contrast. The resulting redesign replaces
the banner/forms with a collapsible chat sidebar, per-chat menus, recoverable Trash,
free-chat mode, a viewport-sized conversation and a separate Learn & tools view.
All **79 tests passed in 122.882 seconds**, including tool-free conversation memory,
mode ownership/locking, escaped history titles and reversible owned menu actions.
Live Gradio construction and callbacks for selecting/new chats and switching an empty
chat's mode passed. Evidence: `artifacts/ui_redesign_tests.log`.
A real local-model free chat completed two turns, remembered the user's astronomy
preference, exposed zero company tool schemas and generated its sidebar title from
the first message. Evidence: `artifacts/ui_redesign_free_chat.json`.
Chrome automation connected after refreshing the browser-control session on
2026-10-16. Sign-in and the rendered conversation were inspected at desktop size and
at 390 x 844 pixels. These checks exposed and corrected clipped composer layout;
the mobile composer now ends at approximately y=824, within the viewport. The mobile
history toggle also worked. The desktop viewport was restored after inspection.
The subsequent browser pass completed the remaining checks. The app is available
locally at `http://127.0.0.1:7860/app/`. Evidence is recorded in
`artifacts/g11_browser_acceptance.json`, with persisted state in
`artifacts/g11_live/state` and `artifacts/browser_fixture/state`.

- Two simultaneous browser logins used separate host-only cookies: `taylor.analyst`
  on `127.0.0.1:7860` and `alex.sales` on `localhost:7860`, reaching the same server.
  The sales browser was denied the analyst's transcript, trace and report file with
  “Conversation unavailable to this account.” Each sidebar showed its own identity/history.
- Create, keyboard rename, delete to Trash and restore passed. Logout returned to login;
  opening the protected app while logged out returned to login again.
- Desktop (1280 x 900) and narrow (390 x 844) checks covered chat, history, Workspace,
  trace JSON and editable approval JSON. Mobile content stayed within the body width.
  Controls remain reachable by keyboard; Esc then Tab exits the code editor. The UI
  now states that shortcut, wraps editable code, improves download-link contrast,
  removes the misleading browser-only clear button and reduces nested sidebar padding.
  Missing CSV input now explains how to prepare or upload a file.
- A real local-model conversation showed partial answer text while the status reported
  `Running / Latest activity: model_stream`. Both completed turns survived navigation,
  refresh, server restart and logout/login. The database has exactly two human and two
  assistant messages and 62 recorded model-stream events for that conversation.
- The separate scripted browser fixture delayed a real `search_documents` tool for
  **30,049 ms** inside the normal agent/worker/checkpointer path. The browser displayed
  `Running / Latest activity: native_tool_started`. A second chat was created before
  the tool finished, and the page was refreshed. Returning showed the final answer and
  pending report approval, with exactly one accepted human message.
- The pending approval's edited JSON survived background polling. Keyboard approval
  persisted `Browser reviewed report` with the exact reviewed body; the saved decision
  exposed both original and decided arguments. This fixture uses a scripted model,
  so it proves lifecycle behavior rather than provider latency or model quality.
- The company explorer returned ten customer records with provenance and a total of
  3,832; exact-version reading returned `POL-RETURNS-001` version 1 with mock-RAG labels.
  Trace inspection and the scenario date remained visible in Learn & tools.

Repeat the deterministic slow-tool browser exercise with:

```powershell
uv run python scripts/serve_browser_fixture.py
```

It binds only to loopback on port 7863, uses separate fixture data/state, and prints its
URL. Sign in as `taylor.analyst` with the disposable password `browser-fixture-only`,
choose Company assistant and send a message. The fixture is opt-in; normal `acme serve`
does not use it. Stop the fixture with Ctrl+C. Its server was stopped after validation.

After these changes, Ruff and all three foundation/import tests passed. The parent
import-layout checks still report the same unrelated summarization notebook failure
and two IPython errors. Viewport emulation is not a physical-mobile-device test.

## Requirement audit

| Requirement | Evidence |
| --- | --- |
| G10 default calculations, CSV and reports; owned files and limits | `tests/test_jobs.py`, `tests/test_web_setup.py`, full-company CSV in `artifacts/g12_standalone_journey.json` |
| G10 malformed/path/size/deadline/cancellation behavior, no late writes | Nine local-job checks in the recorded suite; owned process exit and artifact stability assertions |
| G10 optional Docker isolation, generated code, cancellation and timeout cleanup | Four real-container tests in `artifacts/g10_g12_final_tests.log`; `docs/local_execution.md` records flags and limits |
| G10 workspace and disconnect boundaries | `docs/local_execution.md`, `docs/learning_app.md`, UI Workspace explanation and browser recovery check |
| G11 identity, owned lifecycle, persistence and two browser sessions | Browser checks above plus server ownership and event/session tests |
| G11 streaming, progress, failures, recovery and edited approvals | Real-model stream plus scripted slow-tool browser fixture and persisted assertions |
| G11 inspection, context differences, evidence and artifacts | Browser trace/explorer/approval views; real-provider `effective_input_context_diff` and download checks in standalone journey |
| G11 narrow layout, keyboard and clear service labels | Desktop/mobile browser observations above; wrapped editor measured at 280px with no horizontal overflow |
| G12 clean setup and published commands | Interactive external-copy setup, standalone journey, locked installation and 76-test external-copy log |
| G12 diagnostics and preservation | Setup/web tests cover missing model, unavailable provider, incompatible data, occupied port, absent optional Docker, unchanged credentials/config/company mutations |
| G12 English learning materials | README quick start, repository map, company guide, data dictionary, learning walkthrough, diagnostics and local-execution guide |

macOS/Linux and cloud inference remain unverified. These optional environments are
separate from the verified Windows/local-model setup.

## Reproduction

```powershell
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run python scripts/verify_independence.py
uv run acme doctor --inference
```

`scripts/verify_learning_api.py` exercises actual Gradio callbacks and configured
inference against an already running disposable validation server. Provision its two
accounts in isolated state first. Its password argument is for disposable test credentials;
do not put a production password on the command line. It is not a browser test.
