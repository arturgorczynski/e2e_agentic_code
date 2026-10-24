"""Actual Gradio HTTP callbacks with real local inference; this is not visual/browser proof.

Use only the isolated test state provisioned for acceptance. The script never reads secrets
from the developer's account or sends messages outside the local learning application.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx


class Session:
    def __init__(self, base, username, password):
        self.base = base
        self.session = uuid4().hex
        self.client = httpx.Client(base_url=base, headers={"Origin": base}, timeout=60)
        response = self.client.post("/login", data={"username": username, "password": password})
        if response.status_code != 303:
            raise RuntimeError("Validation login failed")

    def call(self, name, data):
        response = self.client.post(
            f"/app/gradio_api/call/{name}", json={"data": data, "session_hash": self.session}
        )
        response.raise_for_status()
        identifier = response.json()["event_id"]
        with self.client.stream("GET", f"/app/gradio_api/call/{name}/{identifier}") as stream:
            kind = ""
            for line in stream.iter_lines():
                if line.startswith("event: "):
                    kind = line[7:]
                elif line.startswith("data: "):
                    payload = json.loads(line[6:])
                    if kind == "error":
                        raise RuntimeError(f"Callback {name}: {payload}")
                    if kind == "complete":
                        return payload
        raise RuntimeError(f"Callback {name} ended without a result")

    def close(self):
        self.client.close()


def run(base, password, output):
    evidence = {
        "scope": "Gradio HTTP API + actual configured provider; no browser layout proof",
        "checks": {},
        "observed_states": [],
    }
    first = Session(base, "taylor.analyst", password)
    second = Session(base, "alex.sales", password)
    try:
        loaded = first.call("load", [])
        title = "API acceptance " + uuid4().hex[:8]
        selected = first.call("threads_action", [None, loaded[1]["value"], title])[0]["value"]
        first.call("choose", [selected])
        first.call("change_mode", [selected, "company"])
        first.call(
            "send",
            [
                selected,
                "Read the returns policy effective 2011-12-09. Prepare a report proposal titled "
                "Returns acceptance with a short summary and the exact document/version source. "
                "Do not approve it. State that it is pending approval.",
                None,
            ],
        )
        # Disconnect immediately. A fresh authenticated client must find the saved state.
        first.close()
        first = Session(base, "taylor.analyst", password)
        reloaded = first.call("load", [])
        assert reloaded[1]["value"] == selected
        evidence["checks"]["selection_after_reconnect"] = True
        deadline = time.monotonic() + 310
        while time.monotonic() < deadline:
            snapshot = first.call("poll", [selected])
            state = snapshot[1]
            if state not in evidence["observed_states"]:
                evidence["observed_states"].append(state)
                print(state, flush=True)
            if "**Complete**" in state:
                break
            if "**Failed**" in state:
                raise RuntimeError(state)
            time.sleep(1)
        else:
            raise RuntimeError("Real model did not complete within its deadline")
        history = first.client.get(f"/transcript/{selected}").json()
        assert sum(r["message"]["type"] == "human" for r in history) == 1
        evidence["checks"]["disconnection_preserves_result_and_one_human_message"] = True
        # A second page under the same identity must not suppress the first
        # page's polling or change its mode/selected-chat metadata.
        sibling = Session(base, "taylor.analyst", password)
        try:
            sibling.call("load", [])
            other_chat = sibling.call("threads_action", [None, selected, "Parallel page"])[0][
                "value"
            ]
            sibling.call("choose", [other_chat])
            still_current = first.call("poll", [selected])
            assert "**Complete**" in still_current[1]
            assert still_current[0] == snapshot[0]
            current_metadata = first.call("metadata", [selected])
            assert current_metadata[1]["value"] == "company"
            evidence["checks"]["same_account_pages_update_independently"] = True
        finally:
            sibling.close()
        pending = snapshot[5]["choices"]
        assert pending, "Model did not create the requested report proposal"
        operation = pending[0][1]
        first.call("tool_poll", [selected])
        original = json.loads(first.call("operation", [selected, operation])[0])
        edited = {**original, "title": "Human-reviewed returns acceptance"}
        result = first.call("decision", [selected, operation, None, json.dumps(edited)])[0]
        assert result["saved"] and result["edited"]
        replay = first.call("decision", [selected, operation, None, json.dumps(edited)])[0]
        assert replay == result
        evidence["checks"]["edited_approval_and_idempotent_replay"] = True
        events = first.client.get(f"/trace/{selected}").json()
        inputs = [r for r in events if r["kind"] == "model_request"]
        assert len(inputs) >= 2
        difference = first.call("diff", [selected, inputs[0]["id"], inputs[-1]["id"]])[0]
        assert difference["message_changes"]
        evidence["checks"]["effective_input_context_diff"] = True
        file_id = first.call("prepare", [selected])[0]
        job_id = first.call("analyze", [selected, file_id, "group_sum", "sales_pence", "month", 5])[
            0
        ]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            snapshot = first.call("poll", [selected])
            job = next(r for r in snapshot[4] if r["id"] == job_id)
            if job["status"] == "complete":
                break
            if job["status"] in {"failed", "cancelled", "timed_out"}:
                raise RuntimeError(job["error"])
            time.sleep(0.1)
        assert job["status"] == "complete"
        files = json.loads(job["result_json"])["files"]
        assert "# CSV analysis" in first.client.get(f"/artifacts/{selected}/{files[1]}").text
        evidence["checks"]["full_company_csv_report_without_docker"] = True
        for path in (
            f"/transcript/{selected}",
            f"/trace/{selected}",
            f"/artifacts/{selected}/{files[1]}",
            f"/reports/{selected}/{result['report_id']}",
        ):
            assert second.client.get(path).status_code == 403
        evidence["checks"]["cross_account_http_denial"] = True
        evidence.update(
            thread_id=selected,
            model_requests=len(inputs),
            events=len(events),
            report_id=result["report_id"],
            csv_job=job_id,
        )
    finally:
        first.close()
        second.close()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:7860")
    parser.add_argument(
        "--password", required=True, help="Disposable validation-account password only"
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/g11_api_validation.json"))
    args = parser.parse_args()
    run(args.base, args.password, args.output)


if __name__ == "__main__":
    main()
