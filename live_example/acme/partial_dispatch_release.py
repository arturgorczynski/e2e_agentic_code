"""Audited r12 partial-dispatch case for the fictional Fable account."""

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

REVISION = "acme-documents-2026-r12"
PARENT = "acme-documents-2026-r11"
EFFECTIVE_FROM = "2026-10-21"
PROVENANCE = "fictional_contemporary_scenario"
ORDER_ID = "SCN-ORD-83DAA020DE34-03"
CUSTOMER_ID = "SCN-CUST-83DAA020DE34"
PRODUCT_ID = "SCN-SKU-83DAA020DE34"
WAREHOUSE_ID = "WH-CVT"
INVENTORY_ID = "SCN-INV-83DAA020DE34"
ORDER_ITEMS = tuple(f"SCN-ITEM-83DAA020DE34-{index:03d}" for index in range(9, 13))
SHIPMENT_ID = "SCN-SHIP-83DAA020DE34-03-PARTIAL"
SHIPMENT_ITEMS = tuple(f"SCN-SHIPITEM-83DAA020DE34-R12-{index}" for index in (1, 2))
MOVEMENTS = tuple(f"SCN-STOCK-83DAA020DE34-R12-{index}" for index in (1, 2))
HISTORY_ID = "SCN-HIST-83DAA020DE34-03-2"
TICKET_ID = "SCN-TKT-83DAA020DE34-R12"
EVENT_IDS = ("SCN-TKTEVT-83DAA020DE34-R12-1", "SCN-TKTEVT-83DAA020DE34-R12-2")
DOCUMENT_ID = "CASE-PARTIAL-83DAA020DE34"
OWNER_ID = "EMP-138"
DISPATCHED_ON = "2026-10-17"
OPENED_ON = "2026-10-19"
REVIEWED_ON = "2026-10-21"


def _assert_order(db, *, installed: bool) -> None:
    order = db.execute(
        "SELECT customer_id,ordered_at,status,currency,provenance FROM orders WHERE id=?",
        (ORDER_ID,),
    ).fetchone()
    expected = (
        CUSTOMER_ID,
        "2026-10-10",
        "partial" if installed else "confirmed",
        "GBP",
        "fictional_contemporary_seed",
    )
    if order is None or tuple(order) != expected:
        raise ValueError("Fable order identity or status changed")
    lines = [
        tuple(row)
        for row in db.execute(
            "SELECT id,product_id,quantity,line_pence FROM order_items "
            "WHERE order_id=? ORDER BY id",
            (ORDER_ID,),
        )
    ]
    if lines != [(item, PRODUCT_ID, 1, 6000) for item in ORDER_ITEMS]:
        raise ValueError("Fable order lines changed")
    inventory = db.execute(
        "SELECT warehouse_id,product_id,on_hand,reserved FROM inventory WHERE id=?",
        (INVENTORY_ID,),
    ).fetchone()
    expected_inventory = (
        (WAREHOUSE_ID, PRODUCT_ID, 18, 2) if installed else (WAREHOUSE_ID, PRODUCT_ID, 20, 4)
    )
    if inventory is None or tuple(inventory) != expected_inventory:
        raise ValueError("Fable inventory position changed")
    history = [
        tuple(row)
        for row in db.execute(
            "SELECT id,occurred_at,status FROM order_status_history "
            "WHERE order_id=? ORDER BY occurred_at,id",
            (ORDER_ID,),
        )
    ]
    expected_history = [("SCN-HIST-83DAA020DE34-03-1", "2026-10-10", "confirmed")]
    if installed:
        expected_history.append((HISTORY_ID, DISPATCHED_ON, "partial"))
    if history != expected_history:
        raise ValueError("Fable order status history changed")
    for table in ("invoices", "shipments", "tickets"):
        count = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE order_id=?", (ORDER_ID,)
        ).fetchone()[0]
        if count != (1 if installed and table != "invoices" else 0):
            raise ValueError(f"Unexpected {table} for Fable order")
    if not installed:
        for table, identifiers in (
            ("shipment_items", SHIPMENT_ITEMS),
            ("stock_movements", MOVEMENTS),
            ("ticket_events", EVENT_IDS),
        ):
            if db.execute(
                f"SELECT 1 FROM {table} WHERE id IN ({','.join('?' for _ in identifiers)})",
                identifiers,
            ).fetchone():
                raise ValueError(f"r12 {table} identifiers already exist")
        employee = db.execute("SELECT 1 FROM employees WHERE id=?", (OWNER_ID,)).fetchone()
        if employee is None:
            raise ValueError("Support owner is missing")


def build_partial_dispatch_release(source: Path, state: Path, authored: Path, output: Path) -> dict:
    """Package a new support case against an audited r11 parent."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected an audited r11 parent")
    catalog = json.loads((source / "catalog.json").read_text("utf-8"))
    if any(item["document_id"] == DOCUMENT_ID for item in catalog["documents"]):
        raise ValueError("Partial-dispatch case already exists")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        _assert_order(db, installed=False)
        if db.execute("SELECT 1 FROM documents WHERE id=?", (DOCUMENT_ID,)).fetchone():
            raise ValueError("Partial-dispatch document ID already exists")
    finally:
        db.close()
    body = authored.read_text("utf-8")
    required = (ORDER_ID, SHIPMENT_ID, TICKET_ID, *ORDER_ITEMS)
    if (
        not body.startswith("# ")
        or any(value not in body for value in required)
        or "no recorded delivery" not in body.lower()
    ):
        raise ValueError("Authored case omits the lines or evidence boundary")
    shutil.copytree(source, output)
    (output / "installed.json").unlink(missing_ok=True)
    facts = {
        "customer_id": CUSTOMER_ID,
        "order_id": ORDER_ID,
        "shipment_id": SHIPMENT_ID,
        "ticket_id": TICKET_ID,
        "ordered_units": 4,
        "dispatched_units": 2,
        "outstanding_units": 2,
        "invoice_count": 0,
        "recorded_delivery": False,
        "inventory_on_hand": 18,
        "inventory_reserved": 2,
    }
    catalog["documents"].append(
        _write_controlled(
            output,
            {
                "document_id": DOCUMENT_ID,
                "title": "Case file: partial dispatch for Fable Home Merchants",
                "category": "incident_notes",
                "owner_employee_id": OWNER_ID,
                "access_scope": "support",
                "version": 1,
                "effective_from": EFFECTIVE_FROM,
                "effective_until": None,
                "status": "current",
                "record_links": {"order_id": ORDER_ID, "ticket_id": TICKET_ID},
                "facts": facts,
                "revision": REVISION,
            },
            body,
        )
    )
    catalog["documents"].sort(key=lambda item: (item["document_id"], item["version"]))
    catalog["revision"] = REVISION
    catalog_path = output / "catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in catalog["documents"]}),
        "versions": len(catalog["documents"]),
        "new_support_cases": 1,
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
                        "Four ordered, two dispatched, two outstanding; "
                        "no recorded delivery or invoice"
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
        raise ValueError(f"Partial-dispatch bundle failed audit: {audit['issues']}")
    return manifest


def _transform(db) -> None:
    _assert_order(db, installed=False)
    db.execute("UPDATE orders SET status='partial' WHERE id=?", (ORDER_ID,))
    db.execute(
        "INSERT INTO order_status_history VALUES(?,?,?,?,?)",
        (
            HISTORY_ID,
            ORDER_ID,
            DISPATCHED_ON,
            "partial",
            "Two of four order lines dispatched; two lines remain open",
        ),
    )
    db.execute(
        "INSERT INTO shipments VALUES(?,?,?,?,?,?,?)",
        (
            SHIPMENT_ID,
            ORDER_ID,
            WAREHOUSE_ID,
            DISPATCHED_ON,
            None,
            "Cedar Parcel Network",
            PROVENANCE,
        ),
    )
    for line, shipment_item, movement in zip(
        ORDER_ITEMS[:2], SHIPMENT_ITEMS, MOVEMENTS, strict=True
    ):
        db.execute(
            "INSERT INTO shipment_items VALUES(?,?,?,?)", (shipment_item, SHIPMENT_ID, line, 1)
        )
        db.execute(
            "INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)",
            (
                movement,
                WAREHOUSE_ID,
                PRODUCT_ID,
                DISPATCHED_ON,
                "dispatch",
                -1,
                shipment_item,
                None,
            ),
        )
    updated = db.execute(
        "UPDATE inventory SET on_hand=18,reserved=2,as_of=? "
        "WHERE id=? AND on_hand=20 AND reserved=4",
        (EFFECTIVE_FROM, INVENTORY_ID),
    )
    if updated.rowcount != 1:
        raise ValueError("Fable inventory changed during staged release")
    db.execute(
        "INSERT INTO tickets VALUES(?,?,?,?,?,?,?,?)",
        (
            TICKET_ID,
            ORDER_ID,
            OWNER_ID,
            OPENED_ON,
            "in_progress",
            "partial_dispatch_followup",
            "Internal Support follow-up: confirm delivery evidence for dispatched "
            "lines and the plan for two outstanding lines.",
            PROVENANCE,
        ),
    )
    db.execute(
        "INSERT INTO ticket_events VALUES(?,?,?,?,?)",
        (
            EVENT_IDS[0],
            TICKET_ID,
            OPENED_ON,
            "open",
            "Support follow-up opened for the partial dispatch; no buyer statement "
            "or delivery proof recorded.",
        ),
    )
    db.execute(
        "INSERT INTO ticket_events VALUES(?,?,?,?,?)",
        (
            EVENT_IDS[1],
            TICKET_ID,
            REVIEWED_ON,
            "in_progress",
            "Two lines dispatched; two remain open. Request delivery confirmation "
            "and a separately approved next dispatch date; no ETA promised.",
        ),
    )


def _validate(db, catalog: list[dict], documents: Path) -> None:
    _assert_order(db, installed=True)
    shipment = db.execute(
        "SELECT warehouse_id,dispatched_on,delivered_on,provenance FROM shipments WHERE id=?",
        (SHIPMENT_ID,),
    ).fetchone()
    if shipment is None or tuple(shipment) != (WAREHOUSE_ID, DISPATCHED_ON, None, PROVENANCE):
        raise ValueError("Partial shipment changed")
    shipped = [
        tuple(row)
        for row in db.execute(
            "SELECT si.order_item_id,si.quantity,m.quantity,m.kind FROM shipment_items si "
            "JOIN stock_movements m ON m.shipment_item_id=si.id "
            "WHERE si.shipment_id=? ORDER BY si.order_item_id",
            (SHIPMENT_ID,),
        )
    ]
    if shipped != [(line, 1, -1, "dispatch") for line in ORDER_ITEMS[:2]]:
        raise ValueError("Shipment lines and stock movements do not reconcile")
    ledger = db.execute(
        "SELECT SUM(quantity) FROM stock_movements WHERE warehouse_id=? AND product_id=?",
        (WAREHOUSE_ID, PRODUCT_ID),
    ).fetchone()[0]
    if ledger != 18:
        raise ValueError("Fable stock ledger does not reconcile")
    ticket = db.execute(
        "SELECT assigned_employee_id,opened_on,status,topic,provenance "
        "FROM tickets WHERE id=?",
        (TICKET_ID,),
    ).fetchone()
    if ticket is None or tuple(ticket) != (
        OWNER_ID,
        OPENED_ON,
        "in_progress",
        "partial_dispatch_followup",
        PROVENANCE,
    ):
        raise ValueError("Support case identity or status changed")
    events = [
        tuple(row)
        for row in db.execute(
            "SELECT id,occurred_on,status FROM ticket_events "
            "WHERE ticket_id=? ORDER BY occurred_on,id",
            (TICKET_ID,),
        )
    ]
    if events != [(EVENT_IDS[0], OPENED_ON, "open"), (EVENT_IDS[1], REVIEWED_ON, "in_progress")]:
        raise ValueError("Support case event history changed")
    item = next((row for row in catalog if row["document_id"] == DOCUMENT_ID), None)
    if (
        item is None
        or item["version"] != 1
        or item["record_links"] != {"order_id": ORDER_ID, "ticket_id": TICKET_ID}
    ):
        raise ValueError("Support case document links changed")
    body = (documents / item["relative_path"]).read_text("utf-8")
    if any(value not in body for value in (ORDER_ID, SHIPMENT_ID, TICKET_ID, *ORDER_ITEMS)):
        raise ValueError("Support case lost source identifiers")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Partial-dispatch release creates broken references")


def install_partial_dispatch_release(project: Path, state: Path, bundle: Path) -> dict:
    """Install the staged r12 business event and controlled document."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_transform=_transform,
        database_validator=_validate,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
