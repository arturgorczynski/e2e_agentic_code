"""Install the explicit fictional 2026 cash ledger into an exercise database.

This does not alter the verified historical baseline. A SQLite online backup is
written before installing the extension. Re-running keeps edited seed rows.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from acme.dataset import connect
from acme.expense_ledger import seed_expenses


def install(state: Path) -> dict:
    source = state / "company.sqlite"
    if not source.is_file():
        raise ValueError("Set up the company database first")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = state / "backups" / f"expense-ledger-{stamp}-{uuid4().hex[:6]}"
    backup.mkdir(parents=True, exist_ok=False)
    original = connect(source, readonly=True)
    saved = connect(backup / "company.sqlite")
    try:
        original.backup(saved)
    finally:
        saved.close()
        original.close()
    outcome = seed_expenses(state)
    db = connect(source, readonly=True)
    try:
        rows = [dict(row) for row in db.execute(
            "SELECT id,paid_on,category,amount_pence,supplier_id,purchase_order_id,"
            "provenance FROM company_expenses ORDER BY id"
        )]
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Expense installation has broken references")
    finally:
        db.close()
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    report = {**outcome, "backup": str(backup / "company.sqlite"),
              "rows_sha256": digest, "total_pence": sum(row["amount_pence"] for row in rows),
              "source": "explicit fictional 2026 expense seed; no observed supplier payments"}
    (backup / "install_report.json").write_text(
        json.dumps(report, indent=2) + "\n", "utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path("state"))
    args = parser.parse_args()
    print(json.dumps(install(args.state_dir), indent=2))


if __name__ == "__main__":
    main()
