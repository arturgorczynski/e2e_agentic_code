"""Install reviewed v4 sales portfolios while preserving the mutable exercise DB.

Preview by default. Stop the portal before --apply. This changes only the
customer-to-account-manager relationship; no source invoice or document changes.
"""

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from acme.dataset import baseline_manifest, connect, initialize_state, verify_dataset
from acme.source_data import sha256
from scripts.assign_account_managers import apply_changes, changes


def inspect(project, review):
    baseline = project / "data/company/baseline"
    old = json.loads((baseline / "manifest.json").read_text("utf-8"))
    new = baseline_manifest(review)
    receipt = json.loads((project / "state/baseline.json").read_text("utf-8"))
    if old["dataset_version"] != "acme-company-v3" or new["dataset_version"] != "acme-company-v4":
        raise ValueError("Expected installed v3 and reviewed v4 bundles")
    if old["profile"] != new["profile"] or new["profile"] != "full":
        raise ValueError("Both company bundles must use the full profile")
    if receipt["content_sha256"] != old["content_sha256"]:
        raise ValueError("Exercise receipt differs from the installed v3 baseline")
    if sha256(baseline / "company.sqlite.gz") != old["archive_sha256"]:
        raise ValueError("Installed v3 archive checksum mismatch")
    if old["documents_catalog_sha256"] != new["documents_catalog_sha256"]:
        raise ValueError("Document catalog changed; this installer cannot apply it")
    changed = {
        name
        for name, old_table in old["tables"].items()
        if old_table["sha256"] != new["tables"][name]["sha256"]
    }
    if changed != {"customers"}:
        raise ValueError(f"Expected only customer relationship changes, found {sorted(changed)}")
    db = connect(project / "state/company.sqlite", readonly=True)
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
    backup = state / "backups" / f"bundle-before-v4-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(database) as source, sqlite3.connect(backup / "company.sqlite") as target:
        source.backup(target)
    shutil.copy2(receipt, backup / "baseline.json")
    stage = data / "company" / f"baseline-v4-stage-{stamp}"
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
        replacement_receipt = state / f"baseline-v4-{stamp}.json"
        replacement_receipt.write_text(
            json.dumps(
                {
                    "dataset_version": "acme-company-v4",
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
            baseline.rename(backup / "failed-v4-baseline")
        if old_moved:
            (backup / "baseline").rename(baseline)
        shutil.copy2(backup / "company.sqlite", database)
        shutil.copy2(backup / "baseline.json", receipt)
        raise
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Back up and install v4")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    review = project / "artifacts/company-v4-portfolios-review"
    old, new, planned = inspect(project, review)
    report = {
        "from": old["dataset_version"],
        "to": new["dataset_version"],
        "review_bundle": str(review),
        "customer_candidates": len(planned),
        "applied": False,
    }
    if args.apply:
        verify_dataset(project, review)
        report["backup"] = str(install(project, review, new, planned))
        report["applied"] = True
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
