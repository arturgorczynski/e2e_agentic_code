"""Regression checks for fictional identity enrichment and source classification."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from acme.company_data import (
    account_manager_for,
    category_for,
    customer_name,
    generated_employee_profile,
    seed_inventory,
    seed_source_payments,
    source_ticket,
)
from acme.company_queries import QUERIES
from scripts.assign_account_managers import apply_changes as apply_portfolios
from scripts.assign_account_managers import changes as portfolio_changes
from scripts.enrich_demo_data import OLD_ADDRESS, changes, old_name
from scripts.install_company_v5 import apply_changes as apply_logistics
from scripts.install_company_v8 import collect_local_edits, copy_sqlite, replay_local_edits
from scripts.polish_authored_data import apply_changes
from scripts.polish_authored_data import changes as realism_changes


class DataQualityTests(unittest.TestCase):
    def test_procurement_keeps_unshipped_demand_out_of_opening_stock(self):
        db = sqlite3.connect(":memory:")
        try:
            db.executescript(
                "CREATE TABLE suppliers(id TEXT PRIMARY KEY,lead_days INTEGER);"
                "CREATE TABLE products(id TEXT PRIMARY KEY,supplier_id TEXT,"
                "source_stock_code TEXT);"
                "CREATE TABLE orders(id TEXT PRIMARY KEY,status TEXT);"
                "CREATE TABLE order_fulfillment(order_id TEXT,product_id TEXT,"
                "quantity INTEGER,shipped_quantity INTEGER);"
                "CREATE TABLE stock_movements(id TEXT PRIMARY KEY,warehouse_id TEXT,"
                "product_id TEXT,occurred_on TEXT,kind TEXT,quantity INTEGER,"
                "shipment_item_id TEXT,goods_receipt_id TEXT);"
                "CREATE TABLE purchase_orders(id TEXT PRIMARY KEY,supplier_id TEXT,"
                "warehouse_id TEXT,placed_on TEXT,expected_on TEXT,status TEXT,"
                "provenance TEXT);"
                "CREATE TABLE purchase_order_items(id TEXT PRIMARY KEY,"
                "purchase_order_id TEXT,product_id TEXT,quantity INTEGER);"
                "CREATE TABLE goods_receipts(id TEXT PRIMARY KEY,"
                "purchase_order_item_id TEXT,received_on TEXT,quantity INTEGER);"
                "CREATE TABLE inventory(id TEXT PRIMARY KEY,warehouse_id TEXT,"
                "product_id TEXT,on_hand INTEGER,reserved INTEGER,as_of TEXT);"
                "INSERT INTO suppliers VALUES('SUP-1',8);"
                "INSERT INTO products VALUES('UCI-SKU-PENDING','SUP-1','PENDING');"
                "INSERT INTO products VALUES('UCI-SKU-SOLD','SUP-1','SOLD');"
                "INSERT INTO products VALUES('DEMO-SKU-C','SUP-1',NULL);"
                "INSERT INTO orders VALUES('ORD-PENDING','confirmed');"
                "INSERT INTO orders VALUES('ORD-SOLD','fulfilled');"
                "INSERT INTO order_fulfillment VALUES('ORD-PENDING','UCI-SKU-PENDING',"
                "80995,0);"
                "INSERT INTO order_fulfillment VALUES('ORD-SOLD','UCI-SKU-SOLD',100,100);"
                "INSERT INTO stock_movements VALUES('DISPATCH-1','WH-CVT','UCI-SKU-SOLD',"
                "'2011-05-03','dispatch',-100,'LINE-1',NULL);"
            )
            seed_inventory(db)
            pending = db.execute(
                "SELECT on_hand,reserved FROM inventory WHERE product_id='UCI-SKU-PENDING'"
            ).fetchone()
            self.assertEqual(pending, (0, 0))
            projected = db.execute(
                QUERIES["inventory"][1] + " WHERE id=?", ("STOCK-UCI-SKU-PENDING",)
            )
            self.assertEqual(projected.description[6][0], "backordered")
            self.assertEqual(projected.fetchone()[6], 80995)
            self.assertIsNone(
                db.execute(
                    "SELECT id FROM stock_movements WHERE id='OPEN-UCI-SKU-PENDING'"
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity-shipped_quantity FROM order_fulfillment "
                    "WHERE product_id='UCI-SKU-PENDING'"
                ).fetchone()[0],
                80995,
            )
            received = db.execute(
                "SELECT g.received_on,pi.quantity,po.id FROM goods_receipts g "
                "JOIN purchase_order_items pi ON pi.id=g.purchase_order_item_id "
                "JOIN purchase_orders po ON po.id=pi.purchase_order_id "
                "WHERE pi.product_id='UCI-SKU-SOLD'"
            ).fetchone()
            self.assertLess(received[0], "2011-05-02")
            self.assertTrue(received[2].endswith("2011-05-02"))
            self.assertGreater(received[1], 100)
            self.assertEqual(
                db.execute("SELECT on_hand FROM inventory WHERE product_id='UCI-SKU-SOLD'")
                .fetchone()[0],
                db.execute(
                    "SELECT SUM(quantity) FROM stock_movements "
                    "WHERE product_id='UCI-SKU-SOLD'"
                ).fetchone()[0],
            )
        finally:
            db.close()

    def test_source_remittances_group_invoices_and_service_cases_follow_workdays(self):
        db = sqlite3.connect(":memory:")
        try:
            db.executescript(
                "CREATE TABLE customers(id TEXT PRIMARY KEY,settlement_delay_days INTEGER);"
                "CREATE TABLE orders(id TEXT PRIMARY KEY,customer_id TEXT,source_invoice_no TEXT);"
                "CREATE TABLE invoices(id TEXT PRIMARY KEY,order_id TEXT,due_on TEXT,"
                "total_pence INTEGER);"
                "CREATE TABLE payments(id TEXT PRIMARY KEY,customer_id TEXT,received_on TEXT,"
                "amount_pence INTEGER,currency TEXT,provenance TEXT);"
                "CREATE TABLE payment_allocations(id TEXT PRIMARY KEY,payment_id TEXT,"
                "invoice_id TEXT,allocated_on TEXT,amount_pence INTEGER);"
                "CREATE TABLE employee_assignments(employee_id TEXT,department_id TEXT,"
                "valid_until TEXT);"
                "CREATE TABLE tickets(id TEXT PRIMARY KEY,order_id TEXT,"
                "assigned_employee_id TEXT,opened_on TEXT,status TEXT,topic TEXT,"
                "description TEXT,provenance TEXT);"
                "CREATE TABLE ticket_events(id TEXT PRIMARY KEY,ticket_id TEXT,"
                "occurred_on TEXT,status TEXT,note TEXT);"
                "INSERT INTO customers VALUES('UCI-CUST-1',3);"
                "INSERT INTO employee_assignments VALUES('EMP-SUPPORT','DEP-SUPPORT',NULL);"
            )
            for number in range(100):
                db.execute(
                    "INSERT INTO orders VALUES(?,?,?)",
                    (f"ORD-{number}", "UCI-CUST-1", str(number)),
                )
                db.execute(
                    "INSERT INTO invoices VALUES(?,?,?,?)",
                    (f"INV-{number}", f"ORD-{number}", "2011-03-01", 10000),
                )
            seed_source_payments(db)
            self.assertLess(db.execute("SELECT COUNT(*) FROM payments").fetchone()[0], 100)
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM payments p WHERE p.amount_pence!=(SELECT "
                    "SUM(a.amount_pence) FROM payment_allocations a WHERE a.payment_id=p.id)"
                ).fetchone()[0],
                0,
            )
            self.assertGreater(
                db.execute(
                    "SELECT MAX(n) FROM (SELECT COUNT(*) n FROM payment_allocations "
                    "GROUP BY payment_id)"
                ).fetchone()[0],
                1,
            )
            source_ticket(db, "1", "ORD-1", "2011-11-01", "invoice_copy")
            source_ticket(db, "2", "ORD-2", "2011-12-09", "split_consignment")
            self.assertEqual(
                db.execute("SELECT status FROM tickets WHERE id='TKT-2'").fetchone()[0],
                "open",
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM ticket_events WHERE "
                    "strftime('%w',occurred_on) IN ('0','6')"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute("SELECT assigned_employee_id FROM tickets LIMIT 1").fetchone()[0],
                "EMP-SUPPORT",
            )
        finally:
            db.close()

    def test_customer_names_are_stable_unique_and_not_numbered(self):
        names = [customer_name(number) for number in range(1, 3825)]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(customer_name(9001), "Brookside Home & Gift")
        self.assertNotIn("0001", names[0])

    def test_clear_product_types_override_ambiguous_occasion_words(self):
        cases = {
            "50'S CHRISTMAS GIFT BAG LARGE": "CAT-PACK",
            "DOLLY GIRL BEAKER": "CAT-KITCHEN",
            "I LOVE LONDON MINI BACKPACK": "CAT-TEXTILE",
            "PACK OF 72 RETROSPOT CAKE CASES": "CAT-KITCHEN",
            "TEA BAG PLATE RED RETROSPOT": "CAT-KITCHEN",
            "MINI HIGHLIGHTER PENS": "CAT-STATIONERY",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(category_for(name), expected)

    def test_migration_skips_manually_linked_customer_address(self):
        db = sqlite3.connect(":memory:")
        try:
            db.executescript(
                "CREATE TABLE customers(id TEXT,source_customer_id TEXT,name TEXT,address_id TEXT);"
                "CREATE TABLE addresses(id TEXT,label TEXT,country TEXT);"
                "CREATE TABLE customer_contacts(id TEXT,customer_id TEXT,email TEXT);"
                "CREATE TABLE products(id TEXT,name TEXT,category_id TEXT,supplier_id TEXT);"
            )
            db.execute(
                "INSERT INTO customers VALUES(?,?,?,?)",
                ("UCI-CUST-1", "1", old_name(1), "ADDR-EDIT"),
            )
            db.execute(
                "INSERT INTO addresses VALUES(?,?,?)",
                ("ADDR-EDIT", "42 Demonstration Lane", "United Kingdom"),
            )
            db.execute(
                "INSERT INTO customers VALUES(?,?,?,?)",
                ("DEMO-CUST-001", None, old_name(9001), "ADDR-DEMO-CUST-001"),
            )
            db.execute(
                "INSERT INTO addresses VALUES(?,?,?)",
                ("ADDR-DEMO-CUST-001", OLD_ADDRESS, "United Kingdom"),
            )
            db.execute(
                "INSERT INTO products VALUES(?,?,?,?)",
                ("SKU-1", "CHRISTMAS GIFT BAG", "CAT-SEASON", "SUP-03"),
            )
            customers, addresses, _contacts, products = changes(db)
            self.assertEqual(len(customers), 2)
            self.assertEqual([row[2] for row in addresses], ["ADDR-DEMO-CUST-001"])
            self.assertEqual(products, [("CAT-PACK", "SUP-05", "SKU-1", "SUP-03")])
        finally:
            db.close()

    def test_authored_realism_migration_preserves_manual_edits(self):
        db = sqlite3.connect(":memory:")
        try:
            db.executescript(
                "CREATE TABLE suppliers(id TEXT,name TEXT,lead_days INTEGER,address_id TEXT);"
                "CREATE TABLE addresses(id TEXT,label TEXT,country TEXT,provenance TEXT);"
                "CREATE TABLE departments(id TEXT,name TEXT);"
                "CREATE TABLE employees(id TEXT,job_title TEXT,hired_on TEXT);"
                "CREATE TABLE employee_assignments(id TEXT,employee_id TEXT,"
                "department_id TEXT,valid_from TEXT,valid_until TEXT);"
                "INSERT INTO suppliers VALUES('SUP-01','Beacon Trade Supply',8,'ADDR-SUP-1');"
                "INSERT INTO addresses VALUES('ADDR-SUP-1',"
                "'Fictional supplier office 1; no deliverable street address',"
                "'United Kingdom','authored');"
                "INSERT INTO suppliers VALUES('SUP-02','My custom supplier',9,'ADDR-SUP-2');"
                "INSERT INTO addresses VALUES('ADDR-SUP-2','My edited location',"
                "'United Kingdom','portal_demo_edit');"
                "INSERT INTO departments VALUES('DEP-SALES','Sales');"
                "INSERT INTO employees VALUES('EMP-006','Sales specialist','2009-06-01');"
                "INSERT INTO employee_assignments VALUES('ASG-EMP-006','EMP-006',"
                "'DEP-SALES','2009-06-01',NULL);"
            )
            planned = realism_changes(db)
            self.assertEqual(len(planned["supplier_names"]), 1)
            self.assertEqual(len(planned["supplier_addresses"]), 1)
            self.assertEqual(len(planned["employee_titles"]), 1)
            apply_changes(db, planned)
            self.assertFalse(any(realism_changes(db).values()))
            title, hired = generated_employee_profile("EMP-006", "DEP-SALES")
            self.assertEqual(
                db.execute("SELECT job_title,hired_on FROM employees").fetchone(),
                (title, hired),
            )
            self.assertEqual(
                db.execute("SELECT valid_from FROM employee_assignments").fetchone()[0],
                hired,
            )
            self.assertEqual(
                db.execute("SELECT name FROM suppliers WHERE id='SUP-02'").fetchone()[0],
                "My custom supplier",
            )
            self.assertEqual(
                db.execute("SELECT label FROM addresses WHERE id='ADDR-SUP-2'").fetchone()[0],
                "My edited location",
            )
        finally:
            db.close()

    def test_account_portfolios_use_sales_staff_and_keep_demo_and_manual_assignments(self):
        db = sqlite3.connect(":memory:")
        try:
            db.executescript(
                "CREATE TABLE employee_assignments(employee_id TEXT,department_id TEXT,"
                "valid_until TEXT);"
                "CREATE TABLE customers(id TEXT,source_customer_id TEXT,account_manager_id TEXT);"
                "INSERT INTO employee_assignments VALUES('EMP-003','DEP-SALES',NULL);"
                "INSERT INTO employee_assignments VALUES('EMP-006','DEP-SALES',NULL);"
                "INSERT INTO employee_assignments VALUES('EMP-007','DEP-SALES',NULL);"
                "INSERT INTO employee_assignments VALUES('EMP-008','DEP-FINANCE',NULL);"
                "INSERT INTO customers VALUES('DEMO-CUST-001',NULL,'EMP-003');"
                "INSERT INTO customers VALUES('UCI-CUST-MANUAL','manual','EMP-007');"
            )
            for number in range(100):
                db.execute(
                    "INSERT INTO customers VALUES(?,?,?)",
                    (f"UCI-CUST-{number}", str(number), "EMP-003"),
                )
            db.commit()
            planned = portfolio_changes(db)
            self.assertGreater(len(planned), 40)
            apply_portfolios(db, planned)
            self.assertEqual(portfolio_changes(db), [])
            assigned = {
                row[0]
                for row in db.execute(
                    "SELECT account_manager_id FROM customers WHERE source_customer_id IS NOT NULL"
                )
            }
            self.assertEqual(assigned, {"EMP-003", "EMP-006", "EMP-007"})
            self.assertEqual(
                db.execute(
                    "SELECT account_manager_id FROM customers WHERE id='DEMO-CUST-001'"
                ).fetchone()[0],
                "EMP-003",
            )
            self.assertEqual(account_manager_for(db, "DEMO-CUST-001", None), "EMP-003")
        finally:
            db.close()

    def test_logistics_migration_guards_manual_changes_and_rolls_back(self):
        db = sqlite3.connect(":memory:")
        try:
            db.executescript(
                "CREATE TABLE shipments(id TEXT PRIMARY KEY,delivered_on TEXT,carrier TEXT);"
                "CREATE TABLE purchase_orders(id TEXT PRIMARY KEY,placed_on TEXT,expected_on TEXT);"
                "CREATE TABLE goods_receipts(id TEXT PRIMARY KEY,received_on TEXT);"
                "CREATE TABLE stock_movements(id TEXT PRIMARY KEY,occurred_on TEXT);"
                "CREATE TABLE addresses(id TEXT PRIMARY KEY,label TEXT);"
                "INSERT INTO shipments VALUES('S-1','2011-05-03','Old carrier');"
                "INSERT INTO purchase_orders VALUES('P-1','2011-04-17','2011-05-01');"
                "INSERT INTO goods_receipts VALUES('G-1','2011-05-01');"
                "INSERT INTO stock_movements VALUES('M-1','2011-05-01');"
                "INSERT INTO addresses VALUES('A-1','User-edited address');"
            )
            planned = {
                "shipments": [("S-1", ("2011-05-03", "Old carrier"),
                               ("2011-05-04", "New carrier"))],
                "purchase_orders": [("P-1", ("2011-04-17", "2011-05-01"),
                                     ("2011-04-15", "2011-04-28"))],
                "goods_receipts": [("G-1", ("2011-05-01",), ("2011-04-29",))],
                "stock_movements": [("M-1", ("2011-05-01",), ("2011-04-29",))],
            }
            db.execute("UPDATE goods_receipts SET received_on='2011-04-30'")
            db.commit()
            with patch("scripts.install_company_v5.CHECKS", ()):
                with self.assertRaisesRegex(ValueError, "changed since baseline"):
                    apply_logistics(db, planned)
            self.assertEqual(
                db.execute("SELECT carrier FROM shipments").fetchone()[0], "Old carrier"
            )
            db.execute("UPDATE goods_receipts SET received_on='2011-05-01'")
            db.commit()
            with patch("scripts.install_company_v5.CHECKS", ()):
                apply_logistics(db, planned)
            self.assertEqual(
                db.execute("SELECT carrier FROM shipments").fetchone()[0], "New carrier"
            )
            self.assertEqual(
                db.execute("SELECT label FROM addresses").fetchone()[0], "User-edited address"
            )
        finally:
            db.close()

    def test_legacy_supplier_links_are_reparented_as_one_transaction(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        try:
            db.executescript(
                "CREATE TABLE purchase_orders(id TEXT PRIMARY KEY);"
                "CREATE TABLE purchase_order_items(id TEXT PRIMARY KEY,"
                "purchase_order_id TEXT REFERENCES purchase_orders,"
                "product_id TEXT,quantity INTEGER);"
                "CREATE TABLE goods_receipts(id TEXT PRIMARY KEY,"
                "purchase_order_item_id TEXT REFERENCES purchase_order_items,"
                "received_on TEXT,quantity INTEGER);"
                "CREATE TABLE stock_movements(id TEXT PRIMARY KEY,"
                "goods_receipt_id TEXT REFERENCES goods_receipts,"
                "occurred_on TEXT,quantity INTEGER);"
                "CREATE TABLE addresses(id TEXT PRIMARY KEY,label TEXT);"
                "INSERT INTO purchase_orders VALUES('PO-SUP-07-2011-05');"
                "INSERT INTO purchase_orders VALUES('PO-SUP-02-2011-05');"
                "INSERT INTO purchase_order_items VALUES('OLD','PO-SUP-07-2011-05','SKU',10);"
                "INSERT INTO goods_receipts VALUES('GR-OLD','OLD','2011-05-01',10);"
                "INSERT INTO stock_movements VALUES('MOVE-OLD','GR-OLD','2011-05-01',10);"
                "INSERT INTO addresses VALUES('ADDR-EDIT','User-edited location');"
            )
            old_item = dict(db.execute("SELECT * FROM purchase_order_items").fetchone())
            old_receipt = dict(db.execute("SELECT * FROM goods_receipts").fetchone())
            old_move = dict(db.execute("SELECT * FROM stock_movements").fetchone())
            repair = [
                (
                    (old_item, {**old_item, "id": "NEW", "purchase_order_id": "PO-SUP-02-2011-05"}),
                    (old_receipt, {**old_receipt, "id": "GR-NEW", "purchase_order_item_id": "NEW"}),
                    (old_move, {**old_move, "id": "MOVE-NEW", "goods_receipt_id": "GR-NEW"}),
                )
            ]
            planned = {
                table: [] for table in (
                    "shipments", "purchase_orders", "goods_receipts", "stock_movements"
                )
            }
            db.execute("UPDATE goods_receipts SET received_on='2011-05-02'")
            db.commit()
            with patch("scripts.install_company_v5.CHECKS", ()):
                with self.assertRaisesRegex(ValueError, "changed since preview"):
                    apply_logistics(db, planned, repair)
            self.assertEqual(db.execute("SELECT id FROM purchase_order_items").fetchone()[0], "OLD")
            db.execute("UPDATE goods_receipts SET received_on='2011-05-01'")
            db.commit()
            with patch("scripts.install_company_v5.CHECKS", ()):
                apply_logistics(db, planned, repair)
            self.assertEqual(db.execute("SELECT id FROM purchase_order_items").fetchone()[0], "NEW")
            self.assertEqual(
                db.execute("SELECT purchase_order_item_id FROM goods_receipts").fetchone()[0],
                "NEW",
            )
            self.assertEqual(
                db.execute("SELECT goods_receipt_id FROM stock_movements").fetchone()[0],
                "GR-NEW",
            )
            self.assertEqual(
                db.execute("SELECT label FROM addresses").fetchone()[0],
                "User-edited location",
            )
        finally:
            db.close()

    def test_v8_rebase_preserves_local_addresses_and_rejects_other_edits(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="v6-rebase-test-", dir=project) as temporary:
            folder = Path(temporary)
            old_path, state_path, new_path = (
                folder / "old.sqlite", folder / "state.sqlite", folder / "new.sqlite"
            )
            old = sqlite3.connect(old_path)
            try:
                old.executescript(
                    "CREATE TABLE addresses(id TEXT PRIMARY KEY,label TEXT,country TEXT);"
                    "CREATE TABLE customers(id TEXT PRIMARY KEY,address_id TEXT "
                    "REFERENCES addresses,name TEXT);"
                    "CREATE TABLE orders(id TEXT PRIMARY KEY,ordered_at TEXT);"
                    "INSERT INTO addresses VALUES('A-1','Original','United Kingdom');"
                    "INSERT INTO customers VALUES('C-1','A-1','Sample');"
                    "INSERT INTO orders VALUES('O-1','2011-11-01');"
                )
                old.commit()
                state = sqlite3.connect(state_path)
                revised = sqlite3.connect(new_path)
                try:
                    old.backup(state)
                    old.backup(revised)
                    state.executescript(
                        "INSERT INTO addresses VALUES('A-2','User address','United Kingdom');"
                        "UPDATE addresses SET label='Edited original' WHERE id='A-1';"
                        "UPDATE customers SET address_id='A-2' WHERE id='C-1';"
                    )
                    revised.execute(
                        "UPDATE orders SET ordered_at='2011-10-28' WHERE id='O-1'"
                    )
                    revised.commit()
                finally:
                    state.close()
                    revised.close()
            finally:
                old.close()
            edits = collect_local_edits(old_path, state_path)
            self.assertEqual(len(edits["addresses"]["added"]), 1)
            self.assertEqual(len(edits["addresses"]["changed"]), 1)
            self.assertEqual(len(edits["customers"]["changed"]), 1)
            replay_local_edits(new_path, edits)
            db = sqlite3.connect(new_path)
            try:
                self.assertEqual(
                    db.execute("SELECT ordered_at FROM orders").fetchone()[0], "2011-10-28"
                )
                self.assertEqual(
                    db.execute("SELECT address_id FROM customers").fetchone()[0], "A-2"
                )
                self.assertEqual(
                    db.execute("SELECT label FROM addresses WHERE id='A-1'").fetchone()[0],
                    "Edited original",
                )
            finally:
                db.close()
            copy_sqlite(new_path, state_path)
            state = sqlite3.connect(state_path)
            try:
                state.execute("UPDATE orders SET ordered_at='2011-10-29' WHERE id='O-1'")
                state.commit()
            finally:
                state.close()
            with self.assertRaisesRegex(ValueError, "unhandled edit to orders"):
                collect_local_edits(old_path, state_path)


if __name__ == "__main__":
    unittest.main()
