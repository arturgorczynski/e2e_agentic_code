"""Local authenticated HTTP boundary and private evidence/download routes."""

import html
import json
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from acme.analysis import MAX_INPUT
from acme.app_store import (
    AccessDenied,
    authenticate,
    local_accounts,
    login,
    profile_options,
    provision,
    read_transcript,
    scope_options,
)
from acme.company_tools import execute, read_report
from acme.jobs import read_file, register_file
from acme.trace_view import all_events
from acme.ui import CSS, build_ui
from acme.ui_service import LearningService

PAGE_STYLE = """<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font:15px/1.6 system-ui;background:#f4f7f6;color:#243432;margin:0;padding:24px}
main{max-width:440px;margin:10vh auto;padding:40px;background:white;border-radius:22px;
box-shadow:0 12px 60px #16352c09;border:1px solid #e3ebe7}
h1{font-size:28px;letter-spacing:-.03em;margin:0 0 12px}p{color:#637570}
label{display:block;margin:20px 0 7px;font-size:13px;font-weight:600}
input,button{font:inherit;padding:12px;box-sizing:border-box}
input,select{width:100%;border:1px solid #cfddd7;border-radius:10px;background:#fbfdfc;
font:inherit;padding:12px;box-sizing:border-box}
details{margin-top:28px;border-top:1px solid #e3ebe7;padding-top:20px}
summary{cursor:pointer;font-weight:600}small{display:block;color:#637570;margin-top:8px}
button{margin-top:24px;background:#0f766e;color:white;border:0;border-radius:10px;
width:100%;cursor:pointer}fieldset{border:1px solid #cfddd7;border-radius:10px;padding:12px}
legend{font-size:13px;font-weight:600}.scope{display:flex;gap:8px;align-items:flex-start;
margin:10px 0}.scope input{width:auto;margin-top:4px}.scope small{margin:0}
input:focus-visible,button:focus-visible{outline:2px solid #0d9488;
outline-offset:3px}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#0f766e}
@media(max-width:540px){body{padding:16px}main{padding:26px;margin:5vh auto}}</style>"""


def page(title, body, status=200):
    return HTMLResponse(
        f"<!doctype html><html lang='en'><head><title>{html.escape(title)}</title>"
        f"{PAGE_STYLE}</head><body><main><h1>{html.escape(title)}</h1>{body}</main>"
        "</body></html>",
        status_code=status,
    )


def create_web_app(project, state, data, gr=None):
    service = LearningService(project, state, data)
    session_owners, event_owners = {}, {}

    @asynccontextmanager
    async def lifespan(app):
        service.start()
        try:
            yield
        finally:
            service.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.learning = service
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    def token(request):
        return request.cookies.get("acme_session", "")

    def identity(request):
        return authenticate(project, state, token(request))

    def auth_dependency(request: Request):
        try:
            return identity(request)["username"]
        except AccessDenied:
            return None

    @app.middleware("http")
    async def boundary(request, call_next):
        path = request.url.path
        api = path.startswith("/app/gradio_api/")
        actor = None
        payload = {}
        if api:
            try:
                actor = identity(request)["id"]
            except AccessDenied:
                return JSONResponse({"error": "Sign in required"}, status_code=403)
            # All downloads use our owned routes. These generic Gradio routes are unnecessary.
            suffix = path.removeprefix("/app/gradio_api/")
            if suffix.startswith(("file", "upload", "stream", "call/v2", "mcp")):
                return JSONResponse({"error": "Use the owned workspace routes"}, status_code=403)
        # Browser forms and Gradio mutating requests must come from this exact local origin.
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin", "")
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if origin != expected:
                return JSONResponse(
                    {"error": "Same-origin browser request required"}, status_code=403
                )
            # Bound streamed/chunked uploads before the multipart parser writes its temp file.
            body, total = [], 0
            limit = MAX_INPUT + 65536 if request.url.path.startswith("/uploads/") else 262144
            async for chunk in request.stream():
                total += len(chunk)
                if total > limit:
                    return JSONResponse(
                        {"error": "Request exceeds its size limit"}, status_code=413
                    )
                body.append(chunk)
            # Starlette's cached request replays this bounded body to the route parser.
            request._body = b"".join(body)
            if api and "application/json" in request.headers.get("content-type", ""):
                try:
                    payload = json.loads(request._body)
                except (ValueError, TypeError):
                    return JSONResponse({"error": "Invalid JSON request"}, status_code=400)
                if not isinstance(payload, dict):
                    return JSONResponse({"error": "Expected a JSON object"}, status_code=400)
                if suffix.startswith("call/") or suffix == "queue/join":
                    payload.setdefault("session_hash", uuid4().hex)
                    request._body = json.dumps(payload).encode()
        if api:
            session_hash = payload.get("session_hash") or request.query_params.get("session_hash")
            if suffix.startswith("heartbeat/"):
                session_hash = suffix.split("/", 1)[1]
            if session_hash:
                if not isinstance(session_hash, str) or len(session_hash) > 100:
                    return JSONResponse({"error": "Invalid UI session"}, status_code=400)
                owner = session_owners.setdefault(session_hash, actor)
                if owner != actor:
                    return JSONResponse({"error": "UI session unavailable"}, status_code=403)
            event_id = payload.get("event_id")
            if request.method == "GET" and suffix.startswith("call/"):
                event_id = suffix.rstrip("/").split("/")[-1]
            if event_id and event_owners.get(event_id) != actor:
                return JSONResponse({"error": "UI event unavailable"}, status_code=403)
        if request.url.path in {"/app", "/app/"} and not auth_dependency(request):
            return RedirectResponse("/login", status_code=303)
        response = await call_next(request)
        if (
            api
            and request.method == "POST"
            and response.status_code == 200
            and (suffix.startswith("call/") or suffix == "queue/join")
        ):
            content = b"".join([chunk async for chunk in response.body_iterator])
            event_id = json.loads(content).get("event_id")
            if event_id:
                event_owners[event_id] = actor
            response = Response(
                content, status_code=response.status_code, headers=dict(response.headers)
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(AccessDenied)
    async def denied(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=403)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)[:500]}, status_code=400)

    @app.get("/")
    async def index(request: Request):
        return RedirectResponse("/app/" if auth_dependency(request) else "/login", status_code=303)

    @app.get("/login")
    async def login_page():
        accounts = local_accounts(state)
        profiles = profile_options()
        scopes = scope_options()
        options = "".join(
            f'<option value="{html.escape(row["username"], quote=True)}">'
            f"{html.escape(row['display_name'])} · "
            f"{html.escape(profiles.get(row['access_profile'], {'label': 'Custom'})['label'])}"
            "</option>"
            for row in accounts
        )
        profile_choices = "".join(
            f'<option value="{name}">{html.escape(profile["label"])} — '
            f"{html.escape(profile['description'])}</option>"
            for name, profile in profiles.items()
        )
        profile_explainer = "".join(
            f"<li><strong>{html.escape(profile['label'])}</strong>: "
            f"{html.escape(profile['description'])}</li>"
            for profile in profiles.values()
        )
        scope_choices = "".join(
            f"<label class='scope'><input type='checkbox' name='scope' "
            f"value='{html.escape(name, quote=True)}'><span><strong>"
            f"{html.escape(scope['label'])}</strong><small>"
            f"{html.escape(scope['description'])}</small></span></label>"
            for name, scope in scopes.items()
        )
        existing = (
            (
                "<form method='post' action='/login'>"
                "<label for='username'>Choose your local profile</label><select "
                "id='username' name='username' required>" + options + "</select>"
                "<button type='submit'>Continue</button></form>"
            )
            if accounts
            else "<p>Create your first local user below.</p>"
        )
        return page(
            "Choose your space",
            "<p>Pick a local profile or create one to start chatting.</p>"
            + existing
            + ("<details><summary>Create a new user</summary>" if accounts else "<section>")
            + "<form method='post' action='/users'>"
            "<label for='display-name'>Your name</label><input "
            "id='display-name' name='display_name' "
            "autocomplete='name' required maxlength='80'>"
            "<label for='new-username'>Username</label><input id='new-username' name='username' "
            "autocomplete='username' pattern='[a-z0-9][a-z0-9._-]{2,49}' required maxlength='50'>"
            "<small>3–50 lowercase letters, numbers, dots, underscores or hyphens.</small>"
            "<label for='access-profile'>Access profile</label><select id='access-profile' "
            "name='access_profile'>"
            + profile_choices
            + "<option value='custom'>Custom scope — choose the scopes below</option>"
            + "</select>"
            "<small>Predefined profiles set their scopes automatically. Choose Custom scope "
            "to define a new combination.</small>"
            "<fieldset><legend>Custom scopes</legend>" + scope_choices + "</fieldset>"
            "<details><summary>What do these profiles and scopes mean?</summary>"
            "<p><strong>Profile</strong> is a ready-to-use set of permissions. "
            "<strong>Scope</strong> is a concrete group of tools and data. Custom scope "
            "uses only the boxes selected above. Every write is still an approval proposal, "
            "and every chat remains private to its local profile.</p>"
            "<ul>" + profile_explainer + "</ul>"
            "<p>This is a local learning app, not a shared-login security boundary: anyone "
            "with access to this computer can select a local profile.</p></details>"
            "<button type='submit'>Create user and open chat</button></form>"
            + ("</details>" if accounts else "</section>"),
        )

    def signed_in(session):
        response = RedirectResponse("/app/", status_code=303)
        response.set_cookie(
            "acme_session", session, httponly=True, samesite="strict", max_age=28800, path="/"
        )
        return response

    @app.post("/users")
    async def create_user(request: Request):
        form = await request.form(max_fields=16, max_files=0, max_part_size=2048)
        values = {
            key: str(form.get(key, "")) for key in ("username", "display_name", "access_profile")
        }
        try:
            provision(
                project,
                state,
                values["username"],
                display_name=values["display_name"],
                access_profile=values["access_profile"],
                scopes=[str(item) for item in form.getlist("scope")],
            )
        except ValueError as exc:
            return page(
                "Create user",
                f"<p>{html.escape(str(exc))}</p><a href='/login'>Back to user selection</a>",
                400,
            )
        return signed_in(login(state, values["username"]))

    @app.post("/login")
    async def login_post(request: Request):
        form = await request.form(max_fields=2, max_files=0, max_part_size=2048)
        username = str(form.get("username", ""))
        if len(username) > 100:
            raise ValueError("Invalid profile name length")
        try:
            session = login(state, username)
        except AccessDenied:
            return page(
                "Profile unavailable",
                "<p>Choose an available local profile.</p><a href='/login'>Try again</a>",
                403,
            )
        response = RedirectResponse("/app/", status_code=303)
        response.set_cookie(
            "acme_session",
            session,
            httponly=True,
            samesite="strict",
            max_age=28800,
            secure=request.url.scheme == "https",
            path="/",
        )
        return response

    @app.post("/logout")
    async def logout(request: Request):
        service.logout(token(request))
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("acme_session", path="/")
        return response

    @app.post("/chats/{thread_id}/{action}")
    async def chat_action(thread_id: str, action: str, request: Request):
        try:
            if action == "select":
                service.select(token(request), thread_id)
            elif action == "rename":
                form = await request.form(max_fields=1, max_files=0, max_part_size=2048)
                service.edit_thread(token(request), thread_id, str(form.get("title", "")))
            elif action == "delete":
                service.edit_thread(token(request), thread_id, archive=True)
            elif action == "restore":
                service.restore_thread(token(request), thread_id)
            else:
                raise ValueError("Unknown chat action")
        except ValueError as exc:
            return page(
                "Chat unchanged",
                f"<p>{html.escape(str(exc))}</p><a href='/app/'>Back to chat</a>",
                400,
            )
        return RedirectResponse("/app/", status_code=303)

    @app.get("/artifacts/{thread_id}/{file_id}")
    async def artifact(thread_id: str, file_id: str, request: Request):
        record, content = read_file(service.context(token(request), thread_id), file_id)
        return Response(
            content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{record["name"]}"',
            },
        )

    @app.get("/trace/{thread_id}")
    async def trace(thread_id: str, request: Request):
        events = list(all_events(project, state, token(request), thread_id))
        return Response(
            json.dumps(events, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="trace.json"'},
        )

    @app.get("/reports/{thread_id}/{report_id}")
    async def report(thread_id: str, report_id: str, request: Request):
        row = read_report(service.context(token(request), thread_id), report_id)
        text = "# " + row["title"] + "\n\n" + row["body"] + "\n\nSources:\n" + row["sources_json"]
        return Response(
            text,
            media_type="text/markdown",
            headers={
                "Content-Disposition": 'attachment; filename="approved-report.md"',
            },
        )

    @app.get("/transcript/{thread_id}")
    async def transcript(thread_id: str, request: Request):
        rows, after = [], 0
        while True:
            batch = read_transcript(project, state, token(request), thread_id, after)
            rows.extend(batch)
            if len(batch) < 100:
                break
            after = batch[-1]["seq"]
        return Response(
            json.dumps(rows, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="conversation.json"'},
        )

    @app.get("/evidence/{thread_id}/{entity}/{record_id}")
    async def evidence(
        thread_id: str, entity: str, record_id: str, request: Request, version: int = 1
    ):
        context = service.context(token(request), thread_id)
        result = execute(
            context,
            "read_document" if entity == "documents" else "lookup_record",
            {"document_id": record_id, "version": version, "max_chars": 6000}
            if entity == "documents"
            else {"entity": entity, "record_id": record_id},
        )
        return page(
            "Company evidence", "<pre>" + html.escape(json.dumps(result, indent=2)) + "</pre>"
        )

    @app.get("/uploads/{thread_id}")
    async def upload_page(thread_id: str, request: Request):
        service.context(token(request), thread_id)
        return page(
            "Upload a CSV",
            "<p>UTF-8, comma-separated, up to 5 MiB and 50,000 data rows. "
            "Stored filename: input.csv. The analysis worker validates its contents.</p>"
            f"<form method='post' enctype='multipart/form-data' action='/uploads/{thread_id}'>"
            "<label for='csv'>CSV file</label>"
            "<input id='csv' type='file' name='csv' accept='.csv' required>"
            "<button type='submit'>Upload to this conversation</button></form>",
        )

    @app.post("/uploads/{thread_id}")
    async def upload(thread_id: str, request: Request):
        context = service.context(token(request), thread_id)
        form = await request.form(max_files=1, max_fields=0, max_part_size=MAX_INPUT)
        file = form.get("csv")
        if not file or not hasattr(file, "read"):
            raise ValueError("Choose a CSV file")
        try:
            content = await file.read(MAX_INPUT + 1)
            identifier = register_file(
                context, "input.csv", content, source={"origin": "user_upload"}
            )
        finally:
            await file.close()
        return page(
            "CSV uploaded",
            f"<p>File ID: <code>{identifier}</code></p>"
            "<p>Return to Tools → Files &amp; CSV and select Refresh file library. "
            "Choose your upload to preview or analyze it.</p>"
            "<a href='/app/'>Return to Acme</a>",
        )

    if gr is not None:
        blocks = build_ui(gr, service)
        app = gr.mount_gradio_app(
            app,
            blocks,
            path="/app",
            auth_dependency=auth_dependency,
            allowed_paths=[],
            blocked_paths=[str(project), str(state), str(data)],
            max_file_size=MAX_INPUT,
            show_error=False,
            footer_links=[],
            enable_monitoring=False,
            mcp_server=False,
            css=CSS,
            theme=gr.themes.Soft(primary_hue="teal", neutral_hue="slate"),
        )
    return app
