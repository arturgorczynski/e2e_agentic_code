"""Preview or apply fictional sales-portfolio assignments in an existing v3 copy.

Only observed customers still assigned to the original single account manager
are candidates. Demo scenario accounts and manually changed assignments stay put.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from acme.company_data import account_manager_for


def changes(db):
    result = []
    for identifier, source_id, old_manager in db.execute(
        "SELECT id,source_customer_id,account_manager_id FROM customers "
        "WHERE source_customer_id IS NOT NULL AND account_manager_id='EMP-003'"
    ):
        revised = account_manager_for(db, identifier, source_id)
        if revised != old_manager:
            result.append((revised, identifier, old_manager))
    return result


def apply_changes(db, planned):
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("BEGIN IMMEDIATE")
    try:
        for assignment in planned:
            if db.execute(
                "UPDATE customers SET account_manager_id=? "
                "WHERE id=? AND account_manager_id=? AND source_customer_id IS NOT NULL",
                assignment,
            ).rowcount != 1:
                raise ValueError("Customer assignment changed since preview; no changes committed")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Foreign-key check failed")
        db.commit()
    except Exception:
        db.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "state/company.sqlite",
    )
    parser.add_argument("--apply", action="store_true", help="Back up and update the database")
    args = parser.parse_args()
    database = args.database.resolve()
    db = sqlite3.connect(
        f"file:{database.as_posix()}?mode={'rw' if args.apply else 'ro'}", uri=True
    )
    try:
        planned = changes(db)
        report = {"database": str(database), "candidates": len(planned), "sample": planned[:5]}
        if args.apply and planned:
            backup = (
                database.parent
                / "backups"
                / (
                    "company-before-portfolios-"
                    + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    + ".sqlite"
                )
            )
            backup.parent.mkdir(exist_ok=True)
            with sqlite3.connect(backup) as copy:
                db.backup(copy)
            apply_changes(db, planned)
            report["backup"] = str(backup)
            report["applied"] = True
        else:
            report["applied"] = False
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
