"""Rehearse the r13 documents on an isolated online SQLite backup."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from acme.dataset import connect
from acme.dispatch_handoff_release import (
    OPERATIONS_DOCUMENT_ID,
    REVISION,
    SUPPORT_DOCUMENT_ID,
    install_dispatch_handoff_release,
)
from acme.document_revision import audit_revision_bundle
from acme.partial_dispatch_release import ORDER_ID
from acme.scenarios import audit_contemporary_history


def verify(project: Path, source_state: Path, bundle: Path) -> dict:
    project = project.resolve()
    root = (project / "artifacts/verify-temp").resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = Path(tempfile.mkdtemp(prefix="handoff-r13-", dir=root)).resolve()
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
        first = install_dispatch_handoff_release(project, name, bundle)
        second = install_dispatch_handoff_release(project, name, bundle)
        business = audit_contemporary_history(name)
        documents = audit_revision_bundle(name / "documents")
        db = connect(name / "company.sqlite", readonly=True)
        try:
            order = db.execute("SELECT status FROM orders WHERE id=?", (ORDER_ID,)).fetchone()
            source_orders = db.execute(
                "SELECT COUNT(*) FROM orders WHERE provenance="
                "'reconstructed from complete UCI invoice'"
            ).fetchone()[0]
            versions = [
                tuple(row)
                for row in db.execute(
                    "SELECT document_id,version,status FROM document_versions "
                    "WHERE document_id IN (?,?) ORDER BY document_id,version",
                    (SUPPORT_DOCUMENT_ID, OPERATIONS_DOCUMENT_ID),
                )
            ]
            operations_scope = db.execute(
                "SELECT access_scope FROM documents WHERE id=?", (OPERATIONS_DOCUMENT_ID,)
            ).fetchone()
            links = [
                tuple(row)
                for row in db.execute(
                    "SELECT order_id,product_id,warehouse_id,ticket_id FROM document_links "
                    "WHERE document_id=? ORDER BY id",
                    (OPERATIONS_DOCUMENT_ID,),
                )
            ]
        finally:
            db.close()
        if (
            first["status"] != "installed"
            or second["status"] != "already_installed"
            or business["status"] != "ok"
            or documents["status"] != "ok"
            or documents["revision"] != REVISION
            or (documents["document_ids"], documents["versions"]) != (173, 459)
            or order is None
            or order["status"] != "partial"
            or source_orders != 15201
            or versions
            != [
                (SUPPORT_DOCUMENT_ID, 1, "superseded"),
                (SUPPORT_DOCUMENT_ID, 2, "current"),
                (OPERATIONS_DOCUMENT_ID, 1, "current"),
            ]
            or operations_scope is None
            or operations_scope["access_scope"] != "operations"
            or len(links) != 4
        ):
            raise ValueError("Isolated dispatch-handoff verification failed")
        return {
            "status": "ok",
            "revision": REVISION,
            "document_ids": documents["document_ids"],
            "versions": documents["versions"],
            "source_derived_orders": source_orders,
            "second_install": second["status"],
            "business_audit": business["status"],
            "business_checks": len(business["violations"]),
            "violation_count": sum(business["violations"].values()),
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
    bundle = args.bundle_dir or project / "artifacts/dispatch-handoff-release-2026-r13/documents"
    print(json.dumps(verify(project, state, bundle), indent=2))


if __name__ == "__main__":
    main()
