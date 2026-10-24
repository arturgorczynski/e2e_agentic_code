"""Independent relational, financial, temporal, document and scenario checks."""

import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from acme.company_data import AS_OF, forecast_input
from acme.company_documents import (
    customer_facts,
    department_facts,
    incident_facts,
    metadata_and_body,
    planning_facts,
    product_facts,
)
from acme.source_data import sha256

ZERO_QUERIES = {
    "customer managers have active sales assignments": (
        "SELECT COUNT(*) FROM customers c WHERE NOT EXISTS(SELECT 1 FROM "
        "employee_assignments a WHERE a.employee_id=c.account_manager_id "
        "AND a.department_id='DEP-SALES' AND a.valid_until IS NULL)"
    ),
    "purchase supplier matches catalog": (
        "SELECT COUNT(*) FROM purchase_order_items pi "
        "JOIN purchase_orders po ON po.id=pi.purchase_order_id "
        "JOIN products p ON p.id=pi.product_id WHERE p.supplier_id!=po.supplier_id"
    ),
    "invoice headers equal lines": (
        "SELECT COUNT(*) FROM invoices i WHERE total_pence != (SELECT SUM(amount_pence) FROM "
        "invoice_items WHERE invoice_id=i.id)"
    ),
    "invoice lines match their order": (
        "SELECT COUNT(*) FROM invoice_items ii JOIN invoices i ON i.id=ii.invoice_id JOIN "
        "order_items oi ON oi.id=ii.order_item_id WHERE oi.order_id!=i.order_id OR "
        "oi.quantity!=ii.quantity OR oi.line_pence!=ii.amount_pence"
    ),
    "payments allocated exactly once in baseline": (
        "SELECT COUNT(*) FROM payments p WHERE amount_pence != (SELECT "
        "COALESCE(SUM(amount_pence),0) FROM payment_allocations WHERE payment_id=p.id)"
    ),
    "allocation ownership and chronology": (
        "SELECT COUNT(*) FROM payment_allocations a JOIN payments p ON p.id=a.payment_id JOIN "
        "invoices i ON i.id=a.invoice_id JOIN orders o ON o.id=i.order_id WHERE "
        "p.customer_id!=o.customer_id OR a.allocated_on<p.received_on OR "
        "a.allocated_on<i.posted_on OR a.allocated_on>'2011-12-09'"
    ),
    "source remittances use weekdays": (
        "SELECT COUNT(*) FROM payments WHERE id LIKE 'PAY-REM-%' AND "
        "(received_on>'2011-12-09' OR strftime('%w',received_on) IN ('0','6'))"
    ),
    "source remittance allocations match receipt date": (
        "SELECT COUNT(*) FROM payment_allocations a JOIN payments p ON p.id=a.payment_id "
        "WHERE p.id LIKE 'PAY-REM-%' AND a.allocated_on!=p.received_on"
    ),
    "no over-settled invoices": "SELECT COUNT(*) FROM invoice_balances WHERE outstanding_pence<0",
    "invoice and credit chronology": (
        "SELECT COUNT(*) FROM credit_notes c JOIN invoices i ON i.id=c.invoice_id WHERE "
        "c.issued_on<i.posted_on OR c.issued_on>'2011-12-09'"
    ),
    "billing follows acceptance": (
        "SELECT COUNT(*) FROM invoices i JOIN orders o ON o.id=i.order_id WHERE "
        "i.posted_on<o.ordered_at OR i.posted_on>'2011-12-09'"
    ),
    "source acceptance uses weekdays": (
        "SELECT COUNT(*) FROM orders WHERE source_invoice_no IS NOT NULL "
        "AND strftime('%w',ordered_at) IN ('0','6')"
    ),
    "source dispatch follows invoice on weekdays": (
        "SELECT COUNT(*) FROM shipments s JOIN orders o ON o.id=s.order_id "
        "JOIN invoices i ON i.order_id=o.id WHERE o.source_invoice_no IS NOT NULL "
        "AND (s.dispatched_on<i.posted_on OR strftime('%w',s.dispatched_on) IN ('0','6'))"
    ),
    "shipment ownership and quantity": (
        "SELECT COUNT(*) FROM shipment_items si JOIN shipments s ON s.id=si.shipment_id JOIN "
        "order_items oi ON oi.id=si.order_item_id WHERE oi.order_id!=s.order_id"
    ),
    "no excess fulfillment": (
        "SELECT COUNT(*) FROM order_fulfillment WHERE shipped_quantity>quantity"
    ),
    "dispatch chronology": (
        "SELECT COUNT(*) FROM shipments s JOIN orders o ON o.id=s.order_id WHERE "
        "s.dispatched_on<o.ordered_at OR s.dispatched_on>'2011-12-09' OR "
        "s.delivered_on>'2011-12-09'"
    ),
    "every dispatch has one matching movement": (
        "SELECT COUNT(*) FROM shipment_items si JOIN shipments s ON s.id=si.shipment_id JOIN "
        "order_items oi ON oi.id=si.order_item_id LEFT JOIN stock_movements m ON "
        "m.shipment_item_id=si.id WHERE m.id IS NULL OR m.quantity!=-si.quantity OR "
        "m.product_id!=oi.product_id OR m.warehouse_id!=s.warehouse_id OR "
        "m.occurred_on!=s.dispatched_on"
    ),
    "every receipt has one matching movement": (
        "SELECT COUNT(*) FROM goods_receipts g JOIN purchase_order_items pi ON "
        "pi.id=g.purchase_order_item_id JOIN purchase_orders p ON p.id=pi.purchase_order_id LEFT "
        "JOIN stock_movements m ON m.goods_receipt_id=g.id WHERE m.id IS NULL OR "
        "m.quantity!=g.quantity OR m.product_id!=pi.product_id OR m.warehouse_id!=p.warehouse_id "
        "OR m.occurred_on!=g.received_on OR g.received_on<p.placed_on OR "
        "g.received_on>'2011-12-09'"
    ),
    "received purchase lines reconcile": (
        "SELECT COUNT(*) FROM purchase_order_items pi JOIN purchase_orders p ON "
        "p.id=pi.purchase_order_id WHERE (p.status='received' AND pi.quantity!=(SELECT "
        "COALESCE(SUM(quantity),0) FROM goods_receipts WHERE purchase_order_item_id=pi.id)) OR "
        "(p.status='open' AND pi.quantity<=(SELECT COALESCE(SUM(quantity),0) FROM goods_receipts "
        "WHERE purchase_order_item_id=pi.id))"
    ),
    "retrospective weekly receipts precede dispatch week": (
        "SELECT COUNT(*) FROM goods_receipts g JOIN purchase_order_items pi ON "
        "pi.id=g.purchase_order_item_id JOIN purchase_orders po ON "
        "po.id=pi.purchase_order_id WHERE po.id LIKE 'PO-SUP-%' "
        "AND (g.received_on>=substr(po.id,length(po.id)-9,10) OR "
        "strftime('%w',g.received_on) IN ('0','6') OR "
        "strftime('%w',po.placed_on) IN ('0','6'))"
    ),
    "stock ends at on-hand balance": (
        "SELECT COUNT(*) FROM inventory i WHERE i.on_hand!=(SELECT COALESCE(SUM(quantity),0) FROM "
        "stock_movements WHERE product_id=i.product_id AND warehouse_id=i.warehouse_id)"
    ),
    "movements have inventory positions": (
        "SELECT COUNT(*) FROM stock_movements m LEFT JOIN inventory i ON "
        "i.product_id=m.product_id AND i.warehouse_id=m.warehouse_id WHERE i.id IS NULL"
    ),
    "stock never becomes negative": (
        "SELECT COUNT(*) FROM (SELECT SUM(quantity) OVER (PARTITION BY warehouse_id,product_id "
        "ORDER BY occurred_on,CASE kind WHEN 'opening' THEN 0 WHEN 'receipt' THEN 1 ELSE 2 END,id "
        "ROWS UNBOUNDED PRECEDING) AS balance FROM stock_movements) WHERE balance<0"
    ),
    "physical reservations do not include backordered demand": (
        "SELECT COUNT(*) FROM inventory i WHERE i.warehouse_id='WH-CVT' AND i.reserved!=(SELECT "
        "MIN(i.on_hand,COALESCE(SUM(f.quantity-f.shipped_quantity),0)) FROM order_fulfillment f "
        "JOIN orders o ON o.id=f.order_id WHERE f.product_id=i.product_id AND "
        "o.status!='cancelled')"
    ),
    "cancellation precedes billing or shipping": (
        "SELECT COUNT(*) FROM orders o WHERE o.status='cancelled' AND (EXISTS(SELECT 1 FROM "
        "invoices WHERE order_id=o.id) OR EXISTS(SELECT 1 FROM shipments WHERE order_id=o.id))"
    ),
    "order status matches fulfillment": (
        "SELECT COUNT(*) FROM orders o WHERE o.status!='cancelled' AND o.status != CASE WHEN NOT "
        "EXISTS(SELECT 1 FROM order_fulfillment WHERE order_id=o.id AND "
        "quantity!=shipped_quantity) THEN 'fulfilled' WHEN EXISTS(SELECT 1 FROM order_fulfillment "
        "WHERE order_id=o.id AND shipped_quantity>0) THEN 'partial' ELSE 'confirmed' END"
    ),
    "order history reaches current status": (
        "SELECT COUNT(*) FROM orders o WHERE o.status != (SELECT h.status FROM "
        "order_status_history h WHERE h.order_id=o.id ORDER BY h.occurred_at DESC,h.id DESC LIMIT "
        "1) OR NOT EXISTS(SELECT 1 FROM order_status_history h WHERE h.order_id=o.id AND "
        "h.status='confirmed' AND h.occurred_at=o.ordered_at)"
    ),
    "status events within lifecycle": (
        "SELECT COUNT(*) FROM order_status_history h JOIN orders o ON o.id=h.order_id WHERE "
        "h.occurred_at<o.ordered_at OR h.occurred_at>'2011-12-09'"
    ),
    "ticket timeline agrees": (
        "SELECT COUNT(*) FROM tickets t JOIN orders o ON o.id=t.order_id WHERE "
        "t.opened_on<o.ordered_at OR t.status!=(SELECT e.status FROM ticket_events e WHERE "
        "e.ticket_id=t.id ORDER BY e.occurred_on DESC,e.id DESC LIMIT 1)"
    ),
    "ticket events within lifecycle": (
        "SELECT COUNT(*) FROM ticket_events e JOIN tickets t ON t.id=e.ticket_id WHERE "
        "e.occurred_on<t.opened_on OR e.occurred_on>'2011-12-09'"
    ),
    "source service cases use support staff": (
        "SELECT COUNT(*) FROM tickets t JOIN orders o ON o.id=t.order_id WHERE "
        "o.source_invoice_no IS NOT NULL AND NOT EXISTS(SELECT 1 FROM employee_assignments a "
        "WHERE a.employee_id=t.assigned_employee_id AND a.department_id='DEP-SUPPORT' "
        "AND a.valid_until IS NULL)"
    ),
    "source service events use weekdays": (
        "SELECT COUNT(*) FROM ticket_events e JOIN tickets t ON t.id=e.ticket_id "
        "JOIN orders o ON o.id=t.order_id WHERE o.source_invoice_no IS NOT NULL "
        "AND strftime('%w',e.occurred_on) IN ('0','6')"
    ),
    "split service cases follow first dispatch": (
        "SELECT COUNT(*) FROM tickets t JOIN orders o ON o.id=t.order_id "
        "WHERE o.source_invoice_no IS NOT NULL AND t.topic='split_consignment' "
        "AND (NOT EXISTS(SELECT 1 FROM shipments s WHERE s.order_id=o.id) OR "
        "t.opened_on<=(SELECT MIN(s.dispatched_on) FROM shipments s WHERE s.order_id=o.id))"
    ),
    "employee assignment intervals do not overlap": (
        "SELECT COUNT(*) FROM employee_assignments a JOIN employee_assignments b ON "
        "a.employee_id=b.employee_id AND a.id<b.id WHERE "
        "a.valid_from<=COALESCE(b.valid_until,'9999-12-31') AND "
        "b.valid_from<=COALESCE(a.valid_until,'9999-12-31')"
    ),
    "each employee has a current assignment": (
        "SELECT COUNT(*) FROM employees e WHERE (SELECT COUNT(*) FROM employee_assignments a "
        "WHERE a.employee_id=e.id AND a.valid_until IS NULL)!=1"
    ),
    "document intervals do not overlap": (
        "SELECT COUNT(*) FROM document_versions a JOIN document_versions b ON "
        "a.document_id=b.document_id AND a.id<b.id WHERE "
        "a.effective_from<COALESCE(b.effective_until,'9999-12-31') AND "
        "b.effective_from<COALESCE(a.effective_until,'9999-12-31')"
    ),
    "documents have a current version": (
        "SELECT COUNT(*) FROM documents d WHERE (SELECT COUNT(*) FROM document_versions v WHERE "
        "v.document_id=d.id AND v.status='current')!=1"
    ),
}


def scenario_evidence(db, project):
    """Read actual scenario facts; action acceptance remains a later runtime gate."""
    invoice = dict(db.execute("SELECT * FROM invoice_balances WHERE id='DEMO-INV-001'").fetchone())
    lines = db.execute(
        (
            "SELECT product_id,quantity-shipped_quantity FROM order_fulfillment WHERE "
            "order_id='DEMO-ORD-002'"
        )
    ).fetchall()
    stock = db.execute(
        "SELECT on_hand,reserved FROM inventory WHERE id='DEMO-STOCK-003'"
    ).fetchone()
    metrics = dict(
        db.execute(
            "SELECT month,sales_pence FROM monthly_customer_sales WHERE customer_id='DEMO-CUST-005'"
        ).fetchall()
    )
    forecast = dict(db.execute("SELECT * FROM forecasts WHERE id='DEMO-FC-006'").fetchone())
    actual = db.execute(
        (
            "SELECT SUM(ii.quantity) FROM invoice_items ii JOIN invoices i ON i.id=ii.invoice_id "
            "JOIN order_items oi ON oi.id=ii.order_item_id WHERE oi.product_id='DEMO-SKU-FC' AND "
            "i.posted_on BETWEEN '2011-11-01' AND '2011-11-30'"
        )
    ).fetchone()[0]
    policies = db.execute(
        (
            "SELECT version,effective_from,effective_until FROM document_versions WHERE "
            "document_id='POL-RETURNS-001' ORDER BY version"
        )
    ).fetchall()
    company = json.loads((project / "data/company/company.json").read_text("utf-8"))
    accounts = {a["id"]: a for a in company["accounts"]}
    return {
        "S01": {
            "outstanding_pence": invoice["outstanding_pence"],
            "days_overdue": (
                date.fromisoformat(AS_OF) - date.fromisoformat(invoice["due_on"])
            ).days,
        },
        "S02": {
            "outstanding_by_sku": dict(lines),
            "order_complete": all(row[1] == 0 for row in lines),
        },
        "S03": {
            "available": stock[0] - stock[1],
            "shortage": 30 - (stock[0] - stock[1]),
            "supplier_eta": db.execute(
                "SELECT expected_on FROM purchase_orders WHERE id='DEMO-PO-003'"
            ).fetchone()[0],
            "inbound_units": db.execute(
                (
                    "SELECT SUM(quantity) FROM purchase_order_items WHERE "
                    "purchase_order_id='DEMO-PO-003'"
                )
            ).fetchone()[0],
        },
        "S04": {
            "status_before": db.execute(
                "SELECT status FROM tickets WHERE id='DEMO-TKT-004'"
            ).fetchone()[0],
            "runtime_gate": "approval and idempotent update not implemented in G04/G05",
        },
        "S05": {
            "change_pence": metrics["2011-11"] - metrics["2011-10"],
            "change_percent": str(
                Decimal(metrics["2011-11"] - metrics["2011-10"]) * 100 / metrics["2011-10"]
            ),
        },
        "S06": {
            "forecast_units": forecast["units"],
            "actual_units": actual,
            "error_units": actual - forecast["units"],
            "error_percent": str(Decimal(actual - forecast["units"]) * 100 / forecast["units"]),
        },
        "S07": {
            "october_pence": metrics["2011-10"],
            "november_pence": metrics["2011-11"],
            "owner_id": "USR-004",
            "runtime_gate": "report is a proposed output; approval/restart/save are G07-G11",
        },
        "S08": {
            "order_exists": db.execute(
                "SELECT COUNT(*) FROM orders WHERE id='DEMO-ORD-008'"
            ).fetchone()[0]
            == 1,
            "runtime_gate": "rejection/no-write acceptance is G09",
        },
        "S09": {
            "finance_permission_granted": "finance.read"
            in company["roles"][accounts["USR-003"]["role"]],
            "runtime_gate": "server-side denial is G06-G11",
        },
        "S10": {
            "owner_id": "USR-001",
            "acting_user_id": "USR-002",
            "runtime_gate": (
                "private app records supplied in evals/runtime_seed.json; ownership enforcement "
                "is G07-G11"
            ),
        },
        "S11": {"versions": [list(row) for row in policies]},
        "S12": {
            "found": db.execute(
                "SELECT COUNT(*) FROM orders WHERE id='DEMO-ORD-NOT-FOUND'"
            ).fetchone()[0]
            > 0
        },
    }


def validate_documents(db, folder, profile):
    catalog = json.loads((folder / "catalog.json").read_text("utf-8"))["documents"]
    expected = {row["relative_path"]: row for row in catalog}
    actual = {p.relative_to(folder).as_posix() for p in (folder / "content").glob("*.md")}
    if actual != set(expected):
        raise ValueError("Document files and catalog differ")
    versions = db.execute("SELECT * FROM document_versions ORDER BY id").fetchall()
    if len(versions) != len(catalog):
        raise ValueError("Document version count differs")
    categories = Counter()
    bodies = set()
    for row in versions:
        item = expected[row["relative_path"]]
        path = folder / row["relative_path"]
        if not path.resolve().is_relative_to(folder.resolve()):
            raise ValueError("Document path leaves the corpus")
        if sha256(path) != row["sha256"] or item["sha256"] != row["sha256"]:
            raise ValueError(f"Document checksum mismatch: {path.name}")
        metadata, body = metadata_and_body(path)
        for field in ("document_id", "version", "effective_from", "effective_until", "status"):
            if metadata[field] != row[field] or metadata[field] != item[field]:
                raise ValueError(f"Document metadata mismatch: {field}")
        doc = db.execute("SELECT * FROM documents WHERE id=?", (row["document_id"],)).fetchone()
        for field in ("owner_employee_id", "access_scope", "category"):
            if metadata[field] != doc[field]:
                raise ValueError(f"Document ownership/scope mismatch: {path.name}")
        if len(body.split()) < 120 or '"expected_facts"' in body or "{{" in body:
            raise ValueError(f"Unfinished or answer-contaminated document: {path.name}")
        if body in bodies:
            raise ValueError("Duplicate document body")
        bodies.add(body)
        category = metadata["category"]
        facts = metadata["facts"]
        if category == "product_guides":
            recomputed = product_facts(db, facts["id"])
        elif category == "customer_terms":
            recomputed = customer_facts(db, facts["id"])
            del recomputed["outstanding_pence"]
        elif category == "department_instructions":
            recomputed = department_facts(db, facts["id"])
        elif category == "incident_notes":
            recomputed = incident_facts(db, facts["id"])
            recomputed["events"] = [
                dict(r)
                for r in db.execute(
                    (
                        "SELECT occurred_on,status,note FROM ticket_events WHERE ticket_id=? "
                        "ORDER BY occurred_on,id"
                    ),
                    (facts["id"],),
                )
            ]
        elif category == "planning_commentary":
            recomputed = planning_facts(db, facts["id"])
        elif category == "procedures":
            table = facts["sample_table"]
            if table not in {
                r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }:
                raise ValueError("Unknown procedure table")
            if not db.execute(
                f"SELECT 1 FROM {table} WHERE id=?", (facts["sample_id"],)
            ).fetchone():
                raise ValueError("Procedure cites missing record")
            recomputed = facts
        else:
            recomputed = facts
        if recomputed != facts:
            raise ValueError(f"Document facts differ from company records: {path.name}")
        phrases = []
        if category == "product_guides":
            phrases = [
                facts["name"],
                f"{facts['observed_lines']} selected order lines",
                f"{facts['ordered_units']} units",
                f"{facts['on_hand']} on hand",
                f"{facts['reserved']} reserved",
                f"{facts['available']} available",
            ]
        elif category == "customer_terms":
            phrases = [
                facts["name"],
                f"{facts['payment_terms_days']} calendar days",
                f"{facts['orders']} selected orders",
                facts["country"],
            ]
        elif category == "department_instructions":
            phrases = [f"{facts['headcount']} assigned employees", facts["responsibility"]]
        elif category == "incident_notes":
            phrases = [facts["order_id"], facts["description"], f"**{facts['status']}**"]
        elif category == "planning_commentary":
            phrases = [
                f"**{facts['units']} units**",
                facts["training_cutoff"],
                f"{facts['training_units']} billed units",
                facts["input_sha256"],
            ]
        elif row["document_id"] == "POL-RETURNS-001":
            if facts["window_days"] != {1: 14, 2: 30}[row["version"]]:
                raise ValueError("Return-window policy differs from the scenario contract")
            phrases = [f"**{facts['window_days']} calendar days**"]
        if any(phrase not in body for phrase in phrases):
            raise ValueError(f"Document prose contradicts its verified facts: {path.name}")
        if metadata["access_scope"] == "general" and (
            {"outstanding_pence", "on_hand", "reserved", "supplier_id"} & set(facts)
        ):
            raise ValueError("Restricted operational or finance data in general document")
        # FKs enforce link targets; compare those links with the searchable metadata.
        links = {
            key: value
            for link in db.execute(
                "SELECT * FROM document_links WHERE document_id=?", (row["document_id"],)
            )
            for key, value in dict(link).items()
            if key not in {"id", "document_id"} and value is not None
        }
        if links != metadata["record_links"]:
            raise ValueError("Document links differ from metadata")
        if row["status"] == "current":
            categories[category] += 1
    if profile == "full" and not 120 <= sum(categories.values()) <= 200:
        raise ValueError("Full corpus must have 120–200 distinct current documents")
    expected_categories = {
        "product_guides",
        "customer_terms",
        "incident_notes",
        "planning_commentary",
        "procedures",
        "department_instructions",
        "policies",
        "financial_reports",
        "research_notes",
    }
    if set(categories) != expected_categories:
        raise ValueError("Document categories differ from the authored corpus")
    return {
        "documents": sum(categories.values()),
        "versions": len(versions),
        "categories": dict(categories),
    }


def validate_source_baskets(db, project, profile):
    """Compare every reconstructed source line with the independent G03 staging data."""
    prepared = project / "data/company/prepared"
    with gzip.open(prepared / "invoice_groups.csv.gz", "rt", encoding="utf-8") as stream:
        eligible = [
            row["invoice_no"] for row in csv.DictReader(stream) if row["eligible_sale"] == "1"
        ]
    chosen = set(eligible if profile == "full" else eligible[:40])
    actual_orders = {
        row[0]
        for row in db.execute(
            "SELECT source_invoice_no FROM orders WHERE source_invoice_no IS NOT NULL"
        )
    }
    if actual_orders != chosen:
        raise ValueError("Selected source invoices differ from the declared profile")
    actual = {
        row[0]: tuple(row[1:])
        for row in db.execute(
            "SELECT oi.source_row_id,o.source_invoice_no,p.source_stock_code,"
            "c.source_customer_id,oi.quantity,oi.raw_unit_price_gbp,i.posted_on "
            "FROM order_items oi JOIN orders o ON o.id=oi.order_id "
            "JOIN invoices i ON i.order_id=o.id JOIN products p ON p.id=oi.product_id "
            "JOIN customers c ON c.id=o.customer_id WHERE oi.source_row_id IS NOT NULL"
        )
    }
    count = 0
    with gzip.open(prepared / "transactions.csv.gz", "rt", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["invoice_no"] not in chosen:
                continue
            expected = (
                row["invoice_no"],
                row["stock_code"],
                row["customer_id"],
                int(row["quantity"]),
                row["unit_price_gbp"],
                row["invoice_date_local"][:10],
            )
            if actual.pop(row["source_row_id"], None) != expected:
                raise ValueError(f"Source basket line changed or missing: {row['source_row_id']}")
            count += 1
    if actual:
        raise ValueError("Company contains unexpected source lines")
    return {"complete_source_invoices": len(chosen), "unchanged_source_lines": count}


def validate_company(db, project, documents, profile):
    checks = []

    def require(condition, name):
        if not condition:
            raise ValueError(f"Company validation failed: {name}")
        checks.append(name)

    require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity")
    require(not db.execute("PRAGMA foreign_key_check").fetchall(), "no orphaned relationships")
    tables = [
        r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]
    require(len(tables) == 35, "35 purposeful tables")
    counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    require(all(counts.values()), "all tables populated")
    if profile == "full":
        for table, minimum in [
            ("employees", 200),
            ("customers", 2000),
            ("products", 2000),
            ("orders", 10000),
            ("order_items", 100000),
        ]:
            require(counts[table] >= minimum, f"full scale {table}")
        require(counts["employees"] == 200, "exactly 200 employees")
        contract = json.loads((project / "data/company/company.json").read_text("utf-8"))
        for department in contract["departments"]:
            actual = db.execute(
                (
                    "SELECT COUNT(*) FROM employee_assignments WHERE department_id=? AND "
                    "valid_until IS NULL"
                ),
                (department["id"],),
            ).fetchone()[0]
            require(actual == department["headcount"], f"department allocation {department['id']}")
    for name, query in ZERO_QUERIES.items():
        require(db.execute(query).fetchone()[0] == 0, name)
    wrong = []
    for row in db.execute("SELECT id,quantity,raw_unit_price_gbp,line_pence FROM order_items"):
        expected = int(
            (Decimal(row[2]) * row[1] * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        )
        if expected != row[3]:
            wrong.append(row[0])
    require(not wrong, "all monetary lines use exact half-up rounding")
    for row in db.execute(
        (
            "SELECT f.*,r.target_start,r.training_cutoff,r.lookback_months FROM forecasts f JOIN "
            "forecast_runs r ON r.id=f.run_id"
        )
    ):
        calculated = forecast_input(
            db, row["product_id"], row["target_start"], row["lookback_months"]
        )
        stored = (
            row["units"],
            row["training_units"],
            row["training_last_date"],
            row["input_sha256"],
        )
        require(calculated == stored, f"forecast input/cutoff {row['id']}")
        require(
            row["training_last_date"] is None
            or row["training_last_date"] <= row["training_cutoff"],
            f"no later observations {row['id']}",
        )
    source_report = validate_source_baskets(db, project, profile)
    checks.append("every selected source basket and line matches G03")
    documents_report = validate_documents(db, documents, profile)
    checks.append("all document IDs, files, versions, links, scopes and factual metadata")
    answer_map = json.loads((project / "evals/source_answer_map.json").read_text("utf-8"))
    require(len(answer_map["scenarios"]) == 12, "twelve source-and-answer mappings")
    for case in answer_map["scenarios"]:
        for table, identifiers in case["records"].items():
            require(table in tables, f"known scenario table {table}")
            for identifier in identifiers:
                require(
                    db.execute(f"SELECT 1 FROM {table} WHERE id=?", (identifier,)).fetchone()
                    is not None,
                    f"scenario record {identifier}",
                )
        for identifier in case["documents"]:
            require(
                db.execute("SELECT 1 FROM document_versions WHERE id=?", (identifier,)).fetchone()
                is not None,
                f"scenario document {identifier}",
            )
        for table, identifiers in case.get("absent_records", {}).items():
            require(table in tables, f"known absent-record table {table}")
            for identifier in identifiers:
                require(
                    db.execute(f"SELECT 1 FROM {table} WHERE id=?", (identifier,)).fetchone()
                    is None,
                    f"intentionally absent record {identifier}",
                )
    evidence = scenario_evidence(db, project)
    contracts = json.loads((project / "evals/g02_scenarios.json").read_text("utf-8"))["scenarios"]
    for case in contracts:
        for name, value in evidence[case["id"]].items():
            if name in case["expected_facts"]:
                require(value == case["expected_facts"][name], f"scenario {case['id']} {name}")
    require(evidence["S04"]["status_before"] == "open", "complaint starts open")
    require(
        evidence["S06"]["forecast_units"] == 1000 and evidence["S06"]["actual_units"] == 850,
        "forecast scenario history and actuals",
    )
    require(
        not evidence["S09"]["finance_permission_granted"], "sales design role lacks finance access"
    )
    require(
        evidence["S11"]["versions"] == [[1, "2011-01-01", "2011-10-31"], [2, "2011-11-01", None]],
        "historical return policy intervals",
    )
    return {
        "status": "passed",
        "profile": profile,
        "table_counts": counts,
        "checks": checks,
        "documents": documents_report,
        "scenario_evidence": evidence,
        "source_baskets": source_report,
    }


def logical_manifest(db):
    tables = {}
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        digest = hashlib.sha256()
        count = 0
        columns = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
        for row in db.execute(f"SELECT * FROM {table} ORDER BY id"):
            digest.update(
                (json.dumps(list(row), ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            )
            count += 1
        tables[table] = {"rows": count, "columns": columns, "sha256": digest.hexdigest()}
    digest = hashlib.sha256(
        json.dumps(tables, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {"content_sha256": digest, "tables": tables}
