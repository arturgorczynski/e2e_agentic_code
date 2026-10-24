"""Focused portal journeys against a small, isolated Acme SQLite fixture."""

import ast
import hashlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from acme.app_store import RunContext, new_thread
from acme.company_tools import decide, document_body, execute
from acme.customer_tools import invoice as customer_invoice
from acme.customer_tools import invoices as customer_invoices
from acme.customer_tools import order as customer_order
from acme.customer_tools import orders as customer_orders
from acme.customer_tools import profile as customer_profile
from acme.dataset import connect
from acme.expense_ledger import ensure_expense_schema
from acme.portal import create_portal
from acme.reset_company import _preserved_rows
from acme.scenarios import (
    audit_contemporary_history,
    seed_contemporary_cases,
    seed_contemporary_history,
)

PROJECT = Path(__file__).resolve().parents[1]


class PortalImportBoundary(unittest.TestCase):
    def test_importing_the_website_does_not_import_the_agent_graph(self):
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import acme.portal; "
                "assert 'acme.agent' not in sys.modules; "
                "assert 'acme.runtime' not in sys.modules",
            ],
            cwd=PROJECT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)


class PortalJourneys(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="portal-test-", dir=PROJECT)
        self.state = Path(self.temporary.name)
        company = connect(self.state / "company.sqlite")
        try:
            company.executescript((PROJECT / "acme/schema.sql").read_text("utf-8"))
            company.executescript(
                """
                INSERT INTO departments VALUES('DEP-FINANCE','Finance','Accounts');
                INSERT INTO locations VALUES('LOC-1','Office','Office');
                INSERT INTO employees VALUES('EMP-1','Test Finance','Analyst','2010-01-01',
                  'finance@example.test','fixture');
                INSERT INTO employee_assignments VALUES('EA-1','EMP-1','DEP-FINANCE',
                  'LOC-1','2010-01-01',NULL);
                INSERT INTO addresses VALUES('ADDR-1','12 Old Road','United Kingdom','fixture');
                INSERT INTO addresses VALUES('ADDR-2','88 Other Road','United Kingdom','fixture');
                INSERT INTO customers VALUES('CUST-1',NULL,'First Customer','ADDR-1',
                  'EMP-1',30,0,'Retail','fixture');
                INSERT INTO customers VALUES('CUST-2',NULL,'Other Customer','ADDR-2',
                  'EMP-1',30,0,'Retail','fixture');
                INSERT INTO customer_contacts VALUES('CONTACT-1','CUST-1','Test Contact',
                  'contact@example.test','Purchasing');
                INSERT INTO categories VALUES('CAT-1','Home','Fixture','Fixture');
                INSERT INTO suppliers VALUES('SUP-1','Fixture Supplier','ADDR-2',7,'fixture');
                INSERT INTO products VALUES('SKU-1',NULL,'Desk Lamp','CAT-1','SUP-1','fixture');
                INSERT INTO price_history VALUES('PRICE-1','SKU-1','2011-12-01','14.00',
                  NULL,'fixture');
                INSERT INTO orders VALUES('ORDER-1',NULL,'CUST-1','2011-12-01',
                  'confirmed','GBP','fixture');
                INSERT INTO orders VALUES('ORDER-2',NULL,'CUST-2','2011-12-02',
                  'confirmed','GBP','fixture');
                INSERT INTO order_items VALUES('ITEM-1','ORDER-1','SKU-1',2,'14.00',2800,NULL);
                INSERT INTO invoices VALUES('INV-1','ORDER-1','2011-12-02',
                  '2012-01-01',2800,'GBP','fixture');
                """
            )
            company.commit()
        finally:
            company.close()
        self.client = TestClient(create_portal(PROJECT, self.state, PROJECT / "data"))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temporary.cleanup()

    def choose(self, kind, subject_id=""):
        response = self.client.post(
            "/api/personas/select", json={"kind": kind, "subject_id": subject_id}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_insights_separate_billing_cash_and_scoped_order_history(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO payments VALUES('PAY-1','CUST-1','2011-12-10',1000,'GBP',
                  'modeled fixture remittance');
                INSERT INTO payment_allocations VALUES('ALLOC-1','PAY-1','INV-1',
                  '2011-12-10',1000);
                INSERT INTO credit_notes VALUES('CREDIT-1','INV-1','2011-12-12',300,
                  'Adjustment','fixture');
                INSERT INTO order_status_history VALUES('STATUS-1','ORDER-1',
                  '2011-12-03','partial','Partially shipped');
                INSERT INTO departments VALUES('DEP-ANALYTICS','Analytics','Reports');
                INSERT INTO employees VALUES('EMP-ANALYST','Test Analyst','Analyst',
                  '2010-01-01','analyst@example.test','fixture');
                INSERT INTO employee_assignments VALUES('EA-ANALYST','EMP-ANALYST',
                  'DEP-ANALYTICS','LOC-1','2010-01-01',NULL);
                """
            )
            db.commit()
        finally:
            db.close()
        period = {"start": "2011-12-01", "end": "2011-12-31", "cohort": "historical"}
        self.choose("customer", "CUST-1")
        self.assertEqual(self.client.get("/api/insights/finance", params=period).status_code, 403)
        self.choose("employee", "EMP-1")
        response = self.client.get("/api/insights/finance", params=period)
        self.assertEqual(response.status_code, 200, response.text)
        totals = response.json()["totals"]
        self.assertEqual(totals["gross_billed_pence"], 2800)
        self.assertEqual(totals["credits_issued_pence"], 300)
        self.assertEqual(totals["net_billing_activity_pence"], 2500)
        self.assertEqual(totals["customer_cash_received_pence"], 1000)
        self.assertEqual(totals["current_outstanding_for_invoice_cohort_pence"], 1500)
        self.assertIsNone(totals["recorded_cash_outflow_pence"])
        history = self.client.get("/api/insights/orders", params=period).json()
        self.assertEqual(history["total"], 2)
        self.assertEqual(history["rows"][1]["id"], "ORDER-1")
        self.assertEqual(history["rows"][1]["basket_pence"], 2800)
        filtered = self.client.get(
            "/api/insights/orders", params={**period, "q": "First Customer", "status": "confirmed"}
        ).json()
        self.assertEqual([row["id"] for row in filtered["rows"]], ["ORDER-1"])
        detail = self.client.get("/api/insights/orders/ORDER-1").json()
        self.assertEqual(detail["invoice"]["outstanding_pence"], 1500)
        self.assertIsNone(detail["shipments"])
        self.assertIsNone(detail["lines"][0]["shipped_quantity"])
        self.assertEqual(detail["statuses"][0]["status"], "partial")
        self.choose("employee", "EMP-ANALYST")
        analyst = self.client.get("/api/insights/finance", params=period).json()
        self.assertEqual(analyst["totals"]["gross_billed_pence"], 2800)
        self.assertIsNone(analyst["totals"]["customer_cash_received_pence"])
        self.assertIsNone(analyst["totals"]["current_outstanding_for_invoice_cohort_pence"])
        self.assertIsNone(self.client.get("/api/insights/orders/ORDER-1").json()["invoice"])
        self.choose("super_user")
        self.assertIsNotNone(
            self.client.get("/api/insights/orders/ORDER-1").json()["lines"][0]["shipped_quantity"]
        )
        self.assertEqual(
            self.client.get(
                "/api/insights/orders", params={**period, "status": "invalid"}
            ).status_code,
            400,
        )

    def test_fictional_expense_ledger_is_scoped_and_not_called_profit(self):
        ensure_expense_schema(self.state / "company.sqlite")
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO company_expenses VALUES('EXP-MKT','2026-01-12',
                  'marketing','Sample agency',5000,'GBP',NULL,NULL,
                  'Authored sample campaign','fictional_contemporary_expense');
                INSERT INTO company_expenses VALUES('EXP-SUP','2026-01-19',
                  'supplier_payment','Fixture Supplier',7000,'GBP','SUP-1',NULL,
                  'Authored sample supplier payment','fictional_contemporary_expense');
                """
            )
            db.commit()
        finally:
            db.close()
        period = {"start": "2026-01-01", "end": "2026-10-21", "cohort": "contemporary"}
        self.choose("employee", "EMP-1")
        finance = self.client.get("/api/insights/finance", params=period).json()
        totals = finance["totals"]
        self.assertEqual(totals["expense_count"], 2)
        self.assertEqual(totals["recorded_cash_outflow_pence"], 12000)
        self.assertEqual(totals["recorded_cash_difference_pence"], -12000)
        self.assertEqual(
            [(row["category"], row["expense_count"], row["amount_pence"])
             for row in finance["expense_categories"]],
            [("supplier_payment", 1, 7000), ("marketing", 1, 5000)],
        )
        listing = self.client.get("/api/insights/expenses", params=period).json()
        self.assertEqual(listing["total"], 2)
        self.assertEqual(listing["filtered_amount_pence"], 12000)
        self.assertEqual(listing["rows"][0]["id"], "EXP-SUP")
        marketing = self.client.get(
            "/api/insights/expenses", params={**period, "category": "marketing"}
        ).json()
        self.assertEqual((marketing["total"], marketing["filtered_amount_pence"]), (1, 5000))
        supplier = self.client.get(
            "/api/insights/expenses", params={**period, "q": "SUP-1"}
        ).json()
        self.assertEqual((supplier["total"], supplier["filtered_amount_pence"]), (1, 7000))
        self.assertEqual(supplier["rows"][0]["id"], "EXP-SUP")
        no_match = self.client.get(
            "/api/insights/expenses", params={**period, "category": "marketing", "q": "supplier"}
        ).json()
        self.assertEqual((no_match["total"], no_match["filtered_amount_pence"]), (0, 0))
        self.assertEqual(
            self.client.get("/api/insights/expenses", params={**period, "q": "EXP-%"}).json()[
                "total"
            ], 0,
        )
        long_search = self.client.get(
            "/api/insights/expenses", params={**period, "q": "x" * 101}
        )
        self.assertEqual(long_search.status_code, 400)
        self.assertIn("not profit", self.client.get(
            "/api/insights/finance", params=period
        ).json()["definitions"]["outflows"])
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Cash evidence", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "cash")
        tool = execute(context, "cash_activity", {
            "start_date": period["start"], "end_date": period["end"],
            "cohort": "contemporary",
        })
        self.assertEqual(tool["status"], "ok")
        self.assertEqual(tool["facts"]["recorded_cash_outflow_pence"], 12000)
        self.assertEqual(tool["facts"]["recorded_cash_difference_pence"], -12000)
        self.assertEqual(tool["facts"]["gross_billed_pence"], totals["gross_billed_pence"])
        self.assertEqual(len(tool["sources"]), 6)
        self.assertEqual(
            [(row["id"], row["fields"]["expense_count"], row["fields"]["amount_pence"])
             for row in tool["records"]],
            [("supplier_payment", 1, 7000), ("marketing", 1, 5000)],
        )
        expense = execute(context, "lookup_record", {
            "entity": "company_expenses", "record_id": "EXP-SUP",
        })
        self.assertEqual(expense["records"][0]["fields"]["purchase_order_id"], None)
        self.assertEqual(expense["records"][0]["fields"]["amount_gbp"], "70.00")
        filtered = execute(context, "list_records", {
            "entity": "company_expenses", "status": "marketing",
        })
        self.assertEqual(filtered["page"]["total"], 1)
        historical = execute(context, "cash_activity", {
            "start_date": "2011-12-01", "end_date": "2011-12-31",
            "cohort": "historical",
        })
        self.assertIsNone(historical["facts"]["recorded_cash_outflow_pence"])
        self.assertEqual(historical["records"], [])
        self.choose("customer", "CUST-1")
        self.assertEqual(self.client.get("/api/insights/expenses", params=period).status_code, 403)
        customer_token = self.client.cookies.get("acme_portal")
        customer_thread = new_thread(
            PROJECT, self.state, customer_token, "Cash denied", mode="company"
        )
        customer_context = RunContext(
            PROJECT, self.state, PROJECT / "data", customer_token, customer_thread, "cash-denied"
        )
        denied = execute(customer_context, "cash_activity", {
            "start_date": period["start"], "end_date": period["end"],
            "cohort": "contemporary",
        })
        self.assertEqual(denied["status"], "error")

    def test_expense_editor_defaults_supplier_link_and_audit(self):
        ensure_expense_schema(self.state / "company.sqlite")
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO suppliers VALUES('SUP-2','Other Supplier','ADDR-2',7,'fixture');
                INSERT INTO warehouses VALUES('WH-EXP','LOC-1','Expense warehouse');
                INSERT INTO purchase_orders VALUES('PO-EXP','SUP-1','WH-EXP',
                  '2026-01-03','2026-02-01','open','fixture');
                """
            )
            db.commit()
        finally:
            db.close()
        self.choose("super_user")
        schema = self.client.get("/api/database/schema/company_expenses").json()
        self.assertEqual(len(schema["suggestions"]["category"]), 5)
        values = {
            "paid_on": "2026-01-10", "category": "supplier_payment",
            "payee": "Fixture Supplier", "amount_pence": "1300",
            "purchase_order_id": "PO-EXP", "description": "Fictional supplier deposit",
        }
        created = self.client.post(
            "/api/database/rows/company_expenses", json={"values": values}
        )
        self.assertEqual(created.status_code, 200, created.text)
        row = created.json()["record"]
        self.assertEqual(row["supplier_id"], "SUP-1")
        self.assertEqual(row["currency"], "GBP")
        self.assertEqual(row["provenance"], "fictional_contemporary_expense")
        self.assertEqual(audit_contemporary_history(self.state)["counts"]["company_expenses"], 1)
        wrong = self.client.post(
            "/api/database/rows/company_expenses",
            json={"values": {**values, "supplier_id": "SUP-2"}},
        )
        self.assertEqual(wrong.status_code, 400)
        self.assertIn("supplier must match purchase order", wrong.json()["detail"])
        changed = self.client.patch(
            f"/api/database/rows/company_expenses/{row['id']}",
            json={"values": {"supplier_id": "SUP-2"}, "expected": row},
        )
        self.assertEqual(changed.status_code, 400)
        db = connect(self.state / "company.sqlite")
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE purchase_orders SET supplier_id='SUP-2' WHERE id='PO-EXP'")
            db.rollback()
            db.execute("DROP TRIGGER expense_supplier_matches_order_update")
            db.execute(
                "UPDATE company_expenses SET supplier_id='SUP-2',paid_on='2026-01-01' WHERE id=?",
                (row["id"],),
            )
            db.commit()
        finally:
            db.close()
        violations = audit_contemporary_history(self.state)["violations"]
        self.assertEqual(violations["expense_supplier_mismatch"], 1)
        self.assertEqual(violations["expense_before_purchase_order"], 1)

    def test_supplier_journey_reconciles_split_receipts_and_respects_operations_scope(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO departments VALUES('DEP-PURCHASE','Purchasing','Purchasing');
                INSERT INTO employees VALUES('EMP-BUY','Test Buyer','Buyer','2010-01-01',
                  'buyer@example.test','fixture');
                INSERT INTO employee_assignments VALUES('EA-BUY','EMP-BUY','DEP-PURCHASE',
                  'LOC-1','2010-01-01',NULL);
                INSERT INTO warehouses VALUES('WH-1','LOC-1','Test warehouse');
                INSERT INTO inventory VALUES('INV-1','WH-1','SKU-1',15,2,'2026-10-21');
                INSERT INTO purchase_orders VALUES('PO-1','SUP-1','WH-1',
                  '2026-08-26','2026-09-05','received','fictional_contemporary_seed');
                INSERT INTO purchase_order_items VALUES('POI-1','PO-1','SKU-1',15);
                INSERT INTO goods_receipts VALUES('GR-1','POI-1','2026-09-10',5);
                INSERT INTO goods_receipts VALUES('GR-2','POI-1','2026-09-20',4);
                INSERT INTO goods_receipts VALUES('GR-3','POI-1','2026-10-21',6);
                INSERT INTO stock_movements VALUES('MOVE-1','WH-1','SKU-1',
                  '2026-09-10','receipt',5,NULL,'GR-1');
                INSERT INTO stock_movements VALUES('MOVE-2','WH-1','SKU-1',
                  '2026-09-20','receipt',4,NULL,'GR-2');
                INSERT INTO stock_movements VALUES('MOVE-3','WH-1','SKU-1',
                  '2026-10-21','receipt',6,NULL,'GR-3');
                """
            )
            db.commit()
        finally:
            db.close()
        url = "/api/database/purchase-journey/PO-1"
        self.choose("customer", "CUST-1")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.choose("employee", "EMP-1")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.choose("employee", "EMP-BUY")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.text)
        journey = response.json()
        self.assertEqual(journey["totals"]["ordered_units"], 15)
        self.assertEqual(journey["totals"]["received_units"], 15)
        self.assertEqual(journey["totals"]["outstanding_units"], 0)
        self.assertEqual(journey["totals"]["receipt_count"], 3)
        self.assertEqual([r["quantity"] for r in journey["receipts"]], [5, 4, 6])
        self.assertEqual(journey["lines"][0]["on_hand"], 15)
        self.assertEqual(journey["receipts"][2]["movement_id"], "MOVE-3")
        self.assertEqual(self.client.get("/api/database/purchase-journey/MISSING").status_code, 404)

    def test_document_effective_date_matches_agent_retrieval_window(self):
        self.choose("super_user")
        effective_on = "2011-12-08"
        response = self.client.get(f"/api/documents?effective_on={effective_on}")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["effective_on"], effective_on)
        documents = payload["documents"]
        self.assertTrue(documents)
        self.assertEqual(len({doc["document_id"] for doc in documents}), len(documents))
        for doc in documents:
            self.assertLessEqual(doc["effective_from"], effective_on)
            if doc["effective_until"] is not None:
                self.assertGreaterEqual(doc["effective_until"], effective_on)
        self.assertEqual(self.client.get("/api/documents?effective_on=bad").status_code, 422)

    def test_agent_document_search_requires_complete_record_mention_and_scope(self):
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Exact document mention")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "doc-mention")
        arguments = {
            "query": "packaging",
            "mentions_record_id": "DEMO-CUST-004",
            "effective_on": "2011-12-09",
        }
        matching = execute(context, "search_documents", arguments)
        self.assertIn("INC-001", {row["id"] for row in matching["records"]})
        self.assertGreater(matching["page"]["total"], 0)
        partial = execute(
            context,
            "search_documents",
            {**arguments, "mentions_record_id": "DEMO-CUST-00"},
        )
        self.assertEqual(partial["page"]["total"], 0)
        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Customer document mention")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "doc-deny")
        denied = execute(context, "search_documents", arguments)
        self.assertEqual(denied["page"]["total"], 0)
        self.assertEqual(denied["records"], [])

    def test_agent_can_list_permitted_document_versions_without_leaking_scope(self):
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Document version history")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "versions")
        history = execute(
            context, "list_document_versions", {"document_id": "POL-RETURNS-001"}
        )
        self.assertEqual(history["status"], "ok")
        self.assertEqual(history["page"]["total"], 2)
        self.assertEqual(
            [(row["fields"]["version"], row["fields"]["status"]) for row in history["records"]],
            [(1, "superseded"), (2, "current")],
        )
        self.assertTrue(all("content" not in row["fields"] for row in history["records"]))
        page = execute(
            context,
            "list_document_versions",
            {"document_id": "POL-RETURNS-001", "offset": 1, "limit": 1},
        )
        self.assertEqual(page["records"][0]["fields"]["version"], 2)
        self.assertFalse(page["page"]["has_more"])

        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Customer version history")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "versions")
        permitted = execute(
            context, "list_document_versions", {"document_id": "POL-RETURNS-001"}
        )
        self.assertEqual(permitted["page"]["total"], 2)
        restricted = execute(
            context, "list_document_versions", {"document_id": "INC-001"}
        )
        self.assertEqual(restricted["status"], "error")
        self.assertEqual(restricted["error"]["code"], "access_denied")

    def test_dynamic_persona_filters_and_superuser_order_focus(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.execute("INSERT INTO departments VALUES('DEP-SUPPORT','Support','Customer care')")
            db.execute(
                "INSERT INTO employees VALUES('EMP-2','Test Support','Advisor',"
                "'2011-01-01','support@example.test','fixture')"
            )
            db.execute(
                "INSERT INTO employee_assignments VALUES('EA-2','EMP-2',"
                "'DEP-SUPPORT','LOC-1','2011-01-01',NULL)"
            )
            db.execute("UPDATE customers SET account_manager_id='EMP-2' WHERE id='CUST-2'")
            db.commit()
        finally:
            db.close()
        options = self.client.get("/api/personas/options").json()
        self.assertIn("DEP-SUPPORT", {row["id"] for row in options["departments"]})
        found = self.client.get(
            "/api/personas/search",
            params={
                "kind": "employee",
                "department": "DEP-SUPPORT",
                "min_customers": 1,
            },
        ).json()
        self.assertEqual([row["id"] for row in found], ["EMP-2"])
        self.assertEqual(found[0]["managed_customers"], 1)
        self.assertEqual(
            self.client.get(
                "/api/personas/search",
                params={
                    "kind": "employee",
                    "location": "LOC-1",
                    "job_title": "Analyst",
                },
            ).json()[0]["id"],
            "EMP-1",
        )
        focuses = self.client.get(
            "/api/personas/search",
            params={
                "kind": "super_user",
                "q": "support",
                "active_only": True,
            },
        ).json()
        self.assertEqual([row["id"] for row in focuses], ["DEP-SUPPORT"])
        selected = self.choose("super_user", "DEP-SUPPORT")
        self.assertEqual(selected["focus_department_id"], "DEP-SUPPORT")
        self.assertEqual(
            [row["id"] for row in self.client.get("/api/employee").json()["recent_orders"]],
            ["ORDER-2"],
        )
        self.choose("super_user", "all")
        self.assertEqual(len(self.client.get("/api/employee").json()["recent_orders"]), 2)

    def test_document_text_tags_and_metadata_filters(self):
        self.choose("super_user")
        options = self.client.get("/api/documents/categories").json()
        self.assertIn("shipment", options["tags"])
        self.assertIn("operations", options["scopes"])
        response = self.client.get(
            "/api/documents",
            params={
                "keyword": "dispatch",
                "tag": "shipment",
                "scope": "operations",
                "category": "policies",
                "owner": "EMP-002",
                "linked_type": "department_id",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        docs = response.json()["documents"]
        self.assertTrue(docs)
        self.assertTrue(all("shipment" in row["tags"] for row in docs))
        detail = self.client.get(
            f"/api/documents/{docs[0]['document_id']}/{docs[0]['version']}"
        ).json()
        self.assertEqual(detail["metadata"]["tags"], docs[0]["tags"])
        account = self.client.get("/api/documents", params={"q": "TERMS-001"}).json()
        self.assertEqual(len(account["documents"]), 1)
        self.assertIn("customer", account["documents"][0]["tags"])
        self.assertNotIn("order", account["documents"][0]["tags"])
        product = self.client.get("/api/documents", params={"q": "PROD-001"}).json()
        self.assertEqual(len(product["documents"]), 1)
        self.assertIn("product", product["documents"][0]["tags"])
        self.assertNotIn("order", product["documents"][0]["tags"])
        order = self.client.get("/api/documents", params={"q": "PROC-001"}).json()
        self.assertIn("order", order["documents"][0]["tags"])

    def test_document_metadata_filters_precede_body_reads_and_scope(self):
        self.choose("super_user")
        with patch("acme.portal.document_body", wraps=document_body) as read_body:
            metadata = self.client.get("/api/documents", params={"q": "TERMS-001"})
            self.assertEqual(metadata.status_code, 200)
            self.assertEqual(read_body.call_count, 0)
            candidates = metadata.json()["total"]
            self.assertGreater(candidates, 0)
            searched = self.client.get(
                "/api/documents", params={"q": "TERMS-001", "keyword": "payment"}
            )
            self.assertEqual(searched.status_code, 200)
            self.assertEqual(read_body.call_count, candidates)
        self.choose("customer", "CUST-1")
        with patch("acme.portal.document_body", wraps=document_body) as read_body:
            hidden = self.client.get(
                "/api/documents", params={"q": "PROD-001", "keyword": "stock"}
            )
            self.assertEqual(hidden.status_code, 200)
            self.assertEqual(hidden.json()["total"], 0)
            self.assertEqual(read_body.call_count, 0)
        self.assertEqual(
            self.client.get("/api/documents", params={"q": "x" * 201}).status_code, 400
        )

    def test_editor_previews_incoming_links_and_field_suggestions(self):
        self.choose("super_user")
        schema = self.client.get("/api/database/schema/orders")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("confirmed", schema.json()["suggestions"]["status"])
        linked = self.client.get("/api/database/rows/addresses/ADDR-1/dependencies")
        self.assertEqual(linked.status_code, 200)
        self.assertFalse(linked.json()["can_delete"])
        self.assertIn(
            {"table": "customers", "column": "address_id", "count": 1, "sample_ids": ["CUST-1"]},
            linked.json()["dependencies"],
        )
        db = connect(self.state / "company.sqlite")
        try:
            db.execute(
                "INSERT INTO addresses VALUES('ADDR-EMPTY','Unused Road',"
                "'United Kingdom','fixture')"
            )
            db.commit()
        finally:
            db.close()
        unlinked = self.client.get("/api/database/rows/addresses/ADDR-EMPTY/dependencies")
        self.assertTrue(unlinked.json()["can_delete"])
        self.choose("employee", "EMP-1")
        self.assertEqual(
            self.client.get("/api/database/rows/addresses/ADDR-1/dependencies").status_code,
            403,
        )

    def test_public_customer_and_cross_customer_boundary(self):
        public = self.client.get("/api/products").json()
        self.assertEqual(public["rows"][0]["id"], "SKU-1")
        detail = self.client.get("/api/products/SKU-1")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["price_observed_at"], "2011-12-01")
        self.assertEqual(detail.json()["last_price_gbp"], "14.00")
        self.assertNotIn("supplier_id", detail.json())
        self.assertEqual(self.client.get("/api/products/UNKNOWN").status_code, 404)
        self.choose("customer", "CUST-1")
        home = self.client.get("/api/customer")
        self.assertEqual(home.status_code, 200)
        self.assertEqual(home.json()["orders"][0]["total_pence"], 2800)
        self.assertEqual(home.json()["activity"]["order_count"], 1)
        self.assertEqual(home.json()["activity"]["last_order_at"], "2011-12-01")
        self.assertEqual(self.client.get("/api/customer/orders/ORDER-1").status_code, 200)
        self.assertEqual(self.client.get("/api/customer/orders/ORDER-2").status_code, 400)
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Customer boundary", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "boundary")
        foreign_order = customer_order(context, "ORDER-2")
        self.assertEqual(foreign_order["status"], "empty")
        self.assertEqual(foreign_order["records"], [])
        self.assertEqual(self.client.get("/api/database/objects").status_code, 403)
        docs = self.client.get("/api/documents").json()["documents"]
        self.assertTrue(docs)
        self.assertTrue(all(item["category"] != "department_instructions" for item in docs))
        self.assertTrue(
            all(
                (item["category"] == "policies" and item["access_scope"] == "general")
                or item["category"] == "customer_terms"
                for item in docs
            )
        )
        self.assertTrue(
            all(
                item["record_links"].get("customer_id") == "CUST-1"
                for item in docs
                if item["category"] == "customer_terms"
            )
        )

    def test_customer_order_pages_keep_whole_order_totals(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executemany(
                "INSERT INTO order_items VALUES(?,?,?,?,?,?,?)",
                [
                    (f"ITEM-PAGE-{number:03d}", "ORDER-1", "SKU-1", 1, "1.00", 100, None)
                    for number in range(105)
                ],
            )
            db.commit()
        finally:
            db.close()
        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Long customer order", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "long-order")

        first = customer_order(context, "ORDER-1")
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["facts"]["total_lines"], 106)
        self.assertEqual(first["facts"]["total_pence"], 13300)
        self.assertEqual(first["facts"]["returned_lines"], 100)
        self.assertEqual(first["facts"]["next_offset"], 100)
        self.assertTrue(first["facts"]["has_more"])
        self.assertEqual(first["records"][0]["shipped_quantity"], 0)

        second = customer_order(context, "ORDER-1", first["facts"]["next_offset"])
        self.assertEqual(second["facts"]["total_lines"], 106)
        self.assertEqual(second["facts"]["returned_lines"], 6)
        self.assertIsNone(second["facts"]["next_offset"])
        self.assertFalse(second["facts"]["has_more"])
        self.assertEqual(
            len({row["line_id"] for row in first["records"] + second["records"]}),
            106,
        )
        self.assertEqual(customer_order(context, "ORDER-2")["status"], "empty")
        with self.assertRaises(ValueError):
            customer_order(context, "ORDER-1", limit=101)

    def test_employee_scopes_tools_and_superuser_database(self):
        employee = self.choose("employee", "EMP-1")
        self.assertIn("finance.read", employee["permissions"])
        self.assertNotIn("operations.read", employee["permissions"])
        self.assertEqual(self.client.get("/api/employee").status_code, 200)
        names = {item["name"] for item in self.client.get("/api/database/objects").json()}
        self.assertIn("invoices", names)
        self.assertNotIn("inventory", names)
        self.assertEqual(self.client.get("/api/database/inventory").status_code, 403)
        self.assertEqual(
            self.client.post("/api/database/query", json={"sql": "SELECT 1"}).status_code, 403
        )
        self.choose("super_user")
        self.assertEqual(len(self.client.get("/api/database/objects").json()), 38)
        filtered = self.client.get("/api/database/orders?column=customer_id&value=CUST-1").json()
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["rows"][0]["id"], "ORDER-1")
        tools = self.client.get("/api/tools").json()["tools"]
        self.assertEqual(len(tools), 15)
        self.assertIn("list_document_versions", {tool["name"] for tool in tools})
        direct = self.client.post(
            "/api/tools/run_analysis/run",
            json={"arguments": {"operation": "sum", "values": ["2", "3"]}},
        )
        self.assertEqual(direct.status_code, 200, direct.text)
        self.assertEqual(direct.json()["status"], "ok")
        self.assertEqual(
            self.client.post("/api/database/query", json={"sql": "DELETE FROM orders"}).status_code,
            400,
        )
        sql = self.client.post(
            "/api/database/query", json={"sql": "SELECT id FROM orders ORDER BY id"}
        )
        self.assertEqual(len(sql.json()["rows"]), 2)

    def test_order_journey_links_history_and_labels_source_evidence(self):
        self.choose("employee", "EMP-1")
        self.assertEqual(self.client.get("/api/database/order-journey/ORDER-1").status_code, 403)
        company = connect(self.state / "company.sqlite")
        try:
            company.executescript(
                """
                UPDATE orders SET source_invoice_no='SOURCE-1' WHERE id='ORDER-1';
                INSERT INTO warehouses VALUES('WH-1','LOC-1','Main warehouse');
                INSERT INTO shipments VALUES('SHIP-1','ORDER-1','WH-1','2011-12-03',
                  '2011-12-05','Fixture carrier','fixture');
                INSERT INTO shipment_items VALUES('SHIP-L1','SHIP-1','ITEM-1',2);
                INSERT INTO payments VALUES('PAY-1','CUST-1','2011-12-06',1000,'GBP','fixture');
                INSERT INTO payment_allocations VALUES('ALLOC-1','PAY-1','INV-1',
                  '2011-12-06',1000);
                INSERT INTO credit_notes VALUES('CREDIT-1','INV-1','2011-12-07',300,
                  'Packaging adjustment','fixture');
                INSERT INTO tickets VALUES('TICKET-1','ORDER-1','EMP-1','2011-12-08',
                  'resolved','Delivery question','Customer requested an update','fixture');
                INSERT INTO ticket_events VALUES('TE-1','TICKET-1','2011-12-08',
                  'resolved','Confirmed delivery');
                """
            )
            company.commit()
        finally:
            company.close()
        self.choose("super_user")
        response = self.client.get("/api/database/order-journey/ORDER-1")
        self.assertEqual(response.status_code, 200, response.text)
        journey = response.json()
        self.assertEqual(journey["order"]["customer_id"], "CUST-1")
        self.assertEqual(journey["invoice"]["outstanding_pence"], 1500)
        self.assertEqual(journey["items"][0]["shipped_quantity"], 2)
        self.assertEqual(
            {event["kind"] for event in journey["events"]},
            {"order", "invoice", "dispatch", "delivery", "payment", "credit", "ticket"},
        )
        self.assertIn(
            "observed source invoice date",
            next(event for event in journey["events"] if event["kind"] == "invoice")["basis"],
        )
        self.assertEqual(
            [event["date"] for event in journey["events"]],
            sorted(event["date"] for event in journey["events"]),
        )
        self.assertIsNone(self.client.get("/api/database/order-journey/ORDER-2").json()["invoice"])
        self.assertEqual(self.client.get("/api/database/order-journey/MISSING").status_code, 404)

    def test_customer_order_summary_default_covers_earliest_record(self):
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "History range", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "range-test")
        summary = execute(context, "business_summary", {"report": "customer_orders"})
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["facts"]["start_date"], "2011-12-01")
        self.assertEqual(summary["facts"]["end_date"], "2011-12-09")
        self.assertEqual(len(summary["sources"]), 2)
        self.assertEqual({row["fields"]["order_count"] for row in summary["records"]}, {1})

    def test_invoice_lookup_distinguishes_customer_from_order_filter(self):
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Invoice filter proof", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "filter-test")
        customer = execute(
            context, "list_records", {"entity": "invoices", "customer_id": "CUST-1"}
        )
        self.assertEqual([row["id"] for row in customer["records"]], ["INV-1"])
        self.assertEqual(customer["page"]["total"], 1)
        customer_orders = execute(
            context, "list_records", {"entity": "orders", "customer_id": "CUST-1"}
        )
        self.assertEqual([row["id"] for row in customer_orders["records"]], ["ORDER-1"])
        order = execute(
            context, "list_records", {"entity": "invoices", "parent_id": "ORDER-1"}
        )
        self.assertEqual([row["id"] for row in order["records"]], ["INV-1"])
        mistaken = execute(
            context, "list_records", {"entity": "invoices", "parent_id": "CUST-1"}
        )
        self.assertEqual(mistaken["status"], "error")
        self.assertIn("must be an order ID", mistaken["error"]["message"])
        unsupported = execute(
            context, "list_records", {"entity": "products", "customer_id": "CUST-1"}
        )
        self.assertEqual(unsupported["status"], "error")
        summary = execute(
            context,
            "business_summary",
            {
                "report": "receivables",
                "customer_id": "CUST-1",
                "start_date": "2011-12-01",
                "end_date": "2011-12-09",
            },
        )
        self.assertEqual(summary["facts"]["invoice_count"], 1)
        self.assertEqual(summary["facts"]["outstanding_pence"], 2800)
        order_count = execute(
            context,
            "business_summary",
            {
                "report": "customer_orders",
                "customer_id": "CUST-1",
                "start_date": "2011-12-01",
                "end_date": "2011-12-09",
            },
        )
        self.assertEqual(order_count["records"][0]["fields"]["order_count"], 1)

    def test_source_invoice_null_is_not_invoice_absence_evidence(self):
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Order reference meaning", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "ref-test")
        order = execute(context, "lookup_record", {"entity": "orders", "record_id": "ORDER-1"})
        listed = execute(
            context, "list_records", {"entity": "orders", "customer_id": "CUST-1"}
        )
        invoice = execute(
            context, "list_records", {"entity": "invoices", "parent_id": "ORDER-1"}
        )
        self.assertIsNone(order["records"][0]["fields"]["source_invoice_no"])
        self.assertIn("does not prove", order["facts"]["source_invoice_no_note"])
        self.assertEqual(
            listed["facts"]["source_invoice_no_note"],
            order["facts"]["source_invoice_no_note"],
        )
        self.assertEqual([row["id"] for row in invoice["records"]], ["INV-1"])

    def test_order_item_tools_show_unshipped_quantity_after_partial_dispatch(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO warehouses VALUES('WH-1','LOC-1','Main warehouse');
                INSERT INTO shipments VALUES('SHIP-1','ORDER-1','WH-1','2011-12-03',
                  NULL,'Demo carrier','fixture');
                INSERT INTO shipment_items VALUES('SHIP-L1','SHIP-1','ITEM-1',1);
                """
            )
            db.commit()
        finally:
            db.close()
        self.choose("employee", "EMP-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Partial dispatch", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "ship-test")
        for operation, arguments in [
            ("lookup_record", {"entity": "order_items", "record_id": "ITEM-1"}),
            ("list_records", {"entity": "order_items", "parent_id": "ORDER-1"}),
        ]:
            row = execute(context, operation, arguments)["records"][0]
            self.assertEqual(row["fields"]["quantity"], 2)
            self.assertEqual(row["fields"]["shipped_quantity"], 1)
            self.assertEqual(row["fields"]["unshipped_quantity"], 1)

    def test_stock_movement_tool_is_exact_read_only_and_operations_scoped(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO warehouses VALUES('WH-1','LOC-1','Main warehouse');
                INSERT INTO stock_movements VALUES('MOVE-1','WH-1','SKU-1',
                  '2011-12-01','opening',7,NULL,NULL);
                """
            )
            db.commit()
        finally:
            db.close()
        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Stock", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "stock-deny")
        denied = execute(
            context, "lookup_record", {"entity": "stock_movements", "record_id": "MOVE-1"}
        )
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["error"]["code"], "access_denied")

        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Stock", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "stock-read")
        result = execute(
            context, "lookup_record", {"entity": "stock_movements", "record_id": "MOVE-1"}
        )
        self.assertEqual(result["records"][0]["fields"]["quantity"], 7)
        self.assertEqual(result["records"][0]["fields"]["warehouse_id"], "WH-1")
        page = execute(context, "list_records", {"entity": "stock_movements", "parent_id": "SKU-1"})
        self.assertEqual([row["id"] for row in page["records"]], ["MOVE-1"])

    def test_stock_movement_link_filters_find_receipt_and_dispatch_without_scanning(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO warehouses VALUES('WH-1','LOC-1','Main warehouse');
                INSERT INTO purchase_orders VALUES('PO-1','SUP-1','WH-1',
                  '2011-11-25','2011-12-01','received','fixture');
                INSERT INTO purchase_order_items VALUES('POI-1','PO-1','SKU-1',3);
                INSERT INTO goods_receipts VALUES('GR-1','POI-1','2011-12-01',3);
                INSERT INTO shipments VALUES('SHIP-1','ORDER-1','WH-1',
                  '2011-12-03',NULL,'Fixture carrier','fixture');
                INSERT INTO shipment_items VALUES('SI-1','SHIP-1','ITEM-1',1);
                INSERT INTO stock_movements VALUES('MOVE-OPEN','WH-1','SKU-1',
                  '2011-11-01','opening',7,NULL,NULL);
                INSERT INTO stock_movements VALUES('MOVE-RECEIPT','WH-1','SKU-1',
                  '2011-12-01','receipt',3,NULL,'GR-1');
                INSERT INTO stock_movements VALUES('MOVE-DISPATCH','WH-1','SKU-1',
                  '2011-12-03','dispatch',-1,'SI-1',NULL);
                """
            )
            db.commit()
        finally:
            db.close()
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Linked stock", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "stock-links")
        receipt = execute(
            context,
            "list_records",
            {"entity": "stock_movements", "goods_receipt_id": "GR-1"},
        )
        self.assertEqual([row["id"] for row in receipt["records"]], ["MOVE-RECEIPT"])
        self.assertEqual(receipt["records"][0]["fields"]["quantity"], 3)
        dispatch = execute(
            context,
            "list_records",
            {"entity": "stock_movements", "shipment_item_id": "SI-1"},
        )
        self.assertEqual([row["id"] for row in dispatch["records"]], ["MOVE-DISPATCH"])
        self.assertEqual(dispatch["records"][0]["fields"]["quantity"], -1)
        self.assertEqual(
            execute(
                context,
                "list_records",
                {"entity": "stock_movements", "goods_receipt_id": "GR-NOT-FOUND"},
            )["page"]["total"],
            0,
        )
        for arguments in (
            {"entity": "products", "goods_receipt_id": "GR-1"},
            {
                "entity": "stock_movements",
                "goods_receipt_id": "GR-1",
                "shipment_item_id": "SI-1",
            },
        ):
            self.assertEqual(execute(context, "list_records", arguments)["status"], "error")
        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Linked stock", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "stock-deny")
        denied = execute(
            context,
            "list_records",
            {"entity": "stock_movements", "goods_receipt_id": "GR-1"},
        )
        self.assertEqual(denied["error"]["code"], "access_denied")

    def test_purchase_line_totals_cover_receipts_beyond_one_page(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.execute("INSERT INTO warehouses VALUES('WH-1','LOC-1','Main warehouse')")
            db.execute(
                "INSERT INTO purchase_orders VALUES('PO-MULTI','SUP-1','WH-1',"
                "'2011-11-25','2011-12-01','open','fixture')"
            )
            db.execute(
                "INSERT INTO purchase_order_items VALUES('POI-MULTI','PO-MULTI','SKU-1',20)"
            )
            db.execute(
                "INSERT INTO purchase_order_items VALUES('POI-NONE','PO-MULTI','SKU-1',5)"
            )
            db.execute(
                "INSERT INTO purchase_order_items VALUES('POI-OVER','PO-MULTI','SKU-1',2)"
            )
            db.executemany(
                "INSERT INTO goods_receipts VALUES(?,?,?,?)",
                [(f'GR-{number:02d}', 'POI-MULTI', '2011-12-01', 1) for number in range(12)],
            )
            db.execute(
                "INSERT INTO goods_receipts VALUES('GR-OVER','POI-OVER','2011-12-01',3)"
            )
            db.commit()
        finally:
            db.close()
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Many partial receipts")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "po-totals")
        header_result = execute(
            context, "lookup_record", {"entity": "purchase_orders", "record_id": "PO-MULTI"}
        )
        header = header_result["records"][0]["fields"]
        self.assertIn("may predate", header_result["facts"]["purchase_provenance_note"])
        self.assertEqual(
            (header["line_count"], header["ordered_quantity"],
             header["received_quantity"], header["outstanding_quantity"],
             header["receipt_count"], header["provenance"]),
            (3, 27, 15, 12, 13, "fixture"),
        )
        listed_header = execute(
            context, "list_records", {"entity": "purchase_orders", "parent_id": "SUP-1"}
        )["records"][0]["fields"]
        self.assertEqual(listed_header["received_quantity"], 15)
        line = execute(
            context, "lookup_record", {"entity": "purchase_order_items", "record_id": "POI-MULTI"}
        )["records"][0]["fields"]
        self.assertEqual(
            (line["quantity"], line["receipt_count"], line["received_quantity"],
             line["outstanding_quantity"]),
            (20, 12, 12, 8),
        )
        receipts = execute(
            context,
            "list_records",
            {"entity": "goods_receipts", "parent_id": "POI-MULTI"},
        )
        self.assertEqual(receipts["page"]["returned"], 10)
        self.assertEqual(receipts["page"]["total"], 12)
        self.assertTrue(receipts["page"]["has_more"])
        page = execute(
            context,
            "list_records",
            {"entity": "purchase_order_items", "parent_id": "PO-MULTI", "limit": 1},
        )
        self.assertEqual(page["page"]["total"], 3)
        self.assertEqual(page["records"][0]["fields"]["received_quantity"], 12)
        next_page = execute(
            context,
            "list_records",
            {
                "entity": "purchase_order_items",
                "parent_id": "PO-MULTI",
                "after": page["page"]["next_cursor"],
                "limit": 1,
            },
        )
        self.assertEqual(next_page["records"][0]["fields"]["receipt_count"], 0)
        self.assertEqual(next_page["records"][0]["fields"]["outstanding_quantity"], 5)
        over = execute(
            context, "lookup_record", {"entity": "purchase_order_items", "record_id": "POI-OVER"}
        )["records"][0]["fields"]
        self.assertEqual(over["received_quantity"], 3)
        self.assertEqual(over["outstanding_quantity"], -1)
        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "No supplier access")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "po-deny")
        denied = execute(
            context, "lookup_record", {"entity": "purchase_order_items", "record_id": "POI-MULTI"}
        )
        self.assertEqual(denied["error"]["code"], "access_denied")

    def test_sales_target_tool_checks_linked_forecast_and_analytics_scope(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO departments VALUES('DEP-ANALYTICS','Analytics','Planning');
                INSERT INTO employees VALUES('EMP-A','Test Planner','Planner',
                  '2010-01-01','planner@example.test','fixture');
                INSERT INTO employee_assignments VALUES('EA-A','EMP-A','DEP-ANALYTICS',
                  'LOC-1','2010-01-01',NULL);
                INSERT INTO forecast_runs VALUES('RUN-1','2011-12-01','2011-11-30',
                  '2011-12-01','2011-12-31','trailing mean',1,2,'Freeze prior months');
                INSERT INTO forecasts VALUES('FC-1','RUN-1','SKU-1',6,12,
                  '2011-11-28','fixture-fingerprint');
                INSERT INTO sales_targets VALUES('TARGET-1','DEP-ANALYTICS','FC-1',7,
                  'Planner chose seven units');
                """
            )
            db.commit()
        finally:
            db.close()
        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Target", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "target-deny")
        denied = execute(
            context, "lookup_record", {"entity": "sales_targets", "record_id": "TARGET-1"}
        )
        self.assertEqual(denied["error"]["code"], "access_denied")

        self.choose("employee", "EMP-A")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Target", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "target-read")
        target = execute(
            context, "lookup_record", {"entity": "sales_targets", "record_id": "TARGET-1"}
        )
        self.assertEqual(target["records"][0]["fields"]["target_units"], 7)
        self.assertEqual(target["records"][0]["fields"]["forecast_id"], "FC-1")
        page = execute(context, "list_records", {"entity": "sales_targets", "parent_id": "FC-1"})
        self.assertEqual([row["id"] for row in page["records"]], ["TARGET-1"])
        run = execute(context, "lookup_record", {"entity": "forecast_runs", "record_id": "RUN-1"})
        self.assertEqual(run["records"][0]["fields"]["assumption"], "Freeze prior months")

    def test_forecast_error_waits_for_the_complete_target_period(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO invoice_items VALUES('INVITEM-1','INV-1','ITEM-1',2,2800);
                INSERT INTO order_items VALUES('ITEM-2','ORDER-2','SKU-1',3,'14.00',4200,NULL);
                INSERT INTO invoices VALUES('INV-FUT','ORDER-2','2011-12-20',
                  '2012-01-19',4200,'GBP','fixture');
                INSERT INTO invoice_items VALUES('INVITEM-FUT','INV-FUT','ITEM-2',3,4200);
                INSERT INTO forecast_runs VALUES('RUN-DEC','2011-12-01','2011-11-30',
                  '2011-12-01','2011-12-31','trailing mean',1,2,'December projection');
                INSERT INTO forecasts VALUES('FC-DEC','RUN-DEC','SKU-1',6,12,
                  '2011-11-28','dec-fingerprint');
                INSERT INTO forecast_runs VALUES('RUN-NOV','2011-11-01','2011-10-31',
                  '2011-11-01','2011-11-30','trailing mean',1,2,'November projection');
                INSERT INTO forecasts VALUES('FC-NOV','RUN-NOV','SKU-1',5,10,
                  '2011-10-28','nov-fingerprint');
                """
            )
            db.commit()
        finally:
            db.close()
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Forecast", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "forecast")
        partial = execute(
            context, "business_summary", {"report": "forecast", "forecast_id": "FC-DEC"}
        )["facts"]
        self.assertFalse(partial["period_complete"])
        self.assertEqual(partial["actual_units"], 2)
        self.assertEqual(partial["observed_through"], "2011-12-09")
        self.assertEqual(partial["actual_units_basis"], "partial period to date")
        self.assertIsNone(partial["error_units"])
        self.assertIsNone(partial["error_percent"])
        complete = execute(
            context, "business_summary", {"report": "forecast", "forecast_id": "FC-NOV"}
        )["facts"]
        self.assertTrue(complete["period_complete"])
        self.assertEqual(complete["actual_units"], 0)
        self.assertEqual(complete["error_units"], -5)
        self.assertEqual(complete["error_percent"], "-100")

    def test_customer_orders_reports_full_count_when_recent_list_is_shorter(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.execute(
                "INSERT INTO orders VALUES('ORDER-3',NULL,'CUST-1','2011-12-03',"
                "'confirmed','GBP','fixture')"
            )
            db.commit()
        finally:
            db.close()
        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "My order count", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "count-test")
        short = customer_orders(context, 1)
        self.assertEqual([row["id"] for row in short["records"]], ["ORDER-3"])
        self.assertEqual(short["facts"]["total_orders"], 2)
        self.assertEqual(short["facts"]["returned_orders"], 1)
        self.assertEqual(short["facts"]["offset"], 0)
        self.assertEqual(short["facts"]["next_offset"], 1)
        self.assertTrue(short["facts"]["has_more"])
        self.assertEqual(short["facts"]["page_limit"], 1)
        self.assertEqual(short["facts"]["earliest_order_id"], "ORDER-1")
        self.assertEqual(short["facts"]["earliest_order_at"], "2011-12-01")
        self.assertEqual(short["facts"]["latest_order_id"], "ORDER-3")
        self.assertEqual(short["facts"]["latest_order_at"], "2011-12-03")
        older = customer_orders(context, 1, short["facts"]["next_offset"])
        self.assertEqual([row["id"] for row in older["records"]], ["ORDER-1"])
        self.assertIsNone(older["facts"]["next_offset"])
        full = customer_orders(context, 20)
        self.assertEqual(full["facts"]["total_orders"], 2)
        self.assertFalse(full["facts"]["has_more"])

    def test_customer_account_and_agent_can_page_all_owned_orders_and_invoices(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executemany(
                "INSERT INTO orders VALUES(?,?,?,?,'confirmed','GBP','fixture')",
                [
                    (f"ORDER-PG-{number:03d}", None, "CUST-1", "2011-12-04")
                    for number in range(56)
                ],
            )
            db.executemany(
                "INSERT INTO invoices VALUES(?,?,?,?,0,'GBP','fixture')",
                [
                    (
                        f"INV-PG-{number:03d}",
                        f"ORDER-PG-{number:03d}",
                        "2011-12-05",
                        "2012-01-04",
                    )
                    for number in range(28)
                ],
            )
            db.commit()
        finally:
            db.close()
        self.choose("customer", "CUST-1")
        order_ids = set()
        invoice_ids = set()
        for page_number in range(1, 4):
            response = self.client.get("/api/customer", params={"orders_page": page_number})
            self.assertEqual(response.status_code, 200, response.text)
            page = response.json()
            self.assertEqual(page["orders_page"], page_number)
            self.assertEqual(page["activity"]["order_count"], 57)
            self.assertEqual(len(page["orders"]), 25 if page_number < 3 else 7)
            order_ids.update(row["id"] for row in page["orders"])
        self.assertEqual(len(order_ids), 57)
        self.assertNotIn("ORDER-2", order_ids)
        for page_number in (1, 2):
            page = self.client.get(
                "/api/customer", params={"invoices_page": page_number}
            ).json()
            self.assertEqual(page["activity"]["invoice_count"], 29)
            self.assertEqual(len(page["invoices"]), 25 if page_number == 1 else 4)
            invoice_ids.update(row["id"] for row in page["invoices"])
        self.assertEqual(len(invoice_ids), 29)
        self.assertEqual(self.client.get("/api/customer?orders_page=0").status_code, 422)

        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Older orders", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "pages")
        recent = customer_orders(context, 50)
        older = customer_orders(context, 50, recent["facts"]["next_offset"])
        self.assertEqual(recent["facts"]["total_orders"], 57)
        self.assertEqual(recent["facts"]["earliest_order_id"], "ORDER-1")
        self.assertEqual(recent["facts"]["latest_order_id"], "ORDER-PG-055")
        self.assertEqual([len(recent["records"]), len(older["records"])], [50, 7])
        self.assertFalse(older["facts"]["has_more"])
        self.assertEqual(
            len({row["id"] for row in recent["records"] + older["records"]}), 57
        )
        invoice_first = customer_invoices(context, 20)
        invoice_second = customer_invoices(context, 20, invoice_first["facts"]["next_offset"])
        self.assertEqual(invoice_first["facts"]["total_invoices"], 29)
        self.assertEqual([len(invoice_first["records"]), len(invoice_second["records"])], [20, 9])
        self.assertFalse(invoice_second["facts"]["has_more"])
        self.assertEqual(
            len({row["id"] for row in invoice_first["records"] + invoice_second["records"]}),
            29,
        )

    def test_finance_payment_summary_does_not_mislabel_other_invoice_receipt(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO orders VALUES('ORDER-3',NULL,'CUST-1','2011-12-03',
                  'confirmed','GBP','fixture');
                INSERT INTO invoices VALUES('INV-3','ORDER-3','2011-12-04',
                  '2012-01-03',500,'GBP','fixture');
                INSERT INTO payments VALUES('PAY-1','CUST-1','2011-12-05',
                  1000,'GBP','fixture');
                INSERT INTO payments VALUES('PAY-2','CUST-1','2011-12-06',
                  500,'GBP','fixture');
                INSERT INTO payment_allocations VALUES('ALLOC-1','PAY-1','INV-1',
                  '2011-12-05',1000);
                INSERT INTO payment_allocations VALUES('ALLOC-2','PAY-2','INV-3',
                  '2011-12-06',500);
                """
            )
            db.commit()
        finally:
            db.close()
        self.choose("employee", "EMP-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Payment links")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "payments")
        payments = execute(
            context, "list_records", {"entity": "payments", "customer_id": "CUST-1"}
        )
        by_id = {row["id"]: row["fields"] for row in payments["records"]}
        self.assertEqual(payments["page"]["total"], 2)
        self.assertEqual(by_id["PAY-2"]["allocation_count"], 1)
        self.assertEqual(by_id["PAY-2"]["allocated_pence"], 500)
        self.assertEqual(by_id["PAY-2"]["unallocated_pence"], 0)
        target = execute(
            context, "list_records", {"entity": "payment_allocations", "parent_id": "INV-1"}
        )
        self.assertEqual([row["fields"]["payment_id"] for row in target["records"]], ["PAY-1"])

    def test_customer_invoice_tool_reports_settled_balance_without_other_accounts(self):
        db = connect(self.state / "company.sqlite")
        try:
            db.executescript(
                """
                INSERT INTO invoices VALUES('INV-OTHER','ORDER-2','2011-12-03',
                  '2012-01-02',900,'GBP','fixture');
                INSERT INTO payments VALUES('PAY-1','CUST-1','2011-12-04',
                  1000,'GBP','fixture');
                INSERT INTO payment_allocations VALUES('ALLOC-1','PAY-1','INV-1',
                  '2011-12-04',1000);
                INSERT INTO credit_notes VALUES('CREDIT-1','INV-1','2011-12-05',
                  300,'fixture correction','fixture');
                """
            )
            db.commit()
        finally:
            db.close()
        self.choose("customer", "CUST-1")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "My invoices", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "invoices")
        result = customer_invoices(context, limit=1)
        self.assertEqual(result["facts"]["total_invoices"], 1)
        self.assertEqual(result["facts"]["billed_pence"], 2800)
        self.assertEqual(result["facts"]["outstanding_pence"], 1500)
        self.assertEqual(result["records"][0]["id"], "INV-1")
        self.assertEqual(result["records"][0]["outstanding_pence"], 1500)
        self.assertFalse(result["facts"]["has_more"])
        first = customer_invoice(context, "INV-1", limit=1)
        self.assertEqual(first["facts"]["allocated_pence"], 1000)
        self.assertEqual(first["facts"]["credited_pence"], 300)
        self.assertTrue(first["facts"]["ledger_reconciles"])
        self.assertEqual(first["facts"]["total_entries"], 2)
        self.assertTrue(first["facts"]["has_more"])
        second = customer_invoice(context, "INV-1", limit=1, offset=1)
        self.assertFalse(second["facts"]["has_more"])
        self.assertEqual(
            {row["kind"] for row in first["records"] + second["records"]},
            {"payment_allocation", "credit_note"},
        )
        self.assertEqual(customer_invoice(context, "INV-OTHER")["status"], "empty")
        page = self.client.get("/api/customer/invoices/INV-1")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["invoice"]["outstanding_pence"], 1500)
        self.assertEqual(page.json()["total_entries"], 2)
        self.assertEqual(
            {row["kind"] for row in page.json()["entries"]},
            {"payment_allocation", "credit_note"},
        )
        self.assertEqual(self.client.get("/api/customer/invoices/INV-OTHER").status_code, 404)

    def test_database_audit_is_read_only_and_superuser_scoped(self):
        self.choose("employee", "EMP-1")
        self.assertEqual(self.client.get("/api/database/audit-modern").status_code, 403)
        self.choose("super_user")
        response = self.client.get("/api/database/audit-modern")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["orders"], 0)
        self.assertEqual(len(result["violations"]), 50)
        self.assertEqual(result["violations"]["fulfilled_line_without_invoice"], 0)

    def test_database_editor_creates_updates_audits_and_exposes_real_relationships(self):
        self.choose("employee", "EMP-1")
        employee_graph = self.client.get("/api/database/relationships").json()
        self.assertNotIn("inventory", {item["name"] for item in employee_graph["tables"]})
        self.assertEqual(
            self.client.post("/api/database/rows/addresses", json={"values": {}}).status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/database/schema/orders").status_code, 403)

        self.choose("super_user")
        graph = self.client.get("/api/database/relationships").json()
        self.assertIn(
            {
                "source": "customers",
                "target": "addresses",
                "column": "address_id",
                "table": "addresses",
                "target_column": "id",
            },
            graph["edges"],
        )
        self.assertTrue(self.client.get("/api/database/schema/addresses").json()["editable"])
        self.assertFalse(self.client.get("/api/database/schema/documents").json()["editable"])
        self.assertEqual(
            self.client.post("/api/database/rows/documents", json={"values": {}}).status_code,
            400,
        )

        created = self.client.post(
            "/api/database/rows/addresses",
            json={"values": {"label": "16 Lantern Lane", "country": "United Kingdom"}},
        )
        self.assertEqual(created.status_code, 200, created.text)
        original = created.json()["record"]
        self.assertTrue(original["id"].startswith("EDIT-"))
        self.assertEqual(original["provenance"], "portal_demo_edit")
        updated = self.client.patch(
            f"/api/database/rows/addresses/{original['id']}",
            json={"values": {"label": "18 Lantern Lane"}, "expected": original},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["record"]["label"], "18 Lantern Lane")
        stale = self.client.patch(
            f"/api/database/rows/addresses/{original['id']}",
            json={"values": {"label": "Stale edit"}, "expected": original},
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(
            self.client.get(f"/api/database/addresses/{original['id']}").json()["label"],
            "18 Lantern Lane",
        )
        bad_fk = self.client.post(
            "/api/database/rows/products",
            json={"values": {"name": "Test cup", "category_id": "CAT-1", "supplier_id": "MISSING"}},
        )
        self.assertEqual(bad_fk.status_code, 400)
        deleted = self.client.request(
            "DELETE",
            f"/api/database/rows/addresses/{original['id']}",
            json={"expected": updated.json()["record"]},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(
            self.client.get(f"/api/database/addresses/{original['id']}").status_code,
            404,
        )
        audit = self.client.get("/api/edits").json()
        self.assertEqual([item["entity"] for item in audit[:2]], ["addresses", "addresses"])
        company = connect(self.state / "company.sqlite", readonly=True)
        try:
            self.assertEqual(company.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            company.close()

    def test_simulated_deletion_requires_human_decision_and_keeps_data(self):
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Simulation proof", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "test-run")
        proposed = execute(
            context,
            "simulate_delete",
            {
                "target_kind": "record",
                "entity": "customers",
                "record_id": "CUST-1",
                "reason": "Demonstrate the approval boundary",
            },
        )
        self.assertEqual(proposed["status"], "pending_approval")
        company = connect(self.state / "company.sqlite", readonly=True)
        try:
            self.assertIsNotNone(
                company.execute("SELECT id FROM customers WHERE id='CUST-1'").fetchone()
            )
        finally:
            company.close()
        outcome = decide(context, proposed["operation_id"], "approve")
        self.assertTrue(outcome["simulated"])
        self.assertFalse(outcome["deleted"])
        company = connect(self.state / "company.sqlite", readonly=True)
        try:
            self.assertIsNotNone(
                company.execute("SELECT id FROM customers WHERE id='CUST-1'").fetchone()
            )
        finally:
            company.close()
        document_path = PROJECT / "data/documents/content/POL-RETURNS-001.v2.md"
        before_document = hashlib.sha256(document_path.read_bytes()).hexdigest()
        document_proposal = execute(
            context,
            "simulate_delete",
            {
                "target_kind": "document",
                "document_id": "POL-RETURNS-001",
                "version": 2,
                "reason": "Demonstrate document deletion preview",
            },
        )
        self.assertEqual(document_proposal["status"], "pending_approval")
        document_outcome = decide(context, document_proposal["operation_id"], "approve")
        self.assertFalse(document_outcome["deleted"])
        self.assertEqual(hashlib.sha256(document_path.read_bytes()).hexdigest(), before_document)
        self.choose("customer", "CUST-1")
        customer_token = self.client.cookies.get("acme_portal")
        customer_thread = new_thread(
            PROJECT, self.state, customer_token, "Denied simulation", mode="company"
        )
        customer_context = RunContext(
            PROJECT, self.state, PROJECT / "data", customer_token, customer_thread, "test-run"
        )
        denied = execute(
            customer_context,
            "simulate_delete",
            {
                "target_kind": "record",
                "entity": "customers",
                "record_id": "CUST-1",
                "reason": "Attempt outside superuser persona",
            },
        )
        self.assertEqual(denied["error"]["code"], "access_denied")

    def test_audited_address_edit_reaches_customer_tool_and_survives_restart(self):
        self.choose("super_user")
        response = self.client.post(
            "/api/database/customers/CUST-1/address",
            json={"label": "45 New Market Street", "country": "United Kingdom"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/api/edits").json()[0]["id"], response.json()["id"])
        self.assertEqual(
            self.client.get("/api/database/addresses/ADDR-1").json()["label"], "12 Old Road"
        )
        contact = self.client.post(
            "/api/database/contacts/CONTACT-1",
            json={"name": "Updated Contact", "responsibility": "Order approvals"},
        )
        self.assertEqual(contact.status_code, 200, contact.text)
        self.assertEqual(
            self.client.get("/api/database/customer_contacts/CONTACT-1").json()["responsibility"],
            "Order approvals",
        )
        self.choose("customer", "CUST-1")
        self.assertEqual(
            self.client.get("/api/customer").json()["profile"]["address"], "45 New Market Street"
        )
        self.assertEqual(
            self.client.get("/api/customer").json()["contacts"][0]["name"],
            "Updated Contact",
        )
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Address proof", mode="company")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "test-run")
        result = customer_profile(context)
        self.assertEqual(result["records"][0]["address"], "45 New Market Street")
        self.assertEqual(result["facts"]["contacts"][0]["name"], "Updated Contact")
        self.assertEqual(result["facts"]["contacts"][0]["responsibility"], "Order approvals")
        self.assertEqual(len(result["sources"]), 2)
        self.client.__exit__(None, None, None)
        self.client = TestClient(create_portal(PROJECT, self.state, PROJECT / "data"))
        self.client.__enter__()
        self.choose("customer", "CUST-1")
        self.assertEqual(
            self.client.get("/api/customer").json()["profile"]["address"], "45 New Market Street"
        )

    def test_python_imports_remain_at_module_top(self):
        for path in (PROJECT / "acme").glob("*.py"):
            tree = ast.parse(path.read_text("utf-8"))
            nested = [
                node
                for top in tree.body
                if not isinstance(top, (ast.Import, ast.ImportFrom))
                for node in ast.walk(top)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            self.assertFalse(nested, path.name)

    def test_scenario_filters_and_cross_persona_execution_inventory(self):
        created = self.client.post(
            "/api/personas/scenarios",
            json={
                "name": "Scenario Buyer",
                "order_count": 3,
                "items_per_order": 2,
                "total_pence": 12345,
                "cancelled_count": 1,
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        customer_id = created.json()["id"]
        self.choose("customer", customer_id)
        home = self.client.get("/api/customer").json()
        self.assertEqual(home["activity"]["order_count"], 3)
        self.assertEqual(sum(row["total_pence"] for row in home["orders"]), 12345)
        categories = self.client.get("/api/documents/categories").json()["categories"]
        filtered_documents = self.client.get("/api/documents?category=policies").json()
        self.assertEqual(filtered_documents["categories"], categories)
        token = self.client.cookies.get("acme_portal")
        first_thread = new_thread(PROJECT, self.state, token, "Scenario discussion")
        self.assertIn(
            customer_id,
            {
                row["id"]
                for row in self.client.get(
                    "/api/personas/search?kind=customer&min_orders=3&status=cancelled"
                ).json()
            },
        )
        self.assertNotIn(
            customer_id,
            {
                row["id"]
                for row in self.client.get("/api/personas/search?kind=customer&max_orders=2").json()
            },
        )
        self.choose("customer", "CUST-2")
        other_token = self.client.cookies.get("acme_portal")
        second_thread = new_thread(PROJECT, self.state, other_token, "Other customer")
        self.assertNotIn(
            first_thread,
            {row["id"] for row in self.client.get("/api/execution/conversations").json()},
        )
        self.choose("super_user")
        inspected = self.client.get("/api/execution/conversations")
        self.assertEqual(inspected.status_code, 200, inspected.text)
        self.assertTrue(
            {first_thread, second_thread}.issubset({row["id"] for row in inspected.json()})
        )
        self.assertEqual(
            self.client.get(f"/api/execution/conversations/{first_thread}").status_code,
            200,
        )
        self.assertEqual(
            self.client.get(f"/api/execution/conversations/{first_thread}/events").json()["events"],
            [],
        )

    def test_modern_audit_rejects_cross_account_finance_links(self):
        company = connect(self.state / "company.sqlite")
        try:
            company.executescript(
                """
                UPDATE orders SET ordered_at='2026-01-01',
                  provenance='fictional_contemporary_scenario' WHERE id='ORDER-1';
                INSERT INTO order_status_history VALUES('HIST-1','ORDER-1',
                  '2026-01-01','confirmed','Order accepted');
                UPDATE invoices SET posted_on='2026-01-02',due_on='2026-02-01',
                  provenance='fictional_contemporary_scenario' WHERE id='INV-1';
                INSERT INTO invoice_items VALUES('INVITEM-1','INV-1','ITEM-1',2,2800);
                INSERT INTO order_items VALUES('ITEM-2','ORDER-2','SKU-1',2,'14.00',2800,NULL);
                INSERT INTO payments VALUES('PAY-1','CUST-1','2026-01-03',2800,'GBP',
                  'fictional_contemporary_scenario');
                INSERT INTO payment_allocations VALUES('ALLOC-1','PAY-1','INV-1',
                  '2026-01-03',2800);
                """
            )
            company.commit()
            self.assertEqual(audit_contemporary_history(self.state)["status"], "ok")
            corruptions = [
                (
                    "invoice_before_order",
                    "UPDATE invoices SET posted_on='2025-12-31' WHERE id='INV-1'",
                    "UPDATE invoices SET posted_on='2026-01-02' WHERE id='INV-1'",
                ),
                (
                    "invoice_due_term_mismatch",
                    "UPDATE invoices SET due_on='2026-02-02' WHERE id='INV-1'",
                    "UPDATE invoices SET due_on='2026-02-01' WHERE id='INV-1'",
                ),
                (
                    "invoice_line_order_mismatch",
                    "UPDATE invoice_items SET order_item_id='ITEM-2' WHERE id='INVITEM-1'",
                    "UPDATE invoice_items SET order_item_id='ITEM-1' WHERE id='INVITEM-1'",
                ),
                (
                    "invoice_item_overordered_quantity",
                    "UPDATE invoice_items SET quantity=3 WHERE id='INVITEM-1'",
                    "UPDATE invoice_items SET quantity=2 WHERE id='INVITEM-1'",
                ),
                (
                    "invoice_line_quantity_mismatch",
                    "UPDATE invoice_items SET quantity=1 WHERE id='INVITEM-1'",
                    "UPDATE invoice_items SET quantity=2 WHERE id='INVITEM-1'",
                ),
                (
                    "invoice_line_amount_mismatch",
                    "UPDATE invoice_items SET amount_pence=2700 WHERE id='INVITEM-1'",
                    "UPDATE invoice_items SET amount_pence=2800 WHERE id='INVITEM-1'",
                ),
                (
                    "invoice_without_items",
                    "DELETE FROM invoice_items WHERE id='INVITEM-1'",
                    "INSERT INTO invoice_items VALUES('INVITEM-1','INV-1','ITEM-1',2,2800)",
                ),
                (
                    "order_status_mismatch",
                    "UPDATE orders SET status='partial' WHERE id='ORDER-1'",
                    "UPDATE orders SET status='confirmed' WHERE id='ORDER-1'",
                ),
                (
                    "order_history_before_order",
                    "UPDATE order_status_history SET occurred_at='2025-12-31' WHERE id='HIST-1'",
                    "UPDATE order_status_history SET occurred_at='2026-01-01' WHERE id='HIST-1'",
                ),
                (
                    "payment_customer_mismatch",
                    "UPDATE payments SET customer_id='CUST-2' WHERE id='PAY-1'",
                    "UPDATE payments SET customer_id='CUST-1' WHERE id='PAY-1'",
                ),
                (
                    "payment_allocation_before_receipt",
                    "UPDATE payments SET received_on='2026-01-04' WHERE id='PAY-1'",
                    "UPDATE payments SET received_on='2026-01-03' WHERE id='PAY-1'",
                ),
                (
                    "payment_overallocated",
                    "UPDATE payments SET amount_pence=1000 WHERE id='PAY-1'",
                    "UPDATE payments SET amount_pence=2800 WHERE id='PAY-1'",
                ),
            ]
            for name, corruption, restoration in corruptions:
                with self.subTest(name=name):
                    company.execute(corruption)
                    company.commit()
                    self.assertGreater(
                        audit_contemporary_history(self.state)["violations"][name], 0
                    )
                    company.execute(restoration)
                    company.commit()
                    self.assertEqual(audit_contemporary_history(self.state)["status"], "ok")
            company.execute("UPDATE orders SET status='partial' WHERE id='ORDER-1'")
            company.execute(
                "INSERT INTO order_status_history VALUES('HIST-2','ORDER-1',"
                "'2026-01-04','partial','Incorrect partial status')"
            )
            company.commit()
            violations = audit_contemporary_history(self.state)["violations"]
            self.assertEqual(violations["order_status_mismatch"], 0)
            self.assertEqual(violations["active_order_status_vs_fulfillment"], 1)
            company.execute("DELETE FROM order_status_history WHERE id='HIST-2'")
            company.execute("UPDATE orders SET status='confirmed' WHERE id='ORDER-1'")
            company.commit()
            self.assertEqual(audit_contemporary_history(self.state)["status"], "ok")

            company.execute("UPDATE orders SET status='cancelled' WHERE id='ORDER-1'")
            company.execute(
                "INSERT INTO order_status_history VALUES('HIST-3','ORDER-1',"
                "'2026-01-04','cancelled','Incorrect cancellation')"
            )
            company.commit()
            violations = audit_contemporary_history(self.state)["violations"]
            self.assertEqual(violations["order_status_mismatch"], 0)
            self.assertEqual(violations["cancelled_order_has_billing_or_dispatch"], 1)
            company.execute("DELETE FROM order_status_history WHERE id='HIST-3'")
            company.execute("UPDATE orders SET status='confirmed' WHERE id='ORDER-1'")
            company.commit()
            self.assertEqual(audit_contemporary_history(self.state)["status"], "ok")

            company.execute(
                "INSERT INTO orders VALUES('ORDER-EMPTY',NULL,'CUST-1','2026-01-04',"
                "'confirmed','GBP','fictional_contemporary_scenario')"
            )
            company.execute(
                "INSERT INTO order_status_history VALUES('HIST-EMPTY','ORDER-EMPTY',"
                "'2026-01-04','confirmed','Empty order')"
            )
            company.commit()
            self.assertEqual(
                audit_contemporary_history(self.state)["violations"][
                    "contemporary_order_without_items"
                ],
                1,
            )
            company.execute("DELETE FROM order_status_history WHERE id='HIST-EMPTY'")
            company.execute("DELETE FROM orders WHERE id='ORDER-EMPTY'")
            company.commit()
            self.assertEqual(audit_contemporary_history(self.state)["status"], "ok")
            company.execute(
                "UPDATE payment_allocations SET amount_pence=2700 WHERE id='ALLOC-1'"
            )
            company.execute(
                "INSERT INTO credit_notes VALUES('CREDIT-1','INV-1','2026-01-03',100,"
                "'Pricing correction','fictional_contemporary_scenario')"
            )
            company.commit()
            self.assertEqual(audit_contemporary_history(self.state)["status"], "ok")
            company.execute("UPDATE credit_notes SET issued_on='2026-01-01' WHERE id='CREDIT-1'")
            company.commit()
            self.assertGreater(
                audit_contemporary_history(self.state)["violations"]["credit_before_invoice"],
                0,
            )
        finally:
            company.close()

    def test_modern_audit_detects_missing_fulfillment_links(self):
        company = connect(self.state / "company.sqlite")
        try:
            company.executescript(
                """
                INSERT INTO warehouses VALUES('WH-AUDIT','LOC-1','Audit warehouse');
                INSERT INTO orders VALUES('ORDER-AUDIT',NULL,'CUST-1','2026-01-04',
                  'fulfilled','GBP','fictional_contemporary_scenario');
                INSERT INTO order_status_history VALUES('HIST-AUDIT','ORDER-AUDIT',
                  '2026-01-04','fulfilled','Test completion');
                INSERT INTO shipments VALUES('SHIP-AUDIT','ORDER-AUDIT','WH-AUDIT',
                  '2026-01-05',NULL,'Test carrier','fictional_contemporary_scenario');
                INSERT INTO order_items VALUES('ITEM-AUDIT','ORDER-AUDIT','SKU-1',
                  1,'14.00',1400,NULL);
                """
            )
            company.commit()
            violations = audit_contemporary_history(self.state)["violations"]
            self.assertEqual(violations["fulfilled_without_invoice"], 1)
            self.assertEqual(violations["fulfilled_without_shipment"], 0)
            self.assertEqual(violations["shipment_without_items"], 1)
            self.assertEqual(violations["fulfilled_line_without_invoice"], 1)
            company.execute("DELETE FROM shipments WHERE id='SHIP-AUDIT'")
            company.commit()
            violations = audit_contemporary_history(self.state)["violations"]
            self.assertEqual(violations["fulfilled_without_invoice"], 1)
            self.assertEqual(violations["fulfilled_without_shipment"], 1)
            self.assertEqual(violations["shipment_without_items"], 0)
            company.executescript(
                """
                INSERT INTO order_items VALUES('ITEM-AUDIT-2','ORDER-AUDIT','SKU-1',
                  1,'14.00',1400,NULL);
                INSERT INTO invoices VALUES('INV-AUDIT','ORDER-AUDIT','2026-01-06',
                  '2026-02-05',1400,'GBP','fictional_contemporary_scenario');
                INSERT INTO invoice_items VALUES('INVITEM-AUDIT','INV-AUDIT',
                  'ITEM-AUDIT',1,1400);
                """
            )
            company.commit()
            violations = audit_contemporary_history(self.state)["violations"]
            self.assertEqual(violations["mismatched_invoice_totals"], 0)
            self.assertEqual(violations["invoice_without_items"], 0)
            self.assertEqual(violations["fulfilled_without_invoice"], 0)
            self.assertEqual(violations["fulfilled_line_without_invoice"], 1)
        finally:
            company.close()

    def test_modern_audit_checks_planning_targets_and_cohort_boundary(self):
        company = connect(self.state / "company.sqlite")
        try:
            company.executescript(
                """
                INSERT INTO departments VALUES('DEP-SALES','Sales','Planning');
                INSERT INTO departments VALUES('DEP-ANALYTICS','Analytics','Forecasting');
                INSERT INTO forecast_runs VALUES('SCN-FCRUN-TEST-2026-10-v2',
                  '2026-10-01T09:00:00+00:00','2026-09-30','2026-10-01',
                  '2026-10-31','trailing calendar-month mean of billed units',
                  2,2,'Fictional prior-month input');
                """
            )
            company.execute(
                "INSERT INTO forecasts VALUES(?,?,?,?,?,?,?)",
                (
                    "SCN-FC-TEST-2026-10-v2",
                    "SCN-FCRUN-TEST-2026-10-v2",
                    "SKU-1",
                    0,
                    0,
                    None,
                    hashlib.sha256(b"[]").hexdigest(),
                ),
            )
            company.commit()
            self.assertEqual(
                audit_contemporary_history(self.state)["violations"]["forecast_without_sales_target"],
                1,
            )
            company.execute(
                "INSERT INTO sales_targets VALUES(?,?,?,?,?)",
                (
                    "SCN-TARGET-TEST-2026-10-v2",
                    "DEP-SALES",
                    "SCN-FC-TEST-2026-10-v2",
                    2,
                    "Fictional planner override: two-unit minimum because the short "
                    "lookback has no billed units. This is judgment, not model output.",
                ),
            )
            company.commit()
            self.assertEqual(audit_contemporary_history(self.state)["status"], "ok")
            company.execute(
                "UPDATE sales_targets SET target_units=3 WHERE id='SCN-TARGET-TEST-2026-10-v2'"
            )
            company.commit()
            self.assertEqual(
                audit_contemporary_history(self.state)["violations"]["sales_target_basis_mismatch"],
                1,
            )
            company.execute(
                "UPDATE sales_targets SET target_units=3,assumption='Planner chose three "
                "units for a launch display' WHERE id='SCN-TARGET-TEST-2026-10-v2'"
            )
            company.commit()
            self.assertEqual(
                audit_contemporary_history(self.state)["violations"]["sales_target_basis_mismatch"],
                0,
            )
            company.execute(
                "UPDATE sales_targets SET target_units=2,department_id='DEP-ANALYTICS' "
                "WHERE id='SCN-TARGET-TEST-2026-10-v2'"
            )
            company.commit()
            self.assertEqual(
                audit_contemporary_history(self.state)["violations"]["sales_target_link_mismatch"],
                1,
            )
            company.execute(
                "UPDATE sales_targets SET department_id='DEP-SALES' "
                "WHERE id='SCN-TARGET-TEST-2026-10-v2'"
            )
            company.execute(
                "UPDATE orders SET provenance='fictional_contemporary_scenario' "
                "WHERE id='ORDER-2'"
            )
            company.commit()
            self.assertEqual(
                audit_contemporary_history(self.state)["violations"][
                    "contemporary_orders_in_source_era"
                ],
                1,
            )
            company.execute("UPDATE orders SET provenance='fixture' WHERE id='ORDER-2'")
            company.execute(
                "UPDATE orders SET source_invoice_no='SOURCE-TEST',ordered_at='2026-01-01' "
                "WHERE id='ORDER-1'"
            )
            company.commit()
            self.assertEqual(
                audit_contemporary_history(self.state)["violations"]["source_orders_after_cutoff"],
                1,
            )
            company.execute(
                "UPDATE invoices SET posted_on='2026-01-02',due_on='2026-02-01' "
                "WHERE id='INV-1'"
            )
            company.commit()
            self.assertEqual(
                audit_contemporary_history(self.state)["violations"]["source_invoices_after_cutoff"],
                1,
            )
        finally:
            company.close()

    def test_scenario_customer_has_contact_and_partial_payment_history(self):
        company = connect(self.state / "company.sqlite")
        try:
            company.execute("INSERT INTO warehouses VALUES('WH-1','LOC-1','Main warehouse')")
            company.commit()
        finally:
            company.close()

        baseline_copy = self.state / "baseline-before-scenario.sqlite"
        company = connect(self.state / "company.sqlite", readonly=True)
        baseline = connect(baseline_copy)
        try:
            company.backup(baseline)
        finally:
            baseline.close()
            company.close()
        created = self.client.post(
            "/api/personas/scenarios",
            json={
                "name": "North Quay Supplies",
                "order_count": 3,
                "items_per_order": 2,
                "total_pence": 12000,
                "cancelled_count": 1,
                "fulfilled_count": 1,
                "payment_profile": "partial",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        customer_id = created.json()["id"]
        self.choose("customer", customer_id)
        home = self.client.get("/api/customer").json()
        self.assertIn("Trade Park", home["profile"]["address"])
        self.assertEqual(home["profile"]["segment"], "Independent retail")
        company = connect(self.state / "company.sqlite", readonly=True)
        try:
            contact = company.execute(
                "SELECT * FROM customer_contacts WHERE customer_id=?", (customer_id,)
            ).fetchone()
            self.assertIsNotNone(contact)
            self.assertTrue(contact["email"].endswith(".example"))
            orders = company.execute(
                "SELECT id,status,ordered_at FROM orders WHERE customer_id=? ORDER BY ordered_at",
                (customer_id,),
            ).fetchall()
            self.assertEqual(
                [row["status"] for row in orders], ["cancelled", "fulfilled", "confirmed"]
            )
            self.assertEqual(len({row["ordered_at"] for row in orders}), 3)
            self.assertEqual(
                orders[0]["ordered_at"], (date.today() - timedelta(days=45)).isoformat()
            )
            self.assertTrue(all(row["ordered_at"] > "2011-12-09" for row in orders))
            self.assertEqual(
                {
                    row[0]
                    for row in company.execute(
                        "SELECT DISTINCT provenance FROM orders WHERE customer_id=?", (customer_id,)
                    )
                },
                {"fictional_contemporary_scenario"},
            )
            invoice = company.execute(
                "SELECT b.total_pence,b.outstanding_pence FROM invoice_balances b "
                "JOIN orders o ON o.id=b.order_id WHERE o.customer_id=?",
                (customer_id,),
            ).fetchone()
            self.assertEqual(invoice["outstanding_pence"], invoice["total_pence"] // 2)
            inventory = company.execute(
                "SELECT on_hand,reserved FROM inventory WHERE id LIKE 'SCN-INV-%'"
            ).fetchone()
            self.assertEqual(tuple(inventory), (20, 2))
            self.assertEqual(
                company.execute(
                    "SELECT COUNT(*) FROM shipment_items WHERE id LIKE 'SCN-SHIPITEM-%'"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(company.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                company.execute(
                    "SELECT i.on_hand-SUM(m.quantity) FROM inventory i "
                    "JOIN stock_movements m ON m.warehouse_id=i.warehouse_id "
                    "AND m.product_id=i.product_id WHERE i.id LIKE 'SCN-INV-%'"
                ).fetchone()[0],
                0,
            )
            company.execute("ATTACH DATABASE ? AS baseline", (str(baseline_copy),))
            keep, removed = _preserved_rows(company, [f"customers:{customer_id}"])
            self.assertIn(("customer_contacts", contact["id"]), keep)
            self.assertFalse(removed)
        finally:
            company.close()

    def test_contemporary_cohort_is_linked_and_idempotent(self):
        company = connect(self.state / "company.sqlite")
        try:
            company.execute("INSERT INTO warehouses VALUES('WH-1','LOC-1','Main warehouse')")
            company.execute(
                "INSERT INTO departments VALUES('DEP-SUPPORT','Support','Service cases')"
            )
            company.execute(
                "INSERT INTO employees VALUES('EMP-SUPPORT','Support Agent','Service advisor',"
                "'2010-01-01','support@example.test','fixture')"
            )
            company.execute(
                "INSERT INTO employee_assignments VALUES('EA-SUPPORT','EMP-SUPPORT',"
                "'DEP-SUPPORT','LOC-1','2010-01-01',NULL)"
            )
            company.commit()
        finally:
            company.close()
        first = seed_contemporary_history(self.state)
        self.assertEqual(first["status"], "seeded")
        self.assertEqual(len(first["created"]), 8)
        self.assertTrue((Path(first["backup"]) / "company.sqlite").is_file())
        second = seed_contemporary_history(self.state)
        self.assertEqual(second["status"], "already_present")
        cases = seed_contemporary_cases(self.state)
        self.assertEqual(cases["status"], "seeded")
        self.assertEqual(len(cases["created"]), 8)
        self.assertEqual(seed_contemporary_cases(self.state)["status"], "already_present")
        audit = audit_contemporary_history(self.state)
        self.assertEqual(audit["status"], "ok", audit["violations"])
        modern_candidates = self.client.get(
            "/api/personas/search?kind=customer&period=contemporary"
        ).json()
        self.assertEqual(len(modern_candidates), 8)
        self.assertEqual(
            {row["history_period"] for row in modern_candidates},
            {"Contemporary fictional"},
        )
        historical_candidates = self.client.get(
            "/api/personas/search?kind=customer&period=historical"
        ).json()
        self.assertTrue(
            all(row["id"] != modern_candidates[0]["id"] for row in historical_candidates)
        )
        company = connect(self.state / "company.sqlite", readonly=True)
        try:
            self.assertEqual(
                company.execute(
                    "SELECT COUNT(*) FROM customers WHERE provenance='fictional_contemporary_seed'"
                ).fetchone()[0],
                8,
            )
            self.assertEqual(
                company.execute(
                    "SELECT COUNT(*) FROM orders WHERE provenance='fictional_contemporary_seed'"
                ).fetchone()[0],
                44,
            )
            self.assertEqual(
                company.execute(
                    "SELECT COUNT(*) FROM tickets WHERE provenance='fictional_contemporary_seed'"
                ).fetchone()[0],
                8,
            )
            self.assertEqual(
                company.execute(
                    "SELECT COUNT(*) FROM credit_notes WHERE provenance="
                    "'fictional_contemporary_seed'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                company.execute("SELECT ordered_at FROM orders WHERE id='ORDER-1'").fetchone()[0],
                "2011-12-01",
            )
            self.assertEqual(company.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                company.execute(
                    "SELECT COUNT(*) FROM invoice_balances WHERE outstanding_pence<0"
                ).fetchone()[0],
                0,
            )
            modern_invoice = company.execute(
                "SELECT id FROM invoices WHERE provenance='fictional_contemporary_seed' "
                "ORDER BY id LIMIT 1"
            ).fetchone()[0]
            bramble = next(
                row["id"] for row in first["created"] if row["name"] == "Bramble Housewares"
            )
            company.execute(
                "ATTACH DATABASE ? AS baseline", (str(Path(first["backup"]) / "company.sqlite"),)
            )
            keep, removed = _preserved_rows(company, [f"customers:{bramble}"])
            self.assertFalse(removed)
            self.assertIn(("tickets", f"SCN-TKT-{bramble.removeprefix('SCN-CUST-')}"), keep)
            self.assertIn(("credit_notes", f"SCN-CREDIT-{bramble.removeprefix('SCN-CUST-')}"), keep)
        finally:
            company.close()
        self.choose("super_user")
        token = self.client.cookies.get("acme_portal")
        thread = new_thread(PROJECT, self.state, token, "Modern finance evidence")
        context = RunContext(PROJECT, self.state, PROJECT / "data", token, thread, "test-run")
        invoice_result = execute(
            context, "lookup_record", {"entity": "invoices", "record_id": modern_invoice}
        )
        self.assertEqual(
            invoice_result["records"][0]["fields"]["business_reference"],
            date.today().isoformat(),
        )
        summary = execute(
            context,
            "business_summary",
            {
                "report": "sales",
                "start_date": (date.today() - timedelta(days=365)).isoformat(),
                "end_date": date.today().isoformat(),
            },
        )
        self.assertEqual(summary["status"], "ok")
        self.assertGreater(summary["facts"]["invoice_count"], 0)

        company = connect(self.state / "company.sqlite")
        try:
            row = company.execute(
                "SELECT si.id AS shipment_item_id,si.quantity AS shipped,s.id AS shipment_id,"
                "s.dispatched_on,s.delivered_on,oi.id AS order_item_id,oi.quantity AS ordered,"
                "s.order_id FROM shipment_items si JOIN shipments s ON s.id=si.shipment_id "
                "JOIN order_items oi ON oi.id=si.order_item_id WHERE s.provenance="
                "'fictional_contemporary_seed' ORDER BY si.id LIMIT 1"
            ).fetchone()
            foreign_item = company.execute(
                "SELECT oi.id FROM order_items oi JOIN orders o ON o.id=oi.order_id "
                "WHERE o.provenance='fictional_contemporary_seed' AND o.id!=? "
                "ORDER BY oi.id LIMIT 1",
                (row["order_id"],),
            ).fetchone()[0]
            company.execute(
                "UPDATE shipment_items SET quantity=? WHERE id=?",
                (row["ordered"] + 1, row["shipment_item_id"]),
            )
            company.commit()
            self.assertGreater(
                audit_contemporary_history(self.state)["violations"]["shipped_more_than_ordered"],
                0,
            )
            company.execute(
                "UPDATE shipment_items SET quantity=?,order_item_id=? WHERE id=?",
                (row["shipped"], foreign_item, row["shipment_item_id"]),
            )
            company.commit()
            self.assertGreater(
                audit_contemporary_history(self.state)["violations"]["shipment_order_mismatch"],
                0,
            )
            company.execute(
                "UPDATE shipment_items SET order_item_id=? WHERE id=?",
                (row["order_item_id"], row["shipment_item_id"]),
            )
            company.execute(
                "UPDATE shipments SET dispatched_on='2010-01-01' WHERE id=?",
                (row["shipment_id"],),
            )
            company.commit()
            self.assertGreater(
                audit_contemporary_history(self.state)["violations"]["shipment_before_order"],
                0,
            )
        finally:
            company.close()


if __name__ == "__main__":
    unittest.main()
