"""Read-only company views and a small, audited local edit surface for the portal."""

import json
import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from acme.app_store import now
from acme.dataset import connect


def _company(state: Path):
    return connect(state / "company.sqlite", readonly=True)


def _identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
        raise ValueError("Invalid database object name")
    return '"' + name + '"'


def objects(state: Path) -> list[dict]:
    db = _company(state)
    try:
        return [
            dict(row)
            for row in db.execute(
                "SELECT name,type FROM sqlite_master WHERE type IN ('table','view') "
                "AND name NOT LIKE 'sqlite_%' ORDER BY type,name"
            )
        ]
    finally:
        db.close()


def browse(
    state: Path,
    name: str,
    *,
    search: str = "",
    filter_column: str = "",
    filter_value: str = "",
    page: int = 1,
    size: int = 25,
) -> dict:
    if name not in {item["name"] for item in objects(state)}:
        raise ValueError("Unknown table or view")
    if not 1 <= page <= 100000 or not 1 <= size <= 100:
        raise ValueError("Invalid page size or number")
    db = _company(state)
    try:
        columns = [dict(row) for row in db.execute(f"PRAGMA table_info({_identifier(name)})")]
        foreign_keys = {
            row["from"]: row["table"]
            for row in db.execute(f"PRAGMA foreign_key_list({_identifier(name)})")
        }
        names = {column["name"] for column in columns}
        if filter_column and filter_column not in names:
            raise ValueError("Filter column is not in this table or view")
        text_columns = [col["name"] for col in columns if "TEXT" in col["type"].upper()]
        search = search.strip()[:120]
        clauses, args = [], []
        if search and text_columns:
            clauses.append(
                "(" + " OR ".join(f"{_identifier(col)} LIKE ?" for col in text_columns) + ")"
            )
            args.extend([f"%{search}%"] * len(text_columns))
        if filter_column and filter_value:
            clauses.append(f"CAST({_identifier(filter_column)} AS TEXT)=?")
            args.append(filter_value[:200])
        clause = " WHERE " + " AND ".join(clauses) if clauses else ""
        total = db.execute(f"SELECT COUNT(*) FROM {_identifier(name)}{clause}", args).fetchone()[0]
        rows = [
            dict(row)
            for row in db.execute(
                f"SELECT * FROM {_identifier(name)}{clause} LIMIT ? OFFSET ?",
                (*args, size, (page - 1) * size),
            )
        ]
        return {
            "name": name,
            "columns": columns,
            "foreign_keys": foreign_keys,
            "rows": rows,
            "total": total,
            "page": page,
            "size": size,
        }
    finally:
        db.close()


def record(state: Path, name: str, identifier: str) -> dict | None:
    if name not in {item["name"] for item in objects(state)}:
        raise ValueError("Unknown table or view")
    db = _company(state)
    try:
        columns = {row["name"] for row in db.execute(f"PRAGMA table_info({_identifier(name)})")}
        if "id" not in columns:
            raise ValueError("This object has no ID column; use its table view")
        row = db.execute(f"SELECT * FROM {_identifier(name)} WHERE id=?", (identifier,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def query_sql(state: Path, sql: str) -> dict:
    sql = sql.strip()
    if not sql or len(sql) > 5000 or not re.match(r"^(SELECT|WITH|EXPLAIN)\b", sql, re.I):
        raise ValueError("Enter a SELECT, WITH, or EXPLAIN query (up to 5000 characters)")
    db = _company(state)
    try:
        db.execute("PRAGMA query_only=ON")
        db.set_progress_handler(lambda: 1, 100000)
        cursor = db.execute(sql)
        if cursor.description is None:
            raise ValueError("Query did not return columns")
        columns = [column[0] for column in cursor.description]
        rows = [dict(row) for row in cursor.fetchmany(201)]
        return {"columns": columns, "rows": rows[:200], "truncated": len(rows) > 200}
    except sqlite3.Error as exc:
        raise ValueError(f"Read-only query failed: {exc}") from exc
    finally:
        db.close()


def customers(state: Path, search: str = "", limit: int = 20) -> list[dict]:
    db = _company(state)
    try:
        if not search.strip():
            # Start scenario testing with authored customers and two useful
            # observed histories instead of twenty alphabetically similar names.
            rows = db.execute(
                "SELECT id,name,segment FROM customers "
                "ORDER BY CASE WHEN id LIKE 'DEMO-CUST-%' THEN 0 "
                "WHEN id='UCI-CUST-12748' THEN 1 "
                "WHEN id='UCI-CUST-17850' THEN 2 ELSE 3 END,id LIMIT ?",
                (min(max(limit, 1), 100),),
            )
            return [dict(row) for row in rows]
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,name,segment FROM customers WHERE id LIKE ? OR name LIKE ? "
                "ORDER BY name LIMIT ?",
                (f"%{search[:80]}%", f"%{search[:80]}%", min(max(limit, 1), 100)),
            )
        ]
    finally:
        db.close()


def employees(
    state: Path,
    search: str = "",
    limit: int = 50,
    department: str = "",
    location: str = "",
    job_title: str = "",
    min_customers: int = 0,
    sort: str = "customers_desc",
) -> list[dict]:
    sorts = {
        "customers_desc": "managed_customers DESC,e.name",
        "customers_asc": "managed_customers ASC,e.name",
        "name": "e.name",
        "hired": "e.hired_on,e.name",
    }
    if sort not in sorts or min_customers < 0:
        raise ValueError("Invalid employee search filters")
    db = _company(state)
    try:
        return [
            dict(row)
            for row in db.execute(
                "SELECT e.id,e.name,e.job_title,e.hired_on,d.id AS department_id,"
                "d.name AS department,l.id AS location_id,l.name AS location,"
                "(SELECT COUNT(*) FROM customers c WHERE c.account_manager_id=e.id) "
                "AS managed_customers FROM employees e "
                "LEFT JOIN employee_assignments a ON a.employee_id=e.id "
                "AND a.valid_until IS NULL "
                "LEFT JOIN departments d ON d.id=a.department_id "
                "LEFT JOIN locations l ON l.id=a.location_id "
                "WHERE (e.id LIKE ? OR e.name LIKE ? OR e.job_title LIKE ?) "
                "AND (?='' OR d.id=?) AND (?='' OR l.id=?) "
                "AND (?='' OR e.job_title=?) AND managed_customers>=? "
                "ORDER BY " + sorts[sort] + " LIMIT ?",
                (
                    f"%{search[:80]}%",
                    f"%{search[:80]}%",
                    f"%{search[:80]}%",
                    department,
                    department,
                    location,
                    location,
                    job_title,
                    job_title,
                    min_customers,
                    min(max(limit, 1), 100),
                ),
            )
        ]
    finally:
        db.close()


def employee_options(state: Path) -> dict:
    db = _company(state)
    try:
        return {
            "departments": [
                dict(row) for row in db.execute("SELECT id,name FROM departments ORDER BY name")
            ],
            "locations": [
                dict(row) for row in db.execute("SELECT id,name FROM locations ORDER BY name")
            ],
            "job_titles": [
                row[0]
                for row in db.execute("SELECT DISTINCT job_title FROM employees ORDER BY job_title")
            ],
        }
    finally:
        db.close()


def superuser_focuses(
    state: Path, search: str = "", sort: str = "name", active_only: bool = False
) -> list[dict]:
    if sort not in {"name", "customers_desc", "orders_desc"}:
        raise ValueError("Invalid superuser sort")
    db = _company(state)
    try:
        departments = [
            dict(row)
            for row in db.execute(
                "SELECT d.id,d.name,d.responsibility,COUNT(DISTINCT c.id) AS managed_customers,"
                "COUNT(o.id) AS order_count FROM departments d "
                "LEFT JOIN employee_assignments a ON a.department_id=d.id "
                "AND a.valid_until IS NULL "
                "LEFT JOIN customers c ON c.account_manager_id=a.employee_id "
                "LEFT JOIN orders o ON o.customer_id=c.id GROUP BY d.id"
            )
        ]
        total_customers = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        total_orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    finally:
        db.close()
    rows = [
        {
            "id": "all",
            "name": "Whole company",
            "managed_customers": total_customers,
            "order_count": total_orders,
            "responsibility": "All departments",
        },
        *departments,
    ]
    rows = [
        row
        for row in rows
        if (not active_only or row["managed_customers"] > 0)
        and (
            not search
            or search.casefold()
            in (row["id"] + " " + row["name"] + " " + row["responsibility"]).casefold()
        )
    ]
    if sort == "name":
        return sorted(rows, key=lambda row: (row["id"] != "all", row["name"]))
    return sorted(
        rows,
        key=lambda row: (
            -row["managed_customers" if sort == "customers_desc" else "order_count"],
            row["name"],
        ),
    )


def customer_summary(
    state: Path, customer_id: str, orders_page: int = 1, invoices_page: int = 1
) -> dict:
    """Return the account overview and independent 25-row activity pages."""
    if not 1 <= orders_page <= 10000 or not 1 <= invoices_page <= 10000:
        raise ValueError("Account page must be from 1 to 10000")
    page_size = 25
    db = _company(state)
    try:
        profile = db.execute(
            "SELECT c.*,a.label AS address,a.country,e.name AS account_manager "
            "FROM customers c JOIN addresses a ON a.id=c.address_id "
            "JOIN employees e ON e.id=c.account_manager_id WHERE c.id=?",
            (customer_id,),
        ).fetchone()
        if profile is None:
            raise ValueError("Unknown customer ID")
        activity = db.execute(
            "SELECT COUNT(*) AS order_count,MIN(ordered_at) AS first_order_at,"
            "MAX(ordered_at) AS last_order_at FROM orders WHERE customer_id=?",
            (customer_id,),
        ).fetchone()
        invoice_count = db.execute(
            "SELECT COUNT(*) FROM invoices i JOIN orders o ON o.id=i.order_id "
            "WHERE o.customer_id=?",
            (customer_id,),
        ).fetchone()[0]
        contacts = [
            dict(row)
            for row in db.execute(
                "SELECT id,name,email,responsibility FROM customer_contacts "
                "WHERE customer_id=? ORDER BY id LIMIT 20",
                (customer_id,),
            )
        ]
        orders = [
            dict(row)
            for row in db.execute(
                "SELECT o.id,o.ordered_at,o.status,o.currency,COUNT(oi.id) AS lines,"
                "COALESCE(SUM(oi.line_pence),0) AS total_pence "
                "FROM orders o LEFT JOIN order_items oi ON oi.order_id=o.id "
                "WHERE o.customer_id=? GROUP BY o.id "
                "ORDER BY o.ordered_at DESC,o.id DESC LIMIT ? OFFSET ?",
                (customer_id, page_size, (orders_page - 1) * page_size),
            )
        ]
        invoices = [
            dict(row)
            for row in db.execute(
                "SELECT i.* FROM invoice_balances i JOIN orders o ON o.id=i.order_id "
                "WHERE o.customer_id=? ORDER BY i.posted_on DESC,i.id DESC LIMIT ? OFFSET ?",
                (customer_id, page_size, (invoices_page - 1) * page_size),
            )
        ]
        return {
            "profile": dict(profile),
            "contacts": contacts,
            "activity": {**dict(activity), "invoice_count": invoice_count},
            "orders": orders,
            "invoices": invoices,
            "orders_page": orders_page,
            "invoices_page": invoices_page,
            "page_size": page_size,
        }
    finally:
        db.close()


def customer_order(state: Path, customer_id: str, order_id: str) -> dict:
    db = _company(state)
    try:
        order = db.execute(
            "SELECT * FROM orders WHERE id=? AND customer_id=?", (order_id, customer_id)
        ).fetchone()
        if not order:
            raise ValueError("Order not found for selected customer")
        items = [
            dict(row)
            for row in db.execute(
                "SELECT oi.*,p.name AS product_name FROM order_items oi "
                "JOIN products p ON p.id=oi.product_id WHERE oi.order_id=? ORDER BY oi.id",
                (order_id,),
            )
        ]
        return {"order": dict(order), "items": items}
    finally:
        db.close()


def customer_invoice(
    state: Path, customer_id: str, invoice_id: str, page: int = 1
) -> dict | None:
    """Show one owned invoice and a 25-row page of its settlement ledger."""
    if not 1 <= page <= 10000:
        raise ValueError("Invoice page must be from 1 to 10000")
    db = _company(state)
    try:
        invoice = db.execute(
            "SELECT i.* FROM invoice_balances i JOIN orders o ON o.id=i.order_id "
            "WHERE o.customer_id=? AND i.id=?",
            (customer_id, invoice_id),
        ).fetchone()
        if invoice is None:
            return None
        count = db.execute(
            "SELECT (SELECT COUNT(*) FROM payment_allocations a JOIN payments p "
            "ON p.id=a.payment_id WHERE a.invoice_id=? AND p.customer_id=?) + "
            "(SELECT COUNT(*) FROM credit_notes c WHERE c.invoice_id=?)",
            (invoice_id, customer_id, invoice_id),
        ).fetchone()[0]
        entries = [
            dict(row)
            for row in db.execute(
                "SELECT 'payment_allocation' AS kind,a.id,a.allocated_on AS applied_on,"
                "a.amount_pence,a.payment_id AS reference_id,p.received_on,NULL AS reason "
                "FROM payment_allocations a JOIN payments p ON p.id=a.payment_id "
                "WHERE a.invoice_id=? AND p.customer_id=? "
                "UNION ALL "
                "SELECT 'credit_note' AS kind,c.id,c.issued_on AS applied_on,"
                "c.amount_pence,c.id AS reference_id,NULL AS received_on,c.reason "
                "FROM credit_notes c WHERE c.invoice_id=? "
                "ORDER BY applied_on,id LIMIT 25 OFFSET ?",
                (invoice_id, customer_id, invoice_id, (page - 1) * 25),
            )
        ]
        return {
            "invoice": dict(invoice),
            "entries": entries,
            "total_entries": count,
            "page": page,
            "page_size": 25,
        }
    finally:
        db.close()


def products(state: Path, search: str = "", page: int = 1) -> dict:
    db = _company(state)
    try:
        term = f"%{search[:80]}%"
        total = db.execute(
            "SELECT COUNT(*) FROM products WHERE name LIKE ? OR id LIKE ?", (term, term)
        ).fetchone()[0]
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT p.id,p.name,p.category_id,c.name AS category,"
                "(SELECT raw_unit_price_gbp FROM price_history ph WHERE ph.product_id=p.id "
                "ORDER BY observed_at DESC LIMIT 1) AS last_price_gbp "
                "FROM products p JOIN categories c ON c.id=p.category_id "
                "WHERE p.name LIKE ? OR p.id LIKE ? ORDER BY p.name LIMIT 24 OFFSET ?",
                (term, term, (max(1, page) - 1) * 24),
            )
        ]
        return {"rows": rows, "total": total, "page": max(1, page)}
    finally:
        db.close()


def product_detail(state: Path, product_id: str) -> dict | None:
    """Return public catalog facts for one exact product ID."""
    db = _company(state)
    try:
        row = db.execute(
            "SELECT p.id,p.name,p.source_stock_code,c.name AS category,"
            "(SELECT raw_unit_price_gbp FROM price_history ph WHERE ph.product_id=p.id "
            "ORDER BY observed_at DESC, ph.id DESC LIMIT 1) AS last_price_gbp,"
            "(SELECT observed_at FROM price_history ph WHERE ph.product_id=p.id "
            "ORDER BY observed_at DESC, ph.id DESC LIMIT 1) AS price_observed_at "
            "FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=?",
            (product_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def edit_customer_address(
    state: Path, customer_id: str, label: str, country: str, actor: str
) -> dict:
    label, country = label.strip(), country.strip()
    if not 4 <= len(label) <= 240 or not 2 <= len(country) <= 80:
        raise ValueError("Address must be 4–240 characters and country 2–80 characters")
    audit = connect(state / "app.sqlite")
    try:
        audit.execute(
            "CREATE TABLE IF NOT EXISTS portal_edits (id TEXT PRIMARY KEY, actor TEXT NOT NULL, "
            "entity TEXT NOT NULL, record_id TEXT NOT NULL, before_json TEXT NOT NULL, "
            "after_json TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        audit.execute("ATTACH DATABASE ? AS company", (str((state / "company.sqlite").resolve()),))
        audit.execute("BEGIN IMMEDIATE")
        previous = audit.execute(
            "SELECT c.address_id,a.label,a.country FROM company.customers c "
            "JOIN company.addresses a ON a.id=c.address_id WHERE c.id=?",
            (customer_id,),
        ).fetchone()
        if previous is None:
            raise ValueError("Unknown customer ID")
        before = dict(previous)
        # A fresh address keeps other customers and suppliers unchanged if the old one is shared.
        address_id = "ADDR-EDIT-" + uuid4().hex[:16]
        audit.execute(
            "INSERT INTO company.addresses(id,label,country,provenance) "
            "VALUES(?,?,?,'portal_demo_edit')",
            (address_id, label, country),
        )
        audit.execute(
            "UPDATE company.customers SET address_id=? WHERE id=?", (address_id, customer_id)
        )
        after = {"address_id": address_id, "label": label, "country": country}
        edit_id = "edit-" + uuid4().hex
        audit.execute(
            "INSERT INTO portal_edits VALUES(?,?,?,?,?,?,?)",
            (
                edit_id,
                actor,
                "customers.address_id",
                customer_id,
                json.dumps(before),
                json.dumps(after),
                now(),
            ),
        )
        audit.commit()
        return {"id": edit_id, "before": before, "after": after}
    except Exception:
        audit.rollback()
        raise
    finally:
        audit.close()


def edit_customer_contact(
    state: Path, contact_id: str, name: str, responsibility: str, actor: str
) -> dict:
    name, responsibility = name.strip(), responsibility.strip()
    if not 2 <= len(name) <= 80 or not 3 <= len(responsibility) <= 200:
        raise ValueError("Contact name must be 2–80 characters and responsibility 3–200")
    audit = connect(state / "app.sqlite")
    try:
        audit.execute(
            "CREATE TABLE IF NOT EXISTS portal_edits (id TEXT PRIMARY KEY, actor TEXT NOT NULL, "
            "entity TEXT NOT NULL, record_id TEXT NOT NULL, before_json TEXT NOT NULL, "
            "after_json TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        audit.execute("ATTACH DATABASE ? AS company", (str((state / "company.sqlite").resolve()),))
        audit.execute("BEGIN IMMEDIATE")
        previous = audit.execute(
            "SELECT name,responsibility FROM company.customer_contacts WHERE id=?", (contact_id,)
        ).fetchone()
        if previous is None:
            raise ValueError("Unknown customer contact ID")
        before = dict(previous)
        audit.execute(
            "UPDATE company.customer_contacts SET name=?,responsibility=? WHERE id=?",
            (name, responsibility, contact_id),
        )
        after = {"name": name, "responsibility": responsibility}
        edit_id = "edit-" + uuid4().hex
        audit.execute(
            "INSERT INTO portal_edits VALUES(?,?,?,?,?,?,?)",
            (
                edit_id,
                actor,
                "customer_contacts",
                contact_id,
                json.dumps(before),
                json.dumps(after),
                now(),
            ),
        )
        audit.commit()
        return {"id": edit_id, "before": before, "after": after}
    except Exception:
        audit.rollback()
        raise
    finally:
        audit.close()


def edits(state: Path, limit: int = 50) -> list[dict]:
    db = connect(state / "app.sqlite", readonly=True)
    try:
        try:
            rows = db.execute(
                "SELECT * FROM portal_edits ORDER BY created_at DESC LIMIT ?", (min(limit, 100),)
            )
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            return []
    finally:
        db.close()
