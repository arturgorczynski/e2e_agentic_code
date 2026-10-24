"""Deterministic English company documents from authored guidance and linked facts."""

import hashlib
import json

from acme.company_data import AS_OF, VERSION, insert
from acme.source_data import write_json

PROCEDURES = [
    (
        "Order intake",
        "sales",
        (
            "Confirm the customer account and exact product identifiers. Read the current order "
            "before discussing changes. A repeated product description is not proof that two "
            "order lines are duplicates."
        ),
        (
            "Compare quantities and source basket references. Keep cancelled orders distinct from "
            "unfulfilled orders. Escalate a requested change because the learning tool inventory "
            "does not edit orders."
        ),
        "orders",
    ),
    (
        "Invoice reconciliation",
        "finance",
        (
            "Read the invoice header and every invoice line. Sum posted integer-pence amounts and "
            "compare that total with the header before discussing settlement."
        ),
        (
            "Subtract only allocations to this invoice and its valid credit notes. Report an "
            "inconsistency with its record IDs; do not repair financial postings through a "
            "report."
        ),
        "invoices",
    ),
    (
        "Payment allocation review",
        "finance",
        (
            "Find the payment's customer and compare it with the customer on the destination "
            "invoice. Check receipt and allocation dates before accepting the link."
        ),
        (
            "Allocated amounts cannot exceed the payment. An unallocated balance is not a settled "
            "invoice. The assistant reads evidence but cannot allocate or move money."
        ),
        "payments",
    ),
    (
        "Credit-note explanation",
        "finance",
        (
            "Read the reason and issue date on the credit note. Confirm that the related invoice "
            "was already posted and belongs to the account under discussion."
        ),
        (
            "Distinguish the reduction of a receivable from a cash refund and from returned "
            "physical goods. Require separate evidence for either of those events."
        ),
        "credit_notes",
    ),
    (
        "Split dispatch review",
        "operations",
        (
            "Read every shipment for the order, then group shipment items by order-item "
            "identifier. One shipment can complete one line and leave another partially supplied."
        ),
        (
            "Compare dispatched and ordered units line by line. Do not infer carrier delivery "
            "from warehouse dispatch or quote a purchase-order ETA as a delivery guarantee."
        ),
        "shipments",
    ),
    (
        "Available-stock check",
        "operations",
        (
            "Select the warehouse and product together. Subtract reservations from on-hand units "
            "before comparing the result with a new request."
        ),
        (
            "Use purchase orders to explain possible replenishment, keeping their future "
            "quantities out of current availability. Route the quantified shortage to purchasing."
        ),
        "inventory",
    ),
    (
        "Purchase-order follow-up",
        "operations",
        (
            "Read the supplier, expected date and purchase-order lines. Sum linked goods receipts "
            "rather than assuming that an expected date proves receipt."
        ),
        (
            "An open line remains inbound. Escalate a missed ETA with the line ID and quantity; "
            "the assistant cannot place or accelerate a purchase order."
        ),
        "purchase_orders",
    ),
    (
        "Goods receiving",
        "operations",
        (
            "Compare the received product and quantity with the purchase-order line. Record "
            "discrepancies through an operations process before accepting a stock explanation."
        ),
        (
            "A valid receipt has one positive linked stock movement at the purchase order's "
            "warehouse. Do not relabel a source cancellation as received stock."
        ),
        "goods_receipts",
    ),
    (
        "Stock-ledger reconciliation",
        "operations",
        (
            "Start with the opening movement, add receipts and subtract dispatches by warehouse "
            "and product. Order events by date, treating receipts before dispatches on the same "
            "day."
        ),
        (
            "The running balance may never be negative. Compare the ending balance with on-hand "
            "stock and separately verify reservations against outstanding order lines."
        ),
        "stock_movements",
    ),
    (
        "Complaint evidence review",
        "support",
        (
            "Read the ticket and its linked order, then request missing product, quantity or "
            "photographic evidence. Separate what the buyer reports from what dispatch records "
            "establish."
        ),
        (
            "Show an explicit proposal before an open-to-in_progress change. Rejection preserves "
            "the ticket. Approval cannot authorize a refund or a credit note."
        ),
        "tickets",
    ),
    (
        "Ticket-history handoff",
        "support",
        (
            "Read events in date order and identify the last recorded state. Keep the original "
            "description visible beside follow-up notes."
        ),
        (
            "A resolution must explain the evidence and outcome. Do not erase prior events or "
            "claim a resolved case merely because a draft reply was prepared."
        ),
        "ticket_events",
    ),
    (
        "Customer account handoff",
        "sales",
        (
            "Identify the account manager, billing-country assumption and payment terms. Verify "
            "the source customer identifier before combining purchasing history."
        ),
        (
            "Synthetic names and contact addresses are training labels, not discovered "
            "identities. Customer email addresses use reserved example domains and must not be "
            "contacted."
        ),
        "customers",
    ),
    (
        "Product substitution review",
        "sales",
        (
            "Compare exact stock codes, descriptions and product guides. Similar names or "
            "categories do not establish compatible dimensions, materials or safety properties."
        ),
        (
            "Historical prices are observations, not an approved quotation. Escalate a "
            "substitution to a human product owner rather than promising equivalence."
        ),
        "products",
    ),
    (
        "Historical-price explanation",
        "sales",
        (
            "Show the product, observation date and original source-row identifier for each "
            "selected price. Multiple prices on one date can represent different baskets."
        ),
        (
            "Retain the exact decimal string. Do not silently turn an observed price into a "
            "current price list; posted lines use the documented half-up rounding rule."
        ),
        "price_history",
    ),
    (
        "Monthly sales comparison",
        "analytics",
        (
            "Choose the same customer scope and complete calendar months. Name the "
            "posted-sales-less-credit basis and cite the aggregate's contributing records."
        ),
        (
            "Compute current minus previous and divide by previous for percentage change. A zero "
            "denominator is undefined; a numerical decline alone does not establish a cause."
        ),
        "invoices",
    ),
    (
        "Forecast version comparison",
        "analytics",
        (
            "Choose forecasts for the same product and target period. Compare method versions, "
            "lookback windows and training input fingerprints before comparing their numbers."
        ),
        (
            "Recompute from invoices posted before the cutoff. Keep target actuals outside "
            "generation and flag incomplete actual periods when evaluating accuracy."
        ),
        "forecasts",
    ),
    (
        "Owned report review",
        "sales",
        (
            "Show the concrete report title, contents, source versions and operation ID to the "
            "conversation owner. Wait for a decision before claiming a saved result."
        ),
        (
            "After edits or restart, revalidate scope and ownership. Repeated approval must "
            "return one saved artifact; rejection must leave no report behind."
        ),
        "orders",
    ),
    (
        "Policy version lookup",
        "sales",
        (
            "Extract the event date from the question and find the document version whose "
            "effective interval contains it. Use the business reference date for today."
        ),
        (
            "Cite historical and current versions separately when comparing them. A superseded "
            "version remains valid evidence for its historical interval."
        ),
        "documents",
    ),
]
ROLE_OWNER = {
    "sales": ("EMP-003", "general"),
    "finance": ("EMP-001", "finance"),
    "operations": ("EMP-002", "operations"),
    "support": ("EMP-005", "support"),
    "analytics": ("EMP-004", "analytics"),
}

# Authored long-form material for the future RAG lessons. Each source is kept
# separately so the fixed catalog and SQLite metadata receive the same version.
RAG_SOURCES = (
    (
        "FIN-YTD-2011",
        "2011 year-to-date billing and cash evidence",
        "financial_reports",
        "EMP-001",
        "finance",
        "DEP-FINANCE",
    ),
    (
        "FIN-RECEIVABLES-2011",
        "Receivables aging study",
        "financial_reports",
        "EMP-001",
        "finance",
        "DEP-FINANCE",
    ),
    (
        "FIN-CASH-2011",
        "Billing versus receipt timing",
        "financial_reports",
        "EMP-001",
        "finance",
        "DEP-FINANCE",
    ),
    (
        "SCI-FORECAST-2011",
        "Evaluating wholesale demand forecasts",
        "research_notes",
        "EMP-004",
        "analytics",
        "DEP-ANALYTICS",
    ),
    (
        "SCI-STOCK-2011",
        "Inventory availability and replenishment evidence",
        "research_notes",
        "EMP-002",
        "operations",
        "DEP-LOGISTICS",
    ),
    (
        "SCI-QUALITY-2011",
        "Monitoring dispatch quality",
        "research_notes",
        "EMP-002",
        "operations",
        "DEP-LOGISTICS",
    ),
)


def metadata_and_body(path):
    text = path.read_text("utf-8")
    _, metadata, body = text.split("---\n", 2)
    return json.loads(metadata), body


def add_document(
    db,
    folder,
    catalog,
    identifier,
    title,
    category,
    owner,
    scope,
    body,
    links,
    facts=None,
    version=1,
    effective_from=AS_OF,
    effective_until=None,
):
    if version == 1:
        insert(
            db,
            "documents",
            id=identifier,
            title=title,
            category=category,
            owner_employee_id=owner,
            access_scope=scope,
        )
        for index, (column, value) in enumerate(links, 1):
            insert(
                db,
                "document_links",
                id=f"{identifier}:LINK-{index}",
                document_id=identifier,
                **{column: value},
            )
    relative = f"content/{identifier}.v{version}.md"
    status = "superseded" if effective_until else "current"
    metadata = {
        "document_id": identifier,
        "version": version,
        "owner_employee_id": owner,
        "access_scope": scope,
        "category": category,
        "effective_from": effective_from,
        "effective_until": effective_until,
        "status": status,
        "record_links": dict(links),
        "facts": facts or {},
    }
    text = "---\n" + json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n---\n"
    text += body.strip() + f"\n\nBusiness reference: {AS_OF}. Dataset: {VERSION}.\n"
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    insert(
        db,
        "document_versions",
        id=f"{identifier}:v{version}",
        document_id=identifier,
        version=version,
        effective_from=effective_from,
        effective_until=effective_until,
        status=status,
        relative_path=relative,
        sha256=digest,
    )
    catalog.append({**metadata, "title": title, "relative_path": relative, "sha256": digest})


def product_facts(db, sku):
    product = dict(
        db.execute(
            (
                "SELECT p.id,p.name,c.name AS category,c.handling_note,p.supplier_id FROM "
                "products p JOIN categories c ON c.id=p.category_id WHERE p.id=?"
            ),
            (sku,),
        ).fetchone()
    )
    product.update(
        dict(
            db.execute(
                (
                    "SELECT COUNT(*) AS observed_lines,COALESCE(SUM(quantity),0) AS "
                    "ordered_units,MIN(o.ordered_at) AS first_order,MAX(o.ordered_at) AS "
                    "last_order FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE "
                    "oi.product_id=?"
                ),
                (sku,),
            ).fetchone()
        )
    )
    product.update(
        dict(
            db.execute(
                (
                    "SELECT on_hand,reserved,on_hand-reserved AS available FROM inventory WHERE "
                    "product_id=? AND warehouse_id='WH-CVT'"
                ),
                (sku,),
            ).fetchone()
        )
    )
    return product


def customer_facts(db, cid):
    result = dict(
        db.execute(
            (
                "SELECT c.id,c.name,c.payment_terms_days,c.segment,a.country FROM customers c "
                "JOIN addresses a ON a.id=c.address_id WHERE c.id=?"
            ),
            (cid,),
        ).fetchone()
    )
    result.update(
        dict(
            db.execute(
                (
                    "SELECT COUNT(*) AS orders,MIN(ordered_at) AS first_order,MAX(ordered_at) AS "
                    "last_order FROM orders WHERE customer_id=?"
                ),
                (cid,),
            ).fetchone()
        )
    )
    result["outstanding_pence"] = db.execute(
        (
            "SELECT COALESCE(SUM(i.outstanding_pence),0) FROM invoice_balances i JOIN orders o ON "
            "o.id=i.order_id WHERE o.customer_id=?"
        ),
        (cid,),
    ).fetchone()[0]
    return result


def incident_facts(db, tid):
    return dict(
        db.execute(
            (
                "SELECT t.id,t.order_id,t.topic,t.opened_on,t.status,t.description,o.customer_id "
                "FROM tickets t JOIN orders o ON o.id=t.order_id WHERE t.id=?"
            ),
            (tid,),
        ).fetchone()
    )


def planning_facts(db, fid):
    return dict(
        db.execute(
            (
                "SELECT f.id,f.product_id,f.units,f.training_units,f.input_sha256,r.id AS "
                "run_id,r.method_version,r.lookback_months,r.training_cutoff,"
                "r.target_start,r.target_end "
                "FROM forecasts f JOIN forecast_runs r ON r.id=f.run_id WHERE f.id=?"
            ),
            (fid,),
        ).fetchone()
    )


def department_facts(db, did):
    result = dict(
        db.execute("SELECT id,name,responsibility FROM departments WHERE id=?", (did,)).fetchone()
    )
    result["headcount"] = db.execute(
        "SELECT COUNT(*) FROM employee_assignments WHERE department_id=? AND valid_until IS NULL",
        (did,),
    ).fetchone()[0]
    return result


def build_documents(db, project, folder, profile):
    contract = json.loads((project / "data/company/company.json").read_text("utf-8"))
    catalog = []
    for identifier, policy in contract["document_contracts"].items():
        body = (project / "data/document_sources/core" / f"{identifier}.md").read_text("utf-8")
        scope = policy["scope"]
        owner = next((value[0] for value in ROLE_OWNER.values() if value[1] == scope), "EMP-003")
        links = [
            (
                "department_id",
                {
                    "finance": "DEP-FINANCE",
                    "operations": "DEP-LOGISTICS",
                    "support": "DEP-SUPPORT",
                    "analytics": "DEP-ANALYTICS",
                }.get(scope, "DEP-SALES"),
            )
        ]
        if identifier == "POL-RETURNS-001":
            add_document(
                db,
                folder,
                catalog,
                identifier,
                "Commercial return window",
                "policies",
                owner,
                scope,
                body.replace("{{WINDOW_DAYS}}", "14"),
                links,
                {"window_days": 14},
                effective_from="2011-01-01",
                effective_until="2011-10-31",
            )
            add_document(
                db,
                folder,
                catalog,
                identifier,
                "Commercial return window",
                "policies",
                owner,
                scope,
                body.replace("{{WINDOW_DAYS}}", "30"),
                links,
                {"window_days": 30},
                version=2,
                effective_from="2011-11-01",
            )
        else:
            add_document(
                db,
                folder,
                catalog,
                identifier,
                body.splitlines()[0][2:],
                "policies",
                owner,
                scope,
                body,
                links,
                effective_from="2011-01-01",
            )
    for index, (title, role, action, control, table) in enumerate(PROCEDURES, 1):
        owner, scope = ROLE_OWNER[role]
        sample = db.execute(f"SELECT id FROM {table} ORDER BY id LIMIT 1").fetchone()[0]
        body = (
            f"# {title}\n\n## Purpose and starting evidence\n\n{action}\n\n## Review "
            f"sequence\n\nOpen the {table} record and follow its linked records. A concrete "
            f"baseline reference is `{sample}`. Check identity and the fixed business date before "
            f"interpreting its state. Keep identifiers in the answer so another employee can "
            f"reproduce the lookup.\n\n## Decision and escalation\n\n{control}\n\nIf evidence is "
            f"missing, describe the missing record and stop at that uncertainty. Do not fill the "
            f"gap with a likely date, amount or status. Preserve the distinction between reading "
            f"evidence, proposing a change and completing an authorized change.\n\n## Handoff "
            f"evidence\n\nRecord the actor, business date, reviewed IDs and unresolved "
            f"discrepancy. Include source versions when drafting a report; its review and save "
            f"are separate from this business operation."
        )
        department = {
            "sales": "DEP-SALES",
            "finance": "DEP-FINANCE",
            "operations": "DEP-LOGISTICS",
            "support": "DEP-SUPPORT",
            "analytics": "DEP-ANALYTICS",
        }[role]
        add_document(
            db,
            folder,
            catalog,
            f"PROC-{index:03}",
            title,
            "procedures",
            owner,
            scope,
            body,
            [("department_id", department)],
            {"sample_table": table, "sample_id": sample},
        )
    limit = 40 if profile == "full" else 12
    products = db.execute(
        (
            "SELECT oi.product_id,COUNT(DISTINCT oi.order_id) AS units FROM order_items oi "
            "JOIN products p "
            "ON p.id=oi.product_id WHERE p.source_stock_code IS NOT NULL GROUP BY oi.product_id "
            "ORDER BY units DESC,oi.product_id LIMIT ?"
        ),
        (limit,),
    ).fetchall()
    for index, (sku, _) in enumerate(products, 1):
        facts = product_facts(db, sku)
        body = (
            f"# Product guide: {facts['name']}\n\n## Identity and purchasing history\n\nStock "
            f"reference `{sku}` belongs to {facts['category']}. The catalog name comes from the "
            f"first selected source occurrence. Later descriptions and prices remain on "
            f"individual source lines. This product appears on {facts['observed_lines']} selected "
            f"order lines totaling {facts['ordered_units']} units, from {facts['first_order']} "
            f"through {facts['last_order']}. These figures describe selected baskets, not the "
            f"entire public dataset.\n\n## Fulfillment at Coventry\n\nAt the business reference "
            f"date the modeled stock is {facts['on_hand']} on hand, {facts['reserved']} reserved "
            f"and {facts['available']} available. Reservations belong to outstanding order lines. "
            f"Inspect them before accepting another request. Supply is assigned to "
            f"`{facts['supplier_id']}` under a fictional category-based sourcing rule. Check open "
            f"purchase lines for timing; the supplier link does not prove a current delivery "
            f"promise.\n\n## Handling and substitution\n\n{facts['handling_note']} These are "
            f"authored warehouse handling suggestions, not manufacturer specifications. Do not "
            f"infer dimensions, certifications, food-contact suitability or material composition "
            f"from the description. Compare the exact stock code before suggesting a "
            f"substitute.\n\n## Price evidence\n\nUse this product's price_history rows for "
            f"observed prices and source-row references. They are transaction observations, not a "
            f"current quotation. Keep original precision and apply the posted-line rounding rule "
            f"only when interpreting monetary totals."
        )
        add_document(
            db,
            folder,
            catalog,
            f"PROD-{index:03}",
            f"Product guide: {facts['name']}",
            "product_guides",
            "EMP-002",
            "operations",
            body,
            [("product_id", sku)],
            facts,
        )
    limit = 25 if profile == "full" else 8
    customers = db.execute(
        (
            "SELECT customer_id,COUNT(*) AS n FROM orders WHERE source_invoice_no IS NOT NULL "
            "GROUP BY customer_id ORDER BY n DESC,customer_id LIMIT ?"
        ),
        (limit,),
    ).fetchall()
    for index, (cid, _) in enumerate(customers, 1):
        facts = customer_facts(db, cid)
        # General terms must not leak finance-only balances into search excerpts.
        public_facts = {key: value for key, value in facts.items() if key != "outstanding_pence"}
        body = (
            f"# Account terms: {facts['name']}\n\n## Account identity\n\nUse `{cid}` as the "
            f"stable account reference. The first selected source country is {facts['country']}; "
            f"the account name and {facts['segment'].lower()} segment are fictional. The training "
            f"contact uses a reserved example-domain address. It is not a contact discovered "
            f"about the real retailer's customer.\n\n## Terms and purchasing context\n\nThe "
            f"modeled payment term is {facts['payment_terms_days']} calendar days after invoice "
            f"posting. These terms are assigned by the Acme rule, not extracted from UCI. There "
            f"are {facts['orders']} selected orders between {facts['first_order']} and "
            f"{facts['last_order']}. Compare orders within that coverage before assuming an "
            f"account is inactive or growing.\n\n## Service handoff\n\nSales owns commercial "
            f"coordination. For a delivery question, obtain the specific order and its shipment "
            f"lines. A source country label is insufficient to infer a postal address, route or "
            f"guaranteed lead time. For settlement detail, refer the case to finance rather than "
            f"exposing allocations through a general account summary.\n\n## "
            f"Exceptions\n\nCancelled orders remain in history, partial consignments retain "
            f"outstanding lines, and a credit note requires its own evidence. Quotation changes, "
            f"refunds and order edits are outside the first assistant's write tools. A report can "
            f"identify the required human review without claiming it has taken place."
        )
        add_document(
            db,
            folder,
            catalog,
            f"TERMS-{index:03}",
            f"Account terms: {facts['name']}",
            "customer_terms",
            "EMP-003",
            "general",
            body,
            [("customer_id", cid)],
            public_facts,
        )
    for index, (did,) in enumerate(
        db.execute("SELECT id FROM departments ORDER BY id").fetchall(), 1
    ):
        facts = department_facts(db, did)
        owner = db.execute(
            (
                "SELECT employee_id FROM employee_assignments WHERE department_id=? ORDER BY "
                "employee_id LIMIT 1"
            ),
            (did,),
        ).fetchone()[0]
        body = (
            f"# {facts['name']}: responsibilities and handoffs\n\n## Current team\n\nThe "
            f"department `{did}` has {facts['headcount']} assigned employees in this dataset "
            f"profile. Its remit is: {facts['responsibility']}. Assignment records name each "
            f"employee's operating location and effective interval. A role title in the directory "
            f"does not grant an application permission.\n\n## Daily evidence\n\nStart from the "
            f"business record relevant to that remit and retain its identifier when handing work "
            f"to another team. Check the fixed business date before calling an item overdue, "
            f"incomplete or current. Preserve prior events rather than replacing the story with a "
            f"single status label.\n\n## Cross-team boundaries\n\nSales explains account and "
            f"order context; operations validates stock and fulfillment; finance controls payment "
            f"evidence; support records service investigations; analytics distinguishes observed "
            f"results from assumptions. Escalate questions outside this department's remit to the "
            f"owning function. Do not claim a handoff message was sent by the learning "
            f"assistant.\n\n## Information hygiene\n\nEmployee names and assignments are authored "
            f"training records. The directory contains no salary or private HR details. "
            f"Conversations and reports remain private to their authenticated owner, including "
            f"when their subject concerns this department. Use approved document scopes rather "
            f"than copying restricted evidence into a general team note."
        )
        add_document(
            db,
            folder,
            catalog,
            f"DEPT-{index:03}",
            f"{facts['name']} responsibilities",
            "department_instructions",
            owner,
            "general",
            body,
            [("department_id", did)],
            facts,
        )
    limit = 25 if profile == "full" else 5
    tickets = db.execute(
        (
            "SELECT id FROM tickets ORDER BY CASE topic WHEN 'damaged_goods' THEN 0 WHEN "
            "'invoice_copy' THEN 1 ELSE 2 END,opened_on DESC,id LIMIT ?"
        ),
        (limit,),
    ).fetchall()
    for index, (tid,) in enumerate(tickets, 1):
        facts = incident_facts(db, tid)
        events = [
            dict(row)
            for row in db.execute(
                (
                    "SELECT occurred_on,status,note FROM ticket_events WHERE ticket_id=? ORDER BY "
                    "occurred_on,id"
                ),
                (tid,),
            )
        ]
        timeline = "\n".join(f"- {e['occurred_on']}: {e['status']}. {e['note']}" for e in events)
        facts["events"] = events
        body = (
            f"# Service note: {tid}\n\n## Recorded situation\n\nTicket `{tid}` concerns order "
            f"`{facts['order_id']}` for account `{facts['customer_id']}`. It opened on "
            f"{facts['opened_on']} with topic {facts['topic']}. The recorded description is: "
            f"{facts['description']} This case is simulated around a company order; UCI did not "
            f"provide support messages.\n\n## Evidence timeline\n\n{timeline}\n\nThe current "
            f"recorded state is **{facts['status']}**. The event history, rather than the "
            f"existence of this note, supports that state. Check shipment lines for a quantity "
            f"question and finance-authorized invoice evidence for a settlement question.\n\n## "
            f"Follow-up boundary\n\nTreat the buyer's report as a report until corroborated. An "
            f"open case needs an explicit reviewed proposal before moving to in_progress. A "
            f"closed case remains available for historical analysis; this note does not reopen "
            f"it. Neither state grants permission for compensation, a refund or a stock "
            f"adjustment.\n\n## Handoff\n\nPreserve the ticket and order IDs, identify missing "
            f"evidence, and separate the next suggested action from a completed action. Do not "
            f"infer a new customer delivery date from an inbound supplier ETA."
        )
        add_document(
            db,
            folder,
            catalog,
            f"INC-{index:03}",
            f"Service note: {tid}",
            "incident_notes",
            "EMP-005",
            "support",
            body,
            [("ticket_id", tid), ("order_id", facts["order_id"])],
            facts,
            effective_from=events[-1]["occurred_on"],
        )
    limit = 20 if profile == "full" else 4
    forecasts = db.execute(
        (
            "SELECT f.id FROM forecasts f JOIN forecast_runs r ON r.id=f.run_id ORDER BY "
            "r.target_start DESC,f.product_id,r.method_version LIMIT ?"
        ),
        (limit,),
    ).fetchall()
    for index, (fid,) in enumerate(forecasts, 1):
        facts = planning_facts(db, fid)
        body = (
            f"# Planning note: {facts['product_id']} / {facts['target_start']} / "
            f"v{facts['method_version']}\n\n## Frozen estimate\n\nForecast `{fid}` belongs to run "
            f"`{facts['run_id']}`. It estimates **{facts['units']} units** for "
            f"{facts['target_start']} through {facts['target_end']}. Its training cutoff is "
            f"{facts['training_cutoff']}; the method averages {facts['lookback_months']} "
            f"preceding complete calendar months containing {facts['training_units']} billed "
            f"units. Missing months count as zero.\n\n## Reproduce the estimate\n\nSelect this "
            f"product's invoice lines within that lookback and strictly before the target start. "
            f"Divide their total units by {facts['lookback_months']} and round half up to one "
            f"unit. The recorded input fingerprint is `{facts['input_sha256']}`. It names the "
            f"exact ordered input rows, not a hash of later actual results.\n\n## "
            f"Interpretation\n\nThis is a simple teaching forecast with reconstructed historical "
            f"generation time. It does not model promotions, lead-time uncertainty or the "
            f"excluded public baskets. Compare another version only for the same product and "
            f"target period; shorter history can respond differently without being automatically "
            f"better.\n\n## Evaluation boundary\n\nUse target-period billed units only after "
            f"generation to calculate actual minus forecast. Percentage error divides by forecast "
            f"and is undefined for a zero forecast. December is incomplete at the business "
            f"reference date. Sales targets are explicitly simulated stretch goals; warehouse "
            f"replenishment is retrospective and must not be cited as forecasting evidence."
        )
        add_document(
            db,
            folder,
            catalog,
            f"PLAN-{index:03}",
            f"Planning note: {fid}",
            "planning_commentary",
            "EMP-004",
            "analytics",
            body,
            [("forecast_id", fid), ("product_id", facts["product_id"])],
            facts,
            effective_from=facts["target_start"],
        )
    for identifier, title, category, owner, scope, department in RAG_SOURCES:
        body = (project / "data/document_sources/rag" / f"{identifier}.md").read_text("utf-8")
        add_document(
            db,
            folder,
            catalog,
            identifier,
            title,
            category,
            owner,
            scope,
            body,
            [("department_id", department)],
            facts={"provenance": "authored_acme_learning_document"},
            effective_from=AS_OF,
        )

    write_json(
        folder / "catalog.json",
        {"dataset_version": VERSION, "business_reference": AS_OF, "documents": catalog},
    )
    return len({row["document_id"] for row in catalog}), len(catalog)
