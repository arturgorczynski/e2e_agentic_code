"""Audited r11 ticket event and controlled return-case revision."""

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

REVISION = "acme-documents-2026-r11"
PARENT = "acme-documents-2026-r10"
EFFECTIVE_FROM = "2026-10-21"
DOCUMENT_ID = "CASE-75F3A546B17E"
TICKET_ID = "SCN-TKT-75F3A546B17E"
EVENT_ID = "SCN-TKTEVT-75F3A546B17E-R11"
ORDER_ID = "SCN-ORD-75F3A546B17E-02"
SHIPMENT_ID = "SCN-SHIP-75F3A546B17E-02"
INVOICE_ID = "SCN-BILL-75F3A546B17E-02"
ITEM_IDS = ("SCN-ITEM-75F3A546B17E-003", "SCN-ITEM-75F3A546B17E-004")
POLICY_ID = "POL-RETURNS-001"
POLICY_VERSION = 2
DELIVERED_ON = "2026-08-24"
REQUESTED_ON = "2026-08-26"
REVIEW_NOTE = (
    "Support checked the 26 August request against 24 August recorded delivery and "
    "POL-RETURNS-001:v2: two days is within the 30-day review window. The two "
    "one-unit order lines share a SKU; affected line, quantity and condition "
    "evidence remain unconfirmed. No return or credit was authorized."
)


def _check_source(db, *, before_event: bool) -> None:
    ticket = db.execute(
        "SELECT order_id,assigned_employee_id,opened_on,status,topic,provenance "
        "FROM tickets WHERE id=?",
        (TICKET_ID,),
    ).fetchone()
    expected_status = "open" if before_event else "in_progress"
    if ticket is None or tuple(ticket) != (
        ORDER_ID,
        "EMP-136",
        REQUESTED_ON,
        expected_status,
        "return_request",
        "fictional_contemporary_seed",
    ):
        raise ValueError("Return ticket identity or status changed")
    initial_events = db.execute(
        "SELECT id,occurred_on,status FROM ticket_events WHERE ticket_id=? "
        "ORDER BY occurred_on,id",
        (TICKET_ID,),
    ).fetchall()
    expected_events = [("SCN-TKTEVT-75F3A546B17E-1", REQUESTED_ON, "open")]
    if not before_event:
        expected_events.append((EVENT_ID, EFFECTIVE_FROM, "in_progress"))
    if [tuple(row) for row in initial_events] != expected_events:
        raise ValueError("Return ticket event history changed")
    shipment = db.execute(
        "SELECT order_id,dispatched_on,delivered_on FROM shipments WHERE id=?",
        (SHIPMENT_ID,),
    ).fetchone()
    if shipment is None or tuple(shipment) != (ORDER_ID, "2026-08-23", DELIVERED_ON):
        raise ValueError("Return case delivery record changed")
    items = db.execute(
        "SELECT oi.id,oi.quantity,si.quantity FROM order_items oi "
        "JOIN shipment_items si ON si.order_item_id=oi.id "
        "WHERE oi.order_id=? AND si.shipment_id=? ORDER BY oi.id",
        (ORDER_ID, SHIPMENT_ID),
    ).fetchall()
    if [tuple(row) for row in items] != [(item_id, 1, 1) for item_id in ITEM_IDS]:
        raise ValueError("Return case order and shipment lines changed")
    policy = db.execute(
        "SELECT effective_from,effective_until FROM document_versions "
        "WHERE document_id=? AND version=?",
        (POLICY_ID, POLICY_VERSION),
    ).fetchone()
    if not policy or not (policy["effective_from"] <= DELIVERED_ON <= policy["effective_until"]):
        raise ValueError("Policy v2 did not cover the recorded delivery date")
    invoice = db.execute(
        "SELECT order_id,total_pence FROM invoices WHERE id=?",
        (INVOICE_ID,),
    ).fetchone()
    if invoice is None or tuple(invoice) != (ORDER_ID, 12400):
        raise ValueError("Return case invoice changed")
    for table in ("payment_allocations", "credit_notes"):
        if db.execute(f"SELECT 1 FROM {table} WHERE invoice_id=?", (INVOICE_ID,)).fetchone():
            raise ValueError("Return case invoice has a settlement or credit")


def build_return_case_release(source: Path, state: Path, authored: Path, output: Path) -> dict:
    """Package the edited case and SQL plan from a verified r10 state."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected an audited r10 parent")
    catalog = json.loads((source / "catalog.json").read_text(encoding="utf-8"))
    current = [
        item
        for item in catalog["documents"]
        if item["document_id"] == DOCUMENT_ID and item["status"] == "current"
    ]
    if len(current) != 1 or current[0]["version"] != 1:
        raise ValueError("Expected exactly one current v1 return case")
    item = current[0]
    if item["facts"] != {"ticket_id": TICKET_ID, "order_id": ORDER_ID}:
        raise ValueError("Original return-case facts changed")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        _check_source(db, before_event=True)
    finally:
        db.close()
    body = authored.read_text(encoding="utf-8")
    required = (TICKET_ID, ORDER_ID, SHIPMENT_ID, INVOICE_ID, *ITEM_IDS)
    if (
        not body.startswith("# ")
        or any(identifier not in body for identifier in required)
        or "POL-RETURNS-001:v2" not in body
        or "two calendar days" not in body
        or "not acceptance" not in body
    ):
        raise ValueError("Authored case omits a required source or decision boundary")
    shutil.copytree(source, output)
    (output / "installed.json").unlink(missing_ok=True)
    old_body = (source / item["relative_path"]).read_text("utf-8").split("---\n", 2)[2]
    previous = _write_controlled(
        output, {**item, "status": "superseded", "effective_until": EFFECTIVE_FROM}, old_body
    )
    updated = _write_controlled(
        output,
        {
            **item,
            "version": 2,
            "status": "current",
            "effective_from": EFFECTIVE_FROM,
            "effective_until": None,
            "revision": REVISION,
            "facts": {
                **item["facts"],
                "shipment_id": SHIPMENT_ID,
                "invoice_id": INVOICE_ID,
                "policy_id": POLICY_ID,
                "policy_version": POLICY_VERSION,
                "delivered_on": DELIVERED_ON,
                "requested_on": REQUESTED_ON,
                "days_after_delivery": 2,
                "ticket_status": "in_progress",
                "invoice_pence": 12400,
            },
        },
        body,
    )
    revised = []
    for entry in catalog["documents"]:
        if entry["document_id"] == DOCUMENT_ID and entry["status"] == "current":
            revised.extend((previous, updated))
        else:
            revised.append(entry)
    revised.sort(key=lambda entry: (entry["document_id"], entry["version"]))
    catalog.update({"revision": REVISION, "documents": revised})
    catalog_path = output / "catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "document_ids": len({entry["document_id"] for entry in revised}),
        "versions": len(revised),
        "revised_return_cases": 1,
        "effective_from": EFFECTIVE_FROM,
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output / "editorial_review.json").write_text(
        json.dumps(
            [
                {
                    "document_id": DOCUMENT_ID,
                    "previous_version": 1,
                    "new_version": 2,
                    "review": (
                        "Use the delivery-date policy and separate review "
                        "from return and credit"
                    ),
                    "source_file": authored.name,
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"Return-case bundle failed audit: {audit['issues']}")
    return manifest


def _transform(db) -> None:
    _check_source(db, before_event=True)
    updated = db.execute(
        "UPDATE tickets SET status='in_progress' WHERE id=? AND status='open'",
        (TICKET_ID,),
    )
    if updated.rowcount != 1:
        raise ValueError("Return ticket changed before installation")
    db.execute(
        "INSERT INTO ticket_events VALUES(?,?,?,?,?)",
        (EVENT_ID, TICKET_ID, EFFECTIVE_FROM, "in_progress", REVIEW_NOTE),
    )


def _validate(db, catalog: list[dict], documents: Path) -> None:
    _check_source(db, before_event=False)
    current = [
        item
        for item in catalog
        if item["document_id"] == DOCUMENT_ID and item["status"] == "current"
    ]
    if len(current) != 1 or current[0]["version"] != 2:
        raise ValueError("Revised return case is not current v2")
    item = current[0]
    if item["facts"]["policy_version"] != POLICY_VERSION:
        raise ValueError("Return case cites the wrong policy version")
    body = (documents / item["relative_path"]).read_text("utf-8")
    if POLICY_ID + ":v2" not in body or "in progress" not in body:
        raise ValueError("Revised return-case body lost its outcome")
    note = db.execute("SELECT note FROM ticket_events WHERE id=?", (EVENT_ID,)).fetchone()
    if note is None or note["note"] != REVIEW_NOTE:
        raise ValueError("Return-case review event changed")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Return-case release creates broken references")


def install_return_case_release(project: Path, state: Path, bundle: Path) -> dict:
    """Install the validated r11 event and document with a full backup."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_transform=_transform,
        database_validator=_validate,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
