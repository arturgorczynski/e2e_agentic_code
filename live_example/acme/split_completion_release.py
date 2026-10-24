"""Audited r15 completion of the fictional split supplier delivery."""

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
from acme.split_receipt_release import (
    DOCUMENT_ID,
    INVENTORY_ID,
    LINE_ID,
    ORDER_ID,
    PRODUCT_ID,
    RECEIPTS,
    SUPPLIER_ID,
    WAREHOUSE_ID,
)

REVISION = "acme-documents-2026-r15"
PARENT = "acme-documents-2026-r14"
EFFECTIVE_FROM = "2026-10-21"
RECEIPT_ID = "SCN-GR-SPLIT-75F3A546B17E-03"
MOVEMENT_ID = "SCN-STOCK-SPLIT-75F3A546B17E-03"
QUANTITY = 6


def _assert_order(db, *, completed: bool) -> None:
    order = db.execute(
        "SELECT supplier_id,warehouse_id,placed_on,expected_on,status,provenance "
        "FROM purchase_orders WHERE id=?",
        (ORDER_ID,),
    ).fetchone()
    expected = (
        SUPPLIER_ID,
        WAREHOUSE_ID,
        "2026-08-26",
        "2026-09-05",
        "received" if completed else "open",
        "fictional_contemporary_seed: two partial supplier receipts; six units outstanding",
    )
    if order is None or tuple(order) != expected:
        raise ValueError("Split supplier order changed")
    line = db.execute(
        "SELECT purchase_order_id,product_id,quantity FROM purchase_order_items WHERE id=?",
        (LINE_ID,),
    ).fetchone()
    if line is None or tuple(line) != (ORDER_ID, PRODUCT_ID, 15):
        raise ValueError("Split supplier order line changed")
    rows = [
        tuple(row)
        for row in db.execute(
            "SELECT gr.id,m.id,gr.received_on,gr.quantity,m.quantity,m.goods_receipt_id,"
            "m.product_id,m.warehouse_id,m.occurred_on,m.kind FROM goods_receipts gr "
            "LEFT JOIN stock_movements m ON m.goods_receipt_id=gr.id "
            "WHERE gr.purchase_order_item_id=? ORDER BY gr.id",
            (LINE_ID,),
        )
    ]
    expected_receipts = [*RECEIPTS]
    if completed:
        expected_receipts.append((RECEIPT_ID, MOVEMENT_ID, EFFECTIVE_FROM, QUANTITY))
    expected_rows = [
        (receipt, movement, day, qty, qty, receipt, PRODUCT_ID, WAREHOUSE_ID, day, "receipt")
        for receipt, movement, day, qty in expected_receipts
    ]
    if rows != expected_rows:
        raise ValueError("Split supplier receipts or stock movements changed")
    inventory = db.execute(
        "SELECT on_hand,reserved,as_of FROM inventory WHERE id=?", (INVENTORY_ID,)
    ).fetchone()
    if inventory is None or tuple(inventory) != (
        29 + (QUANTITY if completed else 0),
        4,
        EFFECTIVE_FROM,
    ):
        raise ValueError("Split supplier inventory changed")
    ledger = db.execute(
        "SELECT COALESCE(SUM(quantity),0) FROM stock_movements "
        "WHERE product_id=? AND warehouse_id=?",
        (PRODUCT_ID, WAREHOUSE_ID),
    ).fetchone()[0]
    if inventory["on_hand"] != ledger:
        raise ValueError("Split supplier inventory does not reconcile with stock ledger")


def build_split_completion_release(source: Path, state: Path, authored: Path, output: Path) -> dict:
    """Build an immutable successor from the audited installed r14 release."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected an audited r14 parent")
    catalog = json.loads((source / "catalog.json").read_text("utf-8"))
    current = [
        item
        for item in catalog["documents"]
        if item["document_id"] == DOCUMENT_ID and item["status"] == "current"
    ]
    if len(current) != 1 or current[0]["version"] != 1:
        raise ValueError("Expected the original current Purchasing review v1")
    old = current[0]
    if old["facts"]["outstanding"] != QUANTITY or old["facts"]["received"] != 9:
        raise ValueError("Original Purchasing review facts changed")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        _assert_order(db, completed=False)
    finally:
        db.close()
    body = authored.read_text("utf-8")
    required = (
        ORDER_ID,
        LINE_ID,
        PRODUCT_ID,
        INVENTORY_ID,
        RECEIPT_ID,
        MOVEMENT_ID,
        *[entry[0] for entry in RECEIPTS],
        DOCUMENT_ID + ":v1",
    )
    if not body.startswith("# ") or any(value not in body for value in required):
        raise ValueError("Completion review omits a linked record")
    for phrase in ("15 ordered", "5 + 4 + 6 = 15 received", "0 outstanding", "35 on hand"):
        if phrase not in body:
            raise ValueError(f"Completion review omits reconciliation: {phrase}")

    shutil.copytree(source, output)
    (output / "installed.json").unlink(missing_ok=True)
    old_body = (source / old["relative_path"]).read_text("utf-8").split("---\n", 2)[2]
    superseded = _write_controlled(
        output, {**old, "status": "superseded", "effective_until": EFFECTIVE_FROM}, old_body
    )
    facts = {
        **old["facts"],
        "received": 15,
        "outstanding": 0,
        "receipts": [
            *old["facts"]["receipts"],
            {
                "receipt_id": RECEIPT_ID,
                "movement_id": MOVEMENT_ID,
                "received_on": EFFECTIVE_FROM,
                "quantity": QUANTITY,
            },
        ],
        "inventory_id": INVENTORY_ID,
        "on_hand_as_of_completion": 35,
        "reserved_as_of_completion": 4,
        "previous_version": DOCUMENT_ID + ":v1",
    }
    current_review = _write_controlled(
        output,
        {
            **old,
            "version": 2,
            "status": "current",
            "effective_from": EFFECTIVE_FROM,
            "effective_until": None,
            "revision": REVISION,
            "title": "Supplier order review: completed garland delivery",
            "facts": facts,
        },
        body,
    )
    catalog["documents"] = [
        entry
        for entry in catalog["documents"]
        if not (entry["document_id"] == DOCUMENT_ID and entry["status"] == "current")
    ] + [superseded, current_review]
    catalog["documents"].sort(key=lambda entry: (entry["document_id"], entry["version"]))
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
        "document_ids": len({entry["document_id"] for entry in catalog["documents"]}),
        "versions": len(catalog["documents"]),
        "new_receipts": 1,
        "new_stock_movements": 1,
        "revised_supplier_reviews": 1,
        "effective_from": EFFECTIVE_FROM,
    }
    (output / "release_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    (output / "editorial_review.json").write_text(
        json.dumps(
            [
                {
                    "document_id": DOCUMENT_ID,
                    "previous_version": 1,
                    "new_version": 2,
                    "review": (
                        "Final receipt and stock movement close the 15-unit order; "
                        "prior open review retained"
                    ),
                }
            ],
            indent=2,
        )
        + "\n",
        "utf-8",
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"Completion bundle failed audit: {audit['issues']}")
    return manifest


def _transform(db) -> None:
    _assert_order(db, completed=False)
    db.execute(
        "INSERT INTO goods_receipts VALUES(?,?,?,?)",
        (RECEIPT_ID, LINE_ID, EFFECTIVE_FROM, QUANTITY),
    )
    db.execute(
        "INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)",
        (
            MOVEMENT_ID,
            WAREHOUSE_ID,
            PRODUCT_ID,
            EFFECTIVE_FROM,
            "receipt",
            QUANTITY,
            None,
            RECEIPT_ID,
        ),
    )
    db.execute("UPDATE purchase_orders SET status='received' WHERE id=?", (ORDER_ID,))
    db.execute(
        "UPDATE inventory SET on_hand=on_hand+?,as_of=? WHERE id=?",
        (QUANTITY, EFFECTIVE_FROM, INVENTORY_ID),
    )


def _validate(db, catalog: list[dict], documents: Path) -> None:
    _assert_order(db, completed=True)
    versions = [entry for entry in catalog if entry["document_id"] == DOCUMENT_ID]
    if [(item["version"], item["status"]) for item in versions] != [
        (1, "superseded"),
        (2, "current"),
    ]:
        raise ValueError("Supplier review version history changed")
    if versions[0]["facts"]["outstanding"] != 6 or versions[1]["facts"]["outstanding"] != 0:
        raise ValueError("Supplier review quantities do not preserve history")
    body = (documents / versions[1]["relative_path"]).read_text("utf-8")
    if RECEIPT_ID not in body or "35 on hand" not in body:
        raise ValueError("Current supplier review lost its completion evidence")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Completion release creates broken references")


def install_split_completion_release(project: Path, state: Path, bundle: Path) -> dict:
    """Install the staged r15 SQLite and document revision with backup."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_transform=_transform,
        database_validator=_validate,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
