"""Ask the local Finance or customer agent about the r14 invoice settlement."""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx

INVOICE_ID = "SCN-BILL-83DAA020DE34-01"
DOCUMENT_ID = "FIN-SETTLE-83DAA020DE34-01"
PROMPTS = {
    "finance": (
        "employee",
        "EMP-120",
        f"For Fable Home Merchants invoice {INVOICE_ID}, read the exact Finance "
        f"review {DOCUMENT_ID}. Verify the invoice, both payment receipts and "
        "both payment allocations with your permitted SQL tools. Explain the "
        "invoice total, the balance at the mid-October Support review, and "
        "the balance on 21 October. Distinguish each receipt date from its "
        "allocation date. Label document reports separately from SQL facts. "
        "Do not treat settlement as a refund or order change.",
        DOCUMENT_ID,
    ),
    "customer": (
        "customer",
        "SCN-CUST-83DAA020DE34",
        f"This is my Fable Home Merchants invoice {INVOICE_ID}. What is its "
        "current balance? Show each linked payment allocation and its payment "
        "receipt date. Explain whether a receipt alone proves the invoice was "
        "settled and whether a refund or credit note is recorded. Use my "
        "account tools and do not claim access to internal Finance documents.",
        None,
    ),
}


def evaluate(base_url: str, output: Path, timeout_seconds: int, persona: str) -> dict:
    if output.exists():
        raise ValueError("Choose a new output file so prior evidence cannot be reused")
    kind, subject_id, prompt, expected_document = PROMPTS[persona]
    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        selected_response = client.post(
            "/api/personas/select", json={"kind": kind, "subject_id": subject_id}
        )
        selected_response.raise_for_status()
        selected = selected_response.json()
        if selected.get("kind") != kind or selected.get("subject_id") != subject_id:
            raise ValueError("The intended persona was not selected")
        conversation = client.post("/api/conversations")
        conversation.raise_for_status()
        thread_id = conversation.json()["thread_id"]
        submission_id = f"settlement-r14-{uuid4().hex}"
        sent = client.post(
            "/api/chat",
            json={"thread_id": thread_id, "submission_id": submission_id, "text": prompt},
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
        reads = [
            row["payload"]
            for row in events
            if row["kind"] == "document_read"
            and row["payload"].get("document_id") == expected_document
            and row["payload"].get("version") == 1
        ]
        read_results = [
            row["payload"].get("result", {})
            for row in events
            if row["kind"] == "tool_result"
            and row["payload"].get("tool") == "read_document"
            and row["payload"].get("arguments", {}).get("document_id") == expected_document
            and row["payload"].get("arguments", {}).get("version") == 1
        ]
        full_document_read = bool(reads) and any(
            result.get("status") == "ok"
            and result.get("page", {}).get("has_more") is False
            and result.get("page", {}).get("returned") == result.get("page", {}).get("total")
            for result in read_results
        )
        sql_labels = [row["payload"].get("label", "") for row in events if row["kind"] == "sql"]
        tool_names = [
            row["payload"].get("name") for row in events if row["kind"] == "native_tool_started"
        ]
        denied = [row["payload"] for row in events if row["kind"] == "access_denied"]
        if persona == "finance":
            source_path_ok = (
                full_document_read
                and any(label.endswith(":invoices") for label in sql_labels)
                and any(label.endswith(":payment_allocations") for label in sql_labels)
                and any(label.endswith(":payments") for label in sql_labels)
            )
        else:
            source_path_ok = (
                "my_invoice" in tool_names
                and "portal:my_invoice_settlements" in sql_labels
                and not reads
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
            "persona": {"kind": kind, "subject_id": subject_id},
            "prompt": prompt,
            "answer": answer,
            "checks": {
                "full_document_read": full_document_read,
                "model_requests": sum(row["kind"] == "model_request" for row in events),
                "tool_calls": len(tool_names),
                "sql_labels": sql_labels,
                "tool_names": tool_names,
                "denied_events": len(denied),
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
    parser.add_argument("--persona", choices=tuple(PROMPTS), default="finance")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/settlement-finance-agent-r14.json")
    )
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    result = evaluate(args.base_url, args.output, args.timeout_seconds, args.persona)
    print(json.dumps(result, indent=2))
    if not result["checks"]["source_path_ok"]:
        raise SystemExit("Agent source-path check failed; inspect the saved trace")


if __name__ == "__main__":
    main()
