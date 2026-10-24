"""Audited r14 two-receipt settlement for one fictional 2026 invoice."""

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import (
    _write_controlled,
    audit_revision_bundle,
    install_revision_bundle,
)

REVISION = "acme-documents-2026-r14"
PARENT = "acme-documents-2026-r13"
EFFECTIVE_FROM = "2026-10-21"
CUSTOMER_ID = "SCN-CUST-83DAA020DE34"
ORDER_ID = "SCN-ORD-83DAA020DE34-01"
INVOICE_ID = "SCN-BILL-83DAA020DE34-01"
FIRST_PAYMENT_ID = "SCN-PAY-83DAA020DE34-01"
FIRST_ALLOCATION_ID = "SCN-ALLOC-83DAA020DE34-01"
SECOND_PAYMENT_ID = "SCN-PAY-83DAA020DE34-R14"
SECOND_ALLOCATION_ID = "SCN-ALLOC-83DAA020DE34-R14"
SECOND_RECEIVED_ON = "2026-10-20"
SECOND_ALLOCATED_ON = EFFECTIVE_FROM
DOCUMENT_ID = "FIN-SETTLE-83DAA020DE34-01"
SUPPORT_DOCUMENT_ID = "CASE-83DAA020DE34"
OWNER_ID = "EMP-120"
AMOUNT_PENCE = 12000
PROVENANCE = "fictional_contemporary_scenario"


def _assert_finance(db, *, installed: bool) -> None:
    invoice = db.execute(
        "SELECT order_id,posted_on,due_on,total_pence,currency,provenance "
        "FROM invoices WHERE id=?",
        (INVOICE_ID,),
    ).fetchone()
    if invoice is None or tuple(invoice) != (
        ORDER_ID,
        "2026-10-09",
        "2026-11-08",
        24000,
        "GBP",
        "fictional_contemporary_seed",
    ):
        raise ValueError("Fable invoice changed before settlement release")
    order = db.execute(
        "SELECT customer_id,status FROM orders WHERE id=?", (ORDER_ID,)
    ).fetchone()
    if order is None or tuple(order) != (CUSTOMER_ID, "fulfilled"):
        raise ValueError("Fable order ownership or status changed")
    customer = db.execute(
        "SELECT payment_terms_days FROM customers WHERE id=?", (CUSTOMER_ID,)
    ).fetchone()
    if customer is None or customer[0] != 30:
        raise ValueError("Fable payment terms changed")
    owner = db.execute(
        "SELECT 1 FROM employee_assignments WHERE employee_id=? "
        "AND department_id='DEP-FINANCE' AND valid_until IS NULL",
        (OWNER_ID,),
    ).fetchone()
    if owner is None:
        raise ValueError("Finance document owner is not active")
    payments = [
        tuple(row)
        for row in db.execute(
            "SELECT p.id,p.customer_id,p.received_on,p.amount_pence,p.currency,p.provenance "
            "FROM payments p JOIN payment_allocations a ON a.payment_id=p.id "
            "WHERE a.invoice_id=? ORDER BY p.id",
            (INVOICE_ID,),
        )
    ]
    expected_payments = [
        (
            FIRST_PAYMENT_ID,
            CUSTOMER_ID,
            "2026-10-12",
            AMOUNT_PENCE,
            "GBP",
            "fictional_contemporary_seed",
        )
    ]
    if installed:
        expected_payments.append(
            (
                SECOND_PAYMENT_ID,
                CUSTOMER_ID,
                SECOND_RECEIVED_ON,
                AMOUNT_PENCE,
                "GBP",
                PROVENANCE,
            )
        )
    if payments != expected_payments:
        raise ValueError("Fable invoice payment receipts changed")
    allocations = [
        tuple(row)
        for row in db.execute(
            "SELECT id,payment_id,allocated_on,amount_pence FROM payment_allocations "
            "WHERE invoice_id=? ORDER BY id",
            (INVOICE_ID,),
        )
    ]
    expected_allocations = [
        (FIRST_ALLOCATION_ID, FIRST_PAYMENT_ID, "2026-10-12", AMOUNT_PENCE)
    ]
    if installed:
        expected_allocations.append(
            (SECOND_ALLOCATION_ID, SECOND_PAYMENT_ID, SECOND_ALLOCATED_ON, AMOUNT_PENCE)
        )
    if allocations != expected_allocations:
        raise ValueError("Fable invoice allocation ledger changed")
    if not installed and db.execute(
        "SELECT 1 FROM payments WHERE id=?", (SECOND_PAYMENT_ID,)
    ).fetchone():
        raise ValueError("Second receipt ID already exists")
    if not installed and db.execute(
        "SELECT 1 FROM payment_allocations WHERE id=?", (SECOND_ALLOCATION_ID,)
    ).fetchone():
        raise ValueError("Second allocation ID already exists")
    if db.execute("SELECT 1 FROM credit_notes WHERE invoice_id=?", (INVOICE_ID,)).fetchone():
        raise ValueError("Fable settlement invoice gained a credit note")
    other = db.execute(
        "SELECT i.total_pence,COALESCE(SUM(a.amount_pence),0) FROM invoices i "
        "LEFT JOIN payment_allocations a ON a.invoice_id=i.id "
        "WHERE i.id='SCN-BILL-83DAA020DE34-02' GROUP BY i.id"
    ).fetchone()
    if other is None or tuple(other) != (24000, AMOUNT_PENCE):
        raise ValueError("Comparison invoice changed")


def build_settlement_release(source: Path, state: Path, authored: Path, output: Path) -> dict:
    """Package a Finance review against the audited r13 parent and live ledger."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected an audited r13 parent")
    catalog = json.loads((source / "catalog.json").read_text("utf-8"))
    if any(item["document_id"] == DOCUMENT_ID for item in catalog["documents"]):
        raise ValueError("Finance review already exists")
    case = next(
        (
            item
            for item in catalog["documents"]
            if item["document_id"] == SUPPORT_DOCUMENT_ID and item["status"] == "current"
        ),
        None,
    )
    if case is None or case["version"] != 1:
        raise ValueError("Expected the dated Support case v1")
    case_body = (source / case["relative_path"]).read_text("utf-8")
    if "GBP 120.00 remains\noutstanding at this review" not in case_body:
        raise ValueError("Dated Support balance statement changed")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        _assert_finance(db, installed=False)
    finally:
        db.close()
    body = authored.read_text("utf-8")
    required = (
        CUSTOMER_ID,
        ORDER_ID,
        INVOICE_ID,
        FIRST_PAYMENT_ID,
        FIRST_ALLOCATION_ID,
        SECOND_PAYMENT_ID,
        SECOND_ALLOCATION_ID,
        SUPPORT_DOCUMENT_ID + ":v1",
    )
    if (
        not body.startswith("# ")
        or any(identifier not in body for identifier in required)
        or "Receipt alone" not in body
        or "GBP 0.00" not in body
    ):
        raise ValueError("Finance source omits a linked record or settlement boundary")
    shutil.copytree(source, output)
    (output / "installed.json").unlink(missing_ok=True)
    review = _write_controlled(
        output,
        {
            "document_id": DOCUMENT_ID,
            "title": "Receivables reconciliation: Fable invoice 01",
            "category": "incident_notes",
            "owner_employee_id": OWNER_ID,
            "access_scope": "finance",
            "version": 1,
            "effective_from": EFFECTIVE_FROM,
            "effective_until": None,
            "status": "current",
            "record_links": {
                "customer_id": CUSTOMER_ID,
                "order_id": ORDER_ID,
                "invoice_id": INVOICE_ID,
            },
            "facts": {
                "invoice_id": INVOICE_ID,
                "invoice_total_pence": 24000,
                "first_payment_id": FIRST_PAYMENT_ID,
                "first_allocation_id": FIRST_ALLOCATION_ID,
                "second_payment_id": SECOND_PAYMENT_ID,
                "second_received_on": SECOND_RECEIVED_ON,
                "second_allocation_id": SECOND_ALLOCATION_ID,
                "second_allocated_on": SECOND_ALLOCATED_ON,
                "allocated_total_pence": 24000,
                "balance_as_of": EFFECTIVE_FROM,
                "balance_pence": 0,
                "historical_support_case": SUPPORT_DOCUMENT_ID + ":v1",
            },
            "revision": REVISION,
        },
        body,
    )
    documents = [*catalog["documents"], review]
    documents.sort(key=lambda item: (item["document_id"], item["version"]))
    catalog.update({"revision": REVISION, "documents": documents})
    catalog_path = output / "catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in documents}),
        "versions": len(documents),
        "new_finance_reviews": 1,
        "new_payments": 1,
        "new_allocations": 1,
        "effective_from": EFFECTIVE_FROM,
    }
    (output / "release_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    (output / "editorial_review.json").write_text(
        json.dumps(
            [
                {
                    "document_id": DOCUMENT_ID,
                    "version": 1,
                    "review": (
                        "Separate receipt from allocation and keep the earlier "
                        "Support balance dated"
                    ),
                    "source_file": authored.name,
                }
            ],
            indent=2,
        )
        + "\n",
        "utf-8",
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"Finance review bundle failed audit: {audit['issues']}")
    return manifest


def _transform(db) -> None:
    _assert_finance(db, installed=False)
    db.execute(
        "INSERT INTO payments(id,customer_id,received_on,amount_pence,currency,provenance) "
        "VALUES(?,?,?,?,?,?)",
        (SECOND_PAYMENT_ID, CUSTOMER_ID, SECOND_RECEIVED_ON, AMOUNT_PENCE, "GBP", PROVENANCE),
    )
    db.execute(
        "INSERT INTO payment_allocations(id,payment_id,invoice_id,allocated_on,amount_pence) "
        "VALUES(?,?,?,?,?)",
        (SECOND_ALLOCATION_ID, SECOND_PAYMENT_ID, INVOICE_ID, SECOND_ALLOCATED_ON, AMOUNT_PENCE),
    )


def _validate(db, catalog: list[dict], documents: Path) -> None:
    _assert_finance(db, installed=True)
    review = next((item for item in catalog if item["document_id"] == DOCUMENT_ID), None)
    if review is None or review["version"] != 1 or review["access_scope"] != "finance":
        raise ValueError("Current Finance review is missing or incorrectly scoped")
    body = (documents / review["relative_path"]).read_text("utf-8")
    if SECOND_ALLOCATION_ID not in body or "GBP 0.00" not in body:
        raise ValueError("Finance review lost its dated settlement conclusion")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Settlement release creates broken references")


def install_settlement_release(project: Path, state: Path, bundle: Path) -> dict:
    """Install the staged payment, allocation and scoped document with backup."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_transform=_transform,
        database_validator=_validate,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
