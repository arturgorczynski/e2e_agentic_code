"""Rehearse r11 on a temporary online backup and inspect the linked case."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import audit_revision_bundle
from acme.return_case_release import (
    DOCUMENT_ID,
    EVENT_ID,
    REVISION,
    TICKET_ID,
    install_return_case_release,
)
from acme.scenarios import audit_contemporary_history


def verify(project: Path, source_state: Path, bundle: Path) -> dict:
    project = project.resolve()
    root = (project / "artifacts/verify-temp").resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = Path(tempfile.mkdtemp(prefix="return-r11-", dir=root)).resolve()
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
        first = install_return_case_release(project, name, bundle)
        second = install_return_case_release(project, name, bundle)
        business = audit_contemporary_history(name)
        documents = audit_revision_bundle(name / "documents")
        db = connect(name / "company.sqlite", readonly=True)
        try:
            ticket = db.execute(
                "SELECT status FROM tickets WHERE id=?", (TICKET_ID,)
            ).fetchone()
            events = [
                tuple(row)
                for row in db.execute(
                    "SELECT id,occurred_on,status FROM ticket_events WHERE ticket_id=? "
                    "ORDER BY occurred_on,id",
                    (TICKET_ID,),
                )
            ]
            case = db.execute(
                "SELECT status FROM document_versions WHERE document_id=? AND version=2",
                (DOCUMENT_ID,),
            ).fetchone()
            archived = db.execute(
                "SELECT COUNT(*) FROM orders "
                "WHERE provenance='reconstructed from complete UCI invoice'"
            ).fetchone()[0]
            credits = db.execute(
                "SELECT COUNT(*) FROM credit_notes "
                "WHERE invoice_id='SCN-BILL-75F3A546B17E-02'"
            ).fetchone()[0]
        finally:
            db.close()
        if (
            first["status"] != "installed"
            or second["status"] != "already_installed"
            or business["status"] != "ok"
            or documents["status"] != "ok"
            or documents["revision"] != REVISION
            or ticket is None
            or ticket["status"] != "in_progress"
            or len(events) != 2
            or events[-1] != (EVENT_ID, "2026-10-21", "in_progress")
            or case is None
            or case["status"] != "current"
            or archived != 15201
            or credits != 0
        ):
            raise ValueError("Isolated return-case release verification failed")
        return {
            "status": "ok",
            "revision": documents["revision"],
            "document_ids": documents["document_ids"],
            "versions": documents["versions"],
            "ticket_id": TICKET_ID,
            "ticket_status": ticket["status"],
            "event_count": len(events),
            "source_derived_orders": archived,
            "second_install": second["status"],
            "business_audit": business["status"],
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
    bundle = args.bundle_dir or project / "artifacts/return-case-release-2026-r11/documents"
    print(json.dumps(verify(project, state, bundle), indent=2))


if __name__ == "__main__":
    main()
