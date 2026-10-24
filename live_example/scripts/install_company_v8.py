"""Install a reviewed v8 procurement bundle while carrying forward local address edits.

Preview by default. Stop the portal before --apply. Any unexpected exercise
database difference from v7 aborts the install, preserving the current copy.
"""

import argparse
import json
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from acme.company_validation import validate_company
from acme.dataset import (
    baseline_manifest,
    connect,
    initialize_state,
    unpack_database,
    verify_dataset,
)
from acme.source_data import sha256

CHANGED_TABLES = {
    "document_versions",
    "goods_receipts",
    "inventory",
    "purchase_order_items",
    "purchase_orders",
    "stock_movements",
}
EDITABLE_DELTAS = ("addresses", "customers")


def copy_sqlite(source_path: Path, destination_path: Path) -> None:
    """Copy a complete database through SQLite, including an existing destination."""
    with closing(sqlite3.connect(source_path)) as source, closing(
        sqlite3.connect(destination_path, timeout=10)
    ) as destination:
        source.backup(destination)


def collect_local_edits(old_database: Path, state_database: Path) -> dict:
    """Capture verified local edits while refusing unrelated baseline drift."""
    db = connect(old_database, readonly=True)
    try:
        db.execute(
            "ATTACH DATABASE ? AS exercise", (state_database.resolve().as_uri() + "?mode=ro",)
        )
        result = {table: {"added": [], "changed": []} for table in EDITABLE_DELTAS}
        tables = [row[0] for row in db.execute(
            "SELECT name FROM main.sqlite_master WHERE type='table' ORDER BY name"
        )]
        for table in tables:
            missing = db.execute(
                f"SELECT id FROM main.{table} EXCEPT SELECT id FROM exercise.{table} LIMIT 1"
            ).fetchone()
            if missing:
                raise ValueError(f"Exercise database is missing {table}/{missing[0]}")
            extra = db.execute(
                f"SELECT id FROM exercise.{table} EXCEPT SELECT id FROM main.{table} LIMIT 1"
            ).fetchone()
            if extra and table != "addresses":
                raise ValueError(f"Exercise database has an unhandled {table}/{extra[0]}")
            columns = [row[1] for row in db.execute(f"PRAGMA main.table_info({table})")]
            fields = [column for column in columns if column != "id"]
            predicate = " OR ".join(f'a."{field}" IS NOT b."{field}"' for field in fields)
            changed_ids = [row[0] for row in db.execute(
                f"SELECT a.id FROM main.{table} a JOIN exercise.{table} b ON a.id=b.id "
                f"WHERE {predicate} ORDER BY a.id"
            )]
            if changed_ids and table not in EDITABLE_DELTAS:
                raise ValueError(f"Exercise database has an unhandled edit to {table}")
            if table in EDITABLE_DELTAS:
                if table == "addresses":
                    result[table]["added"] = [dict(row) for row in db.execute(
                        "SELECT b.* FROM exercise.addresses b "
                        "WHERE NOT EXISTS(SELECT 1 FROM main.addresses a WHERE a.id=b.id) "
                        "ORDER BY b.id"
                    )]
                for identifier in changed_ids:
                    before = dict(db.execute(
                        f"SELECT * FROM main.{table} WHERE id=?", (identifier,)
                    ).fetchone())
                    after = dict(db.execute(
                        f"SELECT * FROM exercise.{table} WHERE id=?", (identifier,)
                    ).fetchone())
                    delta = {
                        field: (before[field], after[field])
                        for field in fields if before[field] != after[field]
                    }
                    result[table]["changed"].append((identifier, delta))
        return result
    finally:
        db.close()


def replay_local_edits(database: Path, edits: dict) -> None:
    db = connect(database)
    try:
        db.execute("BEGIN IMMEDIATE")
        for row in edits["addresses"]["added"]:
            columns = ",".join(row)
            placeholders = ",".join("?" for _ in row)
            db.execute(
                f"INSERT INTO addresses ({columns}) VALUES ({placeholders})",
                tuple(row.values()),
            )
        for table in EDITABLE_DELTAS:
            for identifier, delta in edits[table]["changed"]:
                current = db.execute(f"SELECT * FROM {table} WHERE id=?", (identifier,)).fetchone()
                if current is None:
                    raise ValueError(f"New baseline is missing edited {table}/{identifier}")
                for field, (before, after) in delta.items():
                    if current[field] != before:
                        raise ValueError(f"New baseline also changed {table}/{identifier}.{field}")
                    if db.execute(
                        f'UPDATE {table} SET "{field}"=? WHERE id=? AND "{field}" IS ?',
                        (after, identifier, before),
                    ).rowcount != 1:
                        raise ValueError(f"Could not replay {table}/{identifier}.{field}")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Local edit replay produced an orphaned relationship")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def inspect(project: Path, review: Path) -> tuple[dict, dict, dict]:
    baseline = project / "data/company/baseline"
    old = json.loads((baseline / "manifest.json").read_text("utf-8"))
    new = baseline_manifest(review)
    receipt = json.loads((project / "state/baseline.json").read_text("utf-8"))
    if old["dataset_version"] != "acme-company-v7" or new["dataset_version"] != "acme-company-v8":
        raise ValueError("Expected installed v7 and reviewed v8 bundles")
    if old["profile"] != "full" or new["profile"] != "full":
        raise ValueError("Both company bundles must use the full profile")
    if receipt["content_sha256"] != old["content_sha256"]:
        raise ValueError("Exercise receipt differs from installed v5 baseline")
    if sha256(baseline / "company.sqlite.gz") != old["archive_sha256"]:
        raise ValueError("Installed v5 archive checksum mismatch")
    if sha256(project / "data/documents/catalog.json") != old["documents_catalog_sha256"]:
        raise ValueError("Installed v5 document catalog checksum mismatch")
    catalog = json.loads((project / "data/documents/catalog.json").read_text("utf-8"))
    for item in catalog["documents"]:
        if sha256(project / "data/documents" / item["relative_path"]) != item["sha256"]:
            raise ValueError(f"Installed document changed: {item['document_id']}")
    if old["schema_sha256"] != new["schema_sha256"]:
        raise ValueError("Schema changed; this installer cannot apply it")
    changed = {
        name for name, old_table in old["tables"].items()
        if old_table["sha256"] != new["tables"][name]["sha256"]
    }
    if changed != CHANGED_TABLES:
        raise ValueError(f"Unexpected v8 changed tables: {sorted(changed)}")
    for name in ("invoices", "invoice_items", "order_items", "price_history"):
        if old["tables"][name] != new["tables"][name]:
            raise ValueError(f"Observed source evidence changed: {name}")
    with tempfile.TemporaryDirectory(prefix="v8-baseline-", dir=project / "artifacts") as temporary:
        old_database = Path(temporary) / "old.sqlite"
        unpack_database(project / "data", old_database, old)
        edits = collect_local_edits(old_database, project / "state/company.sqlite")
    return old, new, edits


def install(project: Path, review: Path, new: dict, edits: dict) -> Path:
    state = project / "state"
    data = project / "data"
    database = state / "company.sqlite"
    receipt = state / "baseline.json"
    baseline = data / "company/baseline"
    documents = data / "documents"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = state / "backups" / f"bundle-before-v8-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    copy_sqlite(database, backup / "company.sqlite")
    shutil.copy2(receipt, backup / "baseline.json")
    baseline_stage = data / "company" / f"baseline-v8-stage-{stamp}"
    documents_stage = data / f"documents-v8-stage-{stamp}"
    database_stage = state / f"company-v8-stage-{stamp}.sqlite"
    old_baseline_moved = old_documents_moved = False
    new_baseline_moved = new_documents_moved = False
    try:
        shutil.copytree(review / "company/baseline", baseline_stage)
        shutil.copytree(review / "documents", documents_stage)
        unpack_database(review, database_stage, new)
        replay_local_edits(database_stage, edits)
        staged_db = connect(database_stage, readonly=True)
        try:
            validate_company(staged_db, project, documents_stage, "full")
        finally:
            staged_db.close()
        baseline.rename(backup / "baseline")
        old_baseline_moved = True
        documents.rename(backup / "documents")
        old_documents_moved = True
        baseline_stage.rename(baseline)
        new_baseline_moved = True
        documents_stage.rename(documents)
        new_documents_moved = True
        copy_sqlite(database_stage, database)
        installed_db = connect(database, readonly=True)
        try:
            validate_company(installed_db, project, documents, "full")
        finally:
            installed_db.close()
        replacement = state / f"baseline-v8-{stamp}.json"
        replacement.write_text(
            json.dumps(
                {
                    "dataset_version": "acme-company-v8",
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
        database_stage.unlink()
    except Exception:
        if new_baseline_moved:
            baseline.rename(backup / "failed-v8-baseline")
        if new_documents_moved:
            documents.rename(backup / "failed-v8-documents")
        if old_baseline_moved:
            (backup / "baseline").rename(baseline)
        if old_documents_moved:
            (backup / "documents").rename(documents)
        if baseline_stage.exists():
            baseline_stage.rename(backup / "failed-v8-baseline-stage")
        if documents_stage.exists():
            documents_stage.rename(backup / "failed-v8-documents-stage")
        if database_stage.exists():
            database_stage.rename(backup / "failed-v8-database-stage.sqlite")
        copy_sqlite(backup / "company.sqlite", database)
        shutil.copy2(backup / "baseline.json", receipt)
        raise
    return backup


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Back up and install v8")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    review = project / "artifacts/company-v8-procurement-review"
    old, new, edits = inspect(project, review)
    report = {
        "from": old["dataset_version"],
        "to": new["dataset_version"],
        "changed_tables": sorted(CHANGED_TABLES),
        "local_edits": {
            table: {kind: len(rows) for kind, rows in edits[table].items()}
            for table in EDITABLE_DELTAS
        },
        "applied": False,
    }
    if args.apply:
        verify_dataset(project, review)
        report["backup"] = str(install(project, review, new, edits))
        report["applied"] = True
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
