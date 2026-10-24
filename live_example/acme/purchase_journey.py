"""Read-only supplier order history assembled from exact linked records."""

from pathlib import Path

from acme.dataset import connect

PREVIEW_LIMIT = 50


def purchase_journey(state: Path, purchase_order_id: str) -> dict | None:
    db = connect(state / "company.sqlite", readonly=True)
    try:
        header = db.execute(
            "SELECT po.*,s.name AS supplier_name,w.name AS warehouse_name "
            "FROM purchase_orders po JOIN suppliers s ON s.id=po.supplier_id "
            "JOIN warehouses w ON w.id=po.warehouse_id WHERE po.id=?",
            (purchase_order_id,),
        ).fetchone()
        if header is None:
            return None
        order = dict(header)
        totals = dict(db.execute(
            "SELECT COUNT(*) AS line_count,COALESCE(SUM(pi.quantity),0) AS ordered_units,"
            "COALESCE(SUM((SELECT SUM(gr.quantity) FROM goods_receipts gr "
            "WHERE gr.purchase_order_item_id=pi.id)),0) AS received_units,"
            "COALESCE(SUM((SELECT COUNT(*) FROM goods_receipts gr "
            "WHERE gr.purchase_order_item_id=pi.id)),0) AS receipt_count "
            "FROM purchase_order_items pi WHERE pi.purchase_order_id=?",
            (purchase_order_id,),
        ).fetchone())
        totals["outstanding_units"] = totals["ordered_units"] - totals["received_units"]
        lines = [dict(row) for row in db.execute(
            "SELECT pi.id,pi.product_id,p.name AS product_name,pi.quantity AS ordered_units,"
            "COALESCE((SELECT SUM(gr.quantity) FROM goods_receipts gr "
            "WHERE gr.purchase_order_item_id=pi.id),0) AS received_units,"
            "i.id AS inventory_id,i.on_hand,i.reserved,i.as_of AS inventory_as_of "
            "FROM purchase_order_items pi JOIN products p ON p.id=pi.product_id "
            "LEFT JOIN inventory i ON i.product_id=pi.product_id "
            "AND i.warehouse_id=? WHERE pi.purchase_order_id=? ORDER BY pi.id LIMIT ?",
            (order["warehouse_id"], purchase_order_id, PREVIEW_LIMIT),
        )]
        for line in lines:
            line["outstanding_units"] = line["ordered_units"] - line["received_units"]
        receipts = [dict(row) for row in db.execute(
            "SELECT gr.id,gr.received_on,gr.quantity,gr.purchase_order_item_id,"
            "pi.product_id,p.name AS product_name,m.id AS movement_id,"
            "m.quantity AS movement_quantity,m.occurred_on AS movement_on,"
            "m.kind AS movement_kind,m.warehouse_id AS movement_warehouse_id,"
            "m.product_id AS movement_product_id "
            "FROM goods_receipts gr JOIN purchase_order_items pi "
            "ON pi.id=gr.purchase_order_item_id JOIN products p ON p.id=pi.product_id "
            "LEFT JOIN stock_movements m ON m.goods_receipt_id=gr.id "
            "WHERE pi.purchase_order_id=? ORDER BY gr.received_on,gr.id LIMIT ?",
            (purchase_order_id, PREVIEW_LIMIT),
        )]
        return {
            "order": order,
            "basis": "authored contemporary scenario" if order["provenance"].startswith(
                "fictional_contemporary_"
            ) else "modeled historical purchasing workflow",
            "totals": totals,
            "lines": lines,
            "receipts": receipts,
            "preview_limit": PREVIEW_LIMIT,
        }
    finally:
        db.close()
