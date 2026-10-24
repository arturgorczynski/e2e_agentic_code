"""Read-only order history and clearly defined business activity measures.

This module has no web or agent imports. Amounts are stored as integer GBP
pence. Billing and customer remittances are different measures. A separate,
explicitly fictional ledger records selected 2026 supplier and operating
payments; it does not cover all company costs.
"""

from datetime import date
from pathlib import Path

from acme.dataset import connect
from acme.expense_ledger import has_expense_ledger

PAGE_SIZE = 25
LINE_PREVIEW = 50


def validate_period(start: date, end: date, cohort: str) -> None:
    if cohort not in {"historical", "contemporary"}:
        raise ValueError("Choose historical or contemporary records")
    if start > end or end > date.today():
        raise ValueError("Use an ordered date range ending no later than today")
    if (end.year - start.year) * 12 + end.month - start.month >= 36:
        raise ValueError("Choose a range shorter than 36 calendar months")


def _cohort_filter(alias: str, cohort: str) -> str:
    operator = "LIKE" if cohort == "contemporary" else "NOT LIKE"
    return f"{alias}.provenance {operator} 'fictional_contemporary_%'"


def _months(start: date, end: date) -> list[str]:
    year, month = start.year, start.month
    months = []
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def financial_activity(
    state: Path, start: date, end: date, cohort: str, *, include_settlement: bool = True
) -> dict:
    """Aggregate dated invoice postings, credits and customer remittances.

    Credits use their issue date. Current outstanding is a snapshot of invoices
    posted in the range, so it is not a historical month-end balance.
    """
    validate_period(start, end, cohort)
    months = {month: {"month": month, "invoice_count": 0, "gross_billed_pence": 0,
                      "credits_issued_pence": 0, "net_billing_activity_pence": 0,
                      "payment_count": 0, "customer_cash_received_pence": 0,
                      "expense_count": 0, "recorded_cash_outflow_pence": 0}
              for month in _months(start, end)}
    db = connect(state / "company.sqlite", readonly=True)
    try:
        sources = (
            ("invoices", "i", "posted_on", "total_pence", "gross_billed_pence", "invoice_count"),
            ("credit_notes", "c", "issued_on", "amount_pence", "credits_issued_pence", None),
            (
                "payments", "p", "received_on", "amount_pence",
                "customer_cash_received_pence", "payment_count",
            ),
        )
        for table, alias, day, amount, field, count_field in sources:
            if table == "payments" and not include_settlement:
                continue
            rows = db.execute(
                f"SELECT substr({alias}.{day},1,7) AS month,COUNT(*) AS rows,"
                f"COALESCE(SUM({alias}.{amount}),0) AS amount FROM {table} {alias} "
                f"WHERE {alias}.{day} BETWEEN ? AND ? AND {_cohort_filter(alias, cohort)} "
                "GROUP BY month ORDER BY month",
                (start.isoformat(), end.isoformat()),
            )
            for row in rows:
                month = months[row["month"]]
                month[field] = row["amount"]
                if count_field:
                    month[count_field] = row["rows"]
        rows = list(months.values())
        for row in rows:
            row["net_billing_activity_pence"] = (
                row["gross_billed_pence"] - row["credits_issued_pence"]
            )
        expense_available = has_expense_ledger(db) and cohort == "contemporary"
        expense_categories = None
        if include_settlement and expense_available:
            for row in db.execute(
                "SELECT substr(paid_on,1,7) AS month,COUNT(*) AS rows,"
                "COALESCE(SUM(amount_pence),0) AS amount FROM company_expenses "
                "WHERE paid_on BETWEEN ? AND ? GROUP BY month ORDER BY month",
                (start.isoformat(), end.isoformat()),
            ):
                months[row["month"]]["expense_count"] = row["rows"]
                months[row["month"]]["recorded_cash_outflow_pence"] = row["amount"]
            expense_categories = [dict(row) for row in db.execute(
                "SELECT category,COUNT(*) AS expense_count,SUM(amount_pence) "
                "AS amount_pence FROM company_expenses WHERE paid_on BETWEEN ? AND ? "
                "GROUP BY category ORDER BY amount_pence DESC,category",
                (start.isoformat(), end.isoformat()),
            )]
        outstanding = None
        if include_settlement:
            outstanding = db.execute(
                "SELECT COALESCE(SUM(i.outstanding_pence),0) FROM invoice_balances i "
                f"WHERE i.posted_on BETWEEN ? AND ? AND {_cohort_filter('i', cohort)}",
                (start.isoformat(), end.isoformat()),
            ).fetchone()[0]
    finally:
        db.close()
    if not include_settlement:
        for row in rows:
            row["payment_count"] = None
            row["customer_cash_received_pence"] = None
    if not include_settlement or not expense_available:
        for row in rows:
            row["expense_count"] = None
            row["recorded_cash_outflow_pence"] = None
            row["recorded_cash_difference_pence"] = None
    else:
        for row in rows:
            row["recorded_cash_difference_pence"] = (
                row["customer_cash_received_pence"] - row["recorded_cash_outflow_pence"]
            )
    totals = {
        key: sum(row[key] for row in rows)
        for key in ("invoice_count", "gross_billed_pence", "credits_issued_pence",
                    "net_billing_activity_pence")
    }
    totals["payment_count"] = (
        sum(row["payment_count"] for row in rows) if include_settlement else None
    )
    totals["customer_cash_received_pence"] = (
        sum(row["customer_cash_received_pence"] for row in rows)
        if include_settlement else None
    )
    for key in ("expense_count", "recorded_cash_outflow_pence",
                "recorded_cash_difference_pence"):
        totals[key] = (
            sum(row[key] for row in rows) if include_settlement and expense_available else None
        )
    return {
        "cohort": cohort, "start": start.isoformat(), "end": end.isoformat(),
        "currency": "GBP", "months": rows,
        "expense_ledger_available": expense_available,
        "expense_categories": expense_categories,
        "totals": totals | {"current_outstanding_for_invoice_cohort_pence": outstanding},
        "definitions": {
            "net_billing_activity": (
                "Invoices posted in the period less credit notes issued in the "
                "period; not audited revenue or profit."
            ),
            "customer_cash_received": (
                "Recorded customer remittances by receipt date; historical "
                "remittances are modeled, not bank observations."
            ),
            "outstanding": (
                "Current outstanding balance of invoices posted in the selected "
                "period, not a historical period-end balance."
            ),
            "outflows": (
                "The separate ledger contains authored 2026 scenario payments only. "
                "It is not a complete company expense or supplier-invoice ledger; "
                "the recorded cash difference is not profit. Historical outflows are unavailable."
            ),
        },
    }


def expense_history(
    state: Path, start: date, end: date, cohort: str, *, page: int = 1,
    category: str = "", search: str = "",
) -> dict:
    validate_period(start, end, cohort)
    if not 1 <= page <= 10000:
        raise ValueError("Expense page must be from 1 to 10000")
    if category not in {"", "supplier_payment", "logistics", "packaging", "marketing", "software"}:
        raise ValueError("Unknown expense category")
    search = search.strip()
    if len(search) > 100:
        raise ValueError("Expense search must be at most 100 characters")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        available = has_expense_ledger(db) and cohort == "contemporary"
        if not available:
            return {"available": False, "total": 0, "rows": [], "page": page,
                    "page_size": PAGE_SIZE, "filtered_amount_pence": None}
        where = "WHERE paid_on BETWEEN ? AND ?"
        params = [start.isoformat(), end.isoformat()]
        if category:
            where += " AND category=?"
            params.append(category)
        if search:
            term = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where += (
                " AND (id LIKE ? ESCAPE '\\' OR payee LIKE ? ESCAPE '\\' "
                "OR description LIKE ? ESCAPE '\\' OR COALESCE(supplier_id,'') "
                "LIKE ? ESCAPE '\\' OR COALESCE(purchase_order_id,'') LIKE ? ESCAPE '\\')"
            )
            params.extend([term] * 5)
        summary = db.execute(
            "SELECT COUNT(*) AS total,COALESCE(SUM(amount_pence),0) AS amount "
            "FROM company_expenses " + where, params,
        ).fetchone()
        rows = [dict(row) for row in db.execute(
            "SELECT id,paid_on,category,payee,amount_pence,currency,supplier_id,"
            "purchase_order_id,description,provenance FROM company_expenses "
            + where + " ORDER BY paid_on DESC,id DESC LIMIT ? OFFSET ?",
            (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE),
        )]
        return {"available": True, "total": summary["total"], "rows": rows,
                "page": page, "page_size": PAGE_SIZE,
                "filtered_amount_pence": summary["amount"]}
    finally:
        db.close()


def order_history(
    state: Path, start: date, end: date, cohort: str, *, page: int = 1,
    status: str = "", customer_id: str = "", search: str = "",
) -> dict:
    validate_period(start, end, cohort)
    if not 1 <= page <= 10000:
        raise ValueError("Order page must be from 1 to 10000")
    if status not in {"", "confirmed", "partial", "fulfilled", "cancelled"}:
        raise ValueError("Unknown order status")
    if len(search) > 100 or len(customer_id) > 200:
        raise ValueError("Order filter is too long")
    term = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    where = (
        "FROM orders o JOIN customers c ON c.id=o.customer_id "
        "WHERE substr(o.ordered_at,1,10) BETWEEN ? AND ? AND "
        + _cohort_filter("o", cohort)
        + " AND (?='' OR o.status=?) AND (?='' OR o.customer_id=?) "
        "AND (o.id LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\')"
    )
    params = (start.isoformat(), end.isoformat(), status, status, customer_id,
              customer_id, term, term)
    db = connect(state / "company.sqlite", readonly=True)
    try:
        total = db.execute("SELECT COUNT(*) " + where, params).fetchone()[0]
        rows = [dict(row) for row in db.execute(
            "SELECT o.id,o.customer_id,c.name AS customer_name,o.ordered_at,o.status,"
            "o.provenance,(SELECT COUNT(*) FROM order_items oi WHERE oi.order_id=o.id) "
            "AS line_count,COALESCE((SELECT SUM(oi.line_pence) FROM order_items oi "
            "WHERE oi.order_id=o.id),0) AS basket_pence "
            + where + " ORDER BY o.ordered_at DESC,o.id DESC LIMIT ? OFFSET ?",
            (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE),
        )]
    finally:
        db.close()
    return {"cohort": cohort, "start": start.isoformat(), "end": end.isoformat(),
            "page": page, "page_size": PAGE_SIZE, "total": total, "rows": rows,
            "basket_note": (
                "Basket value comes from order lines. It is not invoiced "
                "revenue or cash received."
            )}


def order_history_detail(state: Path, order_id: str, permissions: set[str]) -> dict | None:
    """Reveal linked history only when the selected employee has its table scope."""
    db = connect(state / "company.sqlite", readonly=True)
    try:
        order = db.execute(
            "SELECT o.*,c.name AS customer_name FROM orders o "
            "JOIN customers c ON c.id=o.customer_id WHERE o.id=?", (order_id,)
        ).fetchone()
        if order is None:
            return None
        line_count = db.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id=?", (order_id,)
        ).fetchone()[0]
        can_view_fulfillment = "operations.read" in permissions
        shipped_column = "f.shipped_quantity" if can_view_fulfillment else "NULL"
        fulfillment_join = (
            "JOIN order_fulfillment f ON f.id=oi.id " if can_view_fulfillment else ""
        )
        lines = [dict(row) for row in db.execute(
            "SELECT oi.id,oi.product_id,p.name AS product_name,oi.quantity,"
            f"oi.line_pence,{shipped_column} AS shipped_quantity FROM order_items oi "
            "JOIN products p ON p.id=oi.product_id "
            + fulfillment_join + "WHERE oi.order_id=? ORDER BY oi.id LIMIT ?",
            (order_id, LINE_PREVIEW),
        )]
        statuses = [dict(row) for row in db.execute(
            "SELECT id,occurred_at,status,reason FROM order_status_history "
            "WHERE order_id=? ORDER BY occurred_at,id", (order_id,),
        )]
        shipments = None
        if "operations.read" in permissions:
            shipments = [dict(row) for row in db.execute(
                "SELECT s.id,s.dispatched_on,s.delivered_on,s.carrier,"
                "COALESCE(SUM(si.quantity),0) AS units FROM shipments s "
                "LEFT JOIN shipment_items si ON si.shipment_id=s.id "
                "WHERE s.order_id=? GROUP BY s.id ORDER BY s.dispatched_on,s.id LIMIT ?",
                (order_id, LINE_PREVIEW),
            )]
        invoice = None
        if "finance.read" in permissions:
            found = db.execute(
                "SELECT id,posted_on,due_on,total_pence,outstanding_pence "
                "FROM invoice_balances WHERE order_id=?", (order_id,),
            ).fetchone()
            invoice = dict(found) if found else None
        return {"order": dict(order), "line_count": line_count, "lines": lines,
                "statuses": statuses, "shipments": shipments, "invoice": invoice,
                "preview_limit": LINE_PREVIEW}
    finally:
        db.close()
