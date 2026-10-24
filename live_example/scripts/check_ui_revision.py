"""Read-only service status, or an isolated real-tool acceptance exercise."""

import argparse
import json
import shutil
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

from acme.app_store import login, provision
from acme.dataset import connect
from acme.execution_view import conversation_graph, runs
from acme.jobs import prepare_sales_csv, read_file
from acme.tool_catalog import document_catalog, run_tool
from acme.trace_view import all_events
from acme.ui_service import LearningService

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--model", action="store_true")
    args = parser.parse_args()
    if args.status:
        db = connect(ROOT / "state/app.sqlite", readonly=True)
        try:
            print(
                json.dumps(
                    [
                        dict(r)
                        for r in db.execute(
                            "SELECT status,COUNT(*) AS count FROM ui_requests GROUP BY status"
                        )
                    ]
                )
            )
        finally:
            db.close()
        return
    with (
        tempfile.TemporaryDirectory(prefix="acme-playground-check-") as temporary,
        ExitStack() as cleanup,
    ):
        state = Path(temporary)
        shutil.copy2(ROOT / "state/company.sqlite", state / "company.sqlite")
        service = LearningService(ROOT, state, ROOT / "data")
        cleanup.callback(service.close)
        provision(ROOT, state, "playground.check", access_profile="super_user")
        token = login(state, "playground.check")
        context = service.company_context(token, service.playground(token))
        rows, _ = document_catalog(context)
        print("Accessible document versions:", len(rows))
        result = run_tool(context, "list_records", {"entity": "customers", "limit": 5})
        assert result["status"] == "ok", result
        print("Customer preview rows:", len(result["records"]))
        ranking = run_tool(context, "business_summary", {"report": "customer_orders"})
        assert ranking["status"] == "ok", ranking
        print("Database aggregate:", ranking["status"])
        identifier, version = rows[0][:2]
        doc = run_tool(context, "read_document", {"document_id": identifier, "version": version})
        assert doc["status"] == "ok", doc
        print("Document read:", doc["status"])
        file_id = prepare_sales_csv(context)
        record, content = read_file(context, file_id)
        print("CSV preview:", record["name"], content.decode().splitlines()[:2])
        job = run_tool(
            context,
            "analyze_workspace",
            {
                "action": "analyze",
                "file_id": file_id,
                "operation": "group_sum",
                "value_column": "sales_pence",
                "group_column": "month",
            },
        )
        assert job["result"]["status"] == "complete", job
        print("CSV job: complete")
        if args.search:
            search = run_tool(context, "web_search", {"query": "Python official documentation"})
            print("Live web search:", json.dumps(search, ensure_ascii=True))
            assert search["status"] == "ok" and search["results"], search
        assert service.threads(token) == []
        print("Playground left chat history empty: PASS")
        if args.model:
            service.start()
            prompt = (
                "Use web_search to find Python official documentation. Return two source links."
            )
            thread = service.submit_chat(token, "draft:free", prompt, "live-web-check")
            immediate = service.snapshot(token, thread)
            assert immediate["chat"][0]["content"] == prompt
            print("Prompt visible before the answer: PASS", flush=True)
            until = time.monotonic() + 150
            while time.monotonic() < until:
                snapshot = service.snapshot(token, thread)
                if snapshot["status"] not in {"queued", "running"}:
                    break
                time.sleep(0.5)
            assert snapshot["status"] == "complete", snapshot["error"]
            events = all_events(ROOT, state, token, thread)
            searches = [
                e
                for e in events
                if e["kind"] == "tool_result" and e["payload"].get("tool") == "web_search"
            ]
            print(
                "Web tool calls:",
                json.dumps([e["payload"]["result"] for e in searches]),
                flush=True,
            )
            print("Model response:", snapshot["chat"][-1]["content"], flush=True)
            assert searches and searches[-1]["payload"]["result"]["status"] == "ok"
            assert len([m for m in snapshot["chat"] if m["role"] == "user"]) == 1
            print("Real model + free web tool: PASS")
            print("Answer:", snapshot["chat"][-1]["content"])
            selected = runs(ROOT, state, token, thread)[0]["id"]
            assert "data-step=" in conversation_graph(ROOT, state, token, thread, selected)
            print("Real execution graph: PASS")


if __name__ == "__main__":
    main()
