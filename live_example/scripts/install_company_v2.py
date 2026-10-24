"""Install the reviewed v2 fixed bundle while retaining the mutable exercise state.

Run after `enrich_demo_data.py --apply` and `acme company verify --data-dir
artifacts/company-v2-review`. The old fixed bundle and an online state backup
are retained under state/backups. The portal should be stopped during install.
"""

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from acme.dataset import baseline_manifest, connect


def inside(project, path):
    resolved = path.resolve()
    if not resolved.is_relative_to(project.resolve()):
        raise ValueError(f"Path leaves project workspace: {resolved}")
    return resolved


def matching_table(db, name, columns="*"):
    first = db.execute(
        f"SELECT count(*) FROM (SELECT {columns} FROM main.{name} "
        f"EXCEPT SELECT {columns} FROM upgraded.{name})"
    ).fetchone()[0]
    second = db.execute(
        f"SELECT count(*) FROM (SELECT {columns} FROM upgraded.{name} "
        f"EXCEPT SELECT {columns} FROM main.{name})"
    ).fetchone()[0]
    return first == second == 0


def main():
    project = Path(__file__).resolve().parents[1]
    data = inside(project, project / "data")
    review = inside(project, project / "artifacts/company-v2-review")
    state = inside(project, project / "state")
    old_baseline = inside(project, data / "company/baseline")
    old_documents = inside(project, data / "documents")
    new_baseline = inside(project, review / "company/baseline")
    new_documents = inside(project, review / "documents")
    state_database = inside(project, state / "company.sqlite")
    new_database = inside(project, new_baseline / "company.sqlite")
    receipt_path = inside(project, state / "baseline.json")
    old_manifest = json.loads((old_baseline / "manifest.json").read_text("utf-8"))
    new_manifest = baseline_manifest(review)
    old_receipt = json.loads(receipt_path.read_text("utf-8"))
    if old_manifest["dataset_version"] != "acme-company-v1":
        raise ValueError("Current baseline is not v1; installation cancelled")
    if new_manifest["dataset_version"] != "acme-company-v2":
        raise ValueError("Reviewed bundle is not v2; installation cancelled")
    if old_receipt["content_sha256"] != old_manifest["content_sha256"]:
        raise ValueError("Exercise receipt differs from installed v1 baseline")
    if not new_database.exists():
        raise ValueError("Decompress the reviewed v2 database for comparison first")

    db = connect(state_database, readonly=True)
    try:
        db.execute("ATTACH DATABASE ? AS upgraded", (str(new_database),))
        stable_customers = (
            "id,source_customer_id,name,account_manager_id,payment_terms_days,"
            "settlement_delay_days,segment,provenance"
        )
        for table, columns in (
            ("customers", stable_customers),
            ("customer_contacts", "*"),
            ("products", "*"),
            ("orders", "*"),
            ("tickets", "*"),
            ("document_links", "*"),
        ):
            if not matching_table(db, table, columns):
                raise ValueError(f"Exercise table {table} differs beyond expected v2 enrichment")
    finally:
        db.close()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = inside(project, state / "backups" / f"bundle-before-v2-{stamp}")
    backup.mkdir(parents=True, exist_ok=False)
    staged_baseline = inside(project, data / "company" / f"baseline-staged-{stamp}")
    staged_documents = inside(project, data / f"documents-staged-{stamp}")
    staged_baseline.mkdir()
    for name in (
        "company.sqlite.gz",
        "manifest.json",
        "preparation_report.json",
        "validation_report.json",
    ):
        shutil.copy2(new_baseline / name, staged_baseline / name)
    shutil.copytree(new_documents, staged_documents)
    with (
        sqlite3.connect(state_database) as source,
        sqlite3.connect(backup / "company.sqlite") as target,
    ):
        source.backup(target)
    shutil.copy2(receipt_path, backup / "baseline.json")

    baseline_swapped = False
    documents_swapped = False
    try:
        old_baseline.rename(inside(project, backup / "baseline"))
        staged_baseline.rename(old_baseline)
        baseline_swapped = True
        old_documents.rename(inside(project, backup / "documents"))
        staged_documents.rename(old_documents)
        documents_swapped = True

        db = connect(state_database)
        try:
            db.execute("ATTACH DATABASE ? AS upgraded", (str(new_database),))
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE documents AS target SET "
                "title=(SELECT source.title FROM upgraded.documents AS source "
                "WHERE source.id=target.id),"
                "category=(SELECT source.category FROM upgraded.documents AS source "
                "WHERE source.id=target.id),"
                "owner_employee_id=(SELECT source.owner_employee_id "
                "FROM upgraded.documents AS source WHERE source.id=target.id),"
                "access_scope=(SELECT source.access_scope FROM upgraded.documents AS source "
                "WHERE source.id=target.id)"
            )
            db.execute(
                "UPDATE document_versions AS target SET "
                "sha256=(SELECT source.sha256 FROM upgraded.document_versions AS source "
                "WHERE source.id=target.id)"
            )
            if not matching_table(db, "documents") or not matching_table(db, "document_versions"):
                raise ValueError("Document metadata differs after synchronization")
            if db.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Foreign-key check failed after document synchronization")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        receipt = {
            "dataset_version": "acme-company-v2",
            "content_sha256": new_manifest["content_sha256"],
            "profile": new_manifest["profile"],
        }
        temporary_receipt = inside(project, state / f"baseline-{stamp}.json")
        temporary_receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        temporary_receipt.replace(receipt_path)
        baseline_manifest(data)
        print(json.dumps({"installed": "acme-company-v2", "backup": str(backup)}, indent=2))
    except Exception:
        # Restore the complete exercise database, receipt and fixed files from
        # backups. Never remove the backup itself.
        if documents_swapped:
            old_documents.rename(inside(project, backup / "failed-v2-documents"))
            (backup / "documents").rename(old_documents)
        elif (backup / "documents").exists():
            (backup / "documents").rename(old_documents)
        if baseline_swapped:
            old_baseline.rename(inside(project, backup / "failed-v2-baseline"))
            (backup / "baseline").rename(old_baseline)
        elif (backup / "baseline").exists():
            (backup / "baseline").rename(old_baseline)
        shutil.copy2(backup / "company.sqlite", state_database)
        shutil.copy2(backup / "baseline.json", receipt_path)
        raise


if __name__ == "__main__":
    main()
