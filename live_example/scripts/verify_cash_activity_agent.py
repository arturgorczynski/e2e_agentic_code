"""Run one real local-model cash question and save inspectable evidence."""

import argparse
import json
import time
from datetime import date
from pathlib import Path
from uuid import uuid4

import httpx

from acme.business_insights import financial_activity

PROMPT = (
    "For the fictional Acme 2026 cohort, from 2026-01-01 through 2026-10-22, "
    "how much customer cash was received, how much cash outflow is recorded in "
    "the expense ledger, and what is their difference? Break down the recorded "
    "outflow by category, giving its GBP amount and payment count. Use "
    "cash_activity and name the limits of the expense ledger. Is that "
    "difference company profit?"
)


def run(base_url: str, state: Path, output: Path, timeout: int) -> dict:
    if output.exists():
        raise ValueError("Choose a fresh evidence path")
    activity = financial_activity(
        state, date(2026, 1, 1), date(2026, 10, 22), "contemporary"
    )
    expected = activity["totals"]
    expected_categories = {
        row["category"]: {
            "expense_count": row["expense_count"],
            "amount_pence": row["amount_pence"],
        }
        for row in activity["expense_categories"] or []
    }
    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        selected = client.post(
            "/api/personas/select", json={"kind": "super_user", "subject_id": "all"}
        )
        selected.raise_for_status()
        if selected.json()["kind"] != "super_user":
            raise RuntimeError("Superuser persona was not selected")
        conversation = client.post("/api/conversations")
        conversation.raise_for_status()
        thread_id = conversation.json()["thread_id"]
        sent = client.post(
            "/api/chat",
            json={
                "thread_id": thread_id,
                "submission_id": f"cash-activity-{uuid4().hex}",
                "text": PROMPT,
            },
        )
        sent.raise_for_status()
        deadline = time.monotonic() + timeout
        while True:
            response = client.get(f"/api/conversations/{thread_id}")
            response.raise_for_status()
            snapshot = response.json()
            if snapshot["status"] in {"complete", "failed", "interrupted"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Thread {thread_id} is still {snapshot['status']}")
            time.sleep(2)
        events, after = [], 0
        while True:
            page = client.get(
                f"/api/conversations/{thread_id}/events", params={"after": after}
            )
            page.raise_for_status()
            rows = page.json()["events"]
            if not rows:
                break
            events.extend(rows)
            after = rows[-1]["seq"]

    tool_results = [
        row["payload"].get("result", {})
        for row in events
        if row["kind"] == "tool_result"
        and row["payload"].get("tool") == "cash_activity"
    ]
    sql = [
        {"id": row["id"], "label": row["payload"].get("label"),
         "parameters": row["payload"].get("parameters")}
        for row in events
        if row["kind"] == "sql"
        and str(row["payload"].get("label", "")).startswith("cash_activity:")
    ]
    answers = [row["content"] for row in snapshot["chat"] if row["role"] == "assistant"]
    answer = answers[-1] if answers else ""
    fields = (
        "customer_cash_received_pence", "recorded_cash_outflow_pence",
        "recorded_cash_difference_pence",
    )
    tool_matches = any(
        result.get("status") == "ok"
        and all(result.get("facts", {}).get(field) == expected[field] for field in fields)
        for result in tool_results
    )
    category_matches = any(
        result.get("status") == "ok"
        and {
            row["id"]: {
                "expense_count": row["fields"]["expense_count"],
                "amount_pence": row["fields"]["amount_pence"],
            }
            for row in result.get("records", [])
            if row.get("entity") == "expense_category"
        } == expected_categories
        for result in tool_results
    )
    answer_mentions = all(
        f"{expected[field] / 100:.2f}" in answer.replace(",", "")
        for field in fields
    )
    plain_answer = answer.lower().replace("*", "").replace("_", " ").replace("`", "")
    answer_mentions_categories = all(
        category.replace("_", " ") in plain_answer
        and f"{values['amount_pence'] / 100:.2f}" in plain_answer.replace(",", "")
        for category, values in expected_categories.items()
    )
    report = {
        "thread_id": thread_id,
        "status": snapshot["status"],
        "error": snapshot["error"],
        "prompt": PROMPT,
        "expected_pence": {field: expected[field] for field in fields},
        "expected_categories": expected_categories,
        "cash_tool_results": tool_results,
        "cash_sql_events": sql,
        "answer": answer,
        "tool_matches_database": tool_matches,
        "category_records_match_database": category_matches,
        "answer_mentions_all_gbp_values": answer_mentions,
        "answer_mentions_all_category_amounts": answer_mentions_categories,
        "answer_rejects_profit_label": any(
            phrase in plain_answer for phrase in (
                "not profit", "not a profit", "not company profit",
                "not a measure of profit", "company profit? no"
            )
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:7860")
    parser.add_argument("--state-dir", type=Path, default=Path("state"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    report = run(args.base_url, args.state_dir, args.output, args.timeout)
    print(json.dumps({key: report[key] for key in (
        "thread_id", "status", "tool_matches_database", "answer_mentions_all_gbp_values",
        "category_records_match_database", "answer_mentions_all_category_amounts",
        "answer_rejects_profit_label",
    )}, indent=2))
    if (report["status"] != "complete" or not report["tool_matches_database"]
            or not report["category_records_match_database"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
