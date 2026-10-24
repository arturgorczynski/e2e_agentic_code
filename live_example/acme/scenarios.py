"""Searchable customer histories and bounded fictional portal scenarios."""

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from acme.company_data import forecast_input
from acme.contemporary_identities import SEED_ACCOUNT_IDENTITIES
from acme.dataset import connect
from acme.expense_ledger import has_expense_ledger

CONTEMPORARY_ACCOUNTS = (
    ("Harbour Home Stores", 8, 3, 156000, 1, 5, "partial", 270),
    ("North Quay Supplies", 6, 2, 84000, 0, 4, "settled", 210),
    ("Bramble Housewares", 5, 3, 90000, 1, 3, "unpaid", 160),
    ("Willow Lane Gifts", 7, 2, 77000, 2, 3, "settled", 120),
    ("Cedar & Stone Retail", 4, 4, 116000, 0, 2, "partial", 85),
    ("Lantern Trade Studio", 5, 2, 62000, 1, 2, "unpaid", 60),
    ("Maple Market Collective", 6, 3, 138000, 0, 4, "settled", 30),
    ("Fable Home Merchants", 3, 4, 72000, 0, 2, "partial", 12),
)
CONTEMPORARY_CASES = (
    (
        "Harbour Home Stores",
        "packaging_damage",
        "in_progress",
        "Two outer cartons were crushed on receipt; the buyer requested a condition review.",
    ),
    (
        "North Quay Supplies",
        "invoice_copy",
        "resolved",
        "Purchasing requested a duplicate invoice for its accounts payable reference.",
    ),
    (
        "Bramble Housewares",
        "damaged_goods",
        "resolved",
        "The buyer reported a damaged display item and supplied photographs for review.",
    ),
    (
        "Willow Lane Gifts",
        "delivery_query",
        "resolved",
        "The receiving team requested the carrier record after an internal handoff delay.",
    ),
    (
        "Cedar & Stone Retail",
        "payment_query",
        "in_progress",
        "Accounts payable queried the remaining balance after a part payment.",
    ),
    (
        "Lantern Trade Studio",
        "return_request",
        "open",
        "The buyer asked whether an unopened line could be returned.",
    ),
    (
        "Maple Market Collective",
        "quantity_discrepancy",
        "in_progress",
        "The buyer reported one carton short against the delivery note.",
    ),
    (
        "Fable Home Merchants",
        "proof_of_delivery",
        "resolved",
        "The buyer requested delivery confirmation for the receiving desk.",
    ),
)

CONTEMPORARY_PURCHASING = (
    ("North Quay Supplies", 12, 12, 1, "Complete replenishment after account growth"),
    ("Maple Market Collective", 18, 6, 4, "Supplier sent 6 of 18 units; 12 remain outstanding"),
    ("Fable Home Merchants", 16, 0, 0, "Supplier confirmation overdue; no receipt recorded"),
)

CONTEMPORARY_PLANNING = (
    ("Maple Market Collective", "Notebook demand after September account launch"),
    ("Cedar & Stone Retail", "Homewares range following summer sell-through"),
)


def _seed_suffix(name: str) -> str:
    return hashlib.sha256(f"acme-modern-history:{name}".encode()).hexdigest()[:12].upper()


def customer_candidates(
    state: Path,
    search: str = "",
    min_orders: int = 0,
    max_orders: int | None = None,
    status: str = "",
    sort: str = "orders_desc",
    period: str = "all",
) -> list[dict]:
    if min_orders < 0 or max_orders is not None and max_orders < min_orders:
        raise ValueError("Choose a valid order-count range")
    if status not in {"", "confirmed", "partial", "fulfilled", "cancelled"}:
        raise ValueError("Unknown order status")
    if period not in {"all", "historical", "contemporary"}:
        raise ValueError("Unknown customer history period")
    sorts = {
        "orders_desc": "order_count DESC, c.name",
        "orders_asc": "order_count ASC, c.name",
        "value_desc": "total_pence DESC, c.name",
        "name": "c.name",
    }
    if sort not in sorts:
        raise ValueError("Unknown sort order")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        clauses = ["COALESCE(t.order_count,0) >= ?"]
        parameters: list[object] = [min_orders]
        if max_orders is not None:
            clauses.append("COALESCE(t.order_count,0) <= ?")
            parameters.append(max_orders)
        if search.strip():
            clauses.append("(c.id LIKE ? OR c.name LIKE ?)")
            parameters.extend([f"%{search[:80]}%"] * 2)
        if status:
            clauses.append(
                "EXISTS(SELECT 1 FROM orders matched WHERE matched.customer_id=c.id "
                "AND matched.status=?)"
            )
            parameters.append(status)
        if period != "all":
            operator = "NOT IN" if period == "historical" else "IN"
            clauses.append(
                f"c.provenance {operator} "
                "('fictional_contemporary_seed', 'fictional_contemporary_scenario')"
            )
        rows = db.execute(
            "WITH order_totals AS (SELECT o.id,o.customer_id,o.status,"
            "COALESCE(SUM(oi.line_pence),0) AS value_pence FROM orders o "
            "LEFT JOIN order_items oi ON oi.order_id=o.id GROUP BY o.id), "
            "customer_totals AS (SELECT customer_id,COUNT(*) AS order_count,"
            "SUM(value_pence) AS total_pence,"
            "SUM(status='cancelled') AS cancelled_count FROM order_totals GROUP BY customer_id) "
            "SELECT c.id,c.name,c.segment,COALESCE(t.order_count,0) AS order_count,"
            "COALESCE(t.total_pence,0) AS total_pence,"
            "COALESCE(t.cancelled_count,0) AS cancelled_count,"
            "CASE WHEN c.provenance IN ('fictional_contemporary_seed',"
            "'fictional_contemporary_scenario') THEN 'Contemporary fictional' "
            "ELSE '2011 archive' END AS history_period FROM customers c "
            "LEFT JOIN customer_totals t ON t.customer_id=c.id WHERE "
            + " AND ".join(clauses)
            + " ORDER BY "
            + sorts[sort]
            + " LIMIT 50",
            parameters,
        )
        return [dict(row) for row in rows]
    finally:
        db.close()


def create_customer_scenario(
    state: Path,
    name: str,
    order_count: int,
    items_per_order: int,
    total_pence: int,
    cancelled_count: int,
    fulfilled_count: int = 0,
    payment_profile: str = "settled",
    provenance: str = "fictional_contemporary_scenario",
    days_ago: int = 45,
) -> dict:
    name = name.strip()
    if not 2 <= len(name) <= 100:
        raise ValueError("Customer name must contain 2–100 characters")
    if not 0 <= order_count <= 30 or not 1 <= items_per_order <= 10:
        raise ValueError("Use 0–30 orders and 1–10 items per order")
    if not 0 <= cancelled_count <= order_count:
        raise ValueError("Cancelled orders must be within the order count")
    if not 0 <= fulfilled_count <= order_count - cancelled_count:
        raise ValueError("Fulfilled orders must fit among the non-cancelled orders")
    if payment_profile not in {"settled", "partial", "unpaid"}:
        raise ValueError("Unknown payment history")
    if provenance not in {"fictional_contemporary_scenario", "fictional_contemporary_seed"}:
        raise ValueError("Unknown scenario provenance")
    if not order_count + 5 <= days_ago <= 365:
        raise ValueError("Scenario dates must leave time for fulfillment and payment")
    lines = order_count * items_per_order
    if total_pence < lines or total_pence > 100_000_000:
        raise ValueError("Total value must cover at least one penny per item and at most £1m")
    if not order_count and total_pence:
        raise ValueError("A customer with no orders must have a zero total")
    if payment_profile == "partial" and fulfilled_count and total_pence < 2 * lines:
        raise ValueError("Partial-payment examples need at least two pence per order line")
    db = connect(state / "company.sqlite")
    try:
        manager = (
            db.execute(
                "SELECT e.id FROM employees e JOIN employee_assignments a "
                "ON a.employee_id=e.id AND a.valid_until IS NULL "
                "WHERE a.department_id='DEP-SALES' ORDER BY e.id LIMIT 1"
            ).fetchone()
            or db.execute("SELECT id FROM employees ORDER BY id LIMIT 1").fetchone()
        )
        product = db.execute("SELECT id FROM products ORDER BY id LIMIT 1").fetchone()
        warehouse = db.execute("SELECT id FROM warehouses ORDER BY id LIMIT 1").fetchone()
        source_products = db.execute(
            "SELECT p.category_id,p.supplier_id,c.name AS category_name FROM products p "
            "JOIN categories c ON c.id=p.category_id GROUP BY c.id ORDER BY c.id"
        ).fetchall()
        if manager is None or product is None:
            raise ValueError("The company needs an employee and product for scenarios")
        if fulfilled_count and warehouse is None:
            raise ValueError("Fulfilled scenarios need a company warehouse")
        suffix = (
            _seed_suffix(name)
            if provenance == "fictional_contemporary_seed"
            else uuid4().hex[:12].upper()
        )
        source_product = source_products[int(suffix[:4], 16) % len(source_products)]
        business_today = date.today()
        first_order = business_today - timedelta(days=days_ago)
        stock_opened = first_order - timedelta(days=1)
        customer_id = f"SCN-CUST-{suffix}"
        address_id = f"SCN-ADDR-{suffix}"
        profile = (
            SEED_ACCOUNT_IDENTITIES.get(name)
            if provenance == "fictional_contemporary_seed"
            else None
        )
        city, postcode = (
            ("Bristol", "BS4 8QA"),
            ("Leeds", "LS7 3QJ"),
            ("Coventry", "CV3 4ZW"),
            ("Nottingham", "NG5 7JP"),
        )[int(suffix[:2], 16) % 4]
        street = ("Canal", "Market", "Foundry", "Orchard")[int(suffix[2:4], 16) % 4]
        address = f"Unit {1 + int(suffix[4:6], 16) % 24}, {street} Trade Park, {city}, {postcode}"
        contact_name = ("Mia Carter", "Leo Bennett", "Grace Turner", "Noah Ellis")[
            int(suffix[6:8], 16) % 4
        ]
        domain = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "customer"
        contact_email = f"orders@{domain}-{suffix[:6].lower()}.example"
        manager_id = manager[0]
        if profile:
            assigned = db.execute(
                "SELECT 1 FROM employee_assignments WHERE employee_id=? "
                "AND department_id='DEP-SALES' AND valid_until IS NULL",
                (profile["manager_id"],),
            ).fetchone()
            if assigned:
                manager_id = profile["manager_id"]
            address = profile["address"]
            contact_name = profile["contact_name"]
            contact_email = profile["contact_email"]
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO addresses VALUES(?,?,?,?)",
            (address_id, address, "United Kingdom", "fictional contemporary scenario address"),
        )
        db.execute(
            "INSERT INTO customers VALUES(?,?,?,?,?,?,?,?,?)",
            (
                customer_id,
                None,
                name,
                address_id,
                manager_id,
                30,
                0,
                profile["segment"] if profile else "Independent retail",
                provenance,
            ),
        )
        db.execute(
            "INSERT INTO customer_contacts VALUES(?,?,?,?,?)",
            (
                f"SCN-CONTACT-{suffix}",
                customer_id,
                contact_name,
                contact_email,
                profile["contact_role"] if profile else "Orders and purchasing",
            ),
        )
        base, extra = divmod(total_pence, lines or 1)
        if fulfilled_count or (warehouse is not None and order_count > cancelled_count):
            product_id = f"SCN-SKU-{suffix}"
            inventory_id = f"SCN-INV-{suffix}"
            initial_stock = fulfilled_count * items_per_order + 20
            db.execute(
                "INSERT INTO products VALUES(?,?,?,?,?,?)",
                (
                    product_id,
                    None,
                    {
                        "Lighting and candles": "Amber glass candle holder",
                        "Kitchen and tableware": "Ivory stoneware breakfast cup",
                        "Seasonal decorations": "Winter garland display set",
                        "Stationery": "Linen-cover desk notebook",
                        "Packaging and storage": "Kraft gift carton",
                        "Textiles": "Cotton tea towel pair",
                    }.get(source_product["category_name"], "Assorted homewares pack"),
                    source_product["category_id"],
                    source_product["supplier_id"],
                    provenance,
                ),
            )
            db.execute(
                "INSERT INTO price_history VALUES(?,?,?,?,?,?)",
                (
                    f"SCN-PRICE-{suffix}",
                    product_id,
                    stock_opened.isoformat(),
                    f"{base / 100:.2f}",
                    None,
                    "fixture",
                ),
            )
            db.execute(
                "INSERT INTO inventory VALUES(?,?,?,?,?,?)",
                (
                    inventory_id,
                    warehouse[0],
                    product_id,
                    20,
                    min(20, (order_count - cancelled_count - fulfilled_count) * items_per_order),
                    business_today.isoformat(),
                ),
            )
            db.execute(
                "INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)",
                (
                    f"SCN-STOCK-{suffix}-OPEN",
                    warehouse[0],
                    product_id,
                    stock_opened.isoformat(),
                    "opening",
                    initial_stock,
                    None,
                    None,
                ),
            )
        else:
            product_id = product[0]
        for index in range(order_count):
            order_id = f"SCN-ORD-{suffix}-{index + 1:02d}"
            status = (
                "cancelled"
                if index < cancelled_count
                else "fulfilled"
                if index < cancelled_count + fulfilled_count
                else "confirmed"
            )
            ordered_on = first_order + timedelta(days=index)
            ordered_at = ordered_on.isoformat()
            db.execute(
                "INSERT INTO orders VALUES(?,?,?,?,?,?,?)",
                (
                    order_id,
                    None,
                    customer_id,
                    ordered_at,
                    status,
                    "GBP",
                    provenance,
                ),
            )
            db.execute(
                "INSERT INTO order_status_history VALUES(?,?,?,?,?)",
                (
                    f"SCN-HIST-{suffix}-{index + 1:02d}-1",
                    order_id,
                    ordered_at,
                    "confirmed",
                    "Customer purchase order accepted by sales",
                ),
            )
            if status != "confirmed":
                db.execute(
                    "INSERT INTO order_status_history VALUES(?,?,?,?,?)",
                    (
                        f"SCN-HIST-{suffix}-{index + 1:02d}-2",
                        order_id,
                        (ordered_on + timedelta(days=2)).isoformat(),
                        status,
                        "Customer cancelled before dispatch"
                        if status == "cancelled"
                        else "Dispatch completed against all order lines",
                    ),
                )
            order_total = 0
            item_ids = []
            for item_index in range(items_per_order):
                number = index * items_per_order + item_index
                amount = base + (1 if number < extra else 0)
                item_id = f"SCN-ITEM-{suffix}-{number + 1:03d}"
                item_ids.append((item_id, amount, number))
                order_total += amount
                db.execute(
                    "INSERT INTO order_items VALUES(?,?,?,?,?,?,?)",
                    (
                        item_id,
                        order_id,
                        product_id,
                        1,
                        f"{amount / 100:.2f}",
                        amount,
                        None,
                    ),
                )
            if status == "fulfilled":
                invoice_id = f"SCN-BILL-{suffix}-{index + 1:02d}"
                shipment_id = f"SCN-SHIP-{suffix}-{index + 1:02d}"
                payment_id = f"SCN-PAY-{suffix}-{index + 1:02d}"
                dispatched_on = (ordered_on + timedelta(days=1)).isoformat()
                delivered_on = (ordered_on + timedelta(days=2)).isoformat()
                paid_on = (ordered_on + timedelta(days=4)).isoformat()
                db.execute(
                    "INSERT INTO invoices VALUES(?,?,?,?,?,?,?)",
                    (
                        invoice_id,
                        order_id,
                        dispatched_on,
                        (ordered_on + timedelta(days=31)).isoformat(),
                        order_total,
                        "GBP",
                        provenance,
                    ),
                )
                db.execute(
                    "INSERT INTO shipments VALUES(?,?,?,?,?,?,?)",
                    (
                        shipment_id,
                        order_id,
                        warehouse[0],
                        dispatched_on,
                        delivered_on,
                        "Cedar Parcel Network",
                        provenance,
                    ),
                )
                for item_id, amount, number in item_ids:
                    shipment_item_id = f"SCN-SHIPITEM-{suffix}-{number + 1:03d}"
                    db.execute(
                        "INSERT INTO invoice_items VALUES(?,?,?,?,?)",
                        (f"SCN-BILLITEM-{suffix}-{number + 1:03d}", invoice_id, item_id, 1, amount),
                    )
                    db.execute(
                        "INSERT INTO shipment_items VALUES(?,?,?,?)",
                        (shipment_item_id, shipment_id, item_id, 1),
                    )
                    db.execute(
                        "INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)",
                        (
                            f"SCN-STOCK-{suffix}-{number + 1:03d}",
                            warehouse[0],
                            product_id,
                            dispatched_on,
                            "dispatch",
                            -1,
                            shipment_item_id,
                            None,
                        ),
                    )
                if payment_profile != "unpaid":
                    amount_paid = (
                        order_total if payment_profile == "settled" else max(1, order_total // 2)
                    )
                    db.execute(
                        "INSERT INTO payments VALUES(?,?,?,?,?,?)",
                        (
                            payment_id,
                            customer_id,
                            paid_on,
                            amount_paid,
                            "GBP",
                            provenance,
                        ),
                    )
                    db.execute(
                        "INSERT INTO payment_allocations VALUES(?,?,?,?,?)",
                        (
                            f"SCN-ALLOC-{suffix}-{index + 1:02d}",
                            payment_id,
                            invoice_id,
                            paid_on,
                            amount_paid,
                        ),
                    )
        db.commit()
        return {
            "id": customer_id,
            "name": name,
            "order_count": order_count,
            "items_per_order": items_per_order,
            "total_pence": total_pence,
            "cancelled_count": cancelled_count,
            "fulfilled_count": fulfilled_count,
            "payment_profile": payment_profile,
            "history_period": "contemporary_fictional",
            "business_reference": business_today.isoformat(),
            "provenance": provenance,
            "first_order": first_order.isoformat(),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seed_contemporary_history(state: Path) -> dict:
    """Add a reproducible fictional cohort; snapshot the live database first."""
    database = state / "company.sqlite"
    if not database.is_file():
        raise ValueError("Initialize company state before seeding contemporary history")
    read = connect(database, readonly=True)
    try:
        missing = [
            account
            for account in CONTEMPORARY_ACCOUNTS
            if read.execute(
                "SELECT 1 FROM customers WHERE id=? AND provenance=?",
                (f"SCN-CUST-{_seed_suffix(account[0])}", "fictional_contemporary_seed"),
            ).fetchone()
            is None
        ]
    finally:
        read.close()
    if not missing:
        return {"status": "already_present", "created": [], "backup": None}
    backup = (
        state
        / "backups"
        / ("modern-seed-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6])
    )
    backup.mkdir(parents=True, exist_ok=False)
    source = connect(database, readonly=True)
    snapshot = connect(backup / "company.sqlite")
    try:
        source.backup(snapshot)
    finally:
        snapshot.close()
        source.close()
    created = []
    for name, orders, items, amount, cancelled, fulfilled, payment, days_ago in missing:
        created.append(
            create_customer_scenario(
                state,
                name,
                orders,
                items,
                amount,
                cancelled,
                fulfilled,
                payment,
                provenance="fictional_contemporary_seed",
                days_ago=days_ago,
            )
        )
    (backup / "seed_receipt.json").write_text(
        json.dumps({"created": created, "cohort": "fictional_contemporary_seed"}, indent=2),
        encoding="utf-8",
    )
    return {"status": "seeded", "created": created, "backup": str(backup)}


def align_contemporary_seed_dates(state: Path) -> dict:
    """Spread the first compact seed cohort across 2026 without touching source rows."""
    database = state / "company.sqlite"
    db = connect(database)
    try:
        original_start = (date.today() - timedelta(days=45)).isoformat()
        moves = []
        for (
            name,
            _orders,
            _items,
            _amount,
            _cancelled,
            _fulfilled,
            _payment,
            days_ago,
        ) in CONTEMPORARY_ACCOUNTS:
            suffix = _seed_suffix(name)
            first = db.execute(
                "SELECT MIN(ordered_at) FROM orders WHERE id LIKE ?",
                (f"SCN-ORD-{suffix}-%",),
            ).fetchone()[0]
            target = (date.today() - timedelta(days=days_ago)).isoformat()
            if first == target:
                continue
            if first != original_start:
                raise ValueError(f"Unexpected date for {name}; no seed dates were changed")
            moves.append((suffix, 45 - days_ago))
        if not moves:
            return {"status": "already_aligned", "backup": None, "accounts": 0}
        backup = (
            state
            / "backups"
            / (
                "modern-dates-"
                + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                + "-"
                + uuid4().hex[:6]
            )
        )
        backup.mkdir(parents=True, exist_ok=False)
        snapshot = connect(backup / "company.sqlite")
        try:
            db.backup(snapshot)
        finally:
            snapshot.close()
        date_columns = {
            "price_history": ("observed_at",),
            "stock_movements": ("occurred_on",),
            "orders": ("ordered_at",),
            "order_status_history": ("occurred_at",),
            "invoices": ("posted_on", "due_on"),
            "shipments": ("dispatched_on", "delivered_on"),
            "payments": ("received_on",),
            "payment_allocations": ("allocated_on",),
        }
        id_prefix = {
            "price_history": "SCN-PRICE-",
            "stock_movements": "SCN-STOCK-",
            "orders": "SCN-ORD-",
            "order_status_history": "SCN-HIST-",
            "invoices": "SCN-BILL-",
            "shipments": "SCN-SHIP-",
            "payments": "SCN-PAY-",
            "payment_allocations": "SCN-ALLOC-",
        }
        db.execute("BEGIN IMMEDIATE")
        for suffix, shift in moves:
            modifier = f"{shift:+d} days"
            for table, columns in date_columns.items():
                assignments = ",".join(f"{column}=date({column},?)" for column in columns)
                db.execute(
                    f"UPDATE {table} SET {assignments} WHERE id LIKE ?",
                    (*([modifier] * len(columns)), f"{id_prefix[table]}{suffix}%"),
                )
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Date alignment produced broken foreign keys")
        db.commit()
        (backup / "alignment_receipt.json").write_text(
            json.dumps({"moves": moves, "reference_date": date.today().isoformat()}, indent=2),
            encoding="utf-8",
        )
        return {"status": "aligned", "backup": str(backup), "accounts": len(moves)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def audit_contemporary_history(state: Path) -> dict:
    """Check linked contemporary scenario records without changing the database."""
    db = connect(state / "company.sqlite", readonly=True)
    try:
        checks = {
            "broken_foreign_keys": "SELECT COUNT(*) FROM pragma_foreign_key_check",
            "future_orders": (
                "SELECT COUNT(*) FROM orders WHERE provenance LIKE 'fictional_contemporary_%' "
                "AND ordered_at>date('now')"
            ),
            "contemporary_orders_in_source_era": (
                "SELECT COUNT(*) FROM orders WHERE provenance LIKE 'fictional_contemporary_%' "
                "AND ordered_at<'2026-01-01'"
            ),
            "source_orders_after_cutoff": (
                "SELECT COUNT(*) FROM orders WHERE source_invoice_no IS NOT NULL "
                "AND ordered_at>'2011-12-09'"
            ),
            "source_invoices_after_cutoff": (
                "SELECT COUNT(*) FROM invoices i JOIN orders o ON o.id=i.order_id "
                "WHERE o.source_invoice_no IS NOT NULL AND i.posted_on>'2011-12-09'"
            ),
            "unlinked_contacts": (
                "SELECT COUNT(*) FROM customers c WHERE c.provenance LIKE "
                "'fictional_contemporary_%' AND NOT EXISTS (SELECT 1 FROM customer_contacts "
                "cc WHERE cc.customer_id=c.id)"
            ),
            "mismatched_invoice_totals": (
                "SELECT COUNT(*) FROM invoices i WHERE i.provenance LIKE "
                "'fictional_contemporary_%' AND i.total_pence != (SELECT "
                "COALESCE(SUM(amount_pence),0) FROM invoice_items WHERE invoice_id=i.id)"
            ),
            "invoice_without_items": (
                "SELECT COUNT(*) FROM invoices i WHERE i.provenance LIKE "
                "'fictional_contemporary_%' AND NOT EXISTS (SELECT 1 FROM invoice_items ii "
                "WHERE ii.invoice_id=i.id)"
            ),
            "invoice_before_order": (
                "SELECT COUNT(*) FROM invoices i JOIN orders o ON o.id=i.order_id WHERE "
                "i.provenance LIKE 'fictional_contemporary_%' AND i.posted_on<o.ordered_at"
            ),
            "invoice_due_term_mismatch": (
                "SELECT COUNT(*) FROM invoices i JOIN orders o ON o.id=i.order_id "
                "JOIN customers c ON c.id=o.customer_id WHERE i.provenance LIKE "
                "'fictional_contemporary_%' AND i.due_on != "
                "date(i.posted_on,'+'||c.payment_terms_days||' days')"
            ),
            "fulfilled_without_invoice": (
                "SELECT COUNT(*) FROM orders o WHERE o.provenance LIKE "
                "'fictional_contemporary_%' AND o.status='fulfilled' AND "
                "NOT EXISTS (SELECT 1 FROM invoices i WHERE i.order_id=o.id)"
            ),
            "fulfilled_without_shipment": (
                "SELECT COUNT(*) FROM orders o WHERE o.provenance LIKE "
                "'fictional_contemporary_%' AND o.status='fulfilled' AND "
                "NOT EXISTS (SELECT 1 FROM shipments s WHERE s.order_id=o.id)"
            ),
            "contemporary_order_without_items": (
                "SELECT COUNT(*) FROM orders o WHERE o.provenance LIKE "
                "'fictional_contemporary_%' AND NOT EXISTS (SELECT 1 FROM order_items oi "
                "WHERE oi.order_id=o.id)"
            ),
            "active_order_status_vs_fulfillment": (
                "SELECT COUNT(*) FROM orders o WHERE o.provenance LIKE "
                "'fictional_contemporary_%' AND o.status!='cancelled' AND o.status != "
                "CASE WHEN NOT EXISTS (SELECT 1 FROM order_fulfillment f WHERE "
                "f.order_id=o.id AND f.quantity!=f.shipped_quantity) THEN 'fulfilled' "
                "WHEN EXISTS (SELECT 1 FROM order_fulfillment f WHERE f.order_id=o.id "
                "AND f.shipped_quantity>0) THEN 'partial' ELSE 'confirmed' END"
            ),
            "cancelled_order_has_billing_or_dispatch": (
                "SELECT COUNT(*) FROM orders o WHERE o.provenance LIKE "
                "'fictional_contemporary_%' AND o.status='cancelled' AND ("
                "EXISTS (SELECT 1 FROM invoices i WHERE i.order_id=o.id) OR "
                "EXISTS (SELECT 1 FROM shipments s WHERE s.order_id=o.id) OR "
                "EXISTS (SELECT 1 FROM order_fulfillment f WHERE f.order_id=o.id "
                "AND f.shipped_quantity>0))"
            ),
            "invoice_line_order_mismatch": (
                "SELECT COUNT(*) FROM invoice_items ii JOIN invoices i ON i.id=ii.invoice_id "
                "JOIN order_items oi ON oi.id=ii.order_item_id WHERE i.provenance LIKE "
                "'fictional_contemporary_%' AND oi.order_id!=i.order_id"
            ),
            "invoice_item_overordered_quantity": (
                "SELECT COUNT(*) FROM invoice_items ii JOIN invoices i ON i.id=ii.invoice_id "
                "JOIN order_items oi ON oi.id=ii.order_item_id WHERE i.provenance LIKE "
                "'fictional_contemporary_%' AND ii.quantity>oi.quantity"
            ),
            "invoice_line_quantity_mismatch": (
                "SELECT COUNT(*) FROM invoice_items ii JOIN invoices i ON i.id=ii.invoice_id "
                "JOIN order_items oi ON oi.id=ii.order_item_id WHERE i.provenance LIKE "
                "'fictional_contemporary_%' AND ii.quantity!=oi.quantity"
            ),
            "invoice_line_amount_mismatch": (
                "SELECT COUNT(*) FROM invoice_items ii JOIN invoices i ON i.id=ii.invoice_id "
                "JOIN order_items oi ON oi.id=ii.order_item_id WHERE i.provenance LIKE "
                "'fictional_contemporary_%' AND ii.amount_pence!=oi.line_pence"
            ),
            "fulfilled_line_without_invoice": (
                "SELECT COUNT(*) FROM orders o JOIN order_items oi ON oi.order_id=o.id "
                "LEFT JOIN invoice_items ii ON ii.order_item_id=oi.id WHERE o.provenance LIKE "
                "'fictional_contemporary_%' AND o.status='fulfilled' AND ii.id IS NULL"
            ),
            "negative_invoice_balances": (
                "SELECT COUNT(*) FROM invoice_balances WHERE provenance LIKE "
                "'fictional_contemporary_%' AND outstanding_pence<0"
            ),
            "payment_before_invoice": (
                "SELECT COUNT(*) FROM payment_allocations a JOIN invoices i ON i.id=a.invoice_id "
                "WHERE i.provenance LIKE 'fictional_contemporary_%' AND a.allocated_on<i.posted_on"
            ),
            "payment_customer_mismatch": (
                "SELECT COUNT(*) FROM payment_allocations a JOIN invoices i ON i.id=a.invoice_id "
                "JOIN orders o ON o.id=i.order_id JOIN payments p ON p.id=a.payment_id "
                "WHERE i.provenance LIKE 'fictional_contemporary_%' "
                "AND p.customer_id!=o.customer_id"
            ),
            "payment_allocation_before_receipt": (
                "SELECT COUNT(*) FROM payment_allocations a JOIN invoices i ON i.id=a.invoice_id "
                "JOIN payments p ON p.id=a.payment_id WHERE i.provenance LIKE "
                "'fictional_contemporary_%' AND a.allocated_on<p.received_on"
            ),
            "payment_overallocated": (
                "SELECT COUNT(*) FROM payments p WHERE p.provenance LIKE "
                "'fictional_contemporary_%' AND p.amount_pence<(SELECT "
                "COALESCE(SUM(a.amount_pence),0) FROM payment_allocations a "
                "WHERE a.payment_id=p.id)"
            ),
            "credit_before_invoice": (
                "SELECT COUNT(*) FROM credit_notes c JOIN invoices i ON i.id=c.invoice_id "
                "WHERE c.provenance LIKE 'fictional_contemporary_%' AND c.issued_on<i.posted_on"
            ),
            "shipped_more_than_ordered": (
                "SELECT COUNT(*) FROM order_fulfillment f JOIN orders o ON o.id=f.order_id "
                "WHERE o.provenance LIKE 'fictional_contemporary_%' "
                "AND f.shipped_quantity>f.quantity"
            ),
            "shipment_order_mismatch": (
                "SELECT COUNT(*) FROM shipment_items si JOIN shipments s ON s.id=si.shipment_id "
                "JOIN order_items oi ON oi.id=si.order_item_id WHERE s.provenance LIKE "
                "'fictional_contemporary_%' AND oi.order_id!=s.order_id"
            ),
            "shipment_without_items": (
                "SELECT COUNT(*) FROM shipments s WHERE s.provenance LIKE "
                "'fictional_contemporary_%' AND NOT EXISTS (SELECT 1 FROM shipment_items si "
                "WHERE si.shipment_id=s.id)"
            ),
            "shipment_before_order": (
                "SELECT COUNT(*) FROM shipments s JOIN orders o ON o.id=s.order_id WHERE "
                "s.provenance LIKE 'fictional_contemporary_%' AND s.dispatched_on<o.ordered_at"
            ),
            "future_deliveries": (
                "SELECT COUNT(*) FROM shipments WHERE provenance LIKE "
                "'fictional_contemporary_%' AND delivered_on>date('now')"
            ),
            "shipment_without_movement": (
                "SELECT COUNT(*) FROM shipment_items si JOIN shipments s ON s.id=si.shipment_id "
                "JOIN order_items oi ON oi.id=si.order_item_id "
                "LEFT JOIN stock_movements m ON m.shipment_item_id=si.id WHERE "
                "s.provenance LIKE 'fictional_contemporary_%' AND "
                "(m.id IS NULL OR m.quantity!=-si.quantity OR m.occurred_on!=s.dispatched_on "
                "OR m.product_id!=oi.product_id OR m.warehouse_id!=s.warehouse_id)"
            ),
            "stock_balance_mismatch": (
                "SELECT COUNT(*) FROM inventory i JOIN products p ON p.id=i.product_id "
                "WHERE p.provenance LIKE 'fictional_contemporary_%' AND i.on_hand != "
                "(SELECT COALESCE(SUM(quantity),0) FROM stock_movements m WHERE "
                "m.product_id=i.product_id AND m.warehouse_id=i.warehouse_id)"
            ),
            "order_status_mismatch": (
                "SELECT COUNT(*) FROM orders o WHERE o.provenance LIKE "
                "'fictional_contemporary_%' AND o.status IS NOT (SELECT h.status "
                "FROM order_status_history h WHERE h.order_id=o.id "
                "ORDER BY h.occurred_at DESC,h.id DESC LIMIT 1)"
            ),
            "order_history_before_order": (
                "SELECT COUNT(*) FROM order_status_history h JOIN orders o ON o.id=h.order_id "
                "WHERE o.provenance LIKE 'fictional_contemporary_%' "
                "AND h.occurred_at<o.ordered_at"
            ),
            "ticket_before_order": (
                "SELECT COUNT(*) FROM tickets t JOIN orders o ON o.id=t.order_id WHERE "
                "t.provenance LIKE 'fictional_contemporary_%' AND t.opened_on<o.ordered_at"
            ),
            "ticket_status_mismatch": (
                "SELECT COUNT(*) FROM tickets t WHERE t.provenance LIKE 'fictional_contemporary_%' "
                "AND t.status!=(SELECT e.status FROM ticket_events e WHERE e.ticket_id=t.id "
                "ORDER BY e.occurred_on DESC,e.id DESC LIMIT 1)"
            ),
            "future_ticket_events": (
                "SELECT COUNT(*) FROM ticket_events e JOIN tickets t ON t.id=e.ticket_id "
                "WHERE t.provenance LIKE 'fictional_contemporary_%' "
                "AND e.occurred_on>date('now')"
            ),
            "purchase_supplier_mismatch": (
                "SELECT COUNT(*) FROM purchase_order_items pi JOIN purchase_orders po "
                "ON po.id=pi.purchase_order_id JOIN products p ON p.id=pi.product_id "
                "WHERE po.provenance LIKE 'fictional_contemporary_%' "
                "AND po.supplier_id!=p.supplier_id"
            ),
            "purchase_receipt_mismatch": (
                "SELECT COUNT(*) FROM purchase_order_items pi JOIN purchase_orders po "
                "ON po.id=pi.purchase_order_id WHERE po.provenance LIKE "
                "'fictional_contemporary_%' AND (SELECT COALESCE(SUM(quantity),0) "
                "FROM goods_receipts gr WHERE gr.purchase_order_item_id=pi.id)>pi.quantity"
            ),
            "purchase_status_mismatch": (
                "SELECT COUNT(*) FROM purchase_orders po WHERE po.provenance LIKE "
                "'fictional_contemporary_%' AND ((po.status='received' AND EXISTS "
                "(SELECT 1 FROM purchase_order_items pi WHERE pi.purchase_order_id=po.id "
                "AND (SELECT COALESCE(SUM(quantity),0) FROM goods_receipts gr WHERE "
                "gr.purchase_order_item_id=pi.id)!=pi.quantity)) OR (po.status='open' "
                "AND NOT EXISTS (SELECT 1 FROM purchase_order_items pi WHERE "
                "pi.purchase_order_id=po.id AND (SELECT COALESCE(SUM(quantity),0) "
                "FROM goods_receipts gr WHERE gr.purchase_order_item_id=pi.id)<pi.quantity)))"
            ),
            "purchase_receipt_without_stock": (
                "SELECT COUNT(*) FROM goods_receipts gr JOIN purchase_order_items pi "
                "ON pi.id=gr.purchase_order_item_id JOIN purchase_orders po "
                "ON po.id=pi.purchase_order_id LEFT JOIN stock_movements m "
                "ON m.goods_receipt_id=gr.id WHERE po.provenance LIKE "
                "'fictional_contemporary_%' AND (m.id IS NULL OR m.quantity!=gr.quantity "
                "OR m.occurred_on!=gr.received_on OR m.warehouse_id!=po.warehouse_id "
                "OR m.product_id!=pi.product_id OR gr.received_on<po.placed_on "
                "OR gr.received_on>date('now'))"
            ),
            "forecast_cutoff_mismatch": (
                "SELECT COUNT(*) FROM forecast_runs WHERE id LIKE 'SCN-FCRUN-%' "
                "AND (training_cutoff>=target_start OR generated_at<target_start "
                "OR date(generated_at)>date('now'))"
            ),
            "forecast_without_sales_target": (
                "SELECT COUNT(*) FROM forecasts f WHERE f.id LIKE 'SCN-FC-%' "
                "AND NOT EXISTS(SELECT 1 FROM sales_targets t WHERE t.forecast_id=f.id)"
            ),
            "sales_target_link_mismatch": (
                "SELECT COUNT(*) FROM sales_targets t JOIN forecasts f ON f.id=t.forecast_id "
                "WHERE t.id LIKE 'SCN-TARGET-%' AND (t.id!='SCN-TARGET-'||substr(f.id,8) "
                "OR t.department_id!='DEP-SALES' OR trim(t.assumption)='')"
            ),
        }
        violations = {name: db.execute(sql).fetchone()[0] for name, sql in checks.items()}
        expense_checks = {
            "expense_supplier_mismatch": (
                "SELECT COUNT(*) FROM company_expenses e JOIN purchase_orders po "
                "ON po.id=e.purchase_order_id WHERE e.supplier_id!=po.supplier_id"
            ),
            "expense_before_purchase_order": (
                "SELECT COUNT(*) FROM company_expenses e JOIN purchase_orders po "
                "ON po.id=e.purchase_order_id WHERE e.paid_on<po.placed_on"
            ),
            "future_expenses": (
                "SELECT COUNT(*) FROM company_expenses WHERE paid_on>date('now')"
            ),
        }
        ledger_present = has_expense_ledger(db)
        violations.update({
            name: db.execute(sql).fetchone()[0] if ledger_present else 0
            for name, sql in expense_checks.items()
        })
        violations["forecast_input_mismatch"] = sum(
            forecast_input(db, row["product_id"], row["target_start"], row["lookback_months"])
            != (
                row["units"],
                row["training_units"],
                row["training_last_date"],
                row["input_sha256"],
            )
            for row in db.execute(
                "SELECT f.*,r.target_start,r.lookback_months FROM forecasts f "
                "JOIN forecast_runs r ON r.id=f.run_id WHERE f.id LIKE 'SCN-FC-%'"
            )
        )
        violations["sales_target_basis_mismatch"] = 0
        for row in db.execute(
            "SELECT t.target_units,t.assumption,f.units FROM sales_targets t "
            "JOIN forecasts f ON f.id=t.forecast_id WHERE t.id LIKE 'SCN-TARGET-%'"
        ):
            match = re.search(r"at (\d+)% of forecast; rounded half up", row["assumption"])
            if match:
                expected = (row["units"] * int(match.group(1)) + 50) // 100
            elif "two-unit minimum" in row["assumption"]:
                expected = 2 if row["units"] == 0 else None
            else:
                continue  # A separately explained planner judgment has no fixed ratio.
            violations["sales_target_basis_mismatch"] += row["target_units"] != expected
        counts = {
            table: db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE provenance LIKE 'fictional_contemporary_%'"
            ).fetchone()[0]
            for table in (
                "customers",
                "orders",
                "invoices",
                "shipments",
                "payments",
                "tickets",
                "credit_notes",
                "purchase_orders",
            )
        }
        dates = db.execute(
            "SELECT MIN(ordered_at),MAX(ordered_at) FROM orders WHERE provenance LIKE "
            "'fictional_contemporary_%'"
        ).fetchone()
        counts["forecast_runs"] = db.execute(
            "SELECT COUNT(*) FROM forecast_runs WHERE id LIKE 'SCN-FCRUN-%'"
        ).fetchone()[0]
        counts["forecasts"] = db.execute(
            "SELECT COUNT(*) FROM forecasts WHERE id LIKE 'SCN-FC-%'"
        ).fetchone()[0]
        counts["sales_targets"] = db.execute(
            "SELECT COUNT(*) FROM sales_targets WHERE id LIKE 'SCN-TARGET-%'"
        ).fetchone()[0]
        counts["company_expenses"] = (
            db.execute("SELECT COUNT(*) FROM company_expenses").fetchone()[0]
            if ledger_present else 0
        )
        return {
            "status": "ok" if not any(violations.values()) else "invalid",
            "counts": counts,
            "order_dates": {"first": dates[0], "last": dates[1]},
            "violations": violations,
        }
    finally:
        db.close()


def seed_contemporary_cases(state: Path) -> dict:
    """Add varied linked service cases and one verified credit to the modern cohort."""
    database = state / "company.sqlite"
    db = connect(database)
    try:
        missing = [
            (name, topic, status, description, _seed_suffix(name))
            for name, topic, status, description in CONTEMPORARY_CASES
            if db.execute(
                "SELECT 1 FROM tickets WHERE id=?", (f"SCN-TKT-{_seed_suffix(name)}",)
            ).fetchone()
            is None
        ]
        if not missing:
            return {"status": "already_present", "created": [], "backup": None}
        support = db.execute(
            "SELECT e.id FROM employees e JOIN employee_assignments a "
            "ON a.employee_id=e.id WHERE a.department_id='DEP-SUPPORT' "
            "AND a.valid_until IS NULL ORDER BY e.id"
        ).fetchall()
        if not support:
            raise ValueError("A support employee is required for contemporary cases")
        backup = (
            state
            / "backups"
            / (
                "modern-cases-"
                + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                + "-"
                + uuid4().hex[:6]
            )
        )
        backup.mkdir(parents=True, exist_ok=False)
        snapshot = connect(backup / "company.sqlite")
        try:
            db.backup(snapshot)
        finally:
            snapshot.close()
        created = []
        db.execute("BEGIN IMMEDIATE")
        for index, (name, topic, status, description, suffix) in enumerate(missing):
            account_id = f"SCN-CUST-{suffix}"
            order = db.execute(
                "SELECT o.id,i.id AS invoice_id,s.id AS shipment_id,s.delivered_on "
                "FROM orders o JOIN invoices i ON i.order_id=o.id "
                "JOIN shipments s ON s.order_id=o.id WHERE o.customer_id=? "
                "AND o.provenance='fictional_contemporary_seed' "
                "ORDER BY o.ordered_at,o.id LIMIT 1",
                (account_id,),
            ).fetchone()
            if order is None:
                raise ValueError(f"No fulfilled order for {name}")
            opened = date.fromisoformat(order["delivered_on"]) + timedelta(days=2)
            if opened > date.today():
                raise ValueError(f"Case opening date is in the future for {name}")
            ticket_id = f"SCN-TKT-{suffix}"
            assigned = support[index % len(support)][0]
            db.execute(
                "INSERT INTO tickets VALUES(?,?,?,?,?,?,?,?)",
                (
                    ticket_id,
                    order["id"],
                    assigned,
                    opened.isoformat(),
                    status,
                    topic,
                    f"{description} Order {order['id']}; shipment {order['shipment_id']}.",
                    "fictional_contemporary_seed",
                ),
            )
            db.execute(
                "INSERT INTO ticket_events VALUES(?,?,?,?,?)",
                (
                    f"SCN-TKTEVT-{suffix}-1",
                    ticket_id,
                    opened.isoformat(),
                    "open",
                    f"Customer report logged against order {order['id']}; evidence requested.",
                ),
            )
            if status != "open":
                review = opened + timedelta(days=2)
                db.execute(
                    "INSERT INTO ticket_events VALUES(?,?,?,?,?)",
                    (
                        f"SCN-TKTEVT-{suffix}-2",
                        ticket_id,
                        review.isoformat(),
                        "in_progress",
                        f"Support reviewed invoice {order['invoice_id']} and shipment "
                        f"{order['shipment_id']}; outcome pending confirmation.",
                    ),
                )
            if status == "resolved":
                resolved = opened + timedelta(days=4)
                if resolved > date.today():
                    raise ValueError(f"Case resolution date is in the future for {name}")
                outcome = (
                    f"Damage confirmed; finance issued credit SCN-CREDIT-{suffix}."
                    if topic == "damaged_goods"
                    else f"Requested evidence for invoice {order['invoice_id']} or shipment "
                    f"{order['shipment_id']} supplied; case closed."
                )
                db.execute(
                    "INSERT INTO ticket_events VALUES(?,?,?,?,?)",
                    (
                        f"SCN-TKTEVT-{suffix}-3",
                        ticket_id,
                        resolved.isoformat(),
                        "resolved",
                        outcome,
                    ),
                )
                if topic == "damaged_goods":
                    invoice_total = db.execute(
                        "SELECT total_pence FROM invoices WHERE id=?", (order["invoice_id"],)
                    ).fetchone()[0]
                    db.execute(
                        "INSERT INTO credit_notes VALUES(?,?,?,?,?,?)",
                        (
                            f"SCN-CREDIT-{suffix}",
                            order["invoice_id"],
                            resolved.isoformat(),
                            min(1000, invoice_total // 10),
                            f"Verified display damage; service case {ticket_id}",
                            "fictional_contemporary_seed",
                        ),
                    )
            created.append({"ticket_id": ticket_id, "order_id": order["id"], "topic": topic})
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Contemporary service cases have broken references")
        db.commit()
        (backup / "case_receipt.json").write_text(
            json.dumps({"created": created}, indent=2), encoding="utf-8"
        )
        return {"status": "seeded", "created": created, "backup": str(backup)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seed_contemporary_purchasing(state: Path) -> dict:
    """Add a complete, short-received and delayed supplier order to modern history."""
    database = state / "company.sqlite"
    db = connect(database)
    try:
        missing = [
            (name, ordered, received, delay, reason, _seed_suffix(name))
            for name, ordered, received, delay, reason in CONTEMPORARY_PURCHASING
            if db.execute(
                "SELECT 1 FROM purchase_orders WHERE id=?",
                (f"SCN-PO-{_seed_suffix(name)}",),
            ).fetchone()
            is None
        ]
        if not missing:
            return {"status": "already_present", "created": [], "backup": None}
        backup = (
            state
            / "backups"
            / (
                "modern-purchasing-"
                + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                + "-"
                + uuid4().hex[:6]
            )
        )
        backup.mkdir(parents=True, exist_ok=False)
        snapshot = connect(backup / "company.sqlite")
        try:
            db.backup(snapshot)
        finally:
            snapshot.close()
        created = []
        db.execute("BEGIN IMMEDIATE")
        for name, ordered, received, delay, reason, suffix in missing:
            account_id = f"SCN-CUST-{suffix}"
            product_id = f"SCN-SKU-{suffix}"
            context = db.execute(
                "SELECT MAX(o.ordered_at) AS last_order,p.supplier_id,s.lead_days,"
                "i.id AS inventory_id,i.warehouse_id FROM orders o JOIN products p "
                "ON p.id=? JOIN suppliers s ON s.id=p.supplier_id JOIN inventory i "
                "ON i.product_id=p.id WHERE o.customer_id=? AND "
                "o.provenance='fictional_contemporary_seed'",
                (product_id, account_id),
            ).fetchone()
            if context is None or context["last_order"] is None:
                raise ValueError(f"Contemporary account or product missing: {name}")
            placed = date.fromisoformat(context["last_order"]) + timedelta(days=1)
            expected = placed + timedelta(days=context["lead_days"])
            received_on = expected + timedelta(days=delay) if received else None
            if placed > date.today() or (received_on and received_on > date.today()):
                raise ValueError(f"Purchase event would be in the future: {name}")
            po_id = f"SCN-PO-{suffix}"
            item_id = f"SCN-POITEM-{suffix}"
            status = "received" if received == ordered else "open"
            db.execute(
                "INSERT INTO purchase_orders VALUES(?,?,?,?,?,?,?)",
                (
                    po_id,
                    context["supplier_id"],
                    context["warehouse_id"],
                    placed.isoformat(),
                    expected.isoformat(),
                    status,
                    f"fictional_contemporary_seed: {reason}",
                ),
            )
            db.execute(
                "INSERT INTO purchase_order_items VALUES(?,?,?,?)",
                (item_id, po_id, product_id, ordered),
            )
            if received:
                receipt_id = f"SCN-GR-{suffix}"
                db.execute(
                    "INSERT INTO goods_receipts VALUES(?,?,?,?)",
                    (receipt_id, item_id, received_on.isoformat(), received),
                )
                db.execute(
                    "INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)",
                    (
                        f"SCN-STOCK-{suffix}-RECEIPT",
                        context["warehouse_id"],
                        product_id,
                        received_on.isoformat(),
                        "receipt",
                        received,
                        None,
                        receipt_id,
                    ),
                )
                db.execute(
                    "UPDATE inventory SET on_hand=on_hand+?,as_of=? WHERE id=?",
                    (received, date.today().isoformat(), context["inventory_id"]),
                )
            created.append(
                {
                    "purchase_order_id": po_id,
                    "product_id": product_id,
                    "ordered": ordered,
                    "received": received,
                    "expected_on": expected.isoformat(),
                    "status": status,
                }
            )
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Contemporary purchasing has broken references")
        db.commit()
        (backup / "purchasing_receipt.json").write_text(
            json.dumps({"created": created}, indent=2), encoding="utf-8"
        )
        return {"status": "seeded", "created": created, "backup": str(backup)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seed_contemporary_planning(state: Path) -> dict:
    """Freeze two October planning comparisons using only July-September invoices."""
    database = state / "company.sqlite"
    db = connect(database)
    try:
        missing = [
            (name, explanation, _seed_suffix(name))
            for name, explanation in CONTEMPORARY_PLANNING
            if db.execute(
                "SELECT 1 FROM forecast_runs WHERE id=?",
                (f"SCN-FCRUN-{_seed_suffix(name)}-2026-10-v1",),
            ).fetchone()
            is None
        ]
        if not missing:
            return {"status": "already_present", "created": [], "backup": None}
        if date.today() < date(2026, 10, 1):
            raise ValueError("October planning run cannot be generated before October")
        backup = (
            state
            / "backups"
            / (
                "modern-planning-"
                + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                + "-"
                + uuid4().hex[:6]
            )
        )
        backup.mkdir(parents=True, exist_ok=False)
        snapshot = connect(backup / "company.sqlite")
        try:
            db.backup(snapshot)
        finally:
            snapshot.close()
        created = []
        db.execute("BEGIN IMMEDIATE")
        for name, explanation, suffix in missing:
            product_id = f"SCN-SKU-{suffix}"
            if db.execute("SELECT 1 FROM products WHERE id=?", (product_id,)).fetchone() is None:
                raise ValueError(f"Planning product missing: {name}")
            for version, lookback, stretch in ((1, 3, 125), (2, 2, 110)):
                run_id = f"SCN-FCRUN-{suffix}-2026-10-v{version}"
                forecast_id = f"SCN-FC-{suffix}-2026-10-v{version}"
                units, training_units, last_date, digest = forecast_input(
                    db, product_id, "2026-10-01", lookback
                )
                target = (units * stretch + 50) // 100 if units else 2
                target_assumption = (
                    f"Fictional planning target at {stretch}% of forecast; "
                    "rounded half up. Review stock and supplier evidence separately."
                    if units
                    else "Fictional planner override: two-unit minimum because the short "
                    "lookback has no billed units. This is judgment, not model output."
                )
                db.execute(
                    "INSERT INTO forecast_runs VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        "2026-10-01T09:00:00+00:00",
                        "2026-09-30",
                        "2026-10-01",
                        "2026-10-31",
                        "trailing calendar-month mean of billed units",
                        version,
                        lookback,
                        "Fictional contemporary review: "
                        + explanation
                        + ". Frozen prior complete months; October actuals excluded.",
                    ),
                )
                db.execute(
                    "INSERT INTO forecasts VALUES(?,?,?,?,?,?,?)",
                    (
                        forecast_id,
                        run_id,
                        product_id,
                        units,
                        training_units,
                        last_date,
                        digest,
                    ),
                )
                db.execute(
                    "INSERT INTO sales_targets VALUES(?,?,?,?,?)",
                    (
                        f"SCN-TARGET-{suffix}-2026-10-v{version}",
                        "DEP-SALES",
                        forecast_id,
                        target,
                        target_assumption,
                    ),
                )
                created.append(
                    {
                        "forecast_id": forecast_id,
                        "product_id": product_id,
                        "training_units": training_units,
                        "forecast_units": units,
                        "target_units": target,
                    }
                )
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Contemporary planning has broken references")
        db.commit()
        (backup / "planning_receipt.json").write_text(
            json.dumps({"created": created}, indent=2), encoding="utf-8"
        )
        return {"status": "seeded", "created": created, "backup": str(backup)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
