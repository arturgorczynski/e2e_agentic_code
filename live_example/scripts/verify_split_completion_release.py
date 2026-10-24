"""Rehearse the r15 final supplier receipt on an isolated r14 state."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import audit_revision_bundle
from acme.scenarios import audit_contemporary_history
from acme.split_completion_release import (
    DOCUMENT_ID,
    INVENTORY_ID,
    LINE_ID,
    ORDER_ID,
    RECEIPT_ID,
    REVISION,
    install_split_completion_release,
)


def verify(project: Path, source_state: Path, bundle: Path) -> dict:
    project = project.resolve()
    root = (project / "artifacts/verify-temp").resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = Path(tempfile.mkdtemp(prefix="split-completion-r15-", dir=root)).resolve()
    if not name.is_relative_to(root):
        raise ValueError("Temporary state escaped the workspace")
    try:
        source = connect(source_state / "company.sqlite", readonly=True)
        copy = connect(name / "company.sqlite")
        try:
            source.backup(copy)
        finally:
            copy.close()
            source.close()
        shutil.copytree(source_state / "documents", name / "documents")
        first = install_split_completion_release(project, name, bundle)
        second = install_split_completion_release(project, name, bundle)
        business = audit_contemporary_history(name)
        docs = audit_revision_bundle(name / "documents")
        db = connect(name / "company.sqlite", readonly=True)
        try:
            order = db.execute(
                "SELECT status FROM purchase_orders WHERE id=?", (ORDER_ID,)
            ).fetchone()
            quantities = db.execute(
                "SELECT SUM(quantity) FROM goods_receipts WHERE purchase_order_item_id=?",
                (LINE_ID,),
            ).fetchone()[0]
            inventory = db.execute(
                "SELECT on_hand,reserved FROM inventory WHERE id=?", (INVENTORY_ID,)
            ).fetchone()
            version_rows = [
                tuple(row)
                for row in db.execute(
                    "SELECT version,status FROM document_versions "
                    "WHERE document_id=? ORDER BY version",
                    (DOCUMENT_ID,),
                )
            ]
            receipt = db.execute(
                "SELECT quantity FROM goods_receipts WHERE id=?", (RECEIPT_ID,)
            ).fetchone()
            source_orders = db.execute(
                "SELECT COUNT(*) FROM orders WHERE provenance="
                "'reconstructed from complete UCI invoice'"
            ).fetchone()[0]
        finally:
            db.close()
        if (
            first["status"] != "installed"
            or second["status"] != "already_installed"
            or business["status"] != "ok"
            or sum(business["violations"].values()) != 0
            or docs["status"] != "ok"
            or (docs["revision"], docs["document_ids"], docs["versions"]) != (REVISION, 174, 461)
            or order is None
            or order[0] != "received"
            or quantities != 15
            or inventory is None
            or tuple(inventory) != (35, 4)
            or version_rows != [(1, "superseded"), (2, "current")]
            or receipt is None
            or receipt[0] != 6
            or source_orders != 15201
        ):
            raise ValueError("Isolated split completion verification failed")
        return {
            "status": "ok",
            "revision": REVISION,
            "document_ids": docs["document_ids"],
            "versions": docs["versions"],
            "supplier_order": ORDER_ID,
            "received_units": quantities,
            "on_hand": inventory[0],
            "reserved": inventory[1],
            "source_derived_orders": source_orders,
            "business_checks": len(business["violations"]),
            "violation_count": sum(business["violations"].values()),
            "second_install": second["status"],
        }
    finally:
        if name.is_relative_to(root) and name.exists():
            shutil.rmtree(name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--bundle-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state = (args.state_dir or project / "state").resolve()
    bundle = args.bundle_dir or project / "artifacts/split-completion-release-2026-r15/documents"
    print(json.dumps(verify(project, state, bundle), indent=2))


if __name__ == "__main__":
    main()
