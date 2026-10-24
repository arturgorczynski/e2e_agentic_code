"""Audit the G13 sales report from its portable trace, without a running app or model."""

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path


def verify(report):
    events = report["events"]
    by_id = {row["id"]: row for row in events}
    assert len(by_id) == len(events)
    assert [r["seq"] for r in events] == sorted({r["seq"] for r in events})
    assert len({r["thread_id"] for r in events}) == 1
    requests = [r for r in events if r["kind"] == "model_request"]
    for start_kind, finish_kind in [
        ("model_attempt_started", "model_attempt_finished"),
        ("provider_started", "provider_finished"),
        ("native_tool_started", "native_tool_finished"),
    ]:
        starts = {r["span_id"] for r in events if r["kind"] == start_kind}
        finishes = {r["span_id"] for r in events if r["kind"] == finish_kind}
        assert starts and starts == finishes, (start_kind, starts - finishes)
    for request in requests:
        payload = request["payload"]
        assert payload["system_prompt"] and payload["tools"] and payload["settings"]
        assert any(
            r["kind"] == "model_response" and r["parent_id"] == request["parent_id"] for r in events
        )
    assert len(report["model_input_diffs"]) == len(requests) - 1
    for diff in report["model_input_diffs"]:
        messages = list(diff["before"]["messages"])
        for edit in reversed(diff["message_changes"]):
            left, right = edit["before_range"]
            assert messages[left:right] == edit["removed"]
            messages[left:right] = edit["inserted"]
        assert messages == diff["after"]["messages"]
    assert len(report["provenance"]) == len(requests)
    for request in report["provenance"]:
        assert request["request_event_id"] in by_id
        for message in request["messages"]:
            assert message["source"]["event_id"] in by_id
            assert message["source"]["kind"] != "effective_request_only"

    sales = {}
    for row in events:
        if row["kind"] != "tool_result":
            continue
        args = row["payload"]["arguments"]
        if args.get("customer_id") == "DEMO-CUST-005" and args.get("report") == "sales":
            facts = row["payload"]["result"]["facts"]
            sales[args["start_date"]] = facts["sales_pence"]
            assert any(r["kind"] == "sql" and r["parent_id"] == row["parent_id"] for r in events)
    assert sales == {"2011-10-01": 1000000, "2011-11-01": 750000}
    assert any(
        r["kind"] == "document_read"
        and r["payload"]["document_id"] == "POL-METRICS-001"
        and r["payload"]["version"] == 1
        for r in events
    )
    decisions = [r["payload"] for r in events if r["kind"] == "business_decision"]
    assert len(decisions) == 2
    approved = next(d for d in decisions if d["decision"] == "approve")
    rejected = next(d for d in decisions if d["decision"] == "reject")
    assert approved["saved"] and approved["edited"] and not rejected["saved"]
    assert approved["decided_arguments"]["title"] == "G13 reviewed sales report"
    assert "Reviewer note: MAPLE-13" in approved["decided_arguments"]["body"]
    sources = approved["decided_arguments"]["sources"]
    query_sources = [s for s in sources if s["kind"] == "query"]
    assert len(query_sources) == 2
    assert all(by_id[s["id"]]["kind"] == "sql" for s in query_sources)
    assert any(s["id"] == "POL-METRICS-001" and s["version"] == 1 for s in sources)
    assert sum(r["kind"] == "approval_replayed" for r in events) >= 2
    counts = Counter(r["kind"] for r in events)
    return {
        "status": "passed",
        "input": "portable G13 trace only; no app or model",
        "events": len(events),
        "kinds": dict(counts),
        "exact_context_diffs_reconstructed": len(requests) - 1,
        "all_model_and_tool_spans_finished": True,
        "all_request_messages_have_recorded_origins": True,
        "sales_pence": sales,
        "percentage_change": -25,
        "policy": "POL-METRICS-001 v1",
        "approved_report": approved["report_id"],
        "edited_approval_and_rejection": True,
        "decision_replays": counts["approval_replayed"],
        "boundary": "Observable application/provider inputs and outputs, not hidden reasoning",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = args.trace.read_bytes()
    if args.trace.suffix == ".gz":
        raw = gzip.decompress(raw)
    result = verify(json.loads(raw))
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
