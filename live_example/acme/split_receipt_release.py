"""Audited r10 document and SQLite release for one fictional split supplier receipt."""

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

REVISION = "acme-documents-2026-r10"
PARENT = "acme-documents-2026-r9"
EFFECTIVE_FROM = "2026-10-21"
DOCUMENT_ID = "PROCURE-SPLIT-75F3A546B17E"
ORDER_ID = "SCN-PO-SPLIT-75F3A546B17E"
LINE_ID = "SCN-POITEM-SPLIT-75F3A546B17E"
PRODUCT_ID = "SCN-SKU-75F3A546B17E"
SUPPLIER_ID = "SUP-03"
WAREHOUSE_ID = "WH-CVT"
INVENTORY_ID = "SCN-INV-75F3A546B17E"
PLACED_ON = "2026-08-26"
EXPECTED_ON = "2026-09-05"
ORDERED = 15
RECEIPTS = (
    (
        "SCN-GR-SPLIT-75F3A546B17E-01",
        "SCN-STOCK-SPLIT-75F3A546B17E-01",
        "2026-09-08",
        5,
    ),
    (
        "SCN-GR-SPLIT-75F3A546B17E-02",
        "SCN-STOCK-SPLIT-75F3A546B17E-02",
        "2026-09-16",
        4,
    ),
)
RECEIVED = sum(quantity for _, _, _, quantity in RECEIPTS)
OUTSTANDING = ORDERED - RECEIVED
PROVENANCE = "fictional_contemporary_seed: two partial supplier receipts; six units outstanding"


def _source_context(db) -> None:
    row = db.execute(
        "SELECT p.supplier_id,i.id AS inventory_id,i.warehouse_id,i.as_of "
        "FROM products p JOIN inventory i ON i.product_id=p.id WHERE p.id=?",
        (PRODUCT_ID,),
    ).fetchone()
    if row is None or (
        row["supplier_id"],
        row["inventory_id"],
        row["warehouse_id"],
    ) != (SUPPLIER_ID, INVENTORY_ID, WAREHOUSE_ID):
        raise ValueError("Split-receipt product, supplier or warehouse has changed")
    if row["as_of"] > date.today().isoformat():
        raise ValueError("Inventory snapshot is dated in the future")
    targets = (
        ("purchase_orders", ORDER_ID),
        ("purchase_order_items", LINE_ID),
        *(("goods_receipts", receipt_id) for receipt_id, _, _, _ in RECEIPTS),
        *(("stock_movements", movement_id) for _, movement_id, _, _ in RECEIPTS),
    )
    for table, identifier in targets:
        if db.execute(f"SELECT 1 FROM {table} WHERE id=?", (identifier,)).fetchone():
            raise ValueError(f"Split-receipt target already exists: {identifier}")


def build_split_receipt_release(
    source: Path, state: Path, authored: Path, output: Path
) -> dict:
    """Build an immutable r10 successor without changing the live database."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected an audited r9 parent")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        _source_context(db)
        owner = db.execute(
            "SELECT employee_id FROM employee_assignments "
            "WHERE department_id='DEP-PURCHASE' AND valid_until IS NULL "
            "ORDER BY employee_id LIMIT 1"
        ).fetchone()
        if owner is None:
            raise ValueError("No current Purchasing document owner")
        owner_id = owner["employee_id"]
    finally:
        db.close()
    body = authored.read_text(encoding="utf-8")
    required = (ORDER_ID, LINE_ID, PRODUCT_ID, SUPPLIER_ID, WAREHOUSE_ID)
    required += tuple(identifier for row in RECEIPTS for identifier in row[:2])
    if not body.startswith("# ") or any(identifier not in body for identifier in required):
        raise ValueError("Authored supplier review omits a linked record ID")
    if "15 units" not in body or "9\nunits" not in body or "6 units outstanding" not in body:
        raise ValueError("Authored supplier review omits the quantity reconciliation")

    shutil.copytree(source, output)
    (output / "installed.json").unlink(missing_ok=True)
    catalog_path = output / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if any(item["document_id"] == DOCUMENT_ID for item in catalog["documents"]):
        raise ValueError("Split-receipt document already exists in parent release")
    facts = {
        "purchase_order_id": ORDER_ID,
        "item_id": LINE_ID,
        "product_id": PRODUCT_ID,
        "supplier_id": SUPPLIER_ID,
        "warehouse_id": WAREHOUSE_ID,
        "placed_on": PLACED_ON,
        "expected_on": EXPECTED_ON,
        "ordered": ORDERED,
        "received": RECEIVED,
        "outstanding": OUTSTANDING,
        "receipts": [
            {"receipt_id": receipt, "movement_id": movement, "received_on": day, "quantity": qty}
            for receipt, movement, day, qty in RECEIPTS
        ],
    }
    catalog["documents"].append(
        _write_controlled(
            output,
            {
                "document_id": DOCUMENT_ID,
                "title": "Supplier order review: two partial garland receipts",
                "category": "procurement_cases",
                "owner_employee_id": owner_id,
                "access_scope": "operations",
                "version": 1,
                "effective_from": EFFECTIVE_FROM,
                "effective_until": None,
                "status": "current",
                "record_links": {"product_id": PRODUCT_ID, "warehouse_id": WAREHOUSE_ID},
                "facts": facts,
                "revision": REVISION,
            },
            body,
        )
    )
    catalog["documents"].sort(key=lambda item: (item["document_id"], item["version"]))
    catalog["revision"] = REVISION
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in catalog["documents"]}),
        "versions": len(catalog["documents"]),
        "new_supplier_reviews": 1,
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
                    "version": 1,
                    "review": (
                        "Two dated partial receipts and stock movements reconcile "
                        "to 9 received and 6 outstanding units"
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
        raise ValueError(f"Split-receipt bundle failed audit: {audit['issues']}")
    return manifest


def _transform(db) -> None:
    _source_context(db)
    db.execute(
        "INSERT INTO purchase_orders VALUES(?,?,?,?,?,?,?)",
        (ORDER_ID, SUPPLIER_ID, WAREHOUSE_ID, PLACED_ON, EXPECTED_ON, "open", PROVENANCE),
    )
    db.execute(
        "INSERT INTO purchase_order_items VALUES(?,?,?,?)",
        (LINE_ID, ORDER_ID, PRODUCT_ID, ORDERED),
    )
    for receipt_id, movement_id, received_on, quantity in RECEIPTS:
        db.execute(
            "INSERT INTO goods_receipts VALUES(?,?,?,?)",
            (receipt_id, LINE_ID, received_on, quantity),
        )
        db.execute(
            "INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)",
            (
                movement_id,
                WAREHOUSE_ID,
                PRODUCT_ID,
                received_on,
                "receipt",
                quantity,
                None,
                receipt_id,
            ),
        )
    cursor = db.execute(
        "UPDATE inventory SET on_hand=on_hand+?,as_of=? WHERE id=?",
        (RECEIVED, date.today().isoformat(), INVENTORY_ID),
    )
    if cursor.rowcount != 1:
        raise ValueError("Split-receipt inventory row disappeared")


def _validate(db, catalog: list[dict], documents: Path) -> None:
    item = next((row for row in catalog if row["document_id"] == DOCUMENT_ID), None)
    if item is None or item["version"] != 1 or item["status"] != "current":
        raise ValueError("Split-receipt document is not the current first version")
    if item["facts"]["received"] != RECEIVED or item["facts"]["outstanding"] != OUTSTANDING:
        raise ValueError("Split-receipt document totals changed")
    body = (documents / item["relative_path"]).read_text("utf-8")
    if ORDER_ID not in body or any(receipt not in body for receipt, _, _, _ in RECEIPTS):
        raise ValueError("Split-receipt document lost its business links")
    header = db.execute(
        "SELECT supplier_id,warehouse_id,placed_on,expected_on,status,provenance "
        "FROM purchase_orders WHERE id=?",
        (ORDER_ID,),
    ).fetchone()
    if header is None or tuple(header) != (
        SUPPLIER_ID, WAREHOUSE_ID, PLACED_ON, EXPECTED_ON, "open", PROVENANCE
    ):
        raise ValueError("Split-receipt purchase order disagrees with the release")
    line = db.execute(
        "SELECT purchase_order_id,product_id,quantity FROM purchase_order_items WHERE id=?",
        (LINE_ID,),
    ).fetchone()
    if line is None or tuple(line) != (ORDER_ID, PRODUCT_ID, ORDERED):
        raise ValueError("Split-receipt purchase line disagrees with the release")
    rows = db.execute(
        "SELECT gr.id,m.id,gr.received_on,gr.quantity,m.quantity,m.goods_receipt_id,"
        "m.product_id,m.warehouse_id,m.occurred_on FROM goods_receipts gr "
        "JOIN stock_movements m ON m.goods_receipt_id=gr.id "
        "WHERE gr.purchase_order_item_id=? ORDER BY gr.id",
        (LINE_ID,),
    ).fetchall()
    observed = [tuple(row) for row in rows]
    expected = [
        (receipt, movement, day, qty, qty, receipt, PRODUCT_ID, WAREHOUSE_ID, day)
        for receipt, movement, day, qty in RECEIPTS
    ]
    if observed != expected:
        raise ValueError("Split receipts and stock movements do not reconcile")
    inventory = db.execute(
        "SELECT i.on_hand,i.reserved,(SELECT COALESCE(SUM(quantity),0) "
        "FROM stock_movements m WHERE m.product_id=i.product_id "
        "AND m.warehouse_id=i.warehouse_id) AS ledger "
        "FROM inventory i WHERE i.id=?",
        (INVENTORY_ID,),
    ).fetchone()
    if inventory is None or inventory["on_hand"] != inventory["ledger"]:
        raise ValueError("Split receipt does not reconcile with inventory")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Split-receipt release creates broken references")


def install_split_receipt_release(project: Path, state: Path, bundle: Path) -> dict:
    """Install the verified r10 bundle with staged SQL and a full online backup."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_transform=_transform,
        database_validator=_validate,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
