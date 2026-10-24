"""Add factual purchasing and planning working notes to the document register."""

import hashlib
import json
import shutil
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import _write_controlled, audit_revision_bundle

REVISION = "acme-documents-2026-r4"
EFFECTIVE_FROM = "2026-10-20"


def _purchasing_note(f: dict) -> str:
    outstanding = f["ordered"] - f["received"]
    receipt = (
        f"Goods receipt `{f['receipt_id']}` records {f['received']} units on "
        f"{f['received_on']}. Matching stock movement `{f['movement_id']}` adds exactly "
        f"{f['received']} units to {f['warehouse_name']}."
        if f["received"]
        else "No goods receipt or receipt stock movement is recorded for this order."
    )
    decision = (
        "The line is complete; close the supplier follow-up only after reconciling "
        "the receipt, movement and warehouse count."
        if outstanding == 0
        else f"Keep the purchase order open for {outstanding} outstanding units. Ask the "
        "supplier for a dated revised commitment, and record any later receipt as a "
        "new event rather than editing the original expected date."
    )
    return (
        f"# Supplier order review: {f['supplier_name']} / {f['product_name']}\n\n"
        f"## Scope and record owner\n\nPurchasing owns this fictional 2026 review of "
        f"purchase order `{f['purchase_order_id']}` and line `{f['item_id']}`. It concerns "
        f"{f['product_name']} (`{f['product_id']}`) from {f['supplier_name']} "
        f"(`{f['supplier_id']}`) for {f['warehouse_name']} (`{f['warehouse_id']}`). "
        "This document records exercise evidence at issue date; it is not a supplier "
        "acknowledgement or a customer delivery promise.\n\n"
        f"## Timeline and quantity position\n\nThe order was placed on {f['placed_on']} "
        f"for {f['ordered']} units, with an original expected date of {f['expected_on']}. "
        f"Its current database status is **{f['status']}**. {receipt} The verified "
        f"recorded balance is {outstanding} units still outstanding against this line. "
        "The ordered quantity is a purchasing request; only a goods receipt and "
        "matching stock movement establish physical arrival.\n\n"
        f"## Review decision and next action\n\nThe recorded purchasing context says: "
        f"{f['reason']}. {decision} Check the on-hand and reserved stock separately "
        "before allocating units to a customer order. A confirmed customer order "
        "sharing this product does not by itself reserve this supplier line.\n\n"
        f"## Evidence and handoff\n\nWarehouse Operations should compare the "
        "receipt quantity and condition with the physical count. Sales can describe "
        "an order's current fulfilment status only from that order and its shipment "
        "records. Keep the purchase order, line, receipt and movement identifiers "
        "together when escalating a delayed or short delivery.\n"
    )


def _planning_note(f: dict) -> str:
    interpretation = (
        "An empty short lookback is a limitation of the selected window, not proof "
        "of no demand. Compare the longer-window version before discussing the "
        "planner's minimum with Sales."
        if f["units"] == 0
        else "The target exceeds the model output as a commercial planning choice. "
        "It is not a second forecast or evidence that the extra units will sell."
    )
    return (
        f"# October demand review: {f['product_name']} / method v{f['method_version']}\n\n"
        f"## Decision record\n\nAnalytics recorded forecast `{f['forecast_id']}` "
        f"for product `{f['product_id']}` in run `{f['run_id']}`. It was generated "
        f"on {f['generated_at']} for {f['target_start']} through {f['target_end']}. "
        f"The run's stated assumption is: {f['assumption']} This is a fictional "
        "contemporary planning exercise, separate from the 2011 source archive.\n\n"
        f"## Inputs and reproducibility\n\nThe {f['lookback_months']} preceding "
        f"complete calendar months contain {f['training_units']} billed units for "
        f"this product. The last qualifying invoice date is "
        f"{f['training_last_date'] or 'none'}. The hard input cutoff is "
        f"{f['training_cutoff']}; target-month invoices are excluded. Divide the "
        "training total by the lookback length and round half up to a whole unit. "
        f"The frozen input fingerprint is `{f['input_sha256']}`. Retain the "
        "underlying invoice-line IDs when reproducing a decision.\n\n"
        f"## Forecast, target and interpretation\n\nThe model output is "
        f"**{f['units']} units**. Sales target `{f['target_id']}` is "
        f"**{f['target_units']} units**. Its recorded rationale says: "
        f"{f['target_assumption']} {interpretation} Compare method versions "
        "for the same product and target month using both their lookbacks and "
        "input cutoffs.\n\n"
        "## Follow-up\n\nSales should review current order demand and Operations "
        "should check available stock and open supplier orders before making a "
        "commitment. At the end of October, calculate actual billed units against "
        "this frozen forecast in a separate review. Do not rewrite the input "
        "fingerprint or treat a partial month as a complete outcome.\n"
    )


def build_business_notes_bundle(source: Path, state: Path, output: Path) -> dict:
    """Create an immutable r4 successor from verified r3 and live linked facts."""
    if output.exists():
        raise ValueError("Choose a new document-release directory")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != "acme-documents-2026-r3":
        raise ValueError("Expected the verified r3 document release")
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    shutil.copytree(source, output)
    register_path = output / "catalog.json"
    register = json.loads(register_path.read_text("utf-8"))
    db = connect(state / "company.sqlite", readonly=True)
    try:
        purchasing = db.execute(
            "SELECT po.id AS purchase_order_id,po.supplier_id,s.name AS supplier_name,"
            "po.warehouse_id,w.name AS warehouse_name,po.placed_on,po.expected_on,"
            "po.status,po.provenance AS reason,pi.id AS item_id,pi.product_id,"
            "p.name AS product_name,pi.quantity AS ordered,gr.id AS receipt_id,"
            "gr.quantity AS received,gr.received_on,m.id AS movement_id "
            "FROM purchase_orders po JOIN suppliers s ON s.id=po.supplier_id "
            "JOIN warehouses w ON w.id=po.warehouse_id JOIN purchase_order_items pi "
            "ON pi.purchase_order_id=po.id JOIN products p ON p.id=pi.product_id "
            "LEFT JOIN goods_receipts gr ON gr.purchase_order_item_id=pi.id "
            "LEFT JOIN stock_movements m ON m.goods_receipt_id=gr.id "
            "WHERE po.id LIKE 'SCN-PO-%' ORDER BY po.id"
        ).fetchall()
        if len(purchasing) != 3:
            raise ValueError("Expected three contemporary supplier order cases")
        purchase_owner = db.execute(
            "SELECT employee_id FROM employee_assignments WHERE department_id='DEP-PURCHASE' "
            "AND valid_until IS NULL ORDER BY employee_id LIMIT 1"
        ).fetchone()[0]
        for row in purchasing:
            facts = dict(row)
            facts["received"] = facts["received"] or 0
            facts["source_provenance"], _, facts["reason"] = facts["reason"].partition(": ")
            identifier = "PROCURE-" + facts["purchase_order_id"].removeprefix("SCN-PO-")
            register["documents"].append(
                _write_controlled(
                    output,
                    {
                        "document_id": identifier,
                        "title": f"Supplier order review: {facts['supplier_name']}",
                        "category": "procurement_cases",
                        "owner_employee_id": purchase_owner,
                        "access_scope": "operations",
                        "version": 1,
                        "effective_from": EFFECTIVE_FROM,
                        "effective_until": None,
                        "status": "current",
                        "record_links": {
                            "product_id": facts["product_id"],
                            "warehouse_id": facts["warehouse_id"],
                        },
                        "facts": facts,
                        "revision": REVISION,
                    },
                    _purchasing_note(facts),
                )
            )
        planning = db.execute(
            "SELECT f.id AS forecast_id,f.product_id,p.name AS product_name,"
            "f.units,f.training_units,f.training_last_date,f.input_sha256,"
            "r.id AS run_id,r.generated_at,r.training_cutoff,r.target_start,"
            "r.target_end,r.method_version,r.lookback_months,r.assumption,"
            "t.id AS target_id,t.target_units,t.assumption AS target_assumption "
            "FROM forecasts f JOIN forecast_runs r ON r.id=f.run_id "
            "JOIN products p ON p.id=f.product_id JOIN sales_targets t "
            "ON t.forecast_id=f.id WHERE f.id LIKE 'SCN-FC-%' ORDER BY f.id"
        ).fetchall()
        if len(planning) != 4:
            raise ValueError("Expected four contemporary forecast comparisons")
        analytics_owner = db.execute(
            "SELECT employee_id FROM employee_assignments WHERE department_id='DEP-ANALYTICS' "
            "AND valid_until IS NULL ORDER BY employee_id LIMIT 1"
        ).fetchone()[0]
        for row in planning:
            facts = dict(row)
            identifier = "PLAN-" + facts["forecast_id"].removeprefix("SCN-FC-")
            register["documents"].append(
                _write_controlled(
                    output,
                    {
                        "document_id": identifier,
                        "title": (
                            f"October demand review: {facts['product_name']} "
                            f"v{facts['method_version']}"
                        ),
                        "category": "planning_commentary",
                        "owner_employee_id": analytics_owner,
                        "access_scope": "analytics",
                        "version": 1,
                        "effective_from": EFFECTIVE_FROM,
                        "effective_until": None,
                        "status": "current",
                        "record_links": {
                            "forecast_id": facts["forecast_id"],
                            "product_id": facts["product_id"],
                        },
                        "facts": facts,
                        "revision": REVISION,
                    },
                    _planning_note(facts),
                )
            )
    finally:
        db.close()
    register["revision"] = REVISION
    register["documents"].sort(key=lambda item: (item["document_id"], item["version"]))
    register_path.write_text(
        json.dumps(register, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in register["documents"]}),
        "versions": len(register["documents"]),
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"New document bundle failed audit: {audit['issues']}")
    return manifest
