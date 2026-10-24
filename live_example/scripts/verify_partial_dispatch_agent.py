"""Probe the current partial-dispatch agents and save their event evidence."""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx

ORDER_ID = "SCN-ORD-83DAA020DE34-03"
DOCUMENT_ID = "CASE-PARTIAL-83DAA020DE34"
OPERATIONS_DOCUMENT_ID = "OPS-DISPATCH-83DAA020DE34"
SUPPORT_PROMPT = (
    f"For Fable Home Merchants order {ORDER_ID}, explain how many units were "
    "ordered, dispatched and remain unshipped. Is there recorded delivery or an "
    "invoice? What is the Support follow-up status and next step? Read the exact "
    "case document and use records allowed by my employee scope. Label claims "
    "from the case document separately from facts you checked directly in SQL. "
    "Do not invent a delivery or next dispatch date."
)
CUSTOMER_PROMPT = (
    f"I am Fable Home Merchants. For my order {ORDER_ID}, how many units did I "
    "order, how many were dispatched, and how many are still unshipped? Can "
    "you tell whether the shipped items were delivered or when the others "
    "will be sent? Use my account tools and distinguish what the records show "
    "from what they do not show."
)
WAREHOUSE_PROMPT = (
    f"For Fable Home Merchants order {ORDER_ID}, read the exact Warehouse "
    f"handoff {OPERATIONS_DOCUMENT_ID}. Check the partial shipment, its two "
    "shipment items and the linked stock movements with your Operations "
    "database tools. Check the dated inventory row. Explain the four ordered "
    "units, two dispatched units and two unshipped units. State whether the "
    "two reserved units are allocated specifically to this order, and "
    "whether delivery or a next dispatch date is recorded. Distinguish the "
    "handoff's dated statements from records you checked directly in SQL."
)
PERSONAS = {
    "employee": ("employee", "EMP-138", SUPPORT_PROMPT, DOCUMENT_ID, 2),
    "customer": ("customer", "SCN-CUST-83DAA020DE34", CUSTOMER_PROMPT, None, None),
    "warehouse": ("employee", "EMP-041", WAREHOUSE_PROMPT, OPERATIONS_DOCUMENT_ID, 1),
}


def evaluate(base_url: str, output: Path, timeout_seconds: int, persona_kind: str) -> dict:
    """Capture one real model run and mechanically inspect its source trail."""
    if output.exists():
        raise ValueError("Choose a new output file so prior evidence cannot be reused")
    api_kind, subject_id, prompt, document_id, document_version = PERSONAS[persona_kind]
    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        selection = client.post(
            "/api/personas/select", json={"kind": api_kind, "subject_id": subject_id}
        )
        selection.raise_for_status()
        chosen = selection.json()
        if chosen.get("kind") != api_kind or chosen.get("subject_id") != subject_id:
            raise ValueError("The intended persona was not selected")
        conversation = client.post("/api/conversations")
        conversation.raise_for_status()
        thread_id = conversation.json()["thread_id"]
        submission_id = f"partial-current-{uuid4().hex}"
        sent = client.post(
            "/api/chat",
            json={"thread_id": thread_id, "submission_id": submission_id, "text": prompt},
        )
        sent.raise_for_status()
        deadline = time.monotonic() + timeout_seconds
        while True:
            snapshot_response = client.get(f"/api/conversations/{thread_id}")
            snapshot_response.raise_for_status()
            snapshot = snapshot_response.json()
            if snapshot["status"] in {"complete", "failed", "interrupted"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Run is still {snapshot['status']}; thread {thread_id}")
            time.sleep(2)
        events = []
        after = 0
        while True:
            page_response = client.get(
                f"/api/conversations/{thread_id}/events", params={"after": after}
            )
            page_response.raise_for_status()
            page = page_response.json()["events"]
            if not page:
                break
            events.extend(page)
            after = page[-1]["seq"]
        answers = [row["content"] for row in snapshot["chat"] if row["role"] == "assistant"]
        answer = answers[-1] if answers else ""
        document_reads = [
            row["payload"] for row in events
            if row["kind"] == "document_read"
            and row["payload"].get("document_id") == document_id
            and row["payload"].get("version") == document_version
        ]
        case_results = [
            row["payload"].get("result", {})
            for row in events
            if row["kind"] == "tool_result"
            and row["payload"].get("tool") == "read_document"
            and row["payload"].get("arguments", {}).get("document_id") == document_id
            and row["payload"].get("arguments", {}).get("version") == document_version
        ]
        full_case_read = bool(document_reads) and any(
            result.get("status") == "ok"
            and result.get("page", {}).get("has_more") is False
            and result.get("page", {}).get("returned")
            == result.get("page", {}).get("total")
            for result in case_results
        )
        denied = [row["payload"] for row in events if row["kind"] == "access_denied"]
        sql_labels = [row["payload"].get("label") for row in events if row["kind"] == "sql"]
        tool_names = [
            row["payload"].get("name")
            for row in events
            if row["kind"] == "native_tool_started"
        ]
        if persona_kind == "employee":
            source_path_ok = (
                full_case_read
                and {"lookup:orders", "list:order_items", "lookup:tickets"}
                <= set(sql_labels)
                and not any(
                    label.startswith(
                        ("lookup:shipments", "list:stock_movements", "lookup:invoices")
                    )
                    for label in sql_labels
                )
            )
        elif persona_kind == "warehouse":
            source_path_ok = (
                full_case_read
                and any(label.endswith(":shipments") for label in sql_labels)
                and any(label.endswith(":inventory") for label in sql_labels)
                and any(label.endswith(":shipment_items") for label in sql_labels)
                and any(label.endswith(":stock_movements") for label in sql_labels)
            )
        else:
            source_path_ok = (
                "my_order" in tool_names
                and "portal:my_order" in sql_labels
                and not document_reads
            )
        source_path_ok = source_path_ok and not denied and snapshot["status"] == "complete"
        report = {
            "status": snapshot["status"],
            "error": snapshot["error"],
            "thread_id": thread_id,
            "run_id": next(
                (row["id"] for row in snapshot["runs"] if row["submission_id"] == submission_id),
                None,
            ),
            "persona": {"kind": chosen["kind"], "subject_id": chosen["subject_id"]},
            "document_expected": (
                {"document_id": document_id, "version": document_version}
                if document_id is not None
                else None
            ),
            "prompt": prompt,
            "answer": answer,
            "checks": {
                "full_case_read": full_case_read,
                "model_requests": sum(row["kind"] == "model_request" for row in events),
                "tool_calls": len(tool_names),
                "denied_events": len(denied),
                "sql_labels": sql_labels,
                "tool_names": tool_names,
                "source_path_ok": source_path_ok,
                "answer_requires_manual_review": True,
            },
            "events": events,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return {key: value for key, value in report.items() if key != "events"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:7860")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/partial-dispatch-agent-r13.json")
    )
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--persona", choices=tuple(PERSONAS), default="employee")
    args = parser.parse_args()
    result = evaluate(args.base_url, args.output, args.timeout_seconds, args.persona)
    print(json.dumps(result, indent=2))
    if not result["checks"]["source_path_ok"]:
        raise SystemExit("Agent source-path check failed; inspect the saved trace")


if __name__ == "__main__":
    main()
