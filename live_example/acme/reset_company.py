"""Preview and reset local company edits against the verified installed baseline."""

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from acme.dataset import baseline_manifest, connect, unpack_database
from acme.document_revision import _assert_original_register, apply_revision_register
from acme.expense_ledger import ensure_expense_schema, has_expense_ledger

MAX_PREVIEW_ROWS = 2000
DOCUMENT_TABLES = {"documents", "document_versions", "document_links"}


def _tables(db: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]


def _difference(db: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    columns = [row["name"] for row in db.execute(f'PRAGMA table_info("{table}")')]
    if "id" not in columns:
        raise ValueError(f"Cannot reset table without an ID: {table}")
    different = " OR ".join(
        f'live."{column}" IS NOT base."{column}"' for column in columns if column != "id"
    )
    added = db.execute(
        f'SELECT live.id FROM main."{table}" live LEFT JOIN baseline."{table}" base '
        "ON base.id=live.id WHERE base.id IS NULL"
    )
    modified = db.execute(
        f'SELECT live.id FROM main."{table}" live JOIN baseline."{table}" base '
        f"ON base.id=live.id WHERE {different}"
    )
    removed = db.execute(
        f'SELECT base.id FROM baseline."{table}" base LEFT JOIN main."{table}" live '
        "ON live.id=base.id WHERE live.id IS NULL"
    )
    return (
        [("added", row[0]) for row in added]
        + [("modified", row[0]) for row in modified]
        + [("removed", row[0]) for row in removed]
    )


def _stamp(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _release_case_customers(db: sqlite3.Connection, revised: list[dict]) -> list[str]:
    customers = set()
    for item in revised:
        if not item["document_id"].startswith("CASE-"):
            continue
        ticket_id = item["record_links"]["ticket_id"]
        owner = db.execute(
            "SELECT o.customer_id FROM tickets t JOIN orders o ON o.id=t.order_id WHERE t.id=?",
            (ticket_id,),
        ).fetchone()
        if owner is None:
            raise ValueError(f"Release case lost its ticket: {ticket_id}")
        customers.add(f"customers:{owner[0]}")
    return sorted(customers)


def _release_protected_rows(db: sqlite3.Connection, state: Path) -> set[tuple[str, str]]:
    revision_path = state / "documents"
    if not (revision_path / "installed.json").is_file():
        return set()
    revised = json.loads((revision_path / "catalog.json").read_text("utf-8"))["documents"]
    _assert_original_register(db, revised)
    keep, _ = _preserved_rows(db, _release_case_customers(db, revised))
    return keep


def preview(state: Path, data: Path) -> dict:
    manifest = baseline_manifest(data)
    company = state / "company.sqlite"
    with tempfile.TemporaryDirectory(prefix="baseline-preview-", dir=state) as folder:
        baseline = Path(folder) / "company.sqlite"
        unpack_database(data, baseline, manifest)
        ensure_expense_schema(baseline)
        db = connect(company, readonly=True)
        try:
            db.execute("ATTACH DATABASE ? AS baseline", (str(baseline),))
            changes = []
            counts = {"added": 0, "modified": 0, "removed": 0}
            protected = _release_protected_rows(db, state)
            managed = {"documents": 0, "linked_history": 0, "fictional_expenses": 0}
            release_installed = (state / "documents" / "installed.json").is_file()
            for table in _tables(db):
                if table == "company_expenses":
                    managed["fictional_expenses"] = db.execute(
                        "SELECT COUNT(*) FROM company_expenses"
                    ).fetchone()[0]
                    continue
                for kind, identifier in _difference(db, table):
                    if release_installed and table in DOCUMENT_TABLES:
                        managed["documents"] += 1
                        continue
                    if (table, identifier) in protected:
                        managed["linked_history"] += 1
                        continue
                    counts[kind] += 1
                    if len(changes) < MAX_PREVIEW_ROWS:
                        changes.append(
                            {
                                "table": table,
                                "id": identifier,
                                "kind": kind,
                                "key": f"{table}:{identifier}",
                            }
                        )
            return {
                "baseline_version": manifest["dataset_version"],
                "stamp": _stamp(company),
                "counts": counts,
                "total": sum(counts.values()),
                "changes": changes,
                "truncated": sum(counts.values()) > len(changes),
                "release_managed": managed,
            }
        finally:
            db.close()


def _preserved_rows(
    db: sqlite3.Connection, keys: list[str]
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    tables = set(_tables(db))
    keep: set[tuple[str, str]] = set()
    removed: set[tuple[str, str]] = set()
    for key in keys:
        if ":" not in key:
            raise ValueError("Invalid preserve key")
        table, identifier = key.split(":", 1)
        if table not in tables:
            raise ValueError("Unknown preserved table")
        current = db.execute(f'SELECT id FROM main."{table}" WHERE id=?', (identifier,)).fetchone()
        baseline = db.execute(
            f'SELECT id FROM baseline."{table}" WHERE id=?', (identifier,)
        ).fetchone()
        if current:
            keep.add((table, identifier))
            if table == "customers" and identifier.startswith("SCN-CUST-"):
                suffix = identifier.removeprefix("SCN-CUST-")
                for related in (
                    "addresses",
                    "customer_contacts",
                    "orders",
                    "order_items",
                    "order_status_history",
                    "products",
                    "price_history",
                    "inventory",
                    "stock_movements",
                    "purchase_orders",
                    "purchase_order_items",
                    "goods_receipts",
                    "forecast_runs",
                    "forecasts",
                    "sales_targets",
                    "invoices",
                    "invoice_items",
                    "shipments",
                    "shipment_items",
                    "payments",
                    "payment_allocations",
                    "credit_notes",
                    "tickets",
                    "ticket_events",
                ):
                    for row in db.execute(
                        f'SELECT id FROM main."{related}" WHERE id LIKE ?', (f"SCN-%-{suffix}%",)
                    ):
                        keep.add((related, row[0]))
        elif baseline:
            removed.add((table, identifier))
        else:
            raise ValueError(f"Preserved row no longer exists in either copy: {key}")
    # A preserved new row needs its new foreign-key parents in the replacement.
    pending = list(keep)
    while pending:
        table, identifier = pending.pop()
        row = db.execute(f'SELECT * FROM main."{table}" WHERE id=?', (identifier,)).fetchone()
        for fk in db.execute(f'PRAGMA main.foreign_key_list("{table}")'):
            target, value = fk["table"], row[fk["from"]]
            if (
                value is None
                or db.execute(
                    f'SELECT 1 FROM baseline."{target}" WHERE "{fk["to"] or "id"}"=?', (value,)
                ).fetchone()
            ):
                continue
            parent = (target, str(value))
            if parent not in keep:
                keep.add(parent)
                pending.append(parent)
    return keep, removed


def reset(state: Path, data: Path, stamp: str, preserve: list[str]) -> dict:
    company = state / "company.sqlite"
    if _stamp(company) != stamp:
        raise ValueError("Company data changed since preview. Preview again before resetting")
    if len(preserve) > 2000 or len(set(preserve)) != len(preserve):
        raise ValueError("Invalid preserve selection")
    manifest = baseline_manifest(data)
    staged = state / f".company-reset-{uuid4().hex}.sqlite"
    backup = (
        state
        / "backups"
        / ("reset-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6])
    )
    backup.mkdir(parents=True, exist_ok=False)
    try:
        unpack_database(data, staged, manifest)
        ensure_expense_schema(staged)
        db = connect(company, readonly=True)
        try:
            db.execute("ATTACH DATABASE ? AS baseline", (str(staged),))
            expense_keys = (
                [f"company_expenses:{row[0]}" for row in db.execute(
                    "SELECT id FROM company_expenses"
                )]
                if has_expense_ledger(db) else []
            )
            keep, removed = _preserved_rows(db, [*preserve, *expense_keys])
            revision_path = state / "documents"
            installed_revision = (revision_path / "installed.json").is_file()
            if installed_revision:
                revised = json.loads((revision_path / "catalog.json").read_text("utf-8"))[
                    "documents"
                ]
                keep |= _release_protected_rows(db, state)
                keep = {item for item in keep if item[0] not in DOCUMENT_TABLES}
                removed = {item for item in removed if item[0] not in DOCUMENT_TABLES}
        finally:
            db.close()
        target = connect(staged)
        try:
            target.execute("PRAGMA foreign_keys=OFF")
            target.execute("ATTACH DATABASE ? AS old", (str(company),))
            target.execute("BEGIN IMMEDIATE")
            for table, identifier in sorted(keep):
                target.execute(
                    f'INSERT OR REPLACE INTO main."{table}" SELECT * FROM old."{table}" WHERE id=?',
                    (identifier,),
                )
            for table, identifier in sorted(removed):
                target.execute(f'DELETE FROM main."{table}" WHERE id=?', (identifier,))
            if installed_revision:
                originals = json.loads((data / "documents/catalog.json").read_text("utf-8"))[
                    "documents"
                ]
                apply_revision_register(target, originals, revised)
            if target.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Preserved changes leave broken table references")
            target.commit()
        except Exception:
            target.rollback()
            raise
        finally:
            target.close()
        if _stamp(company) != stamp:
            raise ValueError("Company data changed during reset. Preview again")
        shutil.copy2(company, backup / "company.sqlite")
        shutil.copy2(state / "app.sqlite", backup / "app.sqlite")
        (backup / "selection.json").write_text(
            json.dumps({"preserve": preserve}, indent=2), "utf-8"
        )
        os.replace(staged, company)
        app = connect(state / "app.sqlite")
        try:
            app.execute("ATTACH DATABASE ? AS company", (str(company),))
            if app.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='portal_edits'"
            ).fetchone():
                for row in app.execute("SELECT id,entity,record_id FROM portal_edits").fetchall():
                    if (row["entity"], row["record_id"]) not in keep:
                        app.execute("DELETE FROM portal_edits WHERE id=?", (row["id"],))
            app.execute(
                "DELETE FROM portal_personas WHERE kind='customer' AND NOT EXISTS "
                "(SELECT 1 FROM company.customers c WHERE c.id=portal_personas.subject_id)"
            )
            app.commit()
        finally:
            app.close()
        return {
            "restored": True,
            "preserved": len(keep) + len(removed),
            "backup": str(backup),
            "baseline_version": manifest["dataset_version"],
        }
    finally:
        if staged.exists():
            staged.unlink()
