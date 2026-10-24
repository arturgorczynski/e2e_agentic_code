"""Customer-bound records for the portal agent; no customer ID is model supplied."""

from datetime import date

from acme.app_store import AccessDenied, authorize, event
from acme.company_queries import query
from acme.company_tools import accessible_documents, execute
from acme.demo_identity import persona


def _customer(context) -> str:
    authorize(context, "commercial.read")
    selected = persona(context.project, context.state, context.session_token)
    if selected["kind"] != "customer":
        raise AccessDenied("Customer tools require a customer persona")
    return selected["subject_id"]


def profile(context) -> dict:
    customer_id = _customer(context)
    rows, evidence = query(
        context,
        "portal:my_profile",
        "SELECT c.id,c.name,c.segment,c.payment_terms_days,a.label AS address,"
        "a.country,e.name AS account_manager FROM customers c "
        "JOIN addresses a ON a.id=c.address_id "
        "JOIN employees e ON e.id=c.account_manager_id WHERE c.id=?",
        (customer_id,),
        "commercial.read",
    )
    contacts, contact_evidence = query(
        context,
        "portal:my_contacts",
        "SELECT id,name,email,responsibility FROM customer_contacts "
        "WHERE customer_id=? ORDER BY id LIMIT 20",
        (customer_id,),
        "commercial.read",
    )
    return {
        "status": "ok",
        "records": rows,
        "facts": {"contacts": contacts},
        "sources": [
            {"kind": "query", "id": evidence},
            {"kind": "query", "id": contact_evidence},
        ],
    }


def current_terms(context) -> dict:
    """Read the complete currently effective terms linked to this customer."""
    customer_id = _customer(context)
    effective_on = date.today().isoformat()
    matches = [
        doc
        for doc in accessible_documents(context, effective_on)
        if doc["category"] == "customer_terms"
        and doc["record_links"].get("customer_id") == customer_id
    ]
    event(
        context,
        "customer_terms_lookup",
        {
            "customer_id": customer_id,
            "effective_on": effective_on,
            "versions": [f"{doc['document_id']}:v{doc['version']}" for doc in matches],
        },
    )
    if not matches:
        return {
            "status": "empty",
            "records": [],
            "facts": {"effective_on": effective_on, "reason": "No current terms for this account"},
            "sources": [],
        }
    if len(matches) != 1:
        return {
            "status": "error",
            "records": [],
            "facts": {"effective_on": effective_on},
            "error": "Multiple current terms documents for this account; inspect the catalog",
            "sources": [],
        }
    doc = matches[0]
    return execute(
        context,
        "read_document",
        {"document_id": doc["document_id"], "version": doc["version"], "max_chars": 6000},
    )


def orders(context, limit: int = 20, offset: int = 0) -> dict:
    """List one bounded page of owned orders with an exact lifetime count."""
    if type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("offset must be an integer from 0 to 10000")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer from 1 to 50")
    customer_id = _customer(context)
    count_rows, count_evidence = query(
        context,
        "portal:my_orders_count",
        "SELECT COUNT(*) AS total_orders,MIN(ordered_at) AS earliest_order_at,"
        "MAX(ordered_at) AS latest_order_at,"
        "(SELECT id FROM orders WHERE customer_id=? ORDER BY ordered_at,id LIMIT 1) "
        "AS earliest_order_id,"
        "(SELECT id FROM orders WHERE customer_id=? ORDER BY ordered_at DESC,id DESC LIMIT 1) "
        "AS latest_order_id FROM orders WHERE customer_id=?",
        (customer_id, customer_id, customer_id),
        "commercial.read",
    )
    rows, evidence = query(
        context,
        "portal:my_orders",
        "SELECT o.id,o.ordered_at,o.status,COUNT(oi.id) AS lines,"
        "COALESCE(SUM(oi.line_pence),0) AS total_pence "
        "FROM orders o LEFT JOIN order_items oi ON oi.order_id=o.id "
        "WHERE o.customer_id=? GROUP BY o.id "
        "ORDER BY o.ordered_at DESC,o.id DESC LIMIT ? OFFSET ?",
        (customer_id, limit, offset),
        "commercial.read",
    )
    history = count_rows[0]
    total = history["total_orders"]
    return {
        "status": "ok",
        "records": rows,
        "facts": {
            **history,
            "returned_orders": len(rows),
            "offset": offset,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None,
            "has_more": offset + len(rows) < total,
            "page_limit": limit,
        },
        "sources": [
            {"kind": "query", "id": count_evidence},
            {"kind": "query", "id": evidence},
        ],
    }


def invoices(context, limit: int = 20, offset: int = 0) -> dict:
    """List one page of the selected customer's invoices and exact balances."""
    if type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("offset must be an integer from 0 to 10000")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer from 1 to 50")
    customer_id = _customer(context)
    totals, totals_evidence = query(
        context,
        "portal:my_invoices_totals",
        "SELECT COUNT(*) AS total_invoices,"
        "COALESCE(SUM(i.total_pence),0) AS billed_pence,"
        "COALESCE(SUM(i.outstanding_pence),0) AS outstanding_pence "
        "FROM invoice_balances i JOIN orders o ON o.id=i.order_id "
        "WHERE o.customer_id=?",
        (customer_id,),
        "commercial.read",
    )
    rows, evidence = query(
        context,
        "portal:my_invoices",
        "SELECT i.id,i.order_id,i.posted_on,i.due_on,i.total_pence,"
        "i.outstanding_pence,i.currency "
        "FROM invoice_balances i JOIN orders o ON o.id=i.order_id "
        "WHERE o.customer_id=? ORDER BY i.posted_on DESC,i.id DESC LIMIT ? OFFSET ?",
        (customer_id, limit, offset),
        "commercial.read",
    )
    total = totals[0]["total_invoices"]
    return {
        "status": "ok",
        "records": rows,
        "facts": {
            **totals[0],
            "returned_invoices": len(rows),
            "offset": offset,
            "next_offset": offset + len(rows) if offset + len(rows) < total else None,
            "has_more": offset + len(rows) < total,
            "page_limit": limit,
        },
        "sources": [
            {"kind": "query", "id": totals_evidence},
            {"kind": "query", "id": evidence},
        ],
    }


def invoice(context, invoice_id: str, limit: int = 20, offset: int = 0) -> dict:
    """Read one owned invoice and a bounded page of its settlement events."""
    if type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("offset must be an integer from 0 to 10000")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer from 1 to 50")
    customer_id = _customer(context)
    rows, invoice_evidence = query(
        context,
        "portal:my_invoice",
        "SELECT i.id,i.order_id,i.posted_on,i.due_on,i.total_pence,"
        "i.outstanding_pence,i.currency,"
        "(SELECT COALESCE(SUM(a.amount_pence),0) FROM payment_allocations a "
        "JOIN payments p ON p.id=a.payment_id "
        "WHERE a.invoice_id=i.id AND p.customer_id=o.customer_id) AS allocated_pence,"
        "(SELECT COALESCE(SUM(c.amount_pence),0) FROM credit_notes c "
        "WHERE c.invoice_id=i.id) AS credited_pence,"
        "(SELECT COUNT(*) FROM payment_allocations a JOIN payments p "
        "ON p.id=a.payment_id WHERE a.invoice_id=i.id "
        "AND p.customer_id=o.customer_id) + "
        "(SELECT COUNT(*) FROM credit_notes c WHERE c.invoice_id=i.id) AS total_entries "
        "FROM invoice_balances i JOIN orders o ON o.id=i.order_id "
        "WHERE o.customer_id=? AND i.id=?",
        (customer_id, invoice_id),
        "commercial.read",
    )
    if not rows:
        return {
            "status": "empty",
            "records": [],
            "sources": [{"kind": "query", "id": invoice_evidence}],
        }
    ledger, ledger_evidence = query(
        context,
        "portal:my_invoice_settlements",
        "SELECT 'payment_allocation' AS kind,a.id,a.allocated_on AS applied_on,"
        "a.amount_pence,a.payment_id AS reference_id,p.received_on,NULL AS reason "
        "FROM payment_allocations a JOIN payments p ON p.id=a.payment_id "
        "WHERE a.invoice_id=? AND p.customer_id=? "
        "UNION ALL "
        "SELECT 'credit_note' AS kind,c.id,c.issued_on AS applied_on,"
        "c.amount_pence,c.id AS reference_id,NULL AS received_on,c.reason "
        "FROM credit_notes c WHERE c.invoice_id=? "
        "ORDER BY applied_on,id LIMIT ? OFFSET ?",
        (invoice_id, customer_id, invoice_id, limit, offset),
        "commercial.read",
    )
    details = rows[0]
    total = details["total_entries"]
    return {
        "status": "ok",
        "records": ledger,
        "facts": {
            **details,
            "ledger_reconciles": details["total_pence"]
            - details["allocated_pence"]
            - details["credited_pence"]
            == details["outstanding_pence"],
            "returned_entries": len(ledger),
            "offset": offset,
            "next_offset": offset + len(ledger) if offset + len(ledger) < total else None,
            "has_more": offset + len(ledger) < total,
        },
        "sources": [
            {"kind": "query", "id": invoice_evidence},
            {"kind": "query", "id": ledger_evidence},
        ],
    }


def order(context, order_id: str, offset: int = 0, limit: int = 100) -> dict:
    """Read a bounded page of owned order lines and exact whole-order totals."""
    if type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("offset must be an integer from 0 to 10000")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 to 100")
    customer_id = _customer(context)
    totals, totals_evidence = query(
        context,
        "portal:my_order_totals",
        "SELECT o.id,o.ordered_at,o.status,COUNT(oi.id) AS total_lines,"
        "COALESCE(SUM(oi.line_pence),0) AS total_pence "
        "FROM orders o LEFT JOIN order_items oi ON oi.order_id=o.id "
        "WHERE o.customer_id=? AND o.id=? GROUP BY o.id",
        (customer_id, order_id),
        "commercial.read",
    )
    if not totals:
        return {
            "status": "empty",
            "records": [],
            "sources": [{"kind": "query", "id": totals_evidence}],
        }
    rows, evidence = query(
        context,
        "portal:my_order",
        "SELECT o.id,o.ordered_at,o.status,oi.id AS line_id,oi.quantity,"
        "oi.shipped_quantity,oi.quantity-oi.shipped_quantity AS unshipped_quantity,"
        "oi.line_pence,p.id AS product_id,p.name AS product_name "
        "FROM orders o JOIN order_fulfillment oi ON oi.order_id=o.id "
        "JOIN products p ON p.id=oi.product_id "
        "WHERE o.customer_id=? AND o.id=? ORDER BY oi.id LIMIT ? OFFSET ?",
        (customer_id, order_id, limit, offset),
        "commercial.read",
    )
    total_lines = totals[0]["total_lines"]
    return {
        "status": "ok",
        "records": rows,
        "facts": {
            **totals[0],
            "returned_lines": len(rows),
            "offset": offset,
            "next_offset": offset + len(rows) if offset + len(rows) < total_lines else None,
            "has_more": offset + len(rows) < total_lines,
        },
        "sources": [
            {"kind": "query", "id": totals_evidence},
            {"kind": "query", "id": evidence},
        ],
    }
