"""Preview or install reviewed v5 logistics history without discarding local edits.

Stop the portal before --apply. A changed shipment or purchase field in the
mutable exercise copy aborts the entire transaction instead of overwriting it.
"""

import argparse
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from acme.company_validation import ZERO_QUERIES
from acme.dataset import (
    baseline_manifest,
    connect,
    initialize_state,
    unpack_database,
    verify_dataset,
)
from acme.source_data import sha256

FIELDS = {
    "shipments": ("delivered_on", "carrier"),
    "purchase_orders": ("placed_on", "expected_on"),
    "goods_receipts": ("received_on",),
    "stock_movements": ("occurred_on",),
}
CHECKS = (
    "purchase supplier matches catalog",
    "dispatch chronology",
    "every dispatch has one matching movement",
    "every receipt has one matching movement",
    "stock never becomes negative",
)


def plan_changes(old_database: Path, new_database: Path) -> dict:
    """Compare every row; permit only the four declared sets of mutable fields."""
    db = connect(old_database, readonly=True)
    try:
        db.execute("ATTACH DATABASE ? AS revised", (new_database.resolve().as_uri() + "?mode=ro",))
        planned = {}
        for table, fields in FIELDS.items():
            for left, right in (("main", "revised"), ("revised", "main")):
                missing = db.execute(
                    f"SELECT id FROM {left}.{table} EXCEPT SELECT id FROM {right}.{table} LIMIT 1"
                ).fetchone()
                if missing:
                    raise ValueError(f"{table} has added or removed IDs: {missing[0]}")
            columns = [row[1] for row in db.execute(f"PRAGMA main.table_info({table})")]
            stable = [column for column in columns if column not in fields and column != "id"]
            mismatch = " OR ".join(f'a."{column}" IS NOT b."{column}"' for column in stable)
            if db.execute(
                f"SELECT a.id FROM main.{table} a JOIN revised.{table} b ON a.id=b.id "
                f"WHERE {mismatch} LIMIT 1"
            ).fetchone():
                raise ValueError(f"{table} changed outside approved v5 timeline fields")
            before = ",".join(f'a."{field}"' for field in fields)
            after = ",".join(f'b."{field}"' for field in fields)
            changed = " OR ".join(f'a."{field}" IS NOT b."{field}"' for field in fields)
            rows = db.execute(
                f"SELECT a.id,{before},{after} FROM main.{table} a "
                f"JOIN revised.{table} b ON a.id=b.id WHERE {changed} ORDER BY a.id"
            ).fetchall()
            width = len(fields)
            planned[table] = [
                (row[0], tuple(row[1 : width + 1]), tuple(row[width + 1 :])) for row in rows
            ]
        return planned
    finally:
        db.close()


def legacy_supplier_repairs(old_database: Path, state_database: Path) -> list:
    """Map legacy supplier IDs to the matching v4 records without changing amounts."""
    baseline = connect(old_database, readonly=True)
    state = connect(state_database, readonly=True)
    try:
        new_items = {
            (row["product_id"], row["purchase_order_id"][-7:]): dict(row)
            for row in baseline.execute("SELECT * FROM purchase_order_items")
            if state.execute(
                "SELECT 1 FROM purchase_order_items WHERE id=?", (row["id"],)
            ).fetchone() is None
        }
        legacy_candidates = [
            row for row in state.execute("SELECT * FROM purchase_order_items")
            if (
                (row["product_id"], row["purchase_order_id"][-7:]) in new_items
                and baseline.execute(
                    "SELECT 1 FROM purchase_order_items WHERE id=?", (row["id"],)
                ).fetchone() is None
            )
        ]
        old_items = {
            (row["product_id"], row["purchase_order_id"][-7:]): dict(row)
            for row in legacy_candidates
        }
        if len(old_items) != len(legacy_candidates):
            raise ValueError("More than one legacy purchase line maps to a baseline line")
        if old_items.keys() != new_items.keys():
            raise ValueError("Legacy purchase lines do not match baseline products and months")
        repairs = []
        for key in sorted(old_items):
            old_item, new_item = old_items[key], new_items[key]
            if old_item["product_id"] != new_item["product_id"] or (
                old_item["quantity"] != new_item["quantity"]
            ):
                raise ValueError(f"Legacy purchase quantity changed: {old_item['id']}")
            target_supplier = baseline.execute(
                "SELECT supplier_id FROM purchase_orders WHERE id=?",
                (new_item["purchase_order_id"],),
            ).fetchone()[0]
            state_supplier = state.execute(
                "SELECT supplier_id FROM products WHERE id=?", (key[0],)
            ).fetchone()[0]
            if target_supplier != state_supplier:
                raise ValueError(f"Product supplier changed since baseline: {key[0]}")
            old_receipt = state.execute(
                "SELECT * FROM goods_receipts WHERE purchase_order_item_id=?", (old_item["id"],)
            ).fetchone()
            new_receipt = baseline.execute(
                "SELECT * FROM goods_receipts WHERE purchase_order_item_id=?", (new_item["id"],)
            ).fetchone()
            if old_receipt is None or new_receipt is None:
                raise ValueError(f"Legacy receipt missing: {old_item['id']}")
            old_receipt, new_receipt = dict(old_receipt), dict(new_receipt)
            if any(
                old_receipt[field] != new_receipt[field]
                for field in ("received_on", "quantity")
            ):
                raise ValueError(f"Legacy receipt was edited: {old_receipt['id']}")
            old_move = state.execute(
                "SELECT * FROM stock_movements WHERE goods_receipt_id=?", (old_receipt["id"],)
            ).fetchone()
            new_move = baseline.execute(
                "SELECT * FROM stock_movements WHERE goods_receipt_id=?", (new_receipt["id"],)
            ).fetchone()
            if old_move is None or new_move is None:
                raise ValueError(f"Legacy stock movement missing: {old_receipt['id']}")
            old_move, new_move = dict(old_move), dict(new_move)
            stable_fields = (
                "warehouse_id", "product_id", "occurred_on", "kind", "quantity",
                "shipment_item_id",
            )
            if any(old_move[field] != new_move[field] for field in stable_fields):
                raise ValueError(f"Legacy stock movement was edited: {old_move['id']}")
            for table, target in (
                ("goods_receipts", new_receipt), ("stock_movements", new_move)
            ):
                if state.execute(
                    f"SELECT 1 FROM {table} WHERE id=?", (target["id"],)
                ).fetchone():
                    raise ValueError(f"Target {table} ID already exists: {target['id']}")
            repairs.append(
                ((old_item, new_item), (old_receipt, new_receipt), (old_move, new_move))
            )
        for table, position in (("goods_receipts", 1), ("stock_movements", 2)):
            expected = {repair[position][1]["id"] for repair in repairs}
            missing = {
                row[0] for row in baseline.execute(f"SELECT id FROM {table}")
                if state.execute(f"SELECT 1 FROM {table} WHERE id=?", (row[0],)).fetchone()
                is None
            }
            if missing != expected:
                raise ValueError(f"Unexpected missing {table} rows in exercise state")
        return repairs
    finally:
        baseline.close()
        state.close()


def apply_changes(db: sqlite3.Connection, planned: dict, repairs: list = ()) -> None:
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("BEGIN IMMEDIATE")
    try:
        for repair in repairs:
            for table, (old_record, new_record) in zip(
                ("purchase_order_items", "goods_receipts", "stock_movements"), repair
            ):
                current = db.execute(
                    f"SELECT * FROM {table} WHERE id=?", (old_record["id"],)
                ).fetchone()
                if current is None or dict(current) != old_record:
                    raise ValueError(f"Legacy {table}/{old_record['id']} changed since preview")
                if db.execute(
                    f"SELECT 1 FROM {table} WHERE id=?", (new_record["id"],)
                ).fetchone():
                    raise ValueError(f"Target {table}/{new_record['id']} appeared since preview")
            for table, (old_record, _new_record) in zip(
                ("stock_movements", "goods_receipts", "purchase_order_items"), reversed(repair)
            ):
                db.execute(f"DELETE FROM {table} WHERE id=?", (old_record["id"],))
            for table, (_old_record, new_record) in zip(
                ("purchase_order_items", "goods_receipts", "stock_movements"), repair
            ):
                columns = ",".join(new_record)
                placeholders = ",".join("?" for _ in new_record)
                db.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                    tuple(new_record.values()),
                )
        for table, fields in FIELDS.items():
            sets = ",".join(f'"{field}"=?' for field in fields)
            guard = " AND ".join(f'"{field}" IS ?' for field in fields)
            sql = f"UPDATE {table} SET {sets} WHERE id=? AND {guard}"
            for identifier, old_values, new_values in planned[table]:
                if db.execute(sql, (*new_values, identifier, *old_values)).rowcount != 1:
                    raise ValueError(
                        f"{table}/{identifier} changed since baseline; no edits committed"
                    )
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Foreign-key check failed")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        for label in CHECKS:
            if db.execute(ZERO_QUERIES[label]).fetchone()[0]:
                raise ValueError(f"Business chronology check failed: {label}")
        db.commit()
    except Exception:
        db.rollback()
        raise


def inspect(project: Path, review: Path) -> tuple[dict, dict, dict, list]:
    baseline = project / "data/company/baseline"
    old = json.loads((baseline / "manifest.json").read_text("utf-8"))
    new = baseline_manifest(review)
    receipt = json.loads((project / "state/baseline.json").read_text("utf-8"))
    if old["dataset_version"] != "acme-company-v4" or new["dataset_version"] != "acme-company-v5":
        raise ValueError("Expected installed v4 and reviewed v5 bundles")
    if old["profile"] != "full" or new["profile"] != "full":
        raise ValueError("Both company bundles must use the full profile")
    if receipt["content_sha256"] != old["content_sha256"]:
        raise ValueError("Exercise receipt differs from installed v4 baseline")
    if sha256(baseline / "company.sqlite.gz") != old["archive_sha256"]:
        raise ValueError("Installed v4 archive checksum mismatch")
    if old["schema_sha256"] != new["schema_sha256"]:
        raise ValueError("Schema changed; this installer cannot apply it")
    if old["documents_catalog_sha256"] != new["documents_catalog_sha256"]:
        raise ValueError("Document catalog changed; this installer cannot apply it")
    changed = {
        name for name, old_table in old["tables"].items()
        if old_table["sha256"] != new["tables"][name]["sha256"]
    }
    if changed != set(FIELDS):
        raise ValueError(f"Expected four timeline tables, found {sorted(changed)}")
    with tempfile.TemporaryDirectory(prefix="v5-baseline-", dir=project / "artifacts") as temporary:
        old_database = Path(temporary) / "old.sqlite"
        new_database = Path(temporary) / "new.sqlite"
        unpack_database(project / "data", old_database, old)
        unpack_database(review, new_database, new)
        planned = plan_changes(old_database, new_database)
        repairs = legacy_supplier_repairs(old_database, project / "state/company.sqlite")
    return old, new, planned, repairs


def install(project: Path, review: Path, new: dict, planned: dict, repairs: list) -> Path:
    state = project / "state"
    data = project / "data"
    database = state / "company.sqlite"
    receipt = state / "baseline.json"
    baseline = data / "company/baseline"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = state / "backups" / f"bundle-before-v5-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(database) as source, sqlite3.connect(backup / "company.sqlite") as target:
        source.backup(target)
    shutil.copy2(receipt, backup / "baseline.json")
    stage = data / "company" / f"baseline-v5-stage-{stamp}"
    shutil.copytree(review / "company/baseline", stage)
    old_moved = False
    new_moved = False
    try:
        db = connect(database)
        try:
            apply_changes(db, planned, repairs)
        finally:
            db.close()
        baseline.rename(backup / "baseline")
        old_moved = True
        stage.rename(baseline)
        new_moved = True
        replacement = state / f"baseline-v5-{stamp}.json"
        replacement.write_text(
            json.dumps(
                {
                    "dataset_version": "acme-company-v5",
                    "content_sha256": new["content_sha256"],
                    "profile": new["profile"],
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        replacement.replace(receipt)
        baseline_manifest(data)
        initialize_state(project, state)
    except Exception:
        if new_moved:
            baseline.rename(backup / "failed-v5-baseline")
        if old_moved:
            (backup / "baseline").rename(baseline)
        shutil.copy2(backup / "company.sqlite", database)
        shutil.copy2(backup / "baseline.json", receipt)
        raise
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Back up and install v5")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    review = project / "artifacts/company-v5-logistics-review"
    old, new, planned, repairs = inspect(project, review)
    report = {
        "from": old["dataset_version"],
        "to": new["dataset_version"],
        "review_bundle": str(review),
        "field_changes": {table: len(rows) for table, rows in planned.items()},
        "legacy_supplier_links_repaired": len(repairs),
        "applied": False,
    }
    if args.apply:
        verify_dataset(project, review)
        report["backup"] = str(install(project, review, new, planned, repairs))
        report["applied"] = True
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
