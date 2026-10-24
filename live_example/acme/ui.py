"""Gradio layout and callbacks. The launch script supplies Gradio at UI startup only."""

import csv
import html
import io
import json
from urllib.parse import quote
from uuid import uuid4

from acme.app_store import authenticate
from acme.chat_history import history_html
from acme.company_queries import QUERIES
from acme.company_tools import execute
from acme.docker_jobs import start_python_job
from acme.execution_view import conversation_graph, describe, detail, filter_chats, run_summary
from acme.execution_view import runs as execution_runs
from acme.execution_view import steps as execution_steps
from acme.jobs import cancel_job, list_files, prepare_sales_csv, start_csv_job
from acme.middleware import configuration
from acme.model_config import settings
from acme.tool_catalog import (
    EXAMPLES,
    catalog_html,
    document_catalog,
    report_catalog,
    run_tool,
    saved_report,
    sidebar_tools,
    tool_details,
)
from acme.ui_assets import GRAPH_JS, HISTORY_JS, LAYOUT_CSS

CSS = """
.gradio-container { max-width:none !important; padding:0 12px !important; }
.gradio-container > .main { padding:8px 0 !important; }
#acme-sidebar { background: var(--background-fill-secondary); padding: 20px 14px; }
#acme-sidebar > .sidebar-content { padding:0 !important; }
.acme-brand { display:flex; gap:10px; align-items:center; margin:0 4px 22px;
 color:var(--body-text-color); font-size:19px; }
.acme-brand > span:last-child { font-size:11px; color:var(--body-text-color-subdued); }
.brand-mark { display:grid; place-items:center; width:30px; height:30px;
 border-radius:10px; background:#0f766e; color:white; font-weight:700; }
#new-chat { min-height:42px; border-radius:10px; }
#history-panel { flex:none; height:30dvh; min-height:140px; max-height:300px; overflow-y:auto;
 overflow-x:hidden; }
.history-label { font-size:11px; text-transform:uppercase; letter-spacing:.1em;
 color:var(--body-text-color-subdued); padding:8px 10px; }
.history-row { display:flex; align-items:center; position:relative; border-radius:8px; }
.history-row:hover,.history-row.selected { background:var(--background-fill-primary); }
.history-select { flex:1; min-width:0; }
.history-select button { display:block; width:100%; border:0; background:transparent;
 padding:11px 10px; color:var(--body-text-color); text-align:left; font-size:13px;
 white-space:nowrap; overflow:hidden; text-overflow:ellipsis; cursor:pointer; }
.chat-menu { flex:0 0 30px; }
.chat-menu summary { list-style:none; padding:8px 4px; cursor:pointer;
 color:var(--body-text-color); font-size:12px; }
.chat-menu summary::-webkit-details-marker { display:none; }
.chat-menu-panel { position:absolute; left:4px; right:4px; top:40px; z-index:30;
 background:var(--background-fill-primary); border:1px solid var(--border-color-primary);
 box-shadow:0 8px 24px #0002; border-radius:12px; padding:14px; }
.chat-menu-panel label,.chat-menu-panel small { display:block; font-size:12px;
 color:var(--body-text-color-subdued); margin-bottom:8px; }
.chat-menu-panel input { width:100%; box-sizing:border-box; padding:9px; border-radius:6px;
 border:1px solid var(--border-color-primary); color:var(--body-text-color);
 background:var(--background-fill-secondary); }
.chat-menu-panel button,.trash-row button { border:0; padding:9px 0;
 background:transparent; color:var(--body-text-color); cursor:pointer; }
.chat-menu-panel .delete-chat { color:#dc2626; }
.chat-menu-panel small { font-size:11px; margin:4px 0 0; }
.chat-trash { margin:20px 10px; font-size:12px; color:var(--body-text-color-subdued); }
.chat-trash summary { cursor:pointer; }
.trash-row { display:flex; gap:8px; align-items:center; }
.trash-row span { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
#account-label { font-size:11px; border-top:1px solid var(--border-color-primary);
 padding-top:12px; }
.signout button { border:0; background:transparent; color:var(--body-text-color-subdued);
 cursor:pointer; font-size:12px; padding:6px; }
#acme-navigation { width:100%; max-width:none; margin:0; }
#acme-navigation > .tab-nav { border:0; padding:8px 0; }
#chat-tab { padding:0 !important; border:0 !important;
 height:calc(100dvh - 76px); min-height:0; }
#chat-tab > .column { flex:1; height:100%; min-height:0; }
#chat-heading { align-items:center; margin:4px auto 0; max-width:none; }
#mode-hint { font-size:12px; text-align:right; color:var(--body-text-color-subdued); }
#conversation { border:0 !important; background:transparent !important; box-shadow:none;
 flex:1 1 0 !important; height:0 !important; min-height:0 !important; }
#conversation .message { line-height:1.6; padding:12px 16px !important; }
#conversation .message.user { width:fit-content !important; max-width:88% !important;
 margin-left:auto !important; margin-right:0 !important; box-sizing:border-box; }
#conversation .message.bot { width:fit-content !important; max-width:96% !important;
 margin-left:0 !important; margin-right:auto !important; box-sizing:border-box; }
#acme-sidebar * { scrollbar-width:thin;
 scrollbar-color:var(--border-color-primary) transparent; }
#conversation .user::before { content:"You"; display:block; font-size:11px; font-weight:700;
 opacity:.75; margin-bottom:5px; }
#conversation .bot::before { content:"Acme assistant"; display:block; font-size:11px;
 font-weight:700; opacity:.75; margin-bottom:5px; }
#company-tools { max-height:25dvh; overflow:auto; font-size:12px; }
#company-tools p { font-size:12px; line-height:1.45; }
#mode-switch .wrap { display:flex; gap:2px; padding:4px; border-radius:14px;
 background:var(--background-fill-secondary); flex-wrap:nowrap !important; }
#mode-switch label { border:0 !important; border-radius:10px !important; margin:0 !important;
 padding:9px 8px !important; font-size:12px; }
#mode-switch input { position:absolute; opacity:0; width:1px; height:1px; }
#mode-switch label.selected { background:var(--button-primary-background-fill) !important;
 color:var(--button-primary-text-color) !important; }
#mode-switch label:focus-within { outline:2px solid #0d9488; outline-offset:2px; }
#executions-tab,#tools-tab { max-height:calc(100dvh - 90px); overflow-y:auto;
 padding:12px !important; }
#executions-tab .tabitem,#tools-tab .tabitem { padding:12px 4px; }
/* The built-in clear button only clears the browser; owned deletion lives in chat menus. */
#conversation .top-panel,#execution-conversation .top-panel { display:none; }
#conversation .message-row { max-width:none; margin:0; }
.chat-welcome { max-width:560px; padding:5vh 24px; margin:auto; text-align:center;
 color:var(--body-text-color); }
.chat-welcome h1 { font-size:clamp(26px,3vw,38px); font-weight:600; letter-spacing:-.03em;
 margin:16px 0; color:var(--body-text-color) !important; }
.chat-welcome p { line-height:1.7; color:var(--body-text-color-subdued) !important; }
.welcome-eyebrow { font-size:10px; letter-spacing:.2em; color:var(--body-text-color-subdued); }
.welcome-secondary { font-size:12px; margin-top:24px !important; }
#composer { width:100%; max-width:none; margin:0; align-items:flex-end; padding:10px;
 border:1px solid var(--border-color-primary); border-radius:18px;
 background:var(--background-fill-secondary); box-shadow:0 4px 18px #00000008; }
#composer textarea { background:transparent !important; border:0 !important;
 box-shadow:none !important; padding:10px !important; font-size:15px; }
#composer button { border-radius:12px; min-height:42px; }
#chat-status { width:100%; max-width:none; margin:0; min-height:20px; font-size:11px;
 color:var(--body-text-color-subdued); }
#learning-tab { max-height:calc(100dvh - 100px); overflow-y:auto; padding:24px !important; }
#learning-tab .tabitem { padding:24px 8px; }
.acme-downloads a { display:inline-block; padding:8px 12px; margin:4px;
 border:1px solid var(--border-color-primary); border-radius:8px; font-size:12px;
 color:var(--body-text-color) !important; text-decoration:underline; }
pre { overflow-x:auto; }
button:focus-visible,summary:focus-visible,a:focus-visible,input:focus-visible {
 outline:2px solid #0d9488 !important; outline-offset:3px; }
@media(max-width:700px) {
 .gradio-container { padding:0 10px !important; }
 #mode-hint { display:none; }
 #acme-sidebar.open > .toggle-button { right:20px; }
 #learning-tab { padding:12px !important; }
 .chat-welcome { padding:24px 12px; }
 #composer { padding:6px; flex-wrap:nowrap; }
 #composer > .block { min-width:0 !important; }
}
"""


CSS += LAYOUT_CSS


def token_from(request):
    return request.request.cookies.get("acme_session", "")


def build_ui(gr, service):
    """Keep the UI dependency at the explicit launch boundary, away from CLI/data imports."""

    # Last-opened chat is persisted per account for reload. In-flight view updates
    # must instead follow this browser session, so another tab cannot freeze it.
    selected_views = {}

    def view_key(request):
        actor = authenticate(service.project, service.state, token_from(request))
        return actor["id"], request.session_hash

    def remember_view(request, thread_id):
        key = view_key(request)
        selected_views.pop(key, None)
        selected_views[key] = thread_id
        if len(selected_views) > 512:
            selected_views.pop(next(iter(selected_views)))

    def fail(exc):
        raise gr.Error(str(exc)[:500]) from exc

    def load(request: gr.Request):
        token = token_from(request)
        actor = authenticate(service.project, service.state, token)
        selected = service.select(token)
        remember_view(request, selected)
        choices = [(r["title"], r["id"]) for r in service.threads(token)]
        return (
            f"**{actor['display_name']}** · {actor['access_profile'].replace('_', ' ').title()}",
            gr.update(choices=choices, value=selected),
            str(uuid4()),
        )

    def choose(thread_id, request: gr.Request):
        try:
            service.select(token_from(request), thread_id)
            remember_view(request, thread_id)
            current = list(poll(thread_id, request))
            current[5] = gr.update(choices=current[5].get("choices", []), value=None)
            # Evidence/approval editors must never retain the previous thread's payload.
            return tuple(current)
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def threads_action(action, thread_id, title, request: gr.Request):
        token = token_from(request)
        try:
            if action == "create":
                selected = "draft:" + service.chat_mode(token, thread_id)
            else:
                selected = service.edit_thread(
                    token,
                    thread_id,
                    title if action == "rename" else None,
                    archive=action == "archive",
                )
            remember_view(request, selected)
            return gr.update(
                choices=[(r["title"], r["id"]) for r in service.threads(token)], value=selected
            )
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def send(thread_id, message, submission_id, request: gr.Request):
        try:
            token = token_from(request)
            selected = service.submit_chat(token, thread_id, message, submission_id)
            remember_view(request, selected)
            return (
                "",
                str(uuid4()),
                "Thinking…",
                gr.update(value=selected),
                service.snapshot(token, selected)["chat"],
            )
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def resume(thread_id, request: gr.Request):
        try:
            service.resume(token_from(request), thread_id)
            return "Resume queued; the accepted user message will not be duplicated."
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def poll(thread_id, request: gr.Request):
        if not thread_id:
            return (gr.skip(),) * 8
        token = token_from(request)
        try:
            snapshot = service.snapshot(token, thread_id)
            status = "**" + snapshot["status"].replace("_", " ").title() + "**"
            if snapshot["error"]:
                status += " — " + snapshot["error"]
            activity = snapshot["events"][-8:]
            if activity and snapshot["status"] == "running":
                status += " · Latest activity: `" + activity[-1]["kind"] + "`"
            if snapshot["operations"]:
                status += f" · {len(snapshot['operations'])} awaiting review below"
            if snapshot["status"] == "ready":
                status = (
                    "Type a message below to start. Enter to send · Shift+Enter for a new line."
                )
            timeline = "\n".join(
                f"- `{e['created_at'][11:19]}` **{e['kind']}** · `{e['id']}`" for e in activity
            )
            links = "".join(
                f'<a href="/artifacts/{thread_id}/{r["id"]}" target="_blank" rel="noopener">'
                f"{html.escape(r['name'])} ({r['bytes']:,} bytes)</a>"
                for r in snapshot["files"]
            )
            links += f'<a href="/uploads/{thread_id}" target="_blank" rel="noopener">Upload CSV</a>'
            links += (
                f'<a href="/transcript/{thread_id}" target="_blank" rel="noopener">'
                "Download full history</a>"
            )
            links += (
                f'<a href="/trace/{thread_id}" target="_blank" rel="noopener">Download trace</a>'
            )
            choices = [(r["kind"] + " · " + r["id"], r["id"]) for r in snapshot["operations"]]
            sources = {}
            for source in snapshot["sources"]:
                label = source["id"]
                if source["kind"] == "query":
                    url = f"/trace/{thread_id}"
                    label = "SQL evidence: " + label
                else:
                    entity = "documents" if source["kind"] == "document" else source["entity"]
                    version = source.get("version") or 1
                    url = (
                        f"/evidence/{thread_id}/{quote(entity, safe='')}/"
                        f"{quote(source['id'], safe='')}?version={version}"
                    )
                    if source["kind"] == "document":
                        label += f" · version {version}"
                sources[url] = label
            for report in snapshot["reports"]:
                sources[f"/reports/{thread_id}/{report['id']}"] = "Saved report: " + report["title"]
            evidence_links = (
                '<div class="acme-downloads">'
                + "".join(
                    f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">'
                    f"{html.escape(label)}</a>"
                    for url, label in sources.items()
                )
                + "</div>"
            )
            if selected_views.get(view_key(request), thread_id) != thread_id:
                return (gr.skip(),) * 8
            return (
                snapshot["chat"],
                status,
                timeline,
                '<div class="acme-downloads">' + links + "</div>",
                snapshot["jobs"],
                gr.update(choices=choices),
                snapshot["runs"],
                evidence_links,
            )
        except (ValueError, PermissionError) as exc:
            return (
                [],
                str(exc) + " · Sign in again if your session expired.",
                "",
                "",
                [],
                gr.update(choices=[], value=None),
                [],
                "",
            )

    def inspect(thread_id, kind, text, after, request: gr.Request):
        try:
            return service.inspect(token_from(request), thread_id, kind, text, after)
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def diff(thread_id, before, after, request: gr.Request):
        try:
            return service.diff(token_from(request), thread_id, before, after)
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def operation(thread_id, identifier, request: gr.Request):
        if not identifier:
            return "{}"
        try:
            row = service.operation(token_from(request), thread_id, identifier)
            return json.dumps(json.loads(row["payload_json"]), indent=2, ensure_ascii=False)
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def decision(thread_id, identifier, decision, arguments, request: gr.Request):
        try:
            edited = json.loads(arguments) if decision == "approve" else None
            return service.decision(token_from(request), thread_id, identifier, decision, edited)
        except (ValueError, PermissionError, RuntimeError) as exc:
            fail(exc)

    def explore(thread_id, entity, identifier, text, request: gr.Request):
        try:
            return service.explore(token_from(request), thread_id, entity, identifier, text)
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def document(thread_id, identifier, version, request: gr.Request):
        try:
            return execute(
                service.company_context(token_from(request), thread_id),
                "read_document",
                {"document_id": identifier, "version": int(version), "max_chars": 6000},
            )
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def prepare(thread_id, request: gr.Request):
        try:
            return prepare_sales_csv(service.company_context(token_from(request), thread_id))
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def analyze(thread_id, file_id, operation, value, group, deadline, request: gr.Request):
        try:
            if not file_id or not file_id.strip():
                raise ValueError(
                    "Prepare the monthly sales CSV above, or upload a CSV and enter its file ID."
                )
            return start_csv_job(
                service.company_context(token_from(request), thread_id),
                file_id,
                operation,
                value,
                group or None,
                deadline,
            )
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def cancel(thread_id, identifier, request: gr.Request):
        try:
            result = cancel_job(service.company_context(token_from(request), thread_id), identifier)
            return result
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def python(thread_id, code, file_id, deadline, request: gr.Request):
        try:
            return start_python_job(
                service.company_context(token_from(request), thread_id),
                code,
                file_id or None,
                deadline,
            )
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def metadata(thread_id, request: gr.Request):
        token = token_from(request)
        selected = thread_id or service.select(token)
        current_mode = service.chat_mode(token, selected)
        hint = (
            "Ask anything. Think, write, learn."
            if current_mode == "free"
            else "Company data + documents · 9 Dec 2011 · Mock RAG"
        )
        return (
            history_html(service, token, selected, current_mode),
            gr.update(value=current_mode),
            hint,
        )

    def change_mode(thread_id, value, request: gr.Request):
        try:
            selected = service.switch_mode(token_from(request), thread_id, value)
            remember_view(request, selected)
        except (ValueError, PermissionError) as exc:
            fail(exc)
        choices = [(r["title"], r["id"]) for r in service.threads(token_from(request), value)]
        return gr.update(choices=choices, value=selected), *metadata(selected, request)

    def navigation(thread_id, request: gr.Request):
        token = token_from(request)
        current_mode = service.chat_mode(token, thread_id)
        all_chats = service.threads(token)
        choices = [
            (("Company" if r["mode"] == "company" else "Free") + " · " + r["title"], r["id"])
            for r in all_chats
        ]
        return (
            gr.update(visible=current_mode == "company"),
            sidebar_tools(service.project, service.state, token),
            gr.update(choices=choices, value=None if thread_id.startswith("draft:") else thread_id),
        )

    def history_action(evt: gr.EventData, request: gr.Request):
        token = token_from(request)
        identifier, action = evt._data["thread"], evt._data["action"]
        try:
            if action == "select":
                selected = service.select(token, identifier)
            elif action == "restore":
                selected = service.restore_thread(token, identifier)
            elif action in {"delete", "rename"}:
                selected = service.edit_thread(
                    token,
                    identifier,
                    evt._data.get("title") if action == "rename" else None,
                    archive=action == "delete",
                )
            else:
                raise ValueError("Unknown chat action")
            remember_view(request, selected)
            return gr.update(value=selected), *metadata(selected, request)
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def refresh_execution(thread_id, request: gr.Request):
        try:
            token = token_from(request)
            if not thread_id or thread_id.startswith("draft:"):
                return gr.update(choices=[], value=None), [], "Select one of your chats above."
            rows = execution_runs(service.project, service.state, token, thread_id)
            choices = [
                (f"{r['created_at'][11:19]} · {r['user_text'][:65]} · {r['status']}", r["id"])
                for r in rows
            ]
            snapshot = service.snapshot(token, thread_id)
            return (
                gr.update(choices=choices, value=rows[0]["id"] if rows else None),
                snapshot["chat"],
                (
                    "Click a conversation bubble or choose a message to follow its execution."
                    if rows
                    else "This chat has no executions yet. Send a message in Chat first."
                ),
            )
        except (ValueError, PermissionError) as exc:
            fail(exc)

    def refresh_execution_navigation(thread_id, request: gr.Request):
        chats = service.threads(token_from(request))
        choices = [
            (("Company" if r["mode"] == "company" else "Free") + " · " + r["title"], r["id"])
            for r in chats
        ]
        permitted = {r["id"] for r in chats}
        selected = thread_id if thread_id in permitted else (chats[0]["id"] if chats else None)
        return gr.update(choices=choices, value=selected), *refresh_execution(selected, request)

    def search_chats(words, mode, period, start, end, selected, request: gr.Request):
        try:
            chats = filter_chats(service, token_from(request), words, mode, period, start, end)
            choices = [
                (f"{r['mode'].title()} · {r['title']} · {r['updated_at'][:10]}", r["id"])
                for r in chats
            ]
            chosen = (
                selected
                if any(r["id"] == selected for r in chats)
                else (chats[0]["id"] if chats else None)
            )
            return gr.update(choices=choices, value=chosen)
        except ValueError as exc:
            fail(exc)

    def select_message(thread_id, evt: gr.SelectData, request: gr.Request):
        snapshot = service.snapshot(token_from(request), thread_id)
        index = evt.index[0] if isinstance(evt.index, (tuple, list)) else evt.index
        identifiers = snapshot["chat_runs"]
        return gr.update(value=identifiers[index]) if 0 <= index < len(identifiers) else gr.skip()

    def graph_pick(thread_id, run_id, evt: gr.EventData, request: gr.Request):
        selected = evt._data["run"]
        allowed = execution_runs(service.project, service.state, token_from(request), thread_id)
        if not any(row["id"] == selected for row in allowed):
            fail(ValueError("Execution unavailable"))
        if selected != run_id:
            return gr.update(value=selected), gr.skip()
        return gr.skip(), gr.update(value=evt._data.get("step") or None)

    def select_execution(thread_id, run_id, request: gr.Request):
        if not thread_id or not run_id:
            return (
                [],
                gr.update(choices=[], value=None),
                "No execution selected.",
                gr.update(choices=[], value=None),
                gr.update(choices=[], value=None),
                "<p>No execution to display.</p>",
            )
        token = token_from(request)
        rows = execution_steps(service.project, service.state, token, thread_id, run_id)
        run = next(
            (
                r
                for r in execution_runs(service.project, service.state, token, thread_id)
                if r["id"] == run_id
            ),
            None,
        )
        if run is None:
            fail(ValueError("Execution unavailable for this chat"))
        choices = [(f"{i + 1}. {describe(r)}", r["id"]) for i, r in enumerate(rows)]
        initial = next(
            (r["id"] for r in rows if r["kind"] == "model_request"), rows[0]["id"] if rows else None
        )
        models = [
            (f"Model input {i + 1} · {r['created_at'][11:19]}", r["id"])
            for i, r in enumerate(r for r in rows if r["kind"] == "model_request")
        ]
        return (
            [[i + 1, r["created_at"][11:19], describe(r)] for i, r in enumerate(rows)],
            gr.update(choices=choices, value=initial),
            run_summary(rows, run),
            gr.update(choices=models, value=models[0][1] if models else None),
            gr.update(choices=models, value=models[-1][1] if models else None),
            conversation_graph(service.project, service.state, token, thread_id, run_id, initial),
        )

    def select_step(thread_id, run_id, event_id, request: gr.Request):
        if not event_id or not thread_id or not run_id:
            return "Select a step to inspect it.", None, None, None
        rows = execution_steps(
            service.project, service.state, token_from(request), thread_id, run_id
        )
        row = next((r for r in rows if r["id"] == event_id), None)
        if row is None:
            fail(ValueError("Step unavailable for this execution"))
        return detail(row)

    def select_timeline(thread_id, run_id, evt: gr.SelectData, request: gr.Request):
        rows = execution_steps(
            service.project, service.state, token_from(request), thread_id, run_id
        )
        index = evt.index[0]
        if not 0 <= index < len(rows):
            fail(ValueError("Select a timeline row"))
        return gr.update(value=rows[index]["id"])

    def new_tools_workspace(request: gr.Request):
        return service.playground(token_from(request))

    def tool_poll(thread_id, request: gr.Request):
        if not thread_id:
            return (
                "Open Tools to initialize your private playground.",
                [],
                gr.update(choices=[], value=None),
            )
        snapshot = service.snapshot(token_from(request), thread_id)
        links = "".join(
            f'<a href="/artifacts/{thread_id}/{r["id"]}" target="_blank" rel="noopener">'
            f"{html.escape(r['name'])}</a>"
            for r in snapshot["files"]
        )
        links += f'<a href="/uploads/{thread_id}" target="_blank" rel="noopener">Upload CSV</a>'
        return (
            '<div class="acme-downloads">' + links + "</div>",
            snapshot["jobs"],
            gr.update(
                choices=[(r["kind"] + " · " + r["id"], r["id"]) for r in snapshot["operations"]]
            ),
        )

    def direct(thread_id, name, arguments, request: gr.Request):
        try:
            return run_tool(
                service.company_context(token_from(request), thread_id), name, json.loads(arguments)
            )
        except (ValueError, PermissionError, TypeError) as exc:
            fail(exc)

    def load_documents(thread_id, request: gr.Request):
        rows, choices = document_catalog(service.company_context(token_from(request), thread_id))
        return rows, gr.update(choices=choices, value=choices[0][1] if choices else None)

    def pick_document(thread_id, evt: gr.SelectData, request: gr.Request):
        _, choices = document_catalog(service.company_context(token_from(request), thread_id))
        return gr.update(value=choices[evt.index[0]][1])

    def load_reports(request: gr.Request):
        choices = report_catalog(service, token_from(request))
        return gr.update(choices=choices, value=choices[0][1] if choices else None)

    def view_report(selected, request: gr.Request):
        return saved_report(service, token_from(request), selected)

    def preview_file(thread_id, file_id, request: gr.Request):
        if not file_id:
            return gr.update(visible=False), "Choose a file from the library first.", None
        result = direct(
            thread_id,
            "analyze_workspace",
            json.dumps({"action": "read", "file_id": file_id}),
            request,
        )
        payload = result.get("result", {})
        content = payload.get("content", "")
        if payload.get("name", "").lower().endswith(".csv") and content:
            rows = list(csv.reader(io.StringIO(content)))
            headers, rows = rows[0], rows[1:51]
            if payload.get("truncated") and rows:
                rows = rows[:-1]
            width = len(headers)
            rows = [(row + [""] * width)[:width] for row in rows]
            return (
                gr.update(headers=headers, value=rows, visible=True),
                f"{payload['name']} · preview of up to 50 rows. Download for the full file.",
                result,
            )
        return gr.update(visible=False), content or "No readable content returned.", result

    def refresh_files(thread_id, current, request: gr.Request):
        rows = list_files(service.company_context(token_from(request), thread_id))
        choices = [(f"{r['name']} · {r['bytes']:,} bytes", r["id"]) for r in rows]
        selected = (
            current if any(r["id"] == current for r in rows) else (rows[-1]["id"] if rows else None)
        )
        return gr.update(choices=choices, value=selected)

    def web_lookup(thread_id, query, request: gr.Request):
        result = direct(thread_id, "web_search", json.dumps({"query": query}), request)
        links = "".join(
            f'<article class="tool-card"><a href="{html.escape(r["url"], quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{html.escape(r["title"])}</a>'
            f"<p>{html.escape(r['snippet'])}</p></article>"
            for r in result.get("results", [])
        )
        return links or html.escape(result.get("error", "No results found.")), result

    def calculate(thread_id, operation, values, request: gr.Request):
        result = direct(
            thread_id,
            "run_analysis",
            json.dumps(
                {
                    "operation": operation,
                    "values": [v.strip() for v in values.splitlines() if v.strip()],
                }
            ),
            request,
        )
        value = result.get("facts", {}).get("value")
        suffix = "%" if operation == "percentage_change" else ""
        summary = (
            f"### Result: {value}{suffix}"
            if value is not None
            else "No defined result. Check the values and the tool details below."
        )
        return summary, result

    def search_documents(thread_id, text, effective, request: gr.Request):
        result = direct(
            thread_id,
            "search_documents",
            json.dumps({"query": text, "effective_on": effective}),
            request,
        )
        choices = [
            (
                r["fields"].get("title", r["id"]) + " · v" + str(r["fields"]["version"]),
                json.dumps([r["id"], r["fields"]["version"]]),
            )
            for r in result.get("records", [])
        ]
        return result, gr.update(choices=choices, value=choices[0][1] if choices else None)

    def read_selected_document(thread_id, selected, request: gr.Request):
        if not selected:
            fail(ValueError("Search for a document and choose a result first"))
        identifier, version = json.loads(selected)
        result = document(thread_id, identifier, version, request)
        record = result.get("records", [])
        text = record[0]["fields"].get("content", "") if record else "Document unavailable."
        return f"### {identifier} · version {version}\n\n{text}", result

    def browse(thread_id, entity, identifier, text, parent, cursor, request: gr.Request):
        args = (
            {"entity": entity, "record_id": identifier}
            if identifier
            else {
                "entity": entity,
                "limit": 10,
                "after": cursor or "",
                **({"query": text} if text else {}),
                **({"parent_id": parent} if parent else {}),
            }
        )
        result = direct(
            thread_id, "lookup_record" if identifier else "list_records", json.dumps(args), request
        )
        fields = [r["fields"] for r in result.get("records", [])]
        headers = list(dict.fromkeys(key for row in fields for key in row)) or ["No records"]
        page = result.get("page") or {}
        note = (
            f"Showing {len(fields)} records"
            + (f" of {page['total']}" if "total" in page else "")
            + ". Results follow your selected access scopes."
        )
        if result.get("error"):
            note = result["error"]["message"]
        return (
            {"headers": headers, "data": [[row.get(k) for k in headers] for row in fields]},
            note,
            result,
            page.get("next_cursor") or "",
            gr.update(interactive=bool(page.get("has_more"))),
        )

    def aggregate(thread_id, report, start, end, request: gr.Request):
        args = {"report": report}
        if start.strip():
            args["start_date"] = start.strip()
        if end.strip():
            args["end_date"] = end.strip()
        return direct(thread_id, "business_summary", json.dumps(args), request)

    def database_help(request: gr.Request):
        actor = authenticate(service.project, service.state, token_from(request))
        allowed = [
            name for name, (permission, *_) in QUERIES.items() if permission in actor["permissions"]
        ]
        path = (service.state / "company.sqlite").resolve()
        sample = (
            "import sqlite3\n\nconnection = sqlite3.connect("
            + repr(path.as_uri() + "?mode=ro")
            + ', uri=True)\nprint(connection.execute("SELECT name FROM '
            "sqlite_master WHERE type='table' ORDER BY name\").fetchall())\n"
            "connection.close()"
        )
        options = configuration(service.project)
        profile = settings(service.project)["selection"]["main"]
        return (
            gr.update(
                choices=allowed,
                value="customers" if "customers" in allowed else (allowed[0] if allowed else None),
            ),
            f"Company database: `{path}`\n\n"
            f"Your **{actor['access_profile']}** access scopes apply here. "
            "Direct file access gives local developers the complete database. Use read-only mode.",
            sample,
            f"**Profile:** {actor['display_name']} | **Access:** "
            f"{actor['access_profile'].replace('_', ' ').title()}\n\n"
            f"**Model profile:** {profile}\n\n**Agent preset:** {options['preset']}\n\n"
            f"**Budgets:** {options['model_calls']} model / {options['tool_calls']} tool calls.\n\n"
            "Edit `models.toml` for presets and `.env` for the model. "
            "Start a new chat after changes.",
        )

    def view_poll(thread_id, request: gr.Request):
        values = poll(thread_id, request)
        failed = isinstance(values[1], str) and any(
            word in values[1] for word in ("**Failed**", "**Interrupted**")
        )
        waiting = isinstance(values[5], dict) and bool(values[5].get("choices"))
        return (*values, gr.update(visible=failed), gr.update(visible=waiting))

    with gr.Blocks(
        title="Acme | Chat", analytics_enabled=False, fill_width=True, fill_height=True
    ) as blocks:
        submission = gr.State(str(uuid4()))
        threads = gr.Dropdown(
            label="Current chat", choices=[], visible=False, allow_custom_value=True
        )
        title = gr.Textbox(value="", visible=False)
        timeline = gr.Markdown(visible=False)
        downloads = gr.HTML(visible=False)
        jobs = gr.JSON(visible=False)
        pending = gr.Dropdown(choices=[], label="Requested change", render=False)
        runs_panel = gr.JSON(visible=False)
        sources = gr.HTML(visible=False)
        with gr.Sidebar(width=280, elem_id="acme-sidebar"), gr.Column(elem_id="sidebar-stack"):
            gr.HTML(
                '<div class="acme-brand"><span '
                'class="brand-mark">a</span><strong>Acme</strong><span>Learning '
                "space</span></div>"
            )
            mode = gr.Radio(
                choices=[("Free chat", "free"), ("Company assistant", "company")],
                value="free",
                label="Conversation mode",
                show_label=False,
                container=False,
                elem_id="mode-switch",
            )
            create = gr.Button("New chat", variant="primary", elem_id="new-chat")
            history = gr.HTML(elem_id="history-panel", js_on_load=HISTORY_JS)
            with gr.Accordion(
                "Company tools", open=False, visible=False, elem_id="company-tools-panel"
            ) as company_tools_group:
                available_tools = gr.Markdown(elem_id="company-tools")
            with gr.Accordion("Settings", open=False, elem_id="sidebar-settings"):
                settings_text = gr.Markdown()
                refresh_rate = gr.Slider(
                    minimum=0.25,
                    maximum=2,
                    value=0.75,
                    step=0.25,
                    label="Response refresh (seconds)",
                    info="How often this page checks for streamed text and progress.",
                )
            identity = gr.Markdown(elem_id="account-label")
            gr.HTML(
                '<form action="/logout" method="post" class="signout"><button '
                'type="submit">Switch user / sign out</button></form>'
            )
            rename = gr.Button("Rename", visible=False)
            archive = gr.Button("Delete", visible=False)
        with gr.Tabs(elem_id="acme-navigation"):
            with gr.Tab("Chat", id="chat", elem_id="chat-tab"):
                mode_hint = gr.Markdown("Ask anything. Think, write, learn.", elem_id="mode-hint")
                chat = gr.Chatbot(
                    label="Conversation",
                    show_label=False,
                    height="calc(100dvh - 205px)",
                    min_height=160,
                    buttons=["copy"],
                    allow_file_downloads=False,
                    allow_tags=False,
                    layout="bubble",
                    group_consecutive_messages=False,
                    elem_id="conversation",
                    placeholder='<div class="chat-welcome"><span class="welcome-eyebrow">YOUR '
                    "SPACE TO THINK</span><h1>What is on your mind?</h1><p>Ask a "
                    "question or choose Company assistant to explore Acme.</p></div>",
                )
                status = gr.Markdown("Type a message below to start.", elem_id="chat-status")
                with gr.Row(elem_id="composer"):
                    message = gr.Textbox(
                        label="Your message",
                        show_label=False,
                        placeholder="Message Acme...",
                        lines=1,
                        max_lines=5,
                        scale=12,
                        container=False,
                        autofocus=True,
                    )
                    send_button = gr.Button("Send", variant="primary", scale=0, min_width=90)
                resume_button = gr.Button("Resume interrupted response", visible=False, size="sm")
                with gr.Accordion(
                    "Review requested changes", open=False, visible=False, elem_id="chat-review"
                ) as chat_review_group:
                    pending.render()
                    chat_arguments = gr.Code(
                        value="{}",
                        language="json",
                        interactive=True,
                        label="Review and edit the proposed arguments",
                    )
                    with gr.Row():
                        chat_approve = gr.Button("Approve", variant="primary")
                        chat_reject = gr.Button("Reject")
                    chat_decision = gr.JSON(label="Decision")
            with gr.Tab("Executions", id="executions", elem_id="executions-tab") as executions_tab:
                gr.Markdown(
                    "## Follow the conversation\nFind a chat, click a message, and explore "
                    "the model calls, tools and data behind its answer."
                )
                with gr.Row():
                    execution_search = gr.Textbox(
                        label="Words in title or messages",
                        placeholder="Search conversations…",
                        scale=2,
                    )
                    execution_mode = gr.Dropdown(
                        [("All modes", "all"), ("Free", "free"), ("Company", "company")],
                        value="all",
                        label="Mode",
                    )
                    execution_period = gr.Dropdown(
                        [
                            ("All time", "all"),
                            ("Last 24 hours", "1"),
                            ("Last 7 days", "7"),
                            ("Last 30 days", "30"),
                        ],
                        value="all",
                        label="Updated",
                    )
                with gr.Accordion("Date range (UTC)", open=False):
                    with gr.Row():
                        execution_start = gr.Textbox(label="From date", placeholder="YYYY-MM-DD")
                        execution_end = gr.Textbox(label="Through date", placeholder="YYYY-MM-DD")
                filter_button = gr.Button("Find chats", size="sm")
                with gr.Row():
                    execution_thread = gr.Dropdown(
                        label="Your chats | all modes",
                        choices=[],
                        interactive=True,
                        allow_custom_value=True,
                    )
                    refresh_execution_button = gr.Button("Inspect current chat", scale=0)
                with gr.Column():
                    with gr.Column():
                        run_picker = gr.Dropdown(
                            label="Message / execution · or click a bubble below",
                            choices=[],
                            interactive=True,
                        )
                        execution_chat = gr.Chatbot(
                            label="Saved conversation",
                            height=430,
                            layout="bubble",
                            group_consecutive_messages=False,
                            buttons=["copy"],
                            allow_tags=False,
                            allow_file_downloads=False,
                            elem_id="execution-conversation",
                        )
                        execution_summary = gr.Markdown("Choose a chat above to begin.")
                    with gr.Column():
                        with gr.Tabs():
                            with gr.Tab("Steps"):
                                step_table = gr.Dataframe(
                                    headers=["Step", "UTC", "Activity"],
                                    datatype=["number", "str", "str"],
                                    type="array",
                                    interactive=False,
                                    max_height=360,
                                    label="Click a row to inspect its input and output",
                                    wrap=True,
                                )
                            with gr.Tab("Conversation graph"):
                                gr.Markdown(
                                    "Click a message to expand its path. Select any node "
                                    "to inspect what happened below. Arrows show recorded order."
                                )
                                execution_graph = gr.HTML(js_on_load=GRAPH_JS)
                        step_picker = gr.Dropdown(choices=[], visible=False)
                        step_summary = gr.Markdown("Select a step to see what happened.")
                        with gr.Tabs():
                            with gr.Tab("Input"):
                                step_input = gr.JSON(label="Input to this step")
                            with gr.Tab("Output"):
                                step_output = gr.JSON(label="Output from this step")
                            with gr.Tab("Raw event"):
                                inspection = gr.JSON(label="Complete recorded event")
                with gr.Accordion("Compare model inputs", open=False):
                    gr.Markdown(
                        "Choose two model calls from this execution to compare the exact "
                        "context sent to the model."
                    )
                    with gr.Row():
                        before = gr.Dropdown(
                            label="Earlier model input",
                            choices=[],
                            interactive=True,
                            allow_custom_value=True,
                        )
                        after = gr.Dropdown(
                            label="Later model input",
                            choices=[],
                            interactive=True,
                            allow_custom_value=True,
                        )
                    diff_button = gr.Button("Compare model inputs")
                    difference = gr.JSON(label="Context differences")
                gr.Markdown(
                    "Full histories and traces can also be downloaded from the "
                    "conversation’s evidence links. These records show observable "
                    "inputs and outputs, not hidden reasoning."
                )
            with gr.Tab("Tools", id="tools", elem_id="tools-tab") as tools_tab:
                gr.Markdown(
                    "## Tools playground\nExplore what the assistant can use. Browse the data, "
                    "inspect a tool’s inputs, then run it yourself. Your playground has its own "
                    "files and results, independent of every chat."
                )
                tools_thread = gr.Textbox(visible=False)
                with gr.Row():
                    refresh_tools = gr.Button("Refresh files & approvals", scale=0)
                with gr.Tabs():
                    with gr.Tab("Tool catalog"):
                        gr.HTML(catalog_html(service.project))
                        gr.Markdown(
                            "### Run any model tool\nChoose a tool to load its exact "
                            "input schema and an editable example. The result is returned directly."
                        )
                        selected_tool = gr.Dropdown(
                            list(EXAMPLES), value="list_records", label="Tool"
                        )
                        tool_description = gr.Markdown(tool_details("list_records")[0])
                        tool_arguments = gr.Code(
                            value=tool_details("list_records")[1],
                            language="json",
                            label="Inputs · edit before running",
                            interactive=True,
                        )
                        with gr.Accordion("Exact model-facing input schema", open=False):
                            tool_schema = gr.JSON(value=tool_details("list_records")[2])
                        run_tool_button = gr.Button("Run tool", variant="primary")
                        tool_result = gr.JSON(label="Tool result")
                    with gr.Tab("Web search"):
                        gr.Markdown(
                            "### Search the public web\nFree search with no API key. "
                            "Queries go to public search providers; use public terms. "
                            "Results include source links. Availability may vary."
                        )
                        web_query = gr.Textbox(
                            label="Search query", value="Python official documentation"
                        )
                        web_button = gr.Button("Search web", variant="primary")
                        web_results = gr.HTML()
                        with gr.Accordion("Raw search result", open=False):
                            web_result_json = gr.JSON()
                    with gr.Tab("Documents"):
                        gr.Markdown(
                            "### Search and read documents\nMock RAG ranks text matches. "
                            "Search first, choose a result and read its exact version."
                        )
                        with gr.Row():
                            document_query = gr.Textbox(
                                label="Search", placeholder="returns policy"
                            )
                            document_date = gr.Textbox(label="Effective on", value="2011-12-09")
                        catalog_button = gr.Button("Browse all accessible documents")
                        document_table = gr.Dataframe(
                            headers=[
                                "ID",
                                "Version",
                                "Title",
                                "Scope",
                                "Effective from",
                                "Effective until",
                            ],
                            type="array",
                            interactive=False,
                            max_height=340,
                            wrap=True,
                            label="RAG document library · click a row",
                        )
                        document_search_button = gr.Button("Search documents", variant="primary")
                        with gr.Accordion("Search details and sources", open=False):
                            document_results = gr.JSON(label="Matches and source excerpts")
                        document_choice = gr.Dropdown(
                            label="Document and version", choices=[], interactive=True
                        )
                        document_button = gr.Button("Read selected document")
                        document_text = gr.Markdown()
                        with gr.Accordion("Document tool details", open=False):
                            evidence = gr.JSON(label="Document content and sources")
                    with gr.Tab("Calculator"):
                        gr.Markdown(
                            "### Exact calculations\nEnter one number per line. Percentage "
                            "change uses old value, then new value."
                        )
                        calculator_operation = gr.Dropdown(
                            ["sum", "difference", "percentage_change", "available_stock"],
                            value="percentage_change",
                            label="Operation",
                        )
                        calculator_values = gr.Textbox(
                            value="10000\n7500", lines=4, label="Values | one per line"
                        )
                        calculator_button = gr.Button("Calculate", variant="primary")
                        calculator_summary = gr.Markdown()
                        with gr.Accordion("Calculation tool details", open=False):
                            calculator_result = gr.JSON(label="Calculation result")
                    with gr.Tab("Files & CSV"):
                        gr.Markdown(
                            "### Analyze a file\nRun fixed analysis directly, "
                            "or use these manual learning tools."
                        )
                        gr.Markdown(
                            "Fixed CSV analysis runs without Docker. Workspaces organize files; "
                            "they do not isolate arbitrary host code. Input: 5 MiB; output: 1 MiB; "
                            "account quota: 50 MiB including job scratch space."
                        )
                        tool_downloads = gr.HTML()
                        files_refresh = gr.Button("Refresh file library")
                        file_choice = gr.Dropdown(
                            choices=[], label="Your playground files", interactive=True
                        )
                        prepare_button = gr.Button("Prepare monthly sales CSV")
                        file_id = gr.Textbox(label="Input CSV file ID")
                        preview_button = gr.Button("Preview file content")
                        file_preview_table = gr.Dataframe(
                            headers=["Preview"],
                            type="array",
                            interactive=False,
                            visible=False,
                            max_height=340,
                            wrap=True,
                            label="CSV preview",
                        )
                        file_preview_text = gr.Textbox(
                            label="File preview", interactive=False, max_lines=18
                        )
                        with gr.Accordion("File tool response", open=False):
                            file_preview = gr.JSON(label="Raw file response")
                        with gr.Row():
                            operation_name = gr.Dropdown(
                                ["numeric_summary", "group_sum"],
                                value="group_sum",
                                label="Analysis",
                            )
                            value_column = gr.Textbox(value="sales_pence", label="Numeric column")
                            group_column = gr.Textbox(
                                value="month", label="Group column (group_sum only)"
                            )
                            deadline = gr.Number(
                                value=5, minimum=0.1, maximum=30, label="Deadline in seconds"
                            )
                        analyze_button = gr.Button("Run CSV analysis", variant="primary")
                        job_id = gr.Textbox(label="Job ID to inspect or cancel")
                        cancel_button = gr.Button("Cancel owned analysis worker")
                        cancellation = gr.JSON(label="Cancellation request")
                        tool_jobs = gr.JSON(label="Jobs — live status and result file IDs")
                        with gr.Accordion("Optional generated Python — Docker only", open=False):
                            gr.Markdown(
                                "Requires a running local Docker engine and `python:3.12-slim`. "
                                "No network; read-only CSV at `/input/data.csv`; download stdout. "
                                "Code never runs on the host. Review it before running."
                            )
                            code = gr.Code(
                                value='print("Hello from the optional container")',
                                language="python",
                                label="Python to run",
                                interactive=True,
                                wrap_lines=True,
                            )
                            gr.Markdown("Keyboard: press Esc, then Tab to leave the code editor.")
                            python_button = gr.Button("Run reviewed Python in Docker")
                    with gr.Tab("Database"):
                        gr.Markdown(
                            "### Explore company data\nBrowse permitted records or calculate "
                            "an aggregate. Queries are prepared and bounded; no model is "
                            "involved."
                        )
                        database_description = gr.Markdown()
                        with gr.Row():
                            entity = gr.Dropdown(
                                choices=["customers"],
                                value="customers",
                                label="Table / projection",
                                interactive=True,
                            )
                            record_id = gr.Textbox(label="Exact record ID (optional)")
                            query = gr.Textbox(label="Name search (supported tables)")
                        explore_button = gr.Button("Browse records", variant="primary")
                        parent_id = gr.Textbox(
                            label="Parent ID (optional)",
                            placeholder="Customer ID for orders; order ID for items",
                        )
                        database_cursor = gr.State("")
                        database_next = gr.Button("Next page", interactive=False)
                        database_note = gr.Markdown("Choose a table and select Browse records.")
                        database_table = gr.Dataframe(
                            headers=["Records"],
                            type="array",
                            interactive=False,
                            wrap=True,
                            max_height=360,
                            label="Company records",
                            buttons=["copy", "fullscreen"],
                        )
                        with gr.Accordion("Database tool details and sources", open=False):
                            explorer = gr.JSON(label="Records, page information and sources")
                        with gr.Accordion("Company aggregates", open=True):
                            report_type = gr.Dropdown(
                                ["customer_orders", "sales", "receivables"],
                                value="customer_orders",
                                label="Aggregate",
                            )
                            with gr.Row():
                                report_start = gr.Textbox(
                                    label="From (optional)", placeholder="YYYY-MM-DD"
                                )
                                report_end = gr.Textbox(
                                    label="Through (optional)", placeholder="YYYY-MM-DD"
                                )
                            aggregate_button = gr.Button("Calculate aggregate")
                            aggregate_result = gr.JSON(label="Aggregate result")
                        with gr.Accordion("Connect to SQLite from Python", open=False):
                            gr.Markdown(
                                "The local file needs no database server or Docker. This "
                                "read-only example lists all physical tables. The in-app explorer"
                                " applies selected access scopes and exposes focused projections."
                            )
                            database_code = gr.Code(
                                language="python",
                                label="Read-only connection example",
                                interactive=False,
                                wrap_lines=True,
                            )
                    with gr.Tab("Reports"):
                        gr.Markdown(
                            "### Saved reports\nBrowse reports saved by your account, "
                            "including reports created in conversations."
                        )
                        reports_button = gr.Button("Refresh reports")
                        reports_choice = gr.Dropdown(
                            choices=[], label="Saved report", interactive=True
                        )
                        report_text = gr.Markdown()
                    with gr.Tab("Review changes"):
                        gr.Markdown(
                            "### Review proposed changes\nReport saves and ticket changes wait"
                            " here for your approval. Review the arguments, edit if needed, "
                            "then approve or reject. The server rechecks your permissions."
                        )
                        review_pending = gr.Dropdown(
                            label="Pending operation",
                            choices=[],
                            interactive=True,
                            allow_custom_value=True,
                        )
                        arguments = gr.Code(
                            value="{}",
                            language="json",
                            label="Editable operation arguments",
                            interactive=True,
                            wrap_lines=True,
                        )
                        with gr.Row():
                            approve = gr.Button("Approve edited arguments", variant="primary")
                            reject = gr.Button("Reject")
                        decision_result = gr.JSON(label="Saved decision")
                        with gr.Accordion("Create a proposal directly", open=False):
                            gr.Markdown(
                                "Choose a tool and edit its arguments. Source references must be "
                                "valid and accessible. This creates a pending operation; it does "
                                "not approve the change."
                            )
                            proposal_tool = gr.Dropdown(
                                ["save_report", "update_ticket"],
                                value="save_report",
                                label="Proposal tool",
                            )
                            proposal_arguments = gr.Code(
                                value=json.dumps(
                                    {
                                        "title": "My report",
                                        "body": "Draft report for review.",
                                        "sources": [
                                            {
                                                "kind": "document",
                                                "id": "POL-METRICS-001",
                                                "version": 1,
                                            }
                                        ],
                                    },
                                    indent=2,
                                ),
                                language="json",
                                label="Tool arguments",
                                interactive=True,
                                wrap_lines=True,
                            )
                            proposal_button = gr.Button("Create pending proposal")
                            proposal_result = gr.JSON(label="Proposal result")
        outputs = [chat, status, timeline, downloads, jobs, pending, runs_panel, sources]
        meta_outputs = [history, mode, mode_hint]
        nav_outputs = [company_tools_group, available_tools, execution_thread]
        blocks.load(load, outputs=[identity, threads, submission]).then(
            metadata, inputs=[threads], outputs=meta_outputs
        ).then(navigation, inputs=[threads], outputs=nav_outputs)
        blocks.load(
            database_help, outputs=[entity, database_description, database_code, settings_text]
        )
        mode.input(change_mode, [threads, mode], [threads, *meta_outputs])
        history.navigate(history_action, outputs=[threads, *meta_outputs], show_progress="hidden")
        threads.change(
            choose,
            [threads],
            outputs,
            concurrency_id="view",
            concurrency_limit=1,
            show_progress="hidden",
        ).then(metadata, inputs=[threads], outputs=meta_outputs, show_progress="hidden").then(
            navigation, inputs=[threads], outputs=nav_outputs, show_progress="hidden"
        )
        timer = gr.Timer(0.75)
        timer.tick(
            view_poll,
            [threads],
            outputs + [resume_button, chat_review_group],
            concurrency_id="view",
            concurrency_limit=1,
            show_progress="hidden",
        )
        refresh_rate.change(lambda value: gr.Timer(value), [refresh_rate], [timer])
        for button, action in [(create, "create"), (rename, "rename"), (archive, "archive")]:
            button.click(threads_action, [gr.State(action), threads, title], threads)
        for trigger in [send_button.click, message.submit]:
            trigger(
                send,
                [threads, message, submission],
                [message, submission, status, threads, chat],
                concurrency_id="view",
                concurrency_limit=1,
                show_progress="hidden",
            ).then(metadata, inputs=[threads], outputs=meta_outputs, show_progress="hidden")
        resume_button.click(resume, [threads], status)
        pending.input(operation, [threads, pending], chat_arguments)
        for button, choice in [(chat_approve, "approve"), (chat_reject, "reject")]:
            button.click(
                decision, [threads, pending, gr.State(choice), chat_arguments], chat_decision
            )
        refresh_execution_button.click(navigation, [threads], nav_outputs)
        execution_thread.change(
            refresh_execution, [execution_thread], [run_picker, execution_chat, execution_summary]
        )
        filter_inputs = [
            execution_search,
            execution_mode,
            execution_period,
            execution_start,
            execution_end,
            execution_thread,
        ]
        for trigger in [
            executions_tab.select,
            filter_button.click,
            execution_search.submit,
            execution_mode.input,
            execution_period.input,
        ]:
            trigger(search_chats, filter_inputs, execution_thread, show_progress="hidden")
        run_picker.change(
            select_execution,
            [execution_thread, run_picker],
            [step_table, step_picker, execution_summary, before, after, execution_graph],
            show_progress="hidden",
        )
        step_picker.change(
            select_step,
            [execution_thread, run_picker, step_picker],
            [step_summary, step_input, step_output, inspection],
            show_progress="hidden",
        )
        execution_chat.select(
            select_message, [execution_thread], run_picker, show_progress="hidden"
        )
        execution_graph.pick(
            graph_pick,
            [execution_thread, run_picker],
            [run_picker, step_picker],
            show_progress="hidden",
        )
        step_table.select(select_timeline, [execution_thread, run_picker], step_picker)
        diff_button.click(diff, [execution_thread, before, after], difference)
        tools_tab.select(new_tools_workspace, outputs=tools_thread, show_progress="hidden").then(
            load_documents, tools_thread, [document_table, document_choice], show_progress="hidden"
        ).then(load_reports, outputs=reports_choice, show_progress="hidden").then(
            refresh_files, [tools_thread, file_choice], file_choice, show_progress="hidden"
        )
        selected_tool.input(
            tool_details, selected_tool, [tool_description, tool_arguments, tool_schema]
        )
        run_tool_button.click(direct, [tools_thread, selected_tool, tool_arguments], tool_result)
        web_button.click(web_lookup, [tools_thread, web_query], [web_results, web_result_json])
        web_query.submit(web_lookup, [tools_thread, web_query], [web_results, web_result_json])
        catalog_button.click(load_documents, tools_thread, [document_table, document_choice])
        document_table.select(pick_document, tools_thread, document_choice).then(
            read_selected_document, [tools_thread, document_choice], [document_text, evidence]
        )
        reports_button.click(load_reports, outputs=reports_choice)
        reports_choice.change(view_report, reports_choice, report_text)
        file_preview_outputs = [file_preview_table, file_preview_text, file_preview]
        preview_button.click(preview_file, [tools_thread, file_id], file_preview_outputs)
        files_refresh.click(refresh_files, [tools_thread, file_choice], file_choice)
        file_choice.input(lambda selected: selected or "", file_choice, file_id).then(
            preview_file, [tools_thread, file_id], file_preview_outputs
        )
        tools_thread.change(tool_poll, [tools_thread], [tool_downloads, tool_jobs, review_pending])
        refresh_tools.click(tool_poll, [tools_thread], [tool_downloads, tool_jobs, review_pending])
        tools_timer = gr.Timer(1.5)
        tools_timer.tick(
            tool_poll,
            [tools_thread],
            [tool_downloads, tool_jobs, review_pending],
            show_progress="hidden",
            concurrency_id="tools-view",
            concurrency_limit=1,
        )
        review_pending.input(operation, [tools_thread, review_pending], arguments)
        for button, choice in [(approve, "approve"), (reject, "reject")]:
            button.click(
                decision,
                [tools_thread, review_pending, gr.State(choice), arguments],
                decision_result,
            ).then(tool_poll, [tools_thread], [tool_downloads, tool_jobs, review_pending])
        proposal_button.click(
            direct, [tools_thread, proposal_tool, proposal_arguments], proposal_result
        ).then(tool_poll, [tools_thread], [tool_downloads, tool_jobs, review_pending])
        calculator_button.click(
            calculate,
            [tools_thread, calculator_operation, calculator_values],
            [calculator_summary, calculator_result],
        )
        document_search_button.click(
            search_documents,
            [tools_thread, document_query, document_date],
            [document_results, document_choice],
        )
        document_button.click(
            read_selected_document, [tools_thread, document_choice], [document_text, evidence]
        )
        prepare_button.click(prepare, [tools_thread], file_id).then(
            tool_poll, [tools_thread], [tool_downloads, tool_jobs, review_pending]
        ).then(refresh_files, [tools_thread, file_id], file_choice)
        analyze_button.click(
            analyze,
            [tools_thread, file_id, operation_name, value_column, group_column, deadline],
            job_id,
        )
        cancel_button.click(cancel, [tools_thread, job_id], cancellation)
        python_button.click(python, [tools_thread, code, file_id, deadline], job_id)
        browse_outputs = [database_table, database_note, explorer, database_cursor, database_next]
        explore_button.click(
            browse,
            [tools_thread, entity, record_id, query, parent_id, gr.State("")],
            browse_outputs,
        )
        database_next.click(
            browse,
            [tools_thread, entity, record_id, query, parent_id, database_cursor],
            browse_outputs,
        )
        aggregate_button.click(
            aggregate, [tools_thread, report_type, report_start, report_end], aggregate_result
        )
        blocks.load(poll, [threads], outputs, api_name="poll")
        blocks.queue(default_concurrency_limit=4, max_size=40)
    return blocks
