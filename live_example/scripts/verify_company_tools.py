"""Exercise all eight tools against the full baseline, without a model or network."""

import argparse
import json
import tempfile
from pathlib import Path
from time import perf_counter

from acme.app_store import RunContext, login, new_thread, provision
from acme.company_queries import QUERIES
from acme.company_tools import decide, execute, read_report
from acme.dataset import connect, initialize_state
from acme.source_data import write_json
from acme.tool_schemas import INPUTS, ToolResult


def verify(root, state):
    initialize_state(root, state)
    users = {
        "commercial.read": "alex.sales",
        "finance.read": "morgan.finance",
        "analytics.read": "taylor.analyst",
        "operations.read": "jamie.operations",
        "support.read": "sam.support",
    }
    contexts = {}
    for permission, username in users.items():
        provision(root, state, username, "isolated-validation-password")
        token = login(state, username, "isolated-validation-password")
        thread = new_thread(root, state, token, "Direct full-dataset verification")
        contexts[permission] = RunContext(root, state, root / "data", token, thread, "full-check")
    measurements = []
    entities = {}

    def call(permission, name, arguments, expected="ok"):
        start = perf_counter()
        response = execute(contexts[permission], name, arguments)
        elapsed = perf_counter() - start
        ToolResult.model_validate(response)
        assert response["status"] == expected, (name, response)
        size = len(json.dumps(response).encode())
        assert size <= 48000
        measurements.append({"tool": name, "seconds": round(elapsed, 4), "bytes": size})
        return response

    for entity, (permission, *_) in QUERIES.items():
        page = call(permission, "list_records", {"entity": entity, "limit": 50})
        assert 1 <= len(page["records"]) <= 50
        first = page["records"][0]
        found = call(permission, "lookup_record", {"entity": entity, "record_id": first["id"]})
        assert found["records"][0]["id"] == first["id"]
        entities[entity] = page["page"]["total"]
        if page["page"]["has_more"]:
            next_page = call(
                permission,
                "list_records",
                {"entity": entity, "after": page["page"]["next_cursor"], "limit": 50},
            )
            assert not {r["id"] for r in page["records"]} & {r["id"] for r in next_page["records"]}
    assert entities["orders"] >= 10000 and entities["order_items"] >= 100000
    filtered = call(
        "commercial.read", "list_records", {"entity": "orders", "parent_id": "DEMO-CUST-005"}
    )
    assert filtered["page"]["total"] == 2
    call("commercial.read", "list_records", {"entity": "orders", "limit": 51}, "error")
    call(
        "commercial.read",
        "lookup_record",
        {"entity": "orders", "record_id": "' OR 1=1 --"},
        "empty",
    )
    denied = call(
        "commercial.read",
        "lookup_record",
        {"entity": "invoices", "record_id": "DEMO-INV-001"},
        "error",
    )
    assert denied["error"]["code"] == "access_denied"
    sales = call(
        "analytics.read",
        "business_summary",
        {"report": "sales", "start_date": "2010-12-01", "end_date": "2011-12-09"},
    )
    assert sales["records"] == [] and sales["facts"]["invoice_count"] >= 10000
    db = connect(state / "company.sqlite", readonly=True)
    try:
        # Independent reconciliation: two totals, not the tool's correlated SQL.
        gross = db.execute("SELECT SUM(total_pence) FROM invoices").fetchone()[0]
        credits = db.execute("SELECT SUM(amount_pence) FROM credit_notes").fetchone()[0]
    finally:
        db.close()
    assert sales["facts"]["sales_pence"] == gross - credits
    forecast = call(
        "analytics.read", "business_summary", {"report": "forecast", "forecast_id": "DEMO-FC-006"}
    )
    assert forecast["facts"]["error_units"] == -150
    retrieval_args = {"query": "commercial return window", "effective_on": "2011-10-20"}
    older = call("commercial.read", "search_documents", retrieval_args)
    assert older == call("commercial.read", "search_documents", retrieval_args)
    assert any(
        r["id"] == "POL-RETURNS-001" and r["fields"]["version"] == 1 for r in older["records"]
    )
    current = call("commercial.read", "search_documents", {"query": "commercial return window"})
    assert any(
        r["id"] == "POL-RETURNS-001" and r["fields"]["version"] == 2 for r in current["records"]
    )
    excerpt = call(
        "commercial.read",
        "read_document",
        {"document_id": "POL-RETURNS-001", "version": 2, "max_chars": 80},
    )
    assert len(excerpt["records"][0]["fields"]["content"]) == 80
    call(
        "commercial.read",
        "read_document",
        {"document_id": "POL-CREDIT-001", "version": 1},
        "error",
    )
    analysis = call(
        "analytics.read", "run_analysis", {"operation": "difference", "values": ["1000", "850"]}
    )
    assert analysis["facts"]["value"] == "150"
    report_args = {
        "title": "Full-cohort sales review",
        "body": f"Net invoice cohort: {gross - credits} pence.",
        "sources": sales["sources"],
    }
    proposal = call("analytics.read", "save_report", report_args, "pending_approval")
    ctx = contexts["analytics.read"]
    accepted = decide(ctx, proposal["operation_id"], "approve")
    assert decide(ctx, proposal["operation_id"], "approve") == accepted
    assert read_report(ctx, accepted["report_id"])["title"] == report_args["title"]
    assert call("analytics.read", "save_report", report_args)["facts"]["saved"]
    report_args["title"] = "Rejected draft"
    rejected = call("analytics.read", "save_report", report_args, "pending_approval")
    assert not decide(ctx, rejected["operation_id"], "reject")["saved"]
    ticket_args = {
        "ticket_id": "DEMO-TKT-004",
        "expected_status": "open",
        "new_status": "in_progress",
        "reason": "Review damage photographs with customer",
    }
    ticket = call("support.read", "update_ticket", ticket_args, "pending_approval")
    ctx = contexts["support.read"]
    decision = decide(ctx, ticket["operation_id"], "approve")
    assert decide(ctx, ticket["operation_id"], "approve") == decision
    assert call("support.read", "update_ticket", ticket_args)["facts"]["saved"]
    assert {m["tool"] for m in measurements} == set(INPUTS)
    return {
        "status": "passed",
        "profile": "full",
        "model_calls": 0,
        "entities": entities,
        "tool_calls": len(measurements),
        "measurements": measurements,
        "sales": sales["facts"],
        "max_result_bytes": max(m["bytes"] for m in measurements),
        "checks": [
            "20 entity projections",
            "pagination",
            "filters",
            "invalid arguments",
            "role denial",
            "independent sales reconciliation",
            "deterministic mock RAG",
            "document scopes and versions",
            "bounded arithmetic",
            "source references",
            "approve/reject",
            "idempotent writes",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/g06-full-tools.json"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="acme-full-tools-") as temporary:
        report = verify(Path.cwd().resolve(), Path(temporary))
    write_json(args.output, report)
    print(json.dumps({k: v for k, v in report.items() if k != "measurements"}, indent=2))


if __name__ == "__main__":
    main()
