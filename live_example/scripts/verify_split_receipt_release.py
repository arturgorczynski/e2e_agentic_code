"""Rehearse the r10 release on a temporary online backup, never on live state."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import audit_revision_bundle
from acme.scenarios import audit_contemporary_history
from acme.split_receipt_release import (
    DOCUMENT_ID,
    LINE_ID,
    ORDER_ID,
    RECEIPTS,
    RECEIVED,
    REVISION,
    install_split_receipt_release,
)


def verify(project: Path, source_state: Path, bundle: Path) -> dict:
    project = project.resolve()
    root = project / "artifacts/verify-temp"
    root.mkdir(parents=True, exist_ok=True)
    name = Path(tempfile.mkdtemp(prefix="split-r10-", dir=root)).resolve()
    if not name.is_relative_to(root.resolve()):
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
        first = install_split_receipt_release(project, name, bundle)
        second = install_split_receipt_release(project, name, bundle)
        audit = audit_contemporary_history(name)
        documents = audit_revision_bundle(name / "documents")
        db = connect(name / "company.sqlite", readonly=True)
        try:
            line = db.execute(
                "SELECT pi.quantity,COUNT(gr.id) AS receipt_count,"
                "COALESCE(SUM(gr.quantity),0) AS received FROM purchase_order_items pi "
                "LEFT JOIN goods_receipts gr ON gr.purchase_order_item_id=pi.id "
                "WHERE pi.id=? GROUP BY pi.id",
                (LINE_ID,),
            ).fetchone()
            moves = db.execute(
                "SELECT gr.id,m.id,gr.quantity,m.quantity FROM goods_receipts gr "
                "JOIN stock_movements m ON m.goods_receipt_id=gr.id "
                "WHERE gr.purchase_order_item_id=? ORDER BY gr.id",
                (LINE_ID,),
            ).fetchall()
            purchase_count = db.execute(
                "SELECT COUNT(*) FROM purchase_orders WHERE id LIKE 'SCN-PO-%'"
            ).fetchone()[0]
            document_count = db.execute(
                "SELECT COUNT(*) FROM documents WHERE id=?", (DOCUMENT_ID,)
            ).fetchone()[0]
        finally:
            db.close()
        expected_moves = [
            (receipt, movement, qty, qty) for receipt, movement, _, qty in RECEIPTS
        ]
        if (
            first["status"] != "installed"
            or second["status"] != "already_installed"
            or audit["status"] != "ok"
            or documents["status"] != "ok"
            or documents["revision"] != REVISION
            or line is None
            or tuple(line) != (15, 2, RECEIVED)
            or [tuple(row) for row in moves] != expected_moves
            or purchase_count != 4
            or document_count != 1
        ):
            raise ValueError("Isolated split-receipt release verification failed")
        return {
            "status": "ok",
            "revision": documents["revision"],
            "document_ids": documents["document_ids"],
            "versions": documents["versions"],
            "purchase_orders": purchase_count,
            "new_purchase_order_id": ORDER_ID,
            "ordered": line["quantity"],
            "receipt_count": line["receipt_count"],
            "received": line["received"],
            "outstanding": line["quantity"] - line["received"],
            "contemporary_audit": audit["status"],
            "second_install": second["status"],
        }
    finally:
        if not name.is_relative_to(root.resolve()):
            raise ValueError("Refusing to remove a temporary state outside the workspace")
        shutil.rmtree(name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--bundle-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state = (args.state_dir or project / "state").resolve()
    bundle = args.bundle_dir or project / "artifacts/split-receipt-release-2026-r10/documents"
    print(json.dumps(verify(project, state, bundle), indent=2))


if __name__ == "__main__":
    main()
