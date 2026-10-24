-- Acme v1. Monetary postings are integer GBP pence; raw prices are decimal text.
-- Public observations and fictional operational extensions are distinguished by provenance.
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;
CREATE TABLE departments (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, responsibility TEXT NOT NULL
) STRICT;
CREATE TABLE locations (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, purpose TEXT NOT NULL
) STRICT;
CREATE TABLE employees (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, job_title TEXT NOT NULL,
 hired_on TEXT NOT NULL, email TEXT NOT NULL UNIQUE, provenance TEXT NOT NULL
) STRICT;
CREATE TABLE employee_assignments (
 id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees,
 department_id TEXT NOT NULL REFERENCES departments, location_id TEXT NOT NULL REFERENCES locations,
 valid_from TEXT NOT NULL, valid_until TEXT, CHECK(valid_until IS NULL OR valid_until >= valid_from)
) STRICT;
CREATE UNIQUE INDEX employee_current_assignment ON employee_assignments(employee_id)
 WHERE valid_until IS NULL;
CREATE TABLE addresses (
 id TEXT PRIMARY KEY, label TEXT NOT NULL, country TEXT NOT NULL,
 provenance TEXT NOT NULL
) STRICT;
CREATE TABLE customers (
 id TEXT PRIMARY KEY, source_customer_id TEXT UNIQUE, name TEXT NOT NULL,
 address_id TEXT NOT NULL REFERENCES addresses, account_manager_id TEXT NOT NULL REFERENCES employees,
 payment_terms_days INTEGER NOT NULL CHECK(payment_terms_days IN (14,30,45)),
 settlement_delay_days INTEGER NOT NULL CHECK(settlement_delay_days >= 0),
 segment TEXT NOT NULL, provenance TEXT NOT NULL
) STRICT;
CREATE TABLE customer_contacts (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers,
 name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, responsibility TEXT NOT NULL
) STRICT;
CREATE TABLE suppliers (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, address_id TEXT NOT NULL REFERENCES addresses,
 lead_days INTEGER NOT NULL CHECK(lead_days > 0), provenance TEXT NOT NULL
) STRICT;
CREATE TABLE categories (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, classification_rule TEXT NOT NULL,
 handling_note TEXT NOT NULL
) STRICT;
CREATE TABLE products (
 id TEXT PRIMARY KEY, source_stock_code TEXT UNIQUE, name TEXT NOT NULL,
 category_id TEXT NOT NULL REFERENCES categories, supplier_id TEXT NOT NULL REFERENCES suppliers,
 provenance TEXT NOT NULL
) STRICT;
CREATE TABLE price_history (
 id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products,
 observed_at TEXT NOT NULL, raw_unit_price_gbp TEXT NOT NULL,
 source_row_id TEXT UNIQUE, price_kind TEXT NOT NULL CHECK(price_kind IN ('observed','fixture'))
) STRICT;
CREATE TABLE orders (
 id TEXT PRIMARY KEY, source_invoice_no TEXT UNIQUE,
 customer_id TEXT NOT NULL REFERENCES customers, ordered_at TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('confirmed','partial','fulfilled','cancelled')),
 currency TEXT NOT NULL CHECK(currency='GBP'), provenance TEXT NOT NULL
) STRICT;
CREATE TABLE order_items (
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders,
 product_id TEXT NOT NULL REFERENCES products, quantity INTEGER NOT NULL CHECK(quantity > 0),
 raw_unit_price_gbp TEXT NOT NULL, line_pence INTEGER NOT NULL CHECK(line_pence >= 0),
 source_row_id TEXT UNIQUE
) STRICT;
CREATE TABLE order_status_history (
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders,
 occurred_at TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('confirmed','partial','fulfilled','cancelled')), reason TEXT NOT NULL
) STRICT;
CREATE TABLE warehouses (
 id TEXT PRIMARY KEY, location_id TEXT NOT NULL REFERENCES locations, name TEXT NOT NULL
) STRICT;
CREATE TABLE inventory (
 id TEXT PRIMARY KEY, warehouse_id TEXT NOT NULL REFERENCES warehouses,
 product_id TEXT NOT NULL REFERENCES products, on_hand INTEGER NOT NULL CHECK(on_hand >= 0),
 reserved INTEGER NOT NULL CHECK(reserved >= 0 AND reserved <= on_hand),
 as_of TEXT NOT NULL, UNIQUE(warehouse_id,product_id)
) STRICT;
CREATE TABLE purchase_orders (
 id TEXT PRIMARY KEY, supplier_id TEXT NOT NULL REFERENCES suppliers,
 warehouse_id TEXT NOT NULL REFERENCES warehouses, placed_on TEXT NOT NULL, expected_on TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('open','received')), provenance TEXT NOT NULL,
 CHECK(expected_on >= placed_on)
) STRICT;
CREATE TABLE purchase_order_items (
 id TEXT PRIMARY KEY, purchase_order_id TEXT NOT NULL REFERENCES purchase_orders,
 product_id TEXT NOT NULL REFERENCES products, quantity INTEGER NOT NULL CHECK(quantity > 0)
) STRICT;
CREATE TABLE goods_receipts (
 id TEXT PRIMARY KEY, purchase_order_item_id TEXT NOT NULL REFERENCES purchase_order_items,
 received_on TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0)
) STRICT;
CREATE TABLE shipments (
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders,
 warehouse_id TEXT NOT NULL REFERENCES warehouses, dispatched_on TEXT NOT NULL,
 delivered_on TEXT, carrier TEXT NOT NULL, provenance TEXT NOT NULL,
 CHECK(delivered_on IS NULL OR delivered_on >= dispatched_on)
) STRICT;
CREATE TABLE shipment_items (
 id TEXT PRIMARY KEY, shipment_id TEXT NOT NULL REFERENCES shipments,
 order_item_id TEXT NOT NULL REFERENCES order_items, quantity INTEGER NOT NULL CHECK(quantity > 0),
 UNIQUE(shipment_id,order_item_id)
) STRICT;
CREATE TABLE stock_movements (
 id TEXT PRIMARY KEY, warehouse_id TEXT NOT NULL REFERENCES warehouses,
 product_id TEXT NOT NULL REFERENCES products, occurred_on TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('opening','receipt','dispatch')),
 quantity INTEGER NOT NULL CHECK(quantity != 0),
 shipment_item_id TEXT UNIQUE REFERENCES shipment_items,
 goods_receipt_id TEXT UNIQUE REFERENCES goods_receipts,
 CHECK((kind='opening' AND quantity>0 AND shipment_item_id IS NULL AND goods_receipt_id IS NULL)
 OR (kind='receipt' AND quantity>0 AND goods_receipt_id IS NOT NULL AND shipment_item_id IS NULL)
 OR (kind='dispatch' AND quantity<0 AND shipment_item_id IS NOT NULL AND goods_receipt_id IS NULL))
) STRICT;
CREATE TABLE invoices (
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE REFERENCES orders,
 posted_on TEXT NOT NULL, due_on TEXT NOT NULL, total_pence INTEGER NOT NULL CHECK(total_pence>=0),
 currency TEXT NOT NULL CHECK(currency='GBP'), provenance TEXT NOT NULL,
 CHECK(due_on >= posted_on)
) STRICT;
CREATE TABLE invoice_items (
 id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices,
 order_item_id TEXT NOT NULL UNIQUE REFERENCES order_items,
 quantity INTEGER NOT NULL CHECK(quantity>0), amount_pence INTEGER NOT NULL CHECK(amount_pence>=0)
) STRICT;
CREATE TABLE payments (
 id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers,
 received_on TEXT NOT NULL, amount_pence INTEGER NOT NULL CHECK(amount_pence>0),
 currency TEXT NOT NULL CHECK(currency='GBP'), provenance TEXT NOT NULL
) STRICT;
CREATE TABLE payment_allocations (
 id TEXT PRIMARY KEY, payment_id TEXT NOT NULL REFERENCES payments,
 invoice_id TEXT NOT NULL REFERENCES invoices, allocated_on TEXT NOT NULL,
 amount_pence INTEGER NOT NULL CHECK(amount_pence>0), UNIQUE(payment_id,invoice_id)
) STRICT;
CREATE TABLE credit_notes (
 id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices,
 issued_on TEXT NOT NULL, amount_pence INTEGER NOT NULL CHECK(amount_pence>0),
 reason TEXT NOT NULL, provenance TEXT NOT NULL
) STRICT;
CREATE TABLE tickets (
 id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders,
 assigned_employee_id TEXT NOT NULL REFERENCES employees, opened_on TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('open','in_progress','resolved')),
 topic TEXT NOT NULL, description TEXT NOT NULL, provenance TEXT NOT NULL
) STRICT;
CREATE TABLE ticket_events (
 id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets,
 occurred_on TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('open','in_progress','resolved')),
 note TEXT NOT NULL
) STRICT;
CREATE TABLE forecast_runs (
 id TEXT PRIMARY KEY, generated_at TEXT NOT NULL, training_cutoff TEXT NOT NULL,
 target_start TEXT NOT NULL, target_end TEXT NOT NULL,
 method TEXT NOT NULL, method_version INTEGER NOT NULL CHECK(method_version>0),
 lookback_months INTEGER NOT NULL CHECK(lookback_months>0), assumption TEXT NOT NULL,
 CHECK(training_cutoff < target_start), CHECK(target_end>=target_start),
 CHECK(substr(generated_at,1,10)>training_cutoff AND substr(generated_at,1,10)<=target_start)
) STRICT;
CREATE TABLE forecasts (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES forecast_runs,
 product_id TEXT NOT NULL REFERENCES products, units INTEGER NOT NULL CHECK(units>=0),
 training_units INTEGER NOT NULL CHECK(training_units>=0),
 training_last_date TEXT, input_sha256 TEXT NOT NULL, UNIQUE(run_id,product_id)
) STRICT;
CREATE TABLE sales_targets (
 id TEXT PRIMARY KEY, department_id TEXT NOT NULL REFERENCES departments,
 forecast_id TEXT NOT NULL UNIQUE REFERENCES forecasts, target_units INTEGER NOT NULL CHECK(target_units>=0),
 assumption TEXT NOT NULL
) STRICT;
CREATE TABLE documents (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
 owner_employee_id TEXT NOT NULL REFERENCES employees,
 access_scope TEXT NOT NULL CHECK(access_scope IN ('general','finance','operations','support','analytics'))
) STRICT;
CREATE TABLE document_versions (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents,
 version INTEGER NOT NULL CHECK(version>0), effective_from TEXT NOT NULL, effective_until TEXT,
 status TEXT NOT NULL CHECK(status IN ('current','superseded')),
 relative_path TEXT NOT NULL UNIQUE, sha256 TEXT NOT NULL,
 UNIQUE(document_id,version), CHECK(effective_until IS NULL OR effective_until >= effective_from),
 CHECK((status='current' AND effective_until IS NULL) OR (status='superseded' AND effective_until IS NOT NULL))
) STRICT;
CREATE UNIQUE INDEX current_document_version ON document_versions(document_id) WHERE status='current';
CREATE TABLE document_links (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents,
 customer_id TEXT REFERENCES customers, product_id TEXT REFERENCES products,
 department_id TEXT REFERENCES departments, warehouse_id TEXT REFERENCES warehouses,
 ticket_id TEXT REFERENCES tickets, forecast_id TEXT REFERENCES forecasts,
 invoice_id TEXT REFERENCES invoices, order_id TEXT REFERENCES orders,
 CHECK((customer_id IS NOT NULL)+(product_id IS NOT NULL)+(department_id IS NOT NULL)
 +(warehouse_id IS NOT NULL)+(ticket_id IS NOT NULL)+(forecast_id IS NOT NULL)
 +(invoice_id IS NOT NULL)+(order_id IS NOT NULL)=1)
) STRICT;
CREATE INDEX assignment_department ON employee_assignments(department_id,valid_until);
CREATE INDEX contact_customer ON customer_contacts(customer_id);
CREATE INDEX product_category ON products(category_id);
CREATE INDEX product_supplier ON products(supplier_id);
CREATE INDEX price_product_date ON price_history(product_id,observed_at);
CREATE INDEX order_customer_date ON orders(customer_id,ordered_at);
CREATE INDEX item_order ON order_items(order_id);
CREATE INDEX item_product ON order_items(product_id);
CREATE INDEX status_order_date ON order_status_history(order_id,occurred_at,id);
CREATE INDEX shipment_order_date ON shipments(order_id,dispatched_on);
CREATE INDEX shipped_order_item ON shipment_items(order_item_id);
CREATE INDEX movement_product_date ON stock_movements(warehouse_id,product_id,occurred_on,id);
CREATE INDEX movement_product_kind ON stock_movements(product_id,kind,occurred_on);
CREATE INDEX purchase_supplier ON purchase_orders(supplier_id,expected_on);
CREATE INDEX purchase_line_header ON purchase_order_items(purchase_order_id);
CREATE INDEX receipt_line ON goods_receipts(purchase_order_item_id);
CREATE INDEX invoice_due_date ON invoices(due_on);
CREATE INDEX invoice_posted ON invoices(posted_on);
CREATE INDEX invoice_item_header ON invoice_items(invoice_id);
CREATE INDEX allocation_invoice ON payment_allocations(invoice_id);
CREATE INDEX credit_invoice ON credit_notes(invoice_id);
CREATE INDEX ticket_order ON tickets(order_id);
CREATE INDEX ticket_event_date ON ticket_events(ticket_id,occurred_on,id);
CREATE INDEX forecast_run_product ON forecasts(product_id,run_id);
CREATE INDEX document_scope ON documents(access_scope,category);
CREATE INDEX document_link_parent ON document_links(document_id);
CREATE VIEW invoice_balances AS
 SELECT i.*, i.total_pence
 -COALESCE((SELECT SUM(a.amount_pence) FROM payment_allocations a WHERE a.invoice_id=i.id),0)
 -COALESCE((SELECT SUM(c.amount_pence) FROM credit_notes c WHERE c.invoice_id=i.id),0)
 AS outstanding_pence FROM invoices i;
CREATE VIEW order_fulfillment AS
 SELECT oi.*,COALESCE((SELECT SUM(s.quantity) FROM shipment_items s WHERE s.order_item_id=oi.id),0)
 AS shipped_quantity FROM order_items oi;
CREATE VIEW monthly_customer_sales AS
 SELECT o.customer_id,substr(i.posted_on,1,7) AS month,
 SUM(i.total_pence-COALESCE((SELECT SUM(c.amount_pence) FROM credit_notes c WHERE c.invoice_id=i.id),0))
 AS sales_pence FROM invoices i JOIN orders o ON o.id=i.order_id GROUP BY 1,2;
