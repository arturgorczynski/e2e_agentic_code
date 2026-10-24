"""Rehearse r12 on an isolated online SQLite backup before installation."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import audit_revision_bundle
from acme.partial_dispatch_release import (
    DOCUMENT_ID,
    ORDER_ID,
    REVISION,
    TICKET_ID,
    install_partial_dispatch_release,
)
from acme.scenarios import audit_contemporary_history


def verify(project: Path, source_state: Path, bundle: Path) -> dict:
    project = project.resolve()
    root = (project / "artifacts/verify-temp").resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = Path(tempfile.mkdtemp(prefix="partial-r12-", dir=root)).resolve()
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
        first = install_partial_dispatch_release(project, name, bundle)
        second = install_partial_dispatch_release(project, name, bundle)
        business = audit_contemporary_history(name)
        documents = audit_revision_bundle(name / "documents")
        db = connect(name / "company.sqlite", readonly=True)
        try:
            order = db.execute("SELECT status FROM orders WHERE id=?", (ORDER_ID,)).fetchone()
            ticket = db.execute("SELECT status FROM tickets WHERE id=?", (TICKET_ID,)).fetchone()
            case = db.execute(
                "SELECT status FROM document_versions WHERE document_id=?", (DOCUMENT_ID,)
            ).fetchone()
            source_orders = db.execute(
                "SELECT COUNT(*) FROM orders WHERE provenance="
                "'reconstructed from complete UCI invoice'"
            ).fetchone()[0]
            totals = db.execute(
                "SELECT SUM(oi.quantity),SUM(COALESCE(s.shipped,0)) FROM order_items oi "
                "LEFT JOIN (SELECT si.order_item_id,SUM(si.quantity) AS shipped "
                "FROM shipment_items si GROUP BY si.order_item_id) s ON s.order_item_id=oi.id "
                "WHERE oi.order_id=?",
                (ORDER_ID,),
            ).fetchone()
        finally:
            db.close()
        if (
            first["status"] != "installed"
            or second["status"] != "already_installed"
            or business["status"] != "ok"
            or documents["status"] != "ok"
            or documents["revision"] != REVISION
            or order is None
            or order["status"] != "partial"
            or ticket is None
            or ticket["status"] != "in_progress"
            or case is None
            or case["status"] != "current"
            or tuple(totals) != (4, 2)
            or source_orders != 15201
        ):
            raise ValueError("Isolated partial-dispatch verification failed")
        return {
            "status": "ok",
            "revision": REVISION,
            "document_ids": documents["document_ids"],
            "versions": documents["versions"],
            "order_id": ORDER_ID,
            "ordered_units": totals[0],
            "dispatched_units": totals[1],
            "source_derived_orders": source_orders,
            "second_install": second["status"],
            "business_audit": business["status"],
            "checks": len(business["violations"]),
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
    bundle = args.bundle_dir or project / "artifacts/partial-dispatch-release-2026-r12/documents"
    print(json.dumps(verify(project, state, bundle), indent=2))


if __name__ == "__main__":
    main()
