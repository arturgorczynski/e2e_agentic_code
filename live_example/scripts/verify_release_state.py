"""G13 full-data and explicit reset rehearsal in a disposable exercise directory.

No model, browser, Docker or learner state is used. Runtime/UI acceptance is separate.
Run: uv run python scripts/verify_release_state.py
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from acme.app_store import RunContext, login, new_thread, provision
from acme.company_tools import decide, execute
from acme.company_validation import scenario_evidence
from acme.dataset import connect, initialize_state, verify_dataset
from acme.source_data import write_json

ROOT = Path(__file__).resolve().parents[1]


def scenarios(state):
    db = connect(state / "company.sqlite", readonly=True)
    try:
        return scenario_evidence(db, ROOT)
    finally:
        db.close()


def change_ticket(state, token, title):
    thread = new_thread(ROOT, state, token, title)
    context = RunContext(ROOT, state, ROOT / "data", token, thread, "release-reset")
    proposal = execute(
        context,
        "update_ticket",
        {
            "ticket_id": "DEMO-TKT-004",
            "expected_status": "open",
            "new_status": "in_progress",
            "reason": "Review the release rehearsal complaint",
        },
    )
    assert proposal["status"] == "pending_approval", proposal
    accepted = decide(context, proposal["operation_id"], "approve")
    assert accepted == decide(context, proposal["operation_id"], "approve")
    return proposal["operation_id"]


def verify():
    started = perf_counter()
    integrity = verify_dataset(ROOT, ROOT / "data")
    integrity_seconds = perf_counter() - started
    with tempfile.TemporaryDirectory(prefix="acme-release-reset-") as temporary:
        state = Path(temporary)
        initialize_state(ROOT, state)
        before = scenarios(state)
        provision(ROOT, state, "sam.support", "disposable-release-reset")
        token = login(state, "sam.support", "disposable-release-reset")
        first = change_ticket(state, token, "Before reset")
        assert scenarios(state)["S04"]["status_before"] == "in_progress"
        command = [
            sys.executable,
            "-I",
            "-B",
            "-m",
            "acme",
            "company",
            "reset",
            "--project-dir",
            str(ROOT),
            "--state-dir",
            str(state),
        ]
        refused = subprocess.run(command, capture_output=True, text=True, timeout=60)
        assert refused.returncode != 0 and "--yes" in refused.stderr
        assert scenarios(state)["S04"]["status_before"] == "in_progress"
        reset = subprocess.run(
            command + ["--yes"], capture_output=True, text=True, check=True, timeout=120
        )
        assert json.loads(reset.stdout)["status"] == "reset"
        after = scenarios(state)
        assert before == after, "Reset must reproduce all stored baseline scenario facts"
        second = change_ticket(state, token, "Fresh exercise after reset")
        assert first != second
        db = connect(state / "company.sqlite", readonly=True)
        try:
            assert (
                db.execute("SELECT COUNT(*) FROM ticket_events WHERE id=?", (second,)).fetchone()[0]
                == 1
            )
            assert (
                db.execute("SELECT COUNT(*) FROM ticket_events WHERE id=?", (first,)).fetchone()[0]
                == 0
            )
        finally:
            db.close()
    return {
        "scope": (
            "Full baseline integrity and disposable company-reset rehearsal; no inference or Docker"
        ),
        "status": "passed",
        "integrity_seconds": round(integrity_seconds, 3),
        "total_seconds": round(perf_counter() - started, 3),
        "integrity": integrity,
        "reset_checks": {
            "confirmation_required": True,
            "refusal_preserves_mutation": True,
            "all_scenario_facts_restored": before == after,
            "fresh_thread_reproduces_one_approved_write": True,
            "duplicate_decision_has_no_extra_write": True,
        },
        "reset_boundary": (
            "Company data resets. Accounts, transcripts and historical approvals remain; "
            "use a new thread for a new exercise."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/g13_state_validation.json")
    args = parser.parse_args()
    result = verify()
    write_json(args.output, result)
    print(json.dumps({key: value for key, value in result.items() if key != "integrity"}, indent=2))


if __name__ == "__main__":
    main()
