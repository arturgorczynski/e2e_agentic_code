"""Replace untouched v2 supplier and employee placeholders in a mutable exercise DB.

The default is a read-only preview. --apply makes an online SQLite backup before
updating rows. User-edited values are never overwritten.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from acme.company_data import SUPPLIER_PROFILES, generated_employee_profile

OLD_SUPPLIER_NAMES = (
    "Beacon Trade Supply",
    "Hearth Trade Supply",
    "Solstice Trade Supply",
    "Ledger Trade Supply",
    "Fold Trade Supply",
    "Weave Trade Supply",
    "Orchard Trade Supply",
)
NEW_ADDRESS_PROVENANCE = "authored fictional business location; no delivery address asserted"


def changes(db):
    """Return only rows that still match values written by the v2 generator."""
    supplier_names = []
    supplier_leads = []
    supplier_addresses = []
    for index, (name, location, lead_days) in enumerate(SUPPLIER_PROFILES, 1):
        supplier_id = f"SUP-{index:02}"
        address_id = f"ADDR-SUP-{index}"
        row = db.execute(
            "SELECT name,lead_days,address_id FROM suppliers WHERE id=?", (supplier_id,)
        ).fetchone()
        if row is None:
            continue
        if row[0] == OLD_SUPPLIER_NAMES[index - 1]:
            supplier_names.append((name, supplier_id, row[0]))
        if row[1] == 7 + index and lead_days != row[1]:
            supplier_leads.append((lead_days, supplier_id, row[1]))
        if row[2] == address_id:
            address = db.execute(
                "SELECT label,provenance FROM addresses WHERE id=?", (address_id,)
            ).fetchone()
            old_label = f"Fictional supplier office {index}; no deliverable street address"
            if address is not None and address[0] == old_label and address[1] == "authored":
                supplier_addresses.append(
                    (location, NEW_ADDRESS_PROVENANCE, address_id, old_label, "authored")
                )

    employee_titles = []
    employee_dates = []
    for row in db.execute(
        "SELECT e.id,e.job_title,e.hired_on,a.id,a.valid_from,d.id,d.name "
        "FROM employees e JOIN employee_assignments a ON a.employee_id=e.id "
        "JOIN departments d ON d.id=a.department_id WHERE a.valid_until IS NULL"
    ):
        employee_id, title, hired_on, assignment_id, valid_from, department_id, department = row
        if not employee_id.startswith("EMP-"):
            continue
        try:
            number = int(employee_id.rsplit("-", 1)[-1])
        except ValueError:
            continue
        if number <= 5:
            continue
        revised_title, revised_date = generated_employee_profile(employee_id, department_id)
        if title == f"{department} specialist":
            employee_titles.append((revised_title, employee_id, title))
        if hired_on == "2009-06-01" and valid_from == "2009-06-01" and revised_date != hired_on:
            employee_dates.append((revised_date, employee_id, assignment_id, hired_on))
    return {
        "supplier_names": supplier_names,
        "supplier_leads": supplier_leads,
        "supplier_addresses": supplier_addresses,
        "employee_titles": employee_titles,
        "employee_dates": employee_dates,
    }


def apply_changes(db, planned):
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("BEGIN IMMEDIATE")
    try:
        statements = {
            "supplier_names": "UPDATE suppliers SET name=? WHERE id=? AND name=?",
            "supplier_leads": "UPDATE suppliers SET lead_days=? WHERE id=? AND lead_days=?",
            "supplier_addresses": (
                "UPDATE addresses SET label=?,provenance=? "
                "WHERE id=? AND label=? AND provenance=?"
            ),
            "employee_titles": "UPDATE employees SET job_title=? WHERE id=? AND job_title=?",
        }
        for group, sql in statements.items():
            for row in planned[group]:
                if db.execute(sql, row).rowcount != 1:
                    raise ValueError(f"{group} changed since preview; no changes committed")
        for revised_date, employee_id, assignment_id, old_date in planned["employee_dates"]:
            if db.execute(
                "UPDATE employees SET hired_on=? WHERE id=? AND hired_on=?",
                (revised_date, employee_id, old_date),
            ).rowcount != 1:
                raise ValueError("Employee changed since preview; no changes committed")
            if db.execute(
                "UPDATE employee_assignments SET valid_from=? "
                "WHERE id=? AND valid_from=?",
                (revised_date, assignment_id, old_date),
            ).rowcount != 1:
                raise ValueError("Assignment changed since preview; no changes committed")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Foreign-key check failed")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
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
        report = {
            "database": str(database),
            "candidates": {group: len(rows) for group, rows in planned.items()},
            "sample": {group: rows[:2] for group, rows in planned.items()},
            "applied": False,
        }
        if args.apply and any(planned.values()):
            backup = (
                database.parent
                / "backups"
                / (
                    "company-before-realism-"
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
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
