"""Allowlisted projections and parameterized queries. No caller-supplied SQL."""

from acme.app_store import authorize, event
from acme.dataset import connect

# entity: (permission, fixed projection, parent filter column, status column, text column)
QUERIES = {
    "customers": (
        "commercial.read",
        "SELECT id,name,source_customer_id,segment,payment_terms_days FROM customers",
        None,
        None,
        "name",
    ),
    "orders": (
        "commercial.read",
        "SELECT id,customer_id,ordered_at,status,currency,source_invoice_no,provenance "
        "FROM orders",
        "customer_id",
        "status",
        None,
    ),
    "order_items": (
        "commercial.read",
        (
            "SELECT "
            "id,order_id,product_id,quantity,shipped_quantity,"
            "quantity-shipped_quantity AS unshipped_quantity,"
            "raw_unit_price_gbp,line_pence,source_row_id FROM order_fulfillment"
        ),
        "order_id",
        None,
        None,
    ),
    "products": (
        "commercial.read",
        "SELECT id,name,source_stock_code,category_id,provenance FROM products",
        "category_id",
        None,
        "name",
    ),
    "employees": (
        "commercial.read",
        "SELECT id,name,job_title,email FROM employees",
        None,
        None,
        "name",
    ),
    "invoices": (
        "finance.read",
        (
            "SELECT id,order_id,posted_on,due_on,total_pence,outstanding_pence,currency,"
            "provenance FROM "
            "invoice_balances"
        ),
        "order_id",
        None,
        None,
    ),
    "invoice_items": (
        "finance.read",
        "SELECT id,invoice_id,order_item_id,quantity,amount_pence FROM invoice_items",
        "invoice_id",
        None,
        None,
    ),
    "payments": (
        "finance.read",
        (
            "SELECT id,customer_id,received_on,amount_pence,currency,"
            "(SELECT COUNT(*) FROM payment_allocations a "
            "WHERE a.payment_id=payments.id) AS allocation_count,"
            "COALESCE((SELECT SUM(a.amount_pence) FROM payment_allocations a "
            "WHERE a.payment_id=payments.id),0) AS allocated_pence,"
            "amount_pence-COALESCE((SELECT SUM(a.amount_pence) FROM payment_allocations a "
            "WHERE a.payment_id=payments.id),0) AS unallocated_pence FROM payments"
        ),
        "customer_id",
        None,
        None,
    ),
    "payment_allocations": (
        "finance.read",
        "SELECT id,payment_id,invoice_id,allocated_on,amount_pence FROM payment_allocations",
        "invoice_id",
        None,
        None,
    ),
    "credit_notes": (
        "finance.read",
        "SELECT id,invoice_id,issued_on,amount_pence,reason FROM credit_notes",
        "invoice_id",
        None,
        None,
    ),
    "company_expenses": (
        "finance.read",
        "SELECT id,paid_on,category,payee,amount_pence,currency,supplier_id,"
        "purchase_order_id,description,provenance FROM company_expenses",
        "purchase_order_id",
        "category",
        "payee",
    ),
    "shipments": (
        "operations.read",
        "SELECT id,order_id,warehouse_id,dispatched_on,delivered_on,carrier,provenance "
        "FROM shipments",
        "order_id",
        None,
        None,
    ),
    "shipment_items": (
        "operations.read",
        "SELECT id,shipment_id,order_item_id,quantity FROM shipment_items",
        "shipment_id",
        None,
        None,
    ),
    "stock_movements": (
        "operations.read",
        "SELECT id,warehouse_id,product_id,occurred_on,kind,quantity,"
        "shipment_item_id,goods_receipt_id FROM stock_movements",
        "product_id",
        "kind",
        None,
    ),
    "inventory": (
        "operations.read",
        (
            "SELECT i.id,i.warehouse_id,i.product_id,i.on_hand,i.reserved,"
            "i.on_hand-i.reserved AS available,MAX(0,COALESCE((SELECT "
            "SUM(f.quantity-f.shipped_quantity) FROM order_fulfillment f JOIN orders o "
            "ON o.id=f.order_id WHERE f.product_id=i.product_id AND "
            "o.status!='cancelled'),0)-i.reserved) AS backordered,i.as_of FROM inventory i"
        ),
        "product_id",
        None,
        None,
    ),
    "purchase_orders": (
        "operations.read",
        (
            "SELECT po.id,po.supplier_id,po.warehouse_id,po.placed_on,po.expected_on,"
            "po.status,po.provenance,COALESCE(t.line_count,0) AS line_count,"
            "COALESCE(t.ordered_quantity,0) AS ordered_quantity,"
            "COALESCE(t.received_quantity,0) AS received_quantity,"
            "COALESCE(t.ordered_quantity,0)-COALESCE(t.received_quantity,0) "
            "AS outstanding_quantity,COALESCE(t.receipt_count,0) AS receipt_count "
            "FROM purchase_orders po LEFT JOIN ("
            "SELECT pi.purchase_order_id,COUNT(*) AS line_count,"
            "SUM(pi.quantity) AS ordered_quantity,"
            "SUM(COALESCE((SELECT SUM(gr.quantity) FROM goods_receipts gr "
            "WHERE gr.purchase_order_item_id=pi.id),0)) AS received_quantity,"
            "SUM((SELECT COUNT(*) FROM goods_receipts gr "
            "WHERE gr.purchase_order_item_id=pi.id)) AS receipt_count "
            "FROM purchase_order_items pi GROUP BY pi.purchase_order_id"
            ") t ON t.purchase_order_id=po.id"
        ),
        "supplier_id",
        "status",
        None,
    ),
    "purchase_order_items": (
        "operations.read",
        (
            "SELECT pi.id,pi.purchase_order_id,pi.product_id,pi.quantity,"
            "(SELECT COUNT(*) FROM goods_receipts gr "
            "WHERE gr.purchase_order_item_id=pi.id) AS receipt_count,"
            "COALESCE((SELECT SUM(gr.quantity) FROM goods_receipts gr "
            "WHERE gr.purchase_order_item_id=pi.id),0) AS received_quantity,"
            "pi.quantity-COALESCE((SELECT SUM(gr.quantity) FROM goods_receipts gr "
            "WHERE gr.purchase_order_item_id=pi.id),0) AS outstanding_quantity "
            "FROM purchase_order_items pi"
        ),
        "purchase_order_id",
        None,
        None,
    ),
    "goods_receipts": (
        "operations.read",
        "SELECT id,purchase_order_item_id,received_on,quantity FROM goods_receipts",
        "purchase_order_item_id",
        None,
        None,
    ),
    "tickets": (
        "support.read",
        "SELECT id,order_id,opened_on,status,topic,description FROM tickets",
        "order_id",
        "status",
        "description",
    ),
    "ticket_events": (
        "support.read",
        "SELECT id,ticket_id,occurred_on,status,note FROM ticket_events",
        "ticket_id",
        "status",
        None,
    ),
    "forecasts": (
        "analytics.read",
        (
            "SELECT id,run_id,product_id,units,training_units,training_last_date,input_sha256 "
            "FROM forecasts"
        ),
        "run_id",
        None,
        None,
    ),
    "forecast_runs": (
        "analytics.read",
        (
            "SELECT "
            "id,generated_at,training_cutoff,target_start,target_end,"
            "method,method_version,lookback_months,assumption "
            "FROM forecast_runs"
        ),
        None,
        None,
        None,
    ),
    "sales_targets": (
        "analytics.read",
        "SELECT id,department_id,forecast_id,target_units,assumption FROM sales_targets",
        "forecast_id",
        None,
        None,
    ),
}


def query(context, label, sql, parameters, permission):
    """Log only SQL that was actually executed, with row count and correlation IDs."""
    authorize(context, permission)
    db = connect(context.state / "company.sqlite", readonly=True)
    try:
        rows = [dict(row) for row in db.execute(sql, parameters)]
    finally:
        db.close()
    identifier = event(
        context,
        "sql",
        {
            "integration": "simulated_company_sqlite",
            "label": label,
            "sql": sql,
            "parameters": list(parameters),
            "row_count": len(rows),
            "permission": permission,
        },
    )
    return rows, identifier
