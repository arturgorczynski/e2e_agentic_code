"""Opt-in real Ollama rehearsal of the combined learner preset, with fresh state."""

import argparse
import gzip
import json
import shutil
import sys
from pathlib import Path

from acme.app_store import login, new_thread, provision, read_transcript
from acme.dataset import initialize_state
from acme.runtime import submit
from acme.source_data import write_json
from acme.trace_view import all_events, export_trace


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3-coder:30b")
    parser.add_argument("--output", type=Path, default=Path("artifacts/g09-live"))
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Use a new output directory")
    project = output / "project"
    (project / "data/company").mkdir(parents=True)
    shutil.copy2(root / "data/company/company.json", project / "data/company/company.json")
    config = (root / "models.toml").read_text("utf-8")
    (project / "models.toml").write_text(
        config.replace('preset = "standard"', 'preset = "combined"'), encoding="utf-8"
    )
    (project / ".env").write_text("OLLAMA_BASE_URL=http://localhost:11434\n", encoding="utf-8")
    state = output / "state"
    initialize_state(root, state)
    provision(project, state, "taylor.analyst", "disposable-middleware-check")
    token = login(state, "taylor.analyst", "disposable-middleware-check")
    thread = new_thread(project, state, token, "Combined middleware", mode="free")
    prompts = [
        "Remember ORCHID. October sales were GBP 10000. My email is person@example.com.",
        "November sales were GBP 7500. Remember this too.",
        "Briefly explain how to compare sales in two months.",
        "What was my case label, and what is the percentage change from October to November?",
    ]
    replies = []
    for index, prompt in enumerate(prompts):
        print(f"Real combined-preset turn {index + 1}", flush=True)
        replies.append(
            submit(
                project,
                state,
                root / "data",
                token,
                thread,
                f"combined-{index}",
                prompt,
                profile="local",
                model_name=args.model,
            )
        )
        print(replies[-1]["answer"], flush=True)
    rows = list(all_events(project, state, token, thread))
    requests = [r["payload"] for r in rows if r["kind"] == "model_request"]
    assert len(requests) >= 4
    assert all("person@example.com" not in json.dumps(r["messages"]) for r in requests)
    assert "[REDACTED_EMAIL]" in json.dumps(requests[0]["messages"])
    helpers = [
        r
        for r in rows
        if r["kind"] == "provider_started" and r["payload"]["purpose"] == "summarization"
    ]
    assert helpers
    first_id = requests[0]["messages"][0]["data"]["id"]
    assert first_id not in [m["data"]["id"] for m in requests[-1]["messages"]]
    transcript = read_transcript(project, state, token, thread)
    humans = [
        r["message"]["data"]["content"] for r in transcript if r["message"]["type"] == "human"
    ]
    assert humans == prompts
    assert "ORCHID" in replies[-1]["answer"] and "25" in replies[-1]["answer"]
    company = new_thread(project, state, token, "Read-only company")
    lookup = submit(
        project,
        state,
        root / "data",
        token,
        company,
        "lookup",
        "Look up customer DEMO-CUST-005 and cite its record ID.",
        profile="local",
        model_name=args.model,
    )
    company_rows = list(all_events(project, state, token, company))
    company_requests = [r["payload"] for r in company_rows if r["kind"] == "model_request"]
    assert company_requests and any(r["kind"] == "tool_result" for r in company_rows)
    for request in company_requests:
        assert not {"save_report", "update_ticket", "analyze_workspace"} & {
            tool["name"] for tool in request["tools"]
        }
    assert "DEMO-CUST-005" in lookup["answer"]
    for name, identifier in [("combined", thread), ("read_only", company)]:
        trace = export_trace(project, state, token, identifier, format="json")
        with gzip.open(output / f"{name}_trace.json.gz", "wt", encoding="utf-8") as stream:
            stream.write(trace if isinstance(trace, str) else json.dumps(trace))
    write_json(
        output / "result.json",
        {
            "model": args.model,
            "provider": "local Ollama",
            "preset": "combined",
            "turns": replies,
            "company_reply": lookup,
            "original_user_messages": len(humans),
            "summary_calls": len(helpers),
            "email_redacted_before_main_model": True,
            "original_transcript_preserved": True,
            "read_only_schemas_verified": True,
        },
    )
    print("Combined preset real-model checks passed", flush=True)


if __name__ == "__main__":
    main()
