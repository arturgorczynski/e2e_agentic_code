"""Plain descriptions for tool discovery and direct, authenticated learning exercises."""

import html
import json

from pydantic import Field, ValidationError

from acme.app_store import authenticate
from acme.company_tools import accessible_documents, execute, read_report
from acme.dataset import connect
from acme.memory_tools import open_memory, recall, remember
from acme.middleware import configuration
from acme.tool_schemas import INPUTS, Arguments
from acme.web_search import WebSearchInput, search_web
from acme.workspace_tools import WorkspaceInput, workspace_action


class RememberNoteInput(Arguments):
    topic: str = Field(min_length=2, max_length=40)
    note: str = Field(min_length=3, max_length=500)


class RecallNotesInput(Arguments):
    topic: str | None = Field(default=None, max_length=40)
    limit: int = Field(default=10, ge=1, le=20)


TOOL_SCHEMAS = {
    **INPUTS,
    "analyze_workspace": WorkspaceInput,
    "web_search": WebSearchInput,
    "remember_note": RememberNoteInput,
    "recall_notes": RecallNotesInput,
}

TOOLS = [
    (
        "web_search",
        "Search the web",
        "Free public web search: titles, links and snippets. No API key.",
    ),
    (
        "lookup_record",
        "Look up a record",
        "Read one customer, order, invoice or other permitted record by ID.",
    ),
    (
        "list_records",
        "Browse company data",
        "Read a bounded page. Filter by parent, status, supported name search "
        "or an exact stock-movement link.",
    ),
    (
        "business_summary",
        "Calculate company totals",
        "Sales, receivables, forecasts or the customers with the most orders.",
    ),
    (
        "cash_activity",
        "Trace billing and cash",
        "Compare dated invoice postings, customer receipts and fictional 2026 expenses.",
    ),
    (
        "search_documents",
        "Search documents",
        "Mock RAG text search with document IDs, versions and excerpts.",
    ),
    (
        "list_document_versions",
        "List document versions",
        "Show the permitted revision history and effective dates for one document ID.",
    ),
    (
        "read_document",
        "Read a document",
        "Read a specific policy or guide version with source evidence.",
    ),
    (
        "run_analysis",
        "Calculator",
        "Exact sums, differences, percentage changes and available stock.",
    ),
    (
        "save_report",
        "Propose a report",
        "Draft a report with verified sources. Saving requires your approval.",
    ),
    (
        "update_ticket",
        "Propose a ticket change",
        "Move an open case to in progress after your review and approval.",
    ),
    (
        "simulate_delete",
        "Simulate a deletion",
        "Superuser-only approval exercise. Records the target; never deletes data or files.",
    ),
    (
        "analyze_workspace",
        "Files and CSV",
        "Prepare sales data, run bounded CSV analysis and read downloadable results.",
    ),
    (
        "remember_note",
        "Remember a preference",
        "Save one explicitly requested, non-sensitive preference for this demo persona.",
    ),
    (
        "recall_notes",
        "Recall preferences",
        "Read this persona's notes across conversations from local SQLite memory.",
    ),
]

EXAMPLES = {
    "lookup_record": {"entity": "customers", "record_id": "DEMO-CUST-001"},
    "list_records": {"entity": "customers", "limit": 10},
    "business_summary": {"report": "customer_orders"},
    "cash_activity": {
        "start_date": "2026-01-01", "end_date": "2026-10-22", "cohort": "contemporary"
    },
    "search_documents": {"query": "returns", "effective_on": "2011-12-09"},
    "list_document_versions": {"document_id": "POL-RETURNS-001"},
    "read_document": {"document_id": "POL-METRICS-001", "version": 1, "max_chars": 6000},
    "run_analysis": {"operation": "percentage_change", "values": ["10000", "7500"]},
    "save_report": {
        "title": "Learning report",
        "body": "Draft based on the metrics policy.",
        "sources": [{"kind": "document", "id": "POL-METRICS-001", "version": 1}],
    },
    "update_ticket": {
        "ticket_id": "DEMO-TKT-004",
        "expected_status": "open",
        "new_status": "in_progress",
        "reason": "Reviewing this case",
    },
    "simulate_delete": {
        "target_kind": "record",
        "entity": "customers",
        "record_id": "DEMO-CUST-001",
        "reason": "Training exercise: preview deletion impact only",
    },
    "analyze_workspace": {"action": "list"},
    "remember_note": {"topic": "answer style", "note": "Prefer concise bullet points"},
    "recall_notes": {"topic": "answer style"},
    "web_search": {"query": "Python official documentation", "max_results": 5},
}

DETAILS = {
    "web_search": (
        "Search public pages and return titles, URLs and snippets. Use public terms only; "
        "never send Acme customer records or credentials in a query."
    ),
    "lookup_record": (
        "Read one permitted SQLite record by exact ID. The result includes its fields "
        "and a query event; an unknown ID returns found=false. Purchase orders "
        "include provenance and whole-order receipt totals."
    ),
    "list_records": (
        "Read a bounded, stable page of permitted company rows. Supported parent, "
        "customer, status and text filters depend on the entity. For stock_movements, "
        "goods_receipt_id or shipment_item_id finds the exact linked movement. "
        "Follow next_cursor for longer pages."
    ),
    "business_summary": (
        "Calculate sales, receivables, forecast accuracy or top customers by order count. "
        "Forecast error stays null until its target period is complete."
    ),
    "cash_activity": (
        "Read fixed, parameterized finance queries for a selected date range and cohort. "
        "The authored expense ledger is incomplete; cash difference is not profit."
    ),
    "search_documents": (
        "Find authorized Markdown versions by deterministic text matching. Search "
        "can require an exact record-ID mention in the body. Results are excerpts; "
        "open an exact version to read its full body."
    ),
    "list_document_versions": (
        "List authorized revision metadata for one exact document ID in version order. "
        "This does not read document text; use read_document for wording."
    ),
    "read_document": (
        "Read one authorized document ID and version in bounded character pages. "
        "The result names the version and whether more text remains."
    ),
    "run_analysis": (
        "Perform bounded decimal arithmetic: sum, difference, percentage change or "
        "available stock. It does not run generated code."
    ),
    "save_report": (
        "Propose a report with verified record, document or query sources. A separate "
        "human decision is required before the report is saved."
    ),
    "update_ticket": (
        "Propose moving an open support ticket to in_progress with a reason. "
        "The ticket changes only after a separate human decision."
    ),
    "simulate_delete": (
        "Create a superuser-only training proposal for one record or document version. "
        "Even approval records only a simulation; nothing is deleted."
    ),
    "analyze_workspace": (
        "Prepare a private sales CSV or run bounded numeric analysis on an owned file. "
        "Use returned file and job IDs to follow the calculation."
    ),
    "remember_note": (
        "Store one explicitly requested, non-sensitive preference for the selected "
        "demo persona. Current business facts belong in company tools instead."
    ),
    "recall_notes": (
        "Read saved preferences of the selected demo persona. An optional topic "
        "narrows the result; it cannot read another persona's notes."
    ),
}


def tool_details(name):
    return (
        DETAILS[name],
        json.dumps(EXAMPLES[name], indent=2),
        TOOL_SCHEMAS[name].model_json_schema(),
    )


def catalog_html(project):
    preset = configuration(project)
    cards = []
    for name, title, description in TOOLS:
        availability = "Free + Company" if name == "web_search" else "Company"
        if preset["tool_selection"] == "read_only" and name in {
            "save_report",
            "update_ticket",
            "simulate_delete",
            "analyze_workspace",
        }:
            availability = "Not offered by the current read-only model preset"
        cards.append(
            f'<article class="tool-card"><h3>{html.escape(title)}</h3>'
            f"<code>{name}</code><p>{html.escape(description)}</p>"
            f"<small>{availability} · access scopes apply</small></article>"
        )
    return '<div class="tool-catalog">' + "".join(cards) + "</div>"


def run_tool(context, name, arguments):
    if name in {"remember_note", "recall_notes"}:
        try:
            validated = TOOL_SCHEMAS[name].model_validate(arguments).model_dump()
        except ValidationError as exc:
            issues = [
                f"{'.'.join(map(str, issue['loc']))}: {issue['msg']}"
                for issue in exc.errors()
            ]
            return {
                "status": "error",
                "error": {"code": "invalid_arguments", "message": "; ".join(issues)},
            }
        with open_memory(context.state) as store:
            try:
                if name == "remember_note":
                    return remember(context, store, **validated)
                return recall(context, store, **validated)
            except ValueError as exc:
                return {
                    "status": "error",
                    "error": {"code": "invalid_arguments", "message": str(exc)},
                }
    if name == "analyze_workspace":
        return workspace_action(context, arguments)
    if name == "web_search":
        return search_web(context, arguments)
    return execute(context, name, arguments)


def document_catalog(context):
    documents = accessible_documents(context)
    rows = [
        [
            d["document_id"],
            d["version"],
            d["title"],
            d["access_scope"],
            d["effective_from"],
            d.get("effective_until") or "Current",
        ]
        for d in documents
    ]
    choices = [
        (f"{d['title']} · v{d['version']}", json.dumps([d["document_id"], d["version"]]))
        for d in documents
    ]
    return rows, choices


def report_catalog(service, token):
    actor = authenticate(service.project, service.state, token)
    db = connect(service.state / "app.sqlite", readonly=True)
    try:
        rows = db.execute(
            "SELECT id,thread_id,title,created_at FROM reports WHERE owner_id=? "
            "ORDER BY created_at DESC LIMIT 100",
            (actor["id"],),
        ).fetchall()
        return [
            (f"{r['title']} · {r['created_at'][:10]}", json.dumps([r["thread_id"], r["id"]]))
            for r in rows
        ]
    finally:
        db.close()


def saved_report(service, token, selected):
    if not selected:
        return "No saved report selected. Create and approve a report to see it here."
    thread, identifier = json.loads(selected)
    report = read_report(service.context(token, thread), identifier)
    return f"## {report['title']}\n\n{report['body']}"


def sidebar_tools(project, state, token):
    actor = authenticate(project, state, token)
    preset = configuration(project)
    read_only = preset["tool_selection"] == "read_only"
    lines = [
        "### Company tools",
        "Open **Tools** to try these directly. Data access follows your selected scopes.",
    ]
    for name, title, description in TOOLS:
        if read_only and name in {
            "save_report",
            "update_ticket",
            "simulate_delete",
            "analyze_workspace",
        }:
            continue
        if name == "analyze_workspace" and "analytics.read" not in actor["permissions"]:
            continue
        if name == "update_ticket" and "support.update" not in actor["permissions"]:
            continue
        lines.append(f"**{title}** (`{name}`)  \n{description}")
    return "\n\n".join(lines)
