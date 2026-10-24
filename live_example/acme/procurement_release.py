"""Audited r9 wording correction for one fictional supplier review."""

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

REVISION = "acme-documents-2026-r9"
PARENT = "acme-documents-2026-r8"
EFFECTIVE_FROM = "2026-10-21"
DOCUMENT_ID = "PROCURE-79511D9988BA"
ORDER_ID = "SCN-PO-79511D9988BA"
OLD_REASON = "Supplier short shipped six of eighteen units"
NEW_REASON = "Supplier sent 6 of 18 units; 12 remain outstanding"


def _check_facts(db, item: dict) -> None:
    facts = item["facts"]
    if (
        item["document_id"] != DOCUMENT_ID
        or facts["purchase_order_id"] != ORDER_ID
        or facts["ordered"] != 18
        or facts["received"] != 6
    ):
        raise ValueError("Unexpected supplier-review facts")
    line = db.execute(
        "SELECT quantity FROM purchase_order_items WHERE id=? AND purchase_order_id=?",
        (facts["item_id"], ORDER_ID),
    ).fetchone()
    receipt = db.execute(
        "SELECT quantity FROM goods_receipts WHERE id=? AND purchase_order_item_id=?",
        (facts["receipt_id"], facts["item_id"]),
    ).fetchone()
    movement = db.execute(
        "SELECT quantity,goods_receipt_id FROM stock_movements WHERE id=?",
        (facts["movement_id"],),
    ).fetchone()
    if not (
        line
        and receipt
        and movement
        and line["quantity"] == 18
        and receipt["quantity"] == 6
        and movement["quantity"] == 6
        and movement["goods_receipt_id"] == facts["receipt_id"]
    ):
        raise ValueError("Supplier-review quantities or links disagree with SQLite")


def build_procurement_release(source: Path, state: Path, authored: Path, output: Path) -> dict:
    """Build a new immutable successor from the audited installed r8 bundle."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected an audited r8 parent")
    catalog = json.loads((source / "catalog.json").read_text(encoding="utf-8"))
    current = [
        item
        for item in catalog["documents"]
        if item["document_id"] == DOCUMENT_ID and item["status"] == "current"
    ]
    if len(current) != 1 or current[0]["version"] != 2:
        raise ValueError("Expected exactly one current v2 supplier review")
    item = current[0]
    if item["facts"]["reason"] != OLD_REASON:
        raise ValueError("Supplier-review reason has changed")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        _check_facts(db, item)
        row = db.execute(
            "SELECT provenance FROM purchase_orders WHERE id=?", (ORDER_ID,)
        ).fetchone()
        if not row or row["provenance"] != f"fictional_contemporary_seed: {OLD_REASON}":
            raise ValueError("Expected the original fictional purchase-order provenance")
    finally:
        db.close()
    body = authored.read_text(encoding="utf-8")
    if (
        body.count(NEW_REASON) != 1
        or OLD_REASON in body
        or "12 units still outstanding" not in body
    ):
        raise ValueError("Authored correction must state the received and outstanding quantities")
    shutil.copytree(source, output)
    (output / "installed.json").unlink(missing_ok=True)
    old_body = (source / item["relative_path"]).read_text(encoding="utf-8").split("---\n", 2)[2]
    older = _write_controlled(
        output, {**item, "status": "superseded", "effective_until": EFFECTIVE_FROM}, old_body
    )
    newer = _write_controlled(
        output,
        {
            **item,
            "version": 3,
            "status": "current",
            "effective_from": EFFECTIVE_FROM,
            "effective_until": None,
            "revision": REVISION,
            "facts": {**item["facts"], "reason": NEW_REASON},
        },
        body,
    )
    revised = []
    for entry in catalog["documents"]:
        if entry["document_id"] == DOCUMENT_ID and entry["status"] == "current":
            revised.extend((older, newer))
        else:
            revised.append(entry)
    revised.sort(key=lambda entry: (entry["document_id"], entry["version"]))
    catalog.update({"revision": REVISION, "documents": revised})
    catalog_path = output / "catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "document_ids": len({entry["document_id"] for entry in revised}),
        "versions": len(revised),
        "revised_supplier_reviews": 1,
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
                    "previous_version": 2,
                    "new_version": 3,
                    "correction": "State that 6 units arrived and 12 remain outstanding",
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"Supplier-review release failed audit: {audit['issues']}")
    return manifest


def _transform(db) -> None:
    cursor = db.execute(
        "UPDATE purchase_orders SET provenance=? WHERE id=? AND provenance=?",
        (
            f"fictional_contemporary_seed: {NEW_REASON}",
            ORDER_ID,
            f"fictional_contemporary_seed: {OLD_REASON}",
        ),
    )
    if cursor.rowcount != 1:
        raise ValueError("Purchase-order provenance changed before installation")


def _validate(db, catalog: list[dict], documents: Path) -> None:
    current = [
        item
        for item in catalog
        if item["document_id"] == DOCUMENT_ID and item["status"] == "current"
    ]
    if len(current) != 1 or current[0]["version"] != 3:
        raise ValueError("Corrected supplier review is not current v3")
    item = current[0]
    _check_facts(db, item)
    body = (documents / item["relative_path"]).read_text(encoding="utf-8").split("---\n", 2)[2]
    if item["facts"]["reason"] != NEW_REASON or body.count(NEW_REASON) != 1:
        raise ValueError("Supplier-review body or facts do not carry the correction")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Document release breaks database relationships")


def install_procurement_release(project: Path, state: Path, bundle: Path) -> dict:
    """Install r9 with the shared staged, backed-up revision transaction."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_transform=_transform,
        database_validator=_validate,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
