"""Read-only, provenance-aware view of one order's linked business history."""

from pathlib import Path

from acme.dataset import connect


def order_journey(state: Path, order_id: str) -> dict | None:
    db = connect(state / "company.sqlite", readonly=True)
    try:
        order = db.execute(
            "SELECT o.*, c.name AS customer_name FROM orders o "
            "JOIN customers c ON c.id=o.customer_id WHERE o.id=?",
            (order_id,),
        ).fetchone()
        if order is None:
            return None
        order = dict(order)
        observed = order["source_invoice_no"] is not None
        scenario = "reconstructed workflow" if observed else "authored scenario"
        events = []

        def add(date, kind, title, detail, basis, table, record_id, amount_pence=None):
            events.append(
                {
                    "date": date,
                    "kind": kind,
                    "title": title,
                    "detail": detail,
                    "basis": basis,
                    "table": table,
                    "record_id": record_id,
                    "amount_pence": amount_pence,
                }
            )

        add(
            order["ordered_at"], "order", "Order accepted", order["customer_name"],
            scenario, "orders", order_id,
        )
        for row in db.execute(
            "SELECT * FROM order_status_history WHERE order_id=? ORDER BY occurred_at,id",
            (order_id,),
        ):
            if row["status"] == "confirmed" and row["occurred_at"] == order["ordered_at"]:
                continue
            add(
                row["occurred_at"], "status", f"Status: {row['status']}",
                row["reason"], scenario, "order_status_history", row["id"],
            )

        items = [
            dict(row)
            for row in db.execute(
                "SELECT oi.id, oi.product_id, p.name AS product_name, oi.quantity, "
                "oi.line_pence, f.shipped_quantity FROM order_items oi "
                "JOIN products p ON p.id=oi.product_id "
                "JOIN order_fulfillment f ON f.id=oi.id WHERE oi.order_id=? ORDER BY oi.id",
                (order_id,),
            )
        ]
        invoice_row = db.execute(
            "SELECT * FROM invoice_balances WHERE order_id=?", (order_id,)
        ).fetchone()
        invoice = dict(invoice_row) if invoice_row else None
        if invoice:
            add(
                invoice["posted_on"], "invoice", "Invoice posted",
                f"Due {invoice['due_on']}; total calculated from invoice lines.",
                "observed source invoice date; calculated amount"
                if observed else "authored scenario",
                "invoices", invoice["id"], invoice["total_pence"],
            )

        shipments = db.execute(
            "SELECT s.*, COALESCE(SUM(si.quantity),0) AS units "
            "FROM shipments s LEFT JOIN shipment_items si ON si.shipment_id=s.id "
            "WHERE s.order_id=? GROUP BY s.id ORDER BY s.dispatched_on,s.id",
            (order_id,),
        ).fetchall()
        for row in shipments:
            basis = "modeled logistics" if observed else "authored scenario"
            add(
                row["dispatched_on"], "dispatch", "Shipment dispatched",
                f"{row['units']} units via {row['carrier']}", basis, "shipments", row["id"],
            )
            if row["delivered_on"]:
                add(
                    row["delivered_on"], "delivery", "Shipment delivered",
                    f"{row['units']} units; delivery date follows the modeled route.",
                    basis, "shipments", row["id"],
                )

        if invoice:
            for row in db.execute(
                "SELECT a.id,a.allocated_on,a.amount_pence,p.id AS payment_id,p.received_on "
                "FROM payment_allocations a JOIN payments p ON p.id=a.payment_id "
                "WHERE a.invoice_id=? ORDER BY a.allocated_on,a.id",
                (invoice["id"],),
            ):
                add(
                    row["allocated_on"], "payment", "Payment allocated",
                    f"Payment {row['payment_id']} received {row['received_on']}.",
                    "modeled settlement" if observed else "authored scenario",
                    "payments", row["payment_id"], row["amount_pence"],
                )
            for row in db.execute(
                "SELECT * FROM credit_notes WHERE invoice_id=? ORDER BY issued_on,id",
                (invoice["id"],),
            ):
                add(
                    row["issued_on"], "credit", "Credit note issued", row["reason"],
                    "authored credit scenario", "credit_notes", row["id"],
                    row["amount_pence"],
                )

        for row in db.execute(
            "SELECT t.id AS ticket_id,t.topic,e.id,e.occurred_on,e.status,e.note "
            "FROM tickets t JOIN ticket_events e ON e.ticket_id=t.id "
            "WHERE t.order_id=? ORDER BY e.occurred_on,e.id",
            (order_id,),
        ):
            add(
                row["occurred_on"], "ticket", f"Service: {row['status']}",
                f"{row['topic']} — {row['note']}", "authored service scenario",
                "tickets", row["ticket_id"],
            )

        events.sort(key=lambda event: (event["date"], event["kind"], event["record_id"]))
        return {"order": order, "invoice": invoice, "items": items, "events": events}
    finally:
        db.close()
