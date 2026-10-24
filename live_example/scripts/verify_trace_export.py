"""Reconstruct the invoice investigation from an export alone; no app state or model."""

import argparse
import json
from pathlib import Path


def verify(report):
    events = report["events"]
    by_id = {row["id"]: row for row in events}
    starts = {
        row["span_id"]: row for row in events if row["span_id"] and row["kind"].endswith("_started")
    }
    assert len(by_id) == len(events)
    assert [r["seq"] for r in events] == sorted({r["seq"] for r in events})
    assert len({r["thread_id"] for r in events}) == 1
    assert all("redacted" in r and "redaction_paths" in r for r in events)
    assert all(r["duration_ms"] is None or r["duration_ms"] >= 0 for r in events)
    requests = [row for row in events if row["kind"] == "model_request"]
    assert len(requests) >= 2
    for row in requests:
        assert row["payload"]["system_prompt"]
        assert row["payload"]["tools"]
        assert "settings" in row["payload"]
        assert row["parent_id"] in starts
    for diff in report["model_input_diffs"]:
        reconstructed = list(diff["before"]["messages"])
        for edit in reversed(diff["message_changes"]):
            left, right = edit["before_range"]
            assert reconstructed[left:right] == edit["removed"]
            reconstructed[left:right] = edit["inserted"]
        assert reconstructed == diff["after"]["messages"]
    assert len(report["model_input_diffs"]) == len(requests) - 1
    for request in report["provenance"]:
        assert request["request_event_id"] in by_id
        for message in request["messages"]:
            assert message["source"]["event_id"] in by_id
            assert message["source"]["kind"] != "effective_request_only"
    records = {}
    for row in events:
        if row["kind"] == "tool_result":
            for item in row["payload"]["result"]["records"]:
                records[item["id"]] = {
                    "fields": item["fields"],
                    "event_id": row["id"],
                    "parent_span_id": row["parent_id"],
                }
    assert records["DEMO-INV-001"]["fields"]["outstanding_pence"] == 70000
    assert records["ALLOC-DEMO-PAY-001"]["fields"]["amount_pence"] == 45000
    assert records["DEMO-CN-001"]["fields"]["amount_pence"] == 5000
    for identifier in ("DEMO-INV-001", "ALLOC-DEMO-PAY-001", "DEMO-CN-001"):
        assert any(
            row["kind"] == "sql" and row["parent_id"] == records[identifier]["parent_span_id"]
            for row in events
        ), "The claimed tool fact needs an executed query in its span"
    model_results = [r for r in events if r["kind"] == "model_response"]
    assert any("700.00" in json.dumps(r["payload"]) for r in model_results)
    usage = [r for r in events if r["kind"] == "provider_finished" and any(r["payload"]["usage"])]
    return {
        "status": "passed",
        "input": "export file only",
        "events": len(events),
        "model_requests": len(requests),
        "exact_diffs_reconstructed": len(requests) - 1,
        "provider_results_with_usage": len(usage),
        "evidence": {
            key: records[key] for key in ("DEMO-INV-001", "ALLOC-DEMO-PAY-001", "DEMO-CN-001")
        },
        "redacted": report["redacted"],
        "hidden_reasoning": report["hidden_reasoning"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(json.loads(args.trace.read_text("utf-8")))
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
