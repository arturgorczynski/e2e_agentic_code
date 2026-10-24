"""Audited r13 correction and Operations handoff for the partial dispatch."""

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
from acme.partial_dispatch_release import DOCUMENT_ID as SUPPORT_DOCUMENT_ID
from acme.partial_dispatch_release import (
    EFFECTIVE_FROM,
    INVENTORY_ID,
    MOVEMENTS,
    ORDER_ID,
    ORDER_ITEMS,
    PRODUCT_ID,
    SHIPMENT_ID,
    SHIPMENT_ITEMS,
    TICKET_ID,
    WAREHOUSE_ID,
    _assert_order,
)

REVISION = "acme-documents-2026-r13"
PARENT = "acme-documents-2026-r12"
OPERATIONS_DOCUMENT_ID = "OPS-DISPATCH-83DAA020DE34"
OPERATIONS_OWNER = "EMP-041"


def _assert_business(db) -> None:
    _assert_order(db, installed=True)
    shipment = db.execute(
        "SELECT warehouse_id,dispatched_on,delivered_on FROM shipments WHERE id=?",
        (SHIPMENT_ID,),
    ).fetchone()
    if shipment is None or tuple(shipment) != (WAREHOUSE_ID, "2026-10-17", None):
        raise ValueError("Partial shipment changed before editorial release")
    links = [
        tuple(row)
        for row in db.execute(
            "SELECT si.order_item_id,si.id,m.id,si.quantity,m.quantity "
            "FROM shipment_items si JOIN stock_movements m ON m.shipment_item_id=si.id "
            "WHERE si.shipment_id=? ORDER BY si.order_item_id",
            (SHIPMENT_ID,),
        )
    ]
    expected = [
        (order_item, shipment_item, movement, 1, -1)
        for order_item, shipment_item, movement in zip(
            ORDER_ITEMS[:2], SHIPMENT_ITEMS, MOVEMENTS, strict=True
        )
    ]
    if links != expected:
        raise ValueError("Shipment items and stock movements changed")
    inventory = db.execute(
        "SELECT as_of,on_hand,reserved FROM inventory WHERE id=?",
        (INVENTORY_ID,),
    ).fetchone()
    if inventory is None or tuple(inventory) != (EFFECTIVE_FROM, 18, 2):
        raise ValueError("Dated inventory snapshot changed")
    events = db.execute(
        "SELECT COUNT(*) FROM ticket_events WHERE ticket_id=?", (TICKET_ID,)
    ).fetchone()[0]
    if events != 2:
        raise ValueError("Support event history changed")
    owner = db.execute(
        "SELECT 1 FROM employee_assignments WHERE employee_id=? "
        "AND department_id='DEP-WAREHOUSE' AND valid_until IS NULL",
        (OPERATIONS_OWNER,),
    ).fetchone()
    if owner is None:
        raise ValueError("Operations document owner is not active in Warehouse")


def build_dispatch_handoff_release(
    source: Path, state: Path, support_source: Path, operations_source: Path, output: Path
) -> dict:
    """Package a support correction and a new scoped Operations document."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected an audited r12 parent")
    catalog = json.loads((source / "catalog.json").read_text("utf-8"))
    current = [
        item
        for item in catalog["documents"]
        if item["document_id"] == SUPPORT_DOCUMENT_ID and item["status"] == "current"
    ]
    if len(current) != 1 or current[0]["version"] != 1:
        raise ValueError("Expected the current r12 Support case v1")
    original = current[0]
    if original["facts"].get("inventory_reserved") != 2:
        raise ValueError("Support case reservation snapshot changed")
    if any(item["document_id"] == OPERATIONS_DOCUMENT_ID for item in catalog["documents"]):
        raise ValueError("Operations handoff already exists")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        _assert_business(db)
        if db.execute(
            "SELECT 1 FROM documents WHERE id=?", (OPERATIONS_DOCUMENT_ID,)
        ).fetchone():
            raise ValueError("Operations document ID already exists in SQL")
    finally:
        db.close()
    support_body = support_source.read_text("utf-8")
    operations_body = operations_source.read_text("utf-8")
    required = (ORDER_ID, SHIPMENT_ID, TICKET_ID, *ORDER_ITEMS)
    physical = (*SHIPMENT_ITEMS, *MOVEMENTS, INVENTORY_ID)
    if (
        not support_body.startswith("# ")
        or any(identifier not in support_body for identifier in required)
        or "no link\nallocating" not in support_body
    ):
        raise ValueError("Corrected Support source omits a record or reservation boundary")
    if (
        not operations_body.startswith("# ")
        or any(identifier not in operations_body for identifier in (*required, *physical))
        or "no allocation record" not in operations_body
    ):
        raise ValueError("Operations source omits physical links or reservation boundary")
    shutil.copytree(source, output)
    (output / "installed.json").unlink(missing_ok=True)
    old_body = (source / original["relative_path"]).read_text("utf-8").split("---\n", 2)[2]
    superseded = _write_controlled(
        output,
        {**original, "status": "superseded", "effective_until": EFFECTIVE_FROM},
        old_body,
    )
    revised_facts = {
        **original["facts"],
        "stock_snapshot_on": EFFECTIVE_FROM,
        "reservation_scope": "product_warehouse_aggregate",
        "reservation_allocation_verified": False,
    }
    corrected = _write_controlled(
        output,
        {
            **original,
            "version": 2,
            "status": "current",
            "effective_from": EFFECTIVE_FROM,
            "effective_until": None,
            "facts": revised_facts,
            "revision": REVISION,
        },
        support_body,
    )
    operations = _write_controlled(
        output,
        {
            "document_id": OPERATIONS_DOCUMENT_ID,
            "title": "Warehouse dispatch reconciliation: Fable Home Merchants",
            "category": "incident_notes",
            "owner_employee_id": OPERATIONS_OWNER,
            "access_scope": "operations",
            "version": 1,
            "effective_from": EFFECTIVE_FROM,
            "effective_until": None,
            "status": "current",
            "record_links": {
                "order_id": ORDER_ID,
                "product_id": PRODUCT_ID,
                "warehouse_id": WAREHOUSE_ID,
                "ticket_id": TICKET_ID,
            },
            "facts": {
                "order_id": ORDER_ID,
                "shipment_id": SHIPMENT_ID,
                "inventory_id": INVENTORY_ID,
                "product_id": PRODUCT_ID,
                "warehouse_id": WAREHOUSE_ID,
                "dispatched_units": 2,
                "unshipped_units": 2,
                "stock_snapshot_on": EFFECTIVE_FROM,
                "on_hand": 18,
                "reserved": 2,
                "reservation_scope": "product_warehouse_aggregate",
                "reservation_allocation_verified": False,
                "recorded_delivery": False,
            },
            "revision": REVISION,
        },
        operations_body,
    )
    documents = []
    for item in catalog["documents"]:
        if item["document_id"] == SUPPORT_DOCUMENT_ID and item["status"] == "current":
            documents.extend((superseded, corrected))
        else:
            documents.append(item)
    documents.append(operations)
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
        "corrected_support_cases": 1,
        "new_operations_handoffs": 1,
        "effective_from": EFFECTIVE_FROM,
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", "utf-8"
    )
    (output / "editorial_review.json").write_text(
        json.dumps(
            [
                {
                    "document_id": SUPPORT_DOCUMENT_ID,
                    "new_version": 2,
                    "review": (
                        "Remove unsupported order-specific reservation claim; "
                        "date stock and finance statements"
                    ),
                    "source_file": support_source.name,
                },
                {
                    "document_id": OPERATIONS_DOCUMENT_ID,
                    "new_version": 1,
                    "review": (
                        "Match two shipment items to two dispatch movements; "
                        "mark reservation as aggregate"
                    ),
                    "source_file": operations_source.name,
                },
            ],
            indent=2,
        )
        + "\n",
        "utf-8",
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"Dispatch handoff bundle failed audit: {audit['issues']}")
    return manifest


def _validate(db, catalog: list[dict], documents: Path) -> None:
    _assert_business(db)
    support = next(
        (
            item
            for item in catalog
            if item["document_id"] == SUPPORT_DOCUMENT_ID and item["status"] == "current"
        ),
        None,
    )
    operations = next(
        (item for item in catalog if item["document_id"] == OPERATIONS_DOCUMENT_ID), None
    )
    if (
        support is None
        or support["version"] != 2
        or support["facts"].get("reservation_allocation_verified") is not False
        or operations is None
        or operations["version"] != 1
        or operations["access_scope"] != "operations"
    ):
        raise ValueError("Corrected Support and Operations document versions are incomplete")
    for item in (support, operations):
        body = (documents / item["relative_path"]).read_text("utf-8")
        if ORDER_ID not in body or "aggregate" not in body:
            raise ValueError(
                f"Document lost its order or reservation boundary: {item['document_id']}"
            )
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Dispatch handoff creates broken document links")


def install_dispatch_handoff_release(project: Path, state: Path, bundle: Path) -> dict:
    """Install the r13 scoped documents after a staged SQL and content audit."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_validator=_validate,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
