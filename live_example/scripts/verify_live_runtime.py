"""Real Ollama acceptance: three CLI processes, checkpoint continuity and deduplication.

Run explicitly; this is not part of the offline unit suite. Uses a new local state
directory, an installed tool-capable Ollama model, and no cloud credentials.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from acme.app_store import login, new_thread, provision, read_transcript
from acme.dataset import initialize_state
from acme.source_data import write_json
from acme.trace_view import all_events, export_trace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3-coder:30b")
    parser.add_argument("--output", type=Path, default=Path("artifacts/g07-live"))
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Use a new output directory so this evidence cannot reuse prior messages")
    state = output / "state"
    initialize_state(root, state)
    provision(root, state, "morgan.finance", "local-validation-only-password")
    provision(root, state, "alex.sales", "separate-validation-password")
    token = login(state, "morgan.finance", "local-validation-only-password")
    other = login(state, "alex.sales", "separate-validation-password")
    thread = new_thread(root, state, token, "Live restart acceptance")
    environment = {
        **os.environ,
        "ACME_TOKEN": token,
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": args.model,
        "PYTHONIOENCODING": "utf-8",
    }
    prompts = [
        "Remember the case label CEDAR-71. How much is still owed on DEMO-INV-001 "
        "and how many days overdue is it? Use the invoice tool and cite its ID.",
        "For that same invoice, list allocated payment and credit-note IDs and amounts. "
        "Also repeat the case label I gave you.",
        "What case label did I tell you at the start, and what outstanding balance did "
        "you report in your first answer (not the invoice total)? Use our existing conversation.",
    ]
    commands = []
    outputs = []
    pids = []
    for index, prompt in enumerate(prompts, 1):
        command = [
            sys.executable,
            "-B",
            "-m",
            "acme",
            "chat",
            "send",
            "--state-dir",
            str(state),
            "--thread",
            thread,
            "--submission-id",
            f"live-{index}",
            "--message",
            prompt,
            "--profile",
            "local",
            "--model",
            args.model,
        ]
        print(f"Real model turn {index}: starting a fresh CLI process", flush=True)
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        pids.append(process.pid)
        try:
            stdout, stderr = process.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
        write_json(
            output / f"turn-{index}.json",
            {
                "pid": process.pid,
                "returncode": process.returncode,
                "stdout": stdout,
                "stderr": stderr,
            },
        )
        if process.returncode:
            raise RuntimeError(f"Live turn {index} failed; inspect {output / f'turn-{index}.json'}")
        response = json.loads(stdout)
        outputs.append(response)
        commands.append(command)
        # The exact Unicode answer is saved above; console code pages on Windows
        # may not encode symbols such as the mathematical minus sign.
        print(response["answer"].encode("ascii", "backslashreplace").decode("ascii"), flush=True)
    assert "700" in outputs[0]["answer"]
    assert "CEDAR-71" in outputs[1]["answer"] and "CEDAR-71" in outputs[2]["answer"]
    assert "DEMO-PAY-001" in outputs[1]["answer"] and "DEMO-CN-001" in outputs[1]["answer"]
    # Validate unit handling separately from persistence. Raw provider text is retained.
    answers = [row["answer"] for row in outputs]
    for answer in answers:
        assert not re.search(r"\b(?:700|450|50|1200)(?:\.00)?\s+pence\b", answer, re.I), (
            "Provider mislabeled GBP as pence; inspect raw turn evidence"
        )
    assert re.search(r"(?:GBP\s*|£\s*)700(?:\.00)?\b|700\.00\s*GBP", answers[0])
    assert re.search(r"(?:GBP\s*|£\s*)450(?:\.00)?\b|450\.00\s*GBP", answers[1])
    assert re.search(r"(?:GBP\s*|£\s*)50(?:\.00)?\b|50\.00\s*GBP", answers[1])
    assert re.search(r"(?:GBP\s*|£\s*)700(?:\.00)?\b|700\.00\s*GBP", answers[2])
    events_before = list(all_events(root, state, token, thread))
    repeated = subprocess.run(
        commands[-1],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )
    assert json.loads(repeated.stdout) == outputs[-1]
    assert len(list(all_events(root, state, token, thread))) == len(events_before)
    denied = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "acme",
            "chat",
            "history",
            "--state-dir",
            str(state),
            "--thread",
            thread,
        ],
        cwd=root,
        env={**environment, "ACME_TOKEN": other},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert denied.returncode != 0 and "unavailable" in denied.stderr
    transcript = read_transcript(root, state, token, thread)
    assert sum(row["message"]["type"] == "human" for row in transcript) == 3
    sql = [row["payload"] for row in events_before if row["kind"] == "sql"]
    assert any("invoice_balances" in row["sql"] for row in sql)
    assert any("payment_allocations" in row["sql"] for row in sql)
    assert any("credit_notes" in row["sql"] for row in sql)
    report = {
        "status": "passed",
        "provider": "local Ollama",
        "model": args.model,
        "thread_id": thread,
        "cli_process_ids": pids,
        "turns": outputs,
        "accepted_user_messages": 3,
        "model_requests": sum(row["kind"] == "model_request" for row in events_before),
        "executed_queries": sql,
        "duplicate_submission": "same run/result, no new event",
        "cross_owner_read": "denied",
        "fake_model": False,
        "money_answer_checks": "GBP 700.00 balance, GBP 450.00 allocation, GBP 50.00 credit",
        "provider_marker_present": any("<tool_call>" in answer for answer in answers),
    }
    write_json(output / "validation.json", report)
    (output / "trace.json").write_text(
        export_trace(root, state, token, thread, "json"), encoding="utf-8"
    )
    (output / "trace.md").write_text(export_trace(root, state, token, thread), encoding="utf-8")
    print(f"Live provider verification passed: {output / 'validation.json'}", flush=True)


if __name__ == "__main__":
    main()
