"""Rehearse the r14 payment, allocation and document on an isolated state."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import audit_revision_bundle
from acme.scenarios import audit_contemporary_history
from acme.settlement_release import (
    DOCUMENT_ID,
    INVOICE_ID,
    REVISION,
    SECOND_ALLOCATION_ID,
    SECOND_PAYMENT_ID,
    install_settlement_release,
)


def verify(project: Path, source_state: Path, bundle: Path) -> dict:
    project = project.resolve()
    root = (project / "artifacts/verify-temp").resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = Path(tempfile.mkdtemp(prefix="settlement-r14-", dir=root)).resolve()
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
        first = install_settlement_release(project, name, bundle)
        second = install_settlement_release(project, name, bundle)
        business = audit_contemporary_history(name)
        documents = audit_revision_bundle(name / "documents")
        db = connect(name / "company.sqlite", readonly=True)
        try:
            paid = db.execute(
                "SELECT COALESCE(SUM(amount_pence),0) FROM payment_allocations WHERE invoice_id=?",
                (INVOICE_ID,),
            ).fetchone()[0]
            receipt = db.execute(
                "SELECT received_on,amount_pence FROM payments WHERE id=?", (SECOND_PAYMENT_ID,)
            ).fetchone()
            allocation = db.execute(
                "SELECT allocated_on,amount_pence FROM payment_allocations WHERE id=?",
                (SECOND_ALLOCATION_ID,),
            ).fetchone()
            scope = db.execute(
                "SELECT access_scope FROM documents WHERE id=?", (DOCUMENT_ID,)
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
            or documents["status"] != "ok"
            or (documents["revision"], documents["document_ids"], documents["versions"])
            != (REVISION, 174, 460)
            or paid != 24000
            or receipt is None
            or tuple(receipt) != ("2026-10-20", 12000)
            or allocation is None
            or tuple(allocation) != ("2026-10-21", 12000)
            or scope is None
            or scope["access_scope"] != "finance"
            or source_orders != 15201
        ):
            raise ValueError("Isolated settlement verification failed")
        return {
            "status": "ok",
            "revision": REVISION,
            "document_ids": documents["document_ids"],
            "versions": documents["versions"],
            "invoice_id": INVOICE_ID,
            "allocated_pence": paid,
            "balance_pence": 0,
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
    bundle = args.bundle_dir or project / "artifacts/settlement-release-2026-r14/documents"
    print(json.dumps(verify(project, state, bundle), indent=2))


if __name__ == "__main__":
    main()
