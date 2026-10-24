"""Install the reviewed v3 authored-data bundle without resetting exercises.

Preview by default. Stop the portal before --apply. The installer verifies the
new bundle, backs up the current SQLite database and baseline, migrates only
untouched v2 placeholders, then updates the fixed bundle and state receipt.
"""

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from acme.dataset import baseline_manifest, connect, initialize_state, verify_dataset
from acme.source_data import sha256
from scripts.polish_authored_data import apply_changes, changes

CHANGED_TABLES = frozenset({"addresses", "suppliers", "employees", "employee_assignments"})


def inspect(project, review):
    old_baseline = project / "data/company/baseline"
    state = project / "state"
    old = json.loads((old_baseline / "manifest.json").read_text("utf-8"))
    new = baseline_manifest(review)
    receipt = json.loads((state / "baseline.json").read_text("utf-8"))
    if old["dataset_version"] != "acme-company-v2" or new["dataset_version"] != "acme-company-v3":
        raise ValueError("Expected an installed v2 baseline and a reviewed v3 bundle")
    if old["profile"] != new["profile"] or old["profile"] != "full":
        raise ValueError("The installed and reviewed profiles must both be full")
    if receipt["content_sha256"] != old["content_sha256"]:
        raise ValueError("Exercise receipt differs from the installed v2 baseline")
    if sha256(old_baseline / "company.sqlite.gz") != old["archive_sha256"]:
        raise ValueError("Installed v2 archive checksum mismatch")
    if old["documents_catalog_sha256"] != new["documents_catalog_sha256"]:
        raise ValueError("Document catalog changed; this data-only installer cannot apply it")
    changed = {
        name
        for name, old_table in old["tables"].items()
        if old_table["sha256"] != new["tables"][name]["sha256"]
    }
    if changed != CHANGED_TABLES:
        raise ValueError(f"Unexpected baseline table changes: {sorted(changed)}")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        planned = changes(db)
    finally:
        db.close()
    return old, new, planned


def install(project, review, new, planned):
    state = project / "state"
    data = project / "data"
    database = state / "company.sqlite"
    receipt = state / "baseline.json"
    baseline = data / "company/baseline"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = state / "backups" / f"bundle-before-v3-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(database) as source, sqlite3.connect(backup / "company.sqlite") as target:
        source.backup(target)
    shutil.copy2(receipt, backup / "baseline.json")
    stage = data / "company" / f"baseline-v3-stage-{stamp}"
    shutil.copytree(review / "company/baseline", stage)
    old_moved = False
    new_moved = False
    try:
        db = connect(database)
        try:
            apply_changes(db, planned)
        finally:
            db.close()
        baseline.rename(backup / "baseline")
        old_moved = True
        stage.rename(baseline)
        new_moved = True
        replacement_receipt = state / f"baseline-v3-{stamp}.json"
        replacement_receipt.write_text(
            json.dumps(
                {
                    "dataset_version": "acme-company-v3",
                    "content_sha256": new["content_sha256"],
                    "profile": new["profile"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        replacement_receipt.replace(receipt)
        baseline_manifest(data)
        initialize_state(project, state)
    except Exception:
        if new_moved:
            baseline.rename(backup / "failed-v3-baseline")
        if old_moved:
            (backup / "baseline").rename(baseline)
        shutil.copy2(backup / "company.sqlite", database)
        shutil.copy2(backup / "baseline.json", receipt)
        raise
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Back up and install v3")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    review = project / "artifacts/company-v3-realism-review"
    old, new, planned = inspect(project, review)
    report = {
        "from": old["dataset_version"],
        "to": new["dataset_version"],
        "review_bundle": str(review),
        "mutable_candidates": {name: len(rows) for name, rows in planned.items()},
        "applied": False,
    }
    if args.apply:
        verify_dataset(project, review)
        report["backup"] = str(install(project, review, new, planned))
        report["applied"] = True
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
