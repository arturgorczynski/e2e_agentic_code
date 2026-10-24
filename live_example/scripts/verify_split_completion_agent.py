"""Capture a live Operations agent run against the completed supplier order."""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx

ORDER_ID = "SCN-PO-SPLIT-75F3A546B17E"
DOCUMENT_ID = "PROCURE-SPLIT-75F3A546B17E"
PROMPT = (
    f"For supplier purchase order {ORDER_ID}, use exact company tools to verify "
    "all goods receipts and their linked stock movements, the ordered, received "
    "and outstanding units, and the current inventory on-hand and reserved "
    f"values. Find the version history of Purchasing document {DOCUMENT_ID}, "
    "read its current and earlier versions, and compare their conclusions. "
    "Explain why the old six-outstanding "
    "statement was true before the final receipt. Cite exact record IDs and "
    "distinguish SQL facts from the document's review."
)


def evaluate(base_url: str, output: Path, timeout_seconds: int) -> dict:
    if output.exists():
        raise ValueError("Choose a new output file so prior evidence cannot be reused")
    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        selected = client.post(
            "/api/personas/select", json={"kind": "employee", "subject_id": "EMP-002"}
        )
        selected.raise_for_status()
        if selected.json().get("subject_id") != "EMP-002":
            raise ValueError("Operations employee was not selected")
        conversation = client.post("/api/conversations")
        conversation.raise_for_status()
        thread_id = conversation.json()["thread_id"]
        submission_id = f"supplier-completion-r15-{uuid4().hex}"
        sent = client.post(
            "/api/chat",
            json={"thread_id": thread_id, "submission_id": submission_id, "text": PROMPT},
        )
        sent.raise_for_status()
        deadline = time.monotonic() + timeout_seconds
        while True:
            response = client.get(f"/api/conversations/{thread_id}")
            response.raise_for_status()
            snapshot = response.json()
            if snapshot["status"] in {"complete", "failed", "interrupted"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Run is still {snapshot['status']}; thread {thread_id}")
            time.sleep(2)
        events = []
        after = 0
        while True:
            response = client.get(f"/api/conversations/{thread_id}/events", params={"after": after})
            response.raise_for_status()
            page = response.json()["events"]
            if not page:
                break
            events.extend(page)
            after = page[-1]["seq"]
        answers = [row["content"] for row in snapshot["chat"] if row["role"] == "assistant"]
        answer = answers[-1] if answers else ""
        plain_answer = answer.lower().replace("*", "")
        sql_labels = [row["payload"].get("label", "") for row in events if row["kind"] == "sql"]
        reads = [
            row["payload"] for row in events
            if row["kind"] == "document_read"
            and row["payload"].get("document_id") == DOCUMENT_ID
        ]
        tool_names = [
            row["payload"].get("name") for row in events
            if row["kind"] == "native_tool_started"
        ]
        checks = {
            "order_sql": any(label.endswith(":purchase_orders") for label in sql_labels),
            "receipt_sql": any(label.endswith(":goods_receipts") for label in sql_labels),
            "stock_sql": any(label.endswith(":stock_movements") for label in sql_labels),
            "inventory_sql": any(label.endswith(":inventory") for label in sql_labels),
            "current_document_read": any(row.get("version") == 2 for row in reads),
            "older_document_read": any(row.get("version") == 1 for row in reads),
            "version_history_tool": "list_document_versions" in tool_names,
            "version_history_event": any(
                row["kind"] == "document_versions_listed"
                and row["payload"].get("document_id") == DOCUMENT_ID
                and row["payload"].get("returned_versions") == [1, 2]
                for row in events
            ),
            "answer_three_receipts": all(
                f"SCN-GR-SPLIT-75F3A546B17E-{suffix}" in answer
                for suffix in ("01", "02", "03")
            ),
            "answer_zero_outstanding": any(
                phrase in plain_answer
                for phrase in (
                    "outstanding: 0", "outstanding = 0", "outstanding to 0",
                    "0 outstanding", "zero outstanding",
                )
            ),
            "no_access_denial": not any(row["kind"] == "access_denied" for row in events),
        }
        report = {
            "status": snapshot["status"], "error": snapshot["error"],
            "thread_id": thread_id, "submission_id": submission_id,
            "persona": {"kind": "employee", "subject_id": "EMP-002"},
            "prompt": PROMPT, "answer": answer,
            "checks": checks, "sql_labels": sql_labels,
            "document_reads": reads, "tool_names": tool_names,
            "events": events,
        }
        report["verified"] = snapshot["status"] == "complete" and all(checks.values())
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(json.dumps({"status": snapshot["status"], "verified": report["verified"],
                          "checks": checks,
                          "output": str(output)}, indent=2))
        if not report["verified"]:
            raise ValueError("Live supplier-agent evidence did not satisfy every check")
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:7860")
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/split-completion-agent-r15.json"))
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()
    evaluate(args.base_url, args.output, args.timeout_seconds)


if __name__ == "__main__":
    main()
