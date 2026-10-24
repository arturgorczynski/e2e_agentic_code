"""Build linked company records from complete observed baskets and explicit rules.

This maintainer command is deliberately separate from exercise initialization.
No random generator defines business behaviour, and no model is called.
"""

import calendar
import csv
import gzip
import hashlib
import json
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from acme.source_data import verify_prepared

VERSION = "acme-company-v8"
AS_OF = "2011-12-09"
SUPPLIER_PROFILES = (
    ("Beacon Lighting & Candle Co.", "Alder Works, Coventry, West Midlands", 8),
    ("Hearth Tableware Ltd", "Canal Quarter, Stoke-on-Trent, Staffordshire", 12),
    ("Solstice Seasonal Goods Ltd", "Mill Yard, York, North Yorkshire", 10),
    ("Ledger Paper & Office Ltd", "Station Works, Nottingham, Nottinghamshire", 6),
    ("Fold Packaging Co.", "Bridge Business Park, Leicester, Leicestershire", 9),
    ("Weave Home Textiles Ltd", "Foundry Quarter, Manchester, Greater Manchester", 13),
    ("Orchard Homewares Ltd", "Riverside Trade Park, Bristol, Somerset", 7),
)
GENERATED_JOB_TITLES = {
    "DEP-SALES": (
        "Account manager", "Wholesale sales executive", "Sales coordinator",
        "Key accounts executive",
    ),
    "DEP-WAREHOUSE": (
        "Warehouse operative", "Stock controller", "Goods-in operative",
        "Picking team lead", "Returns processor",
    ),
    "DEP-PURCHASE": (
        "Buyer", "Procurement coordinator", "Replenishment planner", "Supplier liaison",
    ),
    "DEP-FINANCE": (
        "Accounts receivable clerk", "Credit controller", "Billing specialist", "Finance analyst",
    ),
    "DEP-SUPPORT": (
        "Customer service advisor", "Service case coordinator", "Returns advisor",
        "Customer support lead",
    ),
    "DEP-LOGISTICS": (
        "Dispatch coordinator", "Carrier liaison", "Delivery exceptions analyst",
        "Transport planner",
    ),
    "DEP-ANALYTICS": ("Demand analyst", "Reporting analyst", "Inventory planner"),
    "DEP-PEOPLE": ("People operations advisor", "HR administrator", "Recruitment coordinator"),
    "DEP-IT": ("IT support analyst", "Systems administrator", "Application support specialist"),
    "DEP-LEADERSHIP": (
        "Operations director", "Commercial director", "Finance director", "Managing director",
    ),
}
CATEGORIES = [
    (
        "CAT-LIGHT",
        "Lighting and candles",
        "CANDLE|LIGHT|LANTERN",
        "Keep glass fittings separated; inspect holders for chips before dispatch.",
    ),
    (
        "CAT-KITCHEN",
        "Kitchen and tableware",
        "CUP|MUG|PLATE|BOWL|CAKE|TEA|COFFEE|CUTLERY",
        "Use dividers for ceramic items; check that matched sets contain the listed pieces.",
    ),
    (
        "CAT-SEASON",
        "Seasonal decorations",
        "CHRISTMAS|XMAS|EASTER|SANTA|SNOW|ADVENT",
        "Keep seasonal lots identifiable; review seasonal stock before the next buying cycle.",
    ),
    (
        "CAT-STATIONERY",
        "Stationery",
        "PENCIL|PEN |NOTEBOOK|NOTEPAD|STATIONERY|RULER",
        "Protect paper goods from moisture and keep mixed designs distinguishable.",
    ),
    (
        "CAT-PACK",
        "Packaging and storage",
        "BAG|BOX|WRAP|BASKET|TIN|CASE",
        "Avoid crushing; compare dimensions and closures before treating designs as substitutes.",
    ),
    (
        "CAT-TEXTILE",
        "Textiles",
        "CUSHION|APRON|TOWEL|DOORMAT|NAPKIN",
        (
            "Keep dry and separated from fragile goods; do not infer washing instructions from "
            "the name."
        ),
    ),
    (
        "CAT-HOME",
        "Home and gift accessories",
        "fallback",
        (
            "Check the exact design and finish; related descriptions do not establish "
            "interchangeability."
        ),
    ),
]
FIRST_NAMES = (
    "Amelia Oliver Isla Noah Ava George Freya Arthur Mia Leo Grace Oscar Sofia Henry Evie Jack "
    "Lily Charlie Emily Thomas Sophie Harry Alice Theo Ruby Jacob Florence Finley Charlotte "
    "William Phoebe Archie Jessica Lucas Sienna Ethan Daisy Isaac Matilda Joshua Erin James Chloe "
    "Samuel Esme Benjamin Eleanor Daniel"
).split()
LAST_NAMES = (
    "Wilson Davies Evans Thomas Roberts Johnson Lewis Walker Robinson Wood Thompson White Watson "
    "Jackson Wright Green Harris Cooper King Lee Martin Clarke Allen Scott Hill Moore Young "
    "Taylor Brown Edwards Turner Baker Mitchell Carter Phillips Collins Parker Bennett Hughes "
    "Ward"
).split()
CUSTOMER_FIRST = (
    "Alder",
    "Ashford",
    "Bramble",
    "Briar",
    "Brookfield",
    "Cedar",
    "Cotswold",
    "Dunbar",
    "Elm",
    "Fairfield",
    "Fern",
    "Foxglove",
    "Hartwell",
    "Hawthorn",
    "Holloway",
    "Ivory",
    "Kingsley",
    "Linden",
    "Marlow",
    "Meadow",
    "Morrow",
    "Northfield",
    "Oak",
    "Orchard",
    "Pembroke",
    "Riverside",
    "Rosewood",
    "Rowan",
    "Silver",
    "Stonefield",
    "Willow",
    "Wren",
)
CUSTOMER_SECOND = (
    "& Bell",
    "& Cole",
    "& Finch",
    "& Grove",
    "& Hart",
    "& Lane",
    "& Moss",
    "& Reed",
    "& Vale",
    "& Ward",
    "& West",
    "& Wood",
    "House",
    "Lane",
    "Market",
    "Trading",
)
CUSTOMER_TRADE = (
    "Homeware",
    "Gift Shop",
    "Interiors",
    "Tableware",
    "Living",
    "General Store",
    "Home & Gift",
    "Boutique",
    "Housewares",
    "Decor",
    "Retail",
    "Supplies",
)
DEMO_CUSTOMER_NAMES = (
    "Brookside Home & Gift",
    "Marlow Tableware",
    "The Willow Room",
    "Northgate General Store",
    "Cedar & Finch Interiors",
    "Harbour Housewares",
    "Orchard Market Goods",
    "Meadow Lane Gifts",
)
UK_LOCALITIES = (
    ("Coventry", "CV"),
    ("Bristol", "BS"),
    ("Leeds", "LS"),
    ("Nottingham", "NG"),
    ("Birmingham", "B"),
    ("York", "YO"),
    ("Bath", "BA"),
    ("Manchester", "M"),
    ("Cardiff", "CF"),
    ("Oxford", "OX"),
    ("Norwich", "NR"),
    ("Exeter", "EX"),
    ("Reading", "RG"),
    ("Newcastle", "NE"),
    ("Leicester", "LE"),
)
STREETS = (
    "Alder",
    "Bridge",
    "Canal",
    "Church",
    "Crown",
    "Elm",
    "Foundry",
    "Garden",
    "Harbour",
    "High",
    "King",
    "Market",
    "Meadow",
    "Mill",
    "Oak",
    "Orchard",
    "Park",
    "Queen",
    "Railway",
    "River",
    "Station",
    "Stone",
    "Union",
    "Willow",
)
INTERNATIONAL_LOCALITIES = {
    "France": "Lyon",
    "Germany": "Cologne",
    "Switzerland": "Basel",
    "Spain": "Valencia",
    "Australia": "Melbourne",
    "Japan": "Osaka",
    "Italy": "Bologna",
    "Channel Islands": "St Helier",
    "Portugal": "Porto",
    "Cyprus": "Limassol",
    "Norway": "Bergen",
    "USA": "Boston",
    "Canada": "Toronto",
    "Poland": "Kraków",
    "Israel": "Haifa",
    "EIRE": "Cork",
    "Denmark": "Aarhus",
    "United Arab Emirates": "Dubai",
    "Sweden": "Gothenburg",
    "Malta": "Sliema",
    "Greece": "Thessaloniki",
    "Finland": "Turku",
    "Belgium": "Ghent",
    "Netherlands": "Utrecht",
}


def customer_name(sequence):
    """A stable, non-numbered fictional trading name; source IDs remain unchanged."""
    if 9001 <= sequence <= 9008:
        return DEMO_CUSTOMER_NAMES[sequence - 9001]
    # Multiplication by 487 permutes all 6,144 combinations without collisions.
    code = (sequence * 487) % (len(CUSTOMER_FIRST) * len(CUSTOMER_SECOND) * len(CUSTOMER_TRADE))
    trade = CUSTOMER_TRADE[code % len(CUSTOMER_TRADE)]
    first = CUSTOMER_FIRST[(code // len(CUSTOMER_TRADE)) % len(CUSTOMER_FIRST)]
    second = CUSTOMER_SECOND[code // (len(CUSTOMER_TRADE) * len(CUSTOMER_FIRST))]
    return f"{first} {second} {trade}"


def customer_address(country, sequence):
    """Plausible but fictional billing location; never sourced from transaction data."""
    building = 5 + (sequence * 37) % 240
    street = STREETS[(sequence * 11) % len(STREETS)]
    if country == "United Kingdom":
        city, area = UK_LOCALITIES[(sequence * 7) % len(UK_LOCALITIES)]
        district = 1 + (sequence * 3) % 9
        inward = 1 + (sequence * 5) % 9
        letters = "ABCDEFGHJKLMNPRSTUVWXY"
        postcode = (
            letters[(sequence * 13) % len(letters)] + letters[(sequence * 17 + 3) % len(letters)]
        )
        unit = f"Unit {1 + sequence % 40}, " if sequence % 4 == 0 else ""
        return f"{unit}{building} {street} Street, {city}, {area}{district} {inward}{postcode}"
    city = INTERNATIONAL_LOCALITIES.get(country, "International trading district")
    return f"Suite {1 + sequence % 60}, {building} {street} Commerce Centre, {city}"


def generated_employee_profile(identifier, department_id):
    """Stable fictional role and hire date for a generated employee."""
    number = int(identifier.rsplit("-", 1)[-1])
    titles = GENERATED_JOB_TITLES[department_id]
    digest = hashlib.sha256(identifier.encode("ascii")).digest()
    hired_on = date(2007, 1, 1) + timedelta(days=int.from_bytes(digest[:4], "big") % 1700)
    return titles[number % len(titles)], hired_on.isoformat()


def account_manager_for(db, customer_id, source_customer_id):
    """Spread observed customer portfolios across active fictional sales staff."""
    if source_customer_id is None:
        return "EMP-003"
    sales = [
        row[0]
        for row in db.execute(
            "SELECT employee_id FROM employee_assignments "
            "WHERE department_id='DEP-SALES' AND valid_until IS NULL ORDER BY employee_id"
        )
    ]
    if not sales:
        raise ValueError("No active sales employees available for customer assignment")
    slot = int.from_bytes(hashlib.sha256(customer_id.encode("utf-8")).digest()[:8], "big")
    return sales[slot % len(sales)]


def insert(db, table, **record):
    """Insert internal, named fields. Table/field names never come from agent input."""
    columns = ",".join(record)
    placeholders = ",".join("?" for _ in record)
    db.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(record.values()))


def pence(quantity, price):
    return int((Decimal(str(price)) * quantity * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def shift(day, days):
    return (date.fromisoformat(day[:10]) + timedelta(days=days)).isoformat()


def business_shift(day, days):
    """Move a fictional workflow date by weekdays, leaving source dates intact."""
    current = date.fromisoformat(day[:10])
    direction = 1 if days >= 0 else -1
    for _ in range(abs(days)):
        current += timedelta(days=direction)
        while current.weekday() >= 5:
            current += timedelta(days=direction)
    return current.isoformat()


def modeled_acceptance(invoice_no, posted):
    """Fictional acceptance before the observed invoice, on a working day."""
    lead = 1 + stable_bucket(invoice_no + ":acceptance", 4)
    return business_shift(posted, -lead)


def modeled_dispatch(invoice_no, posted, country, has_second):
    """Preserve the old as-of shipment set while removing weekend dispatch."""
    old_first = shift(posted, 1 if country == "United Kingdom" else 3)
    if old_first > AS_OF:
        return None
    lead = (
        1 + stable_bucket(invoice_no + ":first-dispatch", 3)
        if country == "United Kingdom"
        else 2 + stable_bucket(invoice_no + ":first-dispatch", 4)
    )
    latest = business_shift(AS_OF, -1) if has_second else AS_OF
    return min(business_shift(posted, lead), latest)


def modeled_second_dispatch(invoice_no, first_day):
    lag = 2 + stable_bucket(invoice_no + ":second-dispatch", 4)
    return min(business_shift(first_day, lag), AS_OF)


def stable_bucket(label, size):
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % size


def supplier_batch_dates(week_start, supplier_id, lead_days):
    """Schedule a retrospective supplier batch before its dispatch week."""
    key = f"{supplier_id}:{week_start}"
    received = business_shift(week_start, -(1 + stable_bucket(key + ":receipt", 3)))
    if received < "2010-11-01":
        received = week_start
    expected = business_shift(received, stable_bucket(key + ":variance", 3) - 1)
    placed = business_shift(expected, -(lead_days + stable_bucket(key + ":lead", 3)))
    return placed, expected, received


def month_before(month, count):
    year, number = map(int, month[:7].split("-"))
    serial = year * 12 + number - 1 - count
    return f"{serial // 12:04}-{serial % 12 + 1:02}-01"


def category_for(description):
    # Preserve the historical classifier for ambiguous source wording and
    # override only clear product types it previously misplaced.
    value = description.upper()
    overrides = (
        ("CAT-KITCHEN", r"\bTEA\s+BAG\s+PLATES?\b"),
        ("CAT-HOME", r"\b(?:HOT\s+WATER\s+BOTTLES?|WITH\s+SCARF)\b"),
        ("CAT-PACK", r"(?<!TEA )\bBAGS?\b"),
        ("CAT-TEXTILE", r"\b(?:BACKPACKS?|SCARVES?|SCARFS?|TEA\s+TOWELS?)\b"),
        ("CAT-KITCHEN", r"\b(?:BEAKERS?|CAKE\s+CASES?)\b"),
        ("CAT-STATIONERY", r"\b(?:PENS?|ERASERS?)\b"),
        ("CAT-HOME", r"\b(?:COAT\s+HANGERS?|NAPKIN\s+CHARMS?)\b"),
    )
    for identifier, pattern in overrides:
        if re.search(pattern, value):
            return identifier
    for identifier, _, rule, _ in CATEGORIES[:-1]:
        if any(word in value for word in rule.split("|")):
            return identifier
    return "CAT-HOME"


def seed_organization(db, contract, profile):
    for item in contract["departments"]:
        insert(
            db,
            "departments",
            id=item["id"],
            name=item["name"],
            responsibility=item["responsibility"],
        )
    for item in contract["locations"]:
        insert(db, "locations", **item)
    remaining = {
        d["id"]: d["headcount"] if profile == "full" else 2 for d in contract["departments"]
    }
    people = list(contract["employees"])
    for person in people:
        remaining[person["department_id"]] -= 1
    for department in contract["departments"]:
        for _ in range(remaining[department["id"]]):
            number = len(people) + 1
            location = (
                "LOC-CVT"
                if department["id"] in {"DEP-WAREHOUSE", "DEP-LOGISTICS", "DEP-PURCHASE"}
                else "LOC-BRS"
            )
            if department["id"] == "DEP-SUPPORT":
                location = "LOC-LDS"
            surname_index = ((number - 6) * 7 + (number - 6) // len(FIRST_NAMES)) % len(LAST_NAMES)
            people.append(
                {
                    "id": f"EMP-{number:03}",
                    "name": (
                        f"{FIRST_NAMES[(number - 6) % len(FIRST_NAMES)]} "
                        f"{LAST_NAMES[surname_index]}"
                    ),
                    "department_id": department["id"],
                    "location_id": location,
                    "job_title": generated_employee_profile(
                        f"EMP-{number:03}", department["id"]
                    )[0],
                }
            )
    for person in people:
        hired_on = (
            generated_employee_profile(person["id"], person["department_id"])[1]
            if int(person["id"].rsplit("-", 1)[-1]) > len(contract["employees"])
            else "2009-06-01"
        )
        insert(
            db,
            "employees",
            id=person["id"],
            name=person["name"],
            job_title=person["job_title"],
            hired_on=hired_on,
            email=f"{person['id'].lower()}@acme.example",
            provenance="authored organization",
        )
        insert(
            db,
            "employee_assignments",
            id=f"ASG-{person['id']}",
            employee_id=person["id"],
            department_id=person["department_id"],
            location_id=person["location_id"],
            valid_from=hired_on,
            valid_until=None,
        )
    for identifier, location, name in [
        ("WH-CVT", "LOC-CVT", "Coventry distribution"),
        ("WH-LDS", "LOC-LDS", "Leeds returns and exceptions"),
    ]:
        insert(db, "warehouses", id=identifier, location_id=location, name=name)
    for index, (identifier, name, rule, handling) in enumerate(CATEGORIES, 1):
        insert(
            db,
            "categories",
            id=identifier,
            name=name,
            classification_rule=rule,
            handling_note=handling,
        )
        supplier_name, supplier_location, lead_days = SUPPLIER_PROFILES[index - 1]
        insert(
            db,
            "addresses",
            id=f"ADDR-SUP-{index}",
            label=supplier_location,
            country="United Kingdom",
            provenance="authored fictional business location; no delivery address asserted",
        )
        insert(
            db,
            "suppliers",
            id=f"SUP-{index:02}",
            name=supplier_name,
            address_id=f"ADDR-SUP-{index}",
            lead_days=lead_days,
            provenance="authored; category-based sourcing assumption",
        )


def customer(db, identifier, source, country, sequence):
    segment = ["Independent retail", "Online reseller", "Hospitality buyer"][sequence % 3]
    name = customer_name(sequence)
    terms = 30 if country == "United Kingdom" else 45
    insert(
        db,
        "addresses",
        id=f"ADDR-{identifier}",
        label=customer_address(country, sequence),
        country=country,
        provenance="source country; fictional billing location" if source else "authored scenario",
    )
    insert(
        db,
        "customers",
        id=identifier,
        source_customer_id=source,
        name=name,
        address_id=f"ADDR-{identifier}",
        account_manager_id=account_manager_for(db, identifier, source),
        payment_terms_days=terms,
        settlement_delay_days=(sequence % 7) * 3,
        segment=segment,
        provenance="observed ID/country; authored name, segment and terms"
        if source
        else "authored scenario",
    )
    insert(
        db,
        "customer_contacts",
        id=f"CONTACT-{identifier}",
        customer_id=identifier,
        name=f"{FIRST_NAMES[sequence % len(FIRST_NAMES)]} {LAST_NAMES[sequence % len(LAST_NAMES)]}",
        email=f"accounts.{identifier.lower()}@customers.example",
        responsibility=("Purchasing", "Accounts payable", "Order coordination")[sequence % 3],
    )


def product(db, identifier, source, name):
    category = category_for(name)
    supplier = next(i for i, entry in enumerate(CATEGORIES, 1) if entry[0] == category)
    insert(
        db,
        "products",
        id=identifier,
        source_stock_code=source,
        name=name,
        category_id=category,
        supplier_id=f"SUP-{supplier:02}",
        provenance="observed code/description; classified category and fictional supplier"
        if source
        else "authored scenario",
    )


def order(db, identifier, customer_id, posted, lines, source=None, cancelled=False):
    """One observed invoice basket becomes one reconstructed order, without line loss."""
    ordered = modeled_acceptance(source, posted) if source else shift(posted, -1)
    insert(
        db,
        "orders",
        id=identifier,
        source_invoice_no=source,
        customer_id=customer_id,
        ordered_at=ordered,
        status="cancelled" if cancelled else "confirmed",
        currency="GBP",
        provenance="reconstructed from complete UCI invoice" if source else "authored scenario",
    )
    insert(
        db,
        "order_status_history",
        id=f"{identifier}:00",
        order_id=identifier,
        occurred_at=ordered,
        status="confirmed",
        reason=(
            "Modeled weekday acceptance before observed invoice posting"
            if source else "Authored scenario acceptance before posting"
        ),
    )
    items = []
    for index, line in enumerate(lines, 1):
        sku, quantity, price, source_row = line
        item_id = f"{identifier}:L{index:03}"
        amount = pence(quantity, price)
        insert(
            db,
            "order_items",
            id=item_id,
            order_id=identifier,
            product_id=sku,
            quantity=quantity,
            raw_unit_price_gbp=price,
            line_pence=amount,
            source_row_id=source_row,
        )
        items.append((item_id, sku, quantity, amount))
        insert(
            db,
            "price_history",
            id=f"PRICE-{item_id}",
            product_id=sku,
            observed_at=posted,
            raw_unit_price_gbp=price,
            source_row_id=source_row,
            price_kind="observed" if source_row else "fixture",
        )
    if cancelled:
        insert(
            db,
            "order_status_history",
            id=f"{identifier}:99",
            order_id=identifier,
            occurred_at=posted,
            status="cancelled",
            reason="Authored cancellation before billing and dispatch",
        )
        return None, items
    terms = db.execute(
        "SELECT payment_terms_days FROM customers WHERE id=?", (customer_id,)
    ).fetchone()[0]
    invoice = f"INV-{source}" if source else identifier.replace("ORD", "INV")
    insert(
        db,
        "invoices",
        id=invoice,
        order_id=identifier,
        posted_on=posted,
        due_on=shift(posted, terms),
        total_pence=sum(item[3] for item in items),
        currency="GBP",
        provenance="source basket, line-rounded interpretation" if source else "authored scenario",
    )
    for item_id, _, quantity, amount in items:
        insert(
            db,
            "invoice_items",
            id=f"BILL-{item_id}",
            invoice_id=invoice,
            order_item_id=item_id,
            quantity=quantity,
            amount_pence=amount,
        )
    return invoice, items


def dispatch(db, identifier, order_id, day, lines, country="United Kingdom"):
    if identifier.startswith("DEMO-"):
        delivery = shift(day, 2 if country == "United Kingdom" else 5)
        carrier = (
            "Acme simulated domestic carrier"
            if country == "United Kingdom" else "Acme simulated export consolidator"
        )
    else:
        units = sum(quantity for _, _, quantity in lines)
        if country == "United Kingdom":
            carriers = (
                ("Cedar Parcel Network", "Northgate Business Parcels", "Merefield Courier")
                if units < 48 else ("Bridgegate Pallet Network", "Westmere Freight")
            )
            transit = 1 + stable_bucket(identifier + ":transit", 4)
        else:
            carriers = ("Harbourline Export Freight", "Channel Gate Consolidated")
            transit = 4 + stable_bucket(identifier + ":transit", 5)
        carrier = carriers[stable_bucket(identifier + ":carrier", len(carriers))]
        delivery = business_shift(day, transit)
    insert(
        db,
        "shipments",
        id=identifier,
        order_id=order_id,
        warehouse_id="WH-CVT",
        dispatched_on=day,
        delivered_on=delivery if delivery <= AS_OF else None,
        carrier=carrier,
        provenance="rule-based simulation",
    )
    for item_id, sku, quantity in lines:
        if quantity <= 0:
            continue
        line_id = f"{identifier}:{item_id}"
        insert(
            db,
            "shipment_items",
            id=line_id,
            shipment_id=identifier,
            order_item_id=item_id,
            quantity=quantity,
        )
        insert(
            db,
            "stock_movements",
            id=f"MOVE-{line_id}",
            warehouse_id="WH-CVT",
            product_id=sku,
            occurred_on=day,
            kind="dispatch",
            quantity=-quantity,
            shipment_item_id=line_id,
            goods_receipt_id=None,
        )


def finish_order(db, order_id):
    rows = db.execute(
        "SELECT quantity,shipped_quantity FROM order_fulfillment WHERE order_id=?", (order_id,)
    ).fetchall()
    status = (
        "fulfilled"
        if all(a == b for a, b in rows)
        else "partial"
        if any(b for _, b in rows)
        else "confirmed"
    )
    db.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    shipments = db.execute(
        "SELECT id,dispatched_on FROM shipments WHERE order_id=? ORDER BY dispatched_on,id",
        (order_id,),
    ).fetchall()
    for index, (_, day) in enumerate(shipments, 1):
        current = status if index == len(shipments) else "partial"
        insert(
            db,
            "order_status_history",
            id=f"{order_id}:{index:02}",
            order_id=order_id,
            occurred_at=day,
            status=current,
            reason="Derived from complete shipment lines",
        )


def pay(db, payment_id, invoice_id, day, amount):
    owner = db.execute(
        "SELECT o.customer_id FROM invoices i JOIN orders o ON o.id=i.order_id WHERE i.id=?",
        (invoice_id,),
    ).fetchone()[0]
    insert(
        db,
        "payments",
        id=payment_id,
        customer_id=owner,
        received_on=day,
        amount_pence=amount,
        currency="GBP",
        provenance="simulated settlement; not a UCI observation",
    )
    insert(
        db,
        "payment_allocations",
        id=f"ALLOC-{payment_id}",
        payment_id=payment_id,
        invoice_id=invoice_id,
        allocated_on=day,
        amount_pence=amount,
    )


def next_remittance_day(day, weekday):
    """Move a proposed receipt to an account's recurring weekday."""
    current = date.fromisoformat(day)
    return (current + timedelta(days=(weekday - current.weekday()) % 7)).isoformat()


def seed_source_payments(db):
    """Model account remittances without changing observed invoice evidence."""
    invoices = db.execute(
        "SELECT i.id,i.due_on,i.total_pence,o.customer_id,c.settlement_delay_days "
        "FROM invoices i JOIN orders o ON o.id=i.order_id "
        "JOIN customers c ON c.id=o.customer_id "
        "WHERE o.source_invoice_no IS NOT NULL ORDER BY o.customer_id,i.due_on,i.id"
    ).fetchall()
    batches = defaultdict(list)
    for invoice_id, due, total, customer_id, account_delay in invoices:
        if total <= 0:
            continue
        weekday = stable_bucket(customer_id + ":remittance-weekday", 5)
        timing = stable_bucket(invoice_id + ":receipt-timing", 31) - 18
        first = next_remittance_day(shift(due, account_delay + timing), weekday)
        split = total >= 30000 and stable_bucket(invoice_id + ":installments", 5) < 2
        first_amount = total
        if split:
            first_amount = total * (35 + stable_bucket(invoice_id + ":first-share", 41)) // 100
        if first <= AS_OF:
            batches[(customer_id, first)].append((invoice_id, first_amount))
        if split:
            interval = 7 + stable_bucket(invoice_id + ":second-interval", 15)
            second = next_remittance_day(shift(first, interval), weekday)
            if second <= AS_OF:
                batches[(customer_id, second)].append((invoice_id, total - first_amount))
    for (customer_id, day), allocations in sorted(batches.items()):
        payment_id = f"PAY-REM-{customer_id.removeprefix('UCI-CUST-')}-{day.replace('-', '')}"
        insert(
            db,
            "payments",
            id=payment_id,
            customer_id=customer_id,
            received_on=day,
            amount_pence=sum(amount for _, amount in allocations),
            currency="GBP",
            provenance="modeled account remittance; no observed payment or bank reference",
        )
        for invoice_id, amount in sorted(allocations):
            insert(
                db,
                "payment_allocations",
                id=f"ALLOC-{payment_id}-{invoice_id}",
                payment_id=payment_id,
                invoice_id=invoice_id,
                allocated_on=day,
                amount_pence=amount,
            )


def ticket(db, identifier, order_id, opened, topic, description, resolved=False):
    insert(
        db,
        "tickets",
        id=identifier,
        order_id=order_id,
        assigned_employee_id="EMP-005",
        opened_on=opened,
        status="resolved" if resolved else "open",
        topic=topic,
        description=description,
        provenance="simulated service lifecycle",
    )
    insert(
        db,
        "ticket_events",
        id=f"{identifier}:1",
        ticket_id=identifier,
        occurred_on=opened,
        status="open",
        note="Customer evidence request logged; no automatic compensation",
    )
    if resolved:
        insert(
            db,
            "ticket_events",
            id=f"{identifier}:2",
            ticket_id=identifier,
            occurred_on=shift(opened, 1),
            status="in_progress",
            note="Support reviewed the order and fulfillment evidence",
        )
        insert(
            db,
            "ticket_events",
            id=f"{identifier}:3",
            ticket_id=identifier,
            occurred_on=shift(opened, 3),
            status="resolved",
            note="Dispatch evidence explained; case closed without a refund",
        )


def source_ticket(db, invoice_no, order_id, opened, topic):
    """Keep each modeled case tied to an actual order and a support owner."""
    staff = [
        row[0]
        for row in db.execute(
            "SELECT employee_id FROM employee_assignments WHERE "
            "department_id='DEP-SUPPORT' AND valid_until IS NULL ORDER BY employee_id"
        )
    ]
    if not staff:
        raise ValueError("No active support employee for source case")
    identifier = f"TKT-{invoice_no}"
    review = business_shift(opened, 1 + stable_bucket(invoice_no + ":case-review", 3))
    resolved = business_shift(review, 1 + stable_bucket(invoice_no + ":case-resolution", 5))
    status = "resolved" if resolved <= AS_OF else "in_progress" if review <= AS_OF else "open"
    if topic == "split_consignment":
        description = (
            f"Buyer asks for the remaining quantities on {order_id} after the first consignment. "
            "Check the dispatch records before promising a delivery date."
        )
        opening = "Request logged against the first dispatch and its unshipped order lines"
        outcome = "Recorded dispatch sequence explained; no refund or return inferred"
    else:
        description = (
            f"Buyer asks for the posted invoice and order reference for {order_id}. "
            "Check the billed lines before sending a copy."
        )
        opening = "Invoice copy request logged against the posted order"
        outcome = "Invoice and order references checked; copy request closed"
    insert(
        db,
        "tickets",
        id=identifier,
        order_id=order_id,
        assigned_employee_id=staff[stable_bucket(invoice_no + ":support-owner", len(staff))],
        opened_on=opened,
        status=status,
        topic=topic,
        description=description,
        provenance="modeled service case; not an observed customer contact",
    )
    insert(
        db,
        "ticket_events",
        id=f"{identifier}:1",
        ticket_id=identifier,
        occurred_on=opened,
        status="open",
        note=opening,
    )
    if review <= AS_OF:
        insert(
            db,
            "ticket_events",
            id=f"{identifier}:2",
            ticket_id=identifier,
            occurred_on=review,
            status="in_progress",
            note="Support compared the request with invoice and fulfillment records",
        )
    if resolved <= AS_OF:
        insert(
            db,
            "ticket_events",
            id=f"{identifier}:3",
            ticket_id=identifier,
            occurred_on=resolved,
            status="resolved",
            note=outcome,
        )


def seed_observed(db, project, profile):
    prepared = project / "data/company/prepared"
    verify_prepared(prepared)
    with gzip.open(
        prepared / "invoice_groups.csv.gz", "rt", encoding="utf-8", newline=""
    ) as stream:
        eligible = [r["invoice_no"] for r in csv.DictReader(stream) if r["eligible_sale"] == "1"]
    chosen = set(eligible if profile == "full" else eligible[:40])
    baskets = defaultdict(list)
    with gzip.open(prepared / "transactions.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["invoice_no"] in chosen:
                baskets[row["invoice_no"]].append(row)
    known_customers, known_products = set(), set()
    for index, (invoice_no, rows) in enumerate(sorted(baskets.items()), 1):
        first = rows[0]
        cid = f"UCI-CUST-{first['customer_id']}"
        if cid not in known_customers:
            customer(db, cid, first["customer_id"], first["country"], len(known_customers) + 1)
            known_customers.add(cid)
        lines = []
        for row in rows:
            sku = f"UCI-SKU-{row['stock_code']}"
            if sku not in known_products:
                product(db, sku, row["stock_code"], row["description"])
                known_products.add(sku)
            lines.append((sku, int(row["quantity"]), row["unit_price_gbp"], row["source_row_id"]))
        posted = first["invoice_date_local"][:10]
        oid = f"ORD-{invoice_no}"
        _, items = order(db, oid, cid, posted, lines, invoice_no)
        split = any(quantity >= 48 for _, _, quantity, _ in items)
        old_first = shift(posted, 1 if first["country"] == "United Kingdom" else 3)
        has_second = split and shift(old_first, 3) <= AS_OF
        dispatch_day = modeled_dispatch(invoice_no, posted, first["country"], has_second)
        if dispatch_day is not None:
            first_load = []
            second_load = []
            for item, sku, quantity, _ in items:
                first_quantity = quantity if quantity < 48 else quantity * 3 // 4
                first_load.append((item, sku, first_quantity))
                if quantity > first_quantity:
                    second_load.append((item, sku, quantity - first_quantity))
            dispatch(db, f"SHIP-{invoice_no}-1", oid, dispatch_day, first_load, first["country"])
            if second_load and has_second:
                dispatch(
                    db,
                    f"SHIP-{invoice_no}-2",
                    oid,
                    modeled_second_dispatch(invoice_no, dispatch_day),
                    second_load,
                    first["country"],
                )
        finish_order(db, oid)
        # A subset of partial dispatches prompts a service case. The scheduled
        # invoice-copy sample is independent of order size.
        asks_about_split = (
            split and dispatch_day is not None and stable_bucket(invoice_no + ":service", 4) == 0
        )
        if asks_about_split or index % 31 == 0:
            topic = "split_consignment" if asks_about_split else "invoice_copy"
            opened = (
                business_shift(dispatch_day, 1) if asks_about_split
                else business_shift(posted, 2 + stable_bucket(invoice_no + ":invoice-request", 5))
            )
            if opened <= AS_OF:
                source_ticket(db, invoice_no, oid, opened, topic)
    return {"source_invoices": len(baskets), "source_rows": sum(map(len, baskets.values()))}


def seed_scenarios(db):
    for number in range(1, 9):
        customer(db, f"DEMO-CUST-{number:03}", None, "United Kingdom", 9000 + number)
    for code, name in [
        ("A", "Demonstration ceramic mug"),
        ("B", "Demonstration gift bag"),
        ("C", "Demonstration candle holder"),
        ("FIN", "Demonstration wholesale gift carton"),
        ("SALES", "Demonstration monthly gift assortment"),
        ("FC", "Demonstration forecast notebook"),
    ]:
        product(db, f"DEMO-SKU-{code}", None, name)
    invoice, items = order(
        db, "DEMO-ORD-001", "DEMO-CUST-001", "2011-10-31", [("DEMO-SKU-FIN", 10, "120", None)]
    )
    dispatch(db, "DEMO-SHIP-001", "DEMO-ORD-001", "2011-11-01", [(a, b, q) for a, b, q, _ in items])
    finish_order(db, "DEMO-ORD-001")
    pay(db, "DEMO-PAY-001", invoice, "2011-11-15", 45000)
    insert(
        db,
        "credit_notes",
        id="DEMO-CN-001",
        invoice_id=invoice,
        issued_on="2011-11-16",
        amount_pence=5000,
        reason="Authored goodwill credit; no cash refund and no stock return implied",
        provenance="authored scenario",
    )
    _, items = order(
        db,
        "DEMO-ORD-002",
        "DEMO-CUST-002",
        "2011-12-05",
        [("DEMO-SKU-A", 100, "3", None), ("DEMO-SKU-B", 40, "1", None)],
    )
    dispatch(
        db,
        "DEMO-SHIP-002A",
        "DEMO-ORD-002",
        "2011-12-06",
        [(items[0][0], items[0][1], 60), (items[1][0], items[1][1], 40)],
    )
    dispatch(db, "DEMO-SHIP-002B", "DEMO-ORD-002", "2011-12-08", [(items[0][0], items[0][1], 20)])
    finish_order(db, "DEMO-ORD-002")
    order(db, "DEMO-ORD-003", "DEMO-CUST-003", "2011-12-09", [("DEMO-SKU-C", 35, "2", None)])
    _, items = order(
        db, "DEMO-ORD-004", "DEMO-CUST-004", "2011-12-01", [("DEMO-SKU-B", 12, "1", None)]
    )
    dispatch(db, "DEMO-SHIP-004", "DEMO-ORD-004", "2011-12-02", [(a, b, q) for a, b, q, _ in items])
    finish_order(db, "DEMO-ORD-004")
    ticket(
        db,
        "DEMO-TKT-004",
        "DEMO-ORD-004",
        "2011-12-06",
        "damaged_goods",
        (
            "Buyer reports crushed packaging. Request photographs and check the shipment before "
            "proposing the in_progress transition."
        ),
    )
    for month, amount in [("10", "10000"), ("11", "7500")]:
        oid = f"DEMO-ORD-005-{month}"
        _, items = order(
            db, oid, "DEMO-CUST-005", f"2011-{month}-15", [("DEMO-SKU-SALES", 1, amount, None)]
        )
        dispatch(
            db,
            f"DEMO-SHIP-005-{month}",
            oid,
            f"2011-{month}-16",
            [(a, b, q) for a, b, q, _ in items],
        )
        finish_order(db, oid)
    for month, units in [("08", 1000), ("09", 1000), ("10", 1000), ("11", 850)]:
        oid = f"DEMO-ORD-006-{month}"
        _, items = order(
            db, oid, "DEMO-CUST-006", f"2011-{month}-15", [("DEMO-SKU-FC", units, "1", None)]
        )
        dispatch(
            db,
            f"DEMO-SHIP-006-{month}",
            oid,
            f"2011-{month}-16",
            [(a, b, q) for a, b, q, _ in items],
        )
        finish_order(db, oid)
    order(db, "DEMO-ORD-008", "DEMO-CUST-008", "2011-12-09", [("DEMO-SKU-B", 8, "1", None)])
    order(
        db,
        "DEMO-ORD-CANCELLED",
        "DEMO-CUST-007",
        "2011-12-08",
        [("DEMO-SKU-A", 5, "3", None)],
        cancelled=True,
    )


def seed_inventory(db):
    """Reconstruct weekly replenishment without treating future orders as old stock."""
    purchase_batches = {}
    supplier_leads = dict(db.execute("SELECT id,lead_days FROM suppliers"))
    for sku, supplier, source in db.execute(
        "SELECT id,supplier_id,source_stock_code FROM products ORDER BY id"
    ).fetchall():
        outstanding = db.execute(
            (
                "SELECT COALESCE(SUM(f.quantity-f.shipped_quantity),0) FROM order_fulfillment f "
                "JOIN orders o ON o.id=f.order_id WHERE f.product_id=? AND o.status!='cancelled'"
            ),
            (sku,),
        ).fetchone()[0]
        weekly_units = defaultdict(int)
        for day, units in db.execute(
            "SELECT occurred_on,-SUM(quantity) FROM stock_movements WHERE "
            "product_id=? AND kind='dispatch' GROUP BY occurred_on ORDER BY occurred_on",
            (sku,),
        ):
            current = date.fromisoformat(day)
            week_start = (current - timedelta(days=current.weekday())).isoformat()
            weekly_units[week_start] += units
        opening = 0 if source is not None and not weekly_units else 24 + stable_bucket(
            sku + ":opening-stock", 49
        )
        if sku == "DEMO-SKU-C":
            opening = 50
        if opening:
            insert(
                db,
                "stock_movements",
                id=f"OPEN-{sku}",
                warehouse_id="WH-CVT",
                product_id=sku,
                occurred_on="2010-11-01",
                kind="opening",
                quantity=opening,
                shipment_item_id=None,
                goods_receipt_id=None,
            )
        balance = opening
        pack = (6, 12, 24)[stable_bucket(sku + ":carton-size", 3)]
        base_buffer = 18 + stable_bucket(sku + ":stock-buffer", 55)
        for week_start, units in sorted(weekly_units.items()):
            trailing = sum(weekly_units.get(shift(week_start, -7 * lag), 0) for lag in range(1, 5))
            target = max(base_buffer, (trailing * 3 + 7) // 8)
            needed = max(0, units + target - balance)
            quantity = ((needed + pack - 1) // pack) * pack
            if quantity == 0:
                balance -= units
                continue
            po = f"PO-{supplier}-{week_start}"
            purchase_line = f"{po}:{sku}"
            if po not in purchase_batches:
                placed, expected, received = supplier_batch_dates(
                    week_start, supplier, supplier_leads[supplier]
                )
                insert(
                    db,
                    "purchase_orders",
                    id=po,
                    supplier_id=supplier,
                    warehouse_id="WH-CVT",
                    placed_on=placed,
                    expected_on=expected,
                    status="received",
                    provenance=(
                        "retrospective weekly replenishment with carton sizing; "
                        "not an observed purchase order or forecast"
                    ),
                )
                purchase_batches[po] = received
            received = purchase_batches[po]
            insert(
                db,
                "purchase_order_items",
                id=purchase_line,
                purchase_order_id=po,
                product_id=sku,
                quantity=quantity,
            )
            insert(
                db,
                "goods_receipts",
                id=f"GR-{purchase_line}",
                purchase_order_item_id=purchase_line,
                received_on=received,
                quantity=quantity,
            )
            insert(
                db,
                "stock_movements",
                id=f"RECEIPT-{purchase_line}",
                warehouse_id="WH-CVT",
                product_id=sku,
                occurred_on=received,
                kind="receipt",
                quantity=quantity,
                shipment_item_id=None,
                goods_receipt_id=f"GR-{purchase_line}",
            )
            balance += quantity - units
        inventory_id = "DEMO-STOCK-003" if sku == "DEMO-SKU-C" else f"STOCK-{sku}"
        insert(
            db,
            "inventory",
            id=inventory_id,
            warehouse_id="WH-CVT",
            product_id=sku,
            on_hand=balance,
            reserved=min(balance, outstanding),
            as_of=AS_OF,
        )
    supplier = db.execute("SELECT supplier_id FROM products WHERE id='DEMO-SKU-C'").fetchone()[0]
    insert(
        db,
        "purchase_orders",
        id="DEMO-PO-003",
        supplier_id=supplier,
        warehouse_id="WH-CVT",
        placed_on="2011-12-01",
        expected_on="2011-12-12",
        status="open",
        provenance="authored future inbound; not customer delivery promise",
    )
    insert(
        db,
        "purchase_order_items",
        id="DEMO-PO-003:1",
        purchase_order_id="DEMO-PO-003",
        product_id="DEMO-SKU-C",
        quantity=80,
    )
    # Leeds holds inspection supplies; no cancellation is invented as a returned item.
    insert(
        db,
        "inventory",
        id="STOCK-LDS-SUPPLIES",
        warehouse_id="WH-LDS",
        product_id="DEMO-SKU-B",
        on_hand=20,
        reserved=0,
        as_of=AS_OF,
    )
    insert(
        db,
        "stock_movements",
        id="OPEN-LDS-SUPPLIES",
        warehouse_id="WH-LDS",
        product_id="DEMO-SKU-B",
        occurred_on="2010-11-01",
        kind="opening",
        quantity=20,
        shipment_item_id=None,
        goods_receipt_id=None,
    )


def forecast_input(db, sku, target_start, lookback):
    """The generation query has a hard upper bound before the target period."""
    start = month_before(target_start, lookback)
    rows = db.execute(
        (
            "SELECT i.id,i.posted_on,ii.id,ii.quantity FROM invoice_items ii JOIN invoices i ON "
            "i.id=ii.invoice_id JOIN order_items oi ON oi.id=ii.order_item_id WHERE "
            "oi.product_id=? AND i.posted_on>=? AND i.posted_on<? ORDER BY i.posted_on,i.id,ii.id"
        ),
        (sku, start, target_start),
    ).fetchall()
    digest = hashlib.sha256(
        json.dumps([list(r) for r in rows], separators=(",", ":")).encode()
    ).hexdigest()
    total = sum(row[3] for row in rows)
    units = int((Decimal(total) / lookback).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return units, total, max((r[1] for r in rows), default=None), digest


def forecast_products(db):
    """Freeze the product cohort using only activity before the first forecast cutoff."""
    return [
        r[0]
        for r in db.execute(
            "SELECT oi.product_id FROM invoice_items ii "
            "JOIN invoices i ON i.id=ii.invoice_id JOIN order_items oi ON oi.id=ii.order_item_id "
            "JOIN products p ON p.id=oi.product_id "
            "WHERE p.source_stock_code IS NOT NULL AND i.posted_on<'2011-10-01' "
            "GROUP BY oi.product_id ORDER BY SUM(ii.quantity) DESC,oi.product_id LIMIT 12"
        )
    ]


def seed_forecasts(db):
    products = forecast_products(db)
    for month in ("2011-10", "2011-11", "2011-12"):
        start = month + "-01"
        year, number = map(int, month.split("-"))
        end = f"{month}-{calendar.monthrange(year, number)[1]}"
        for version, lookback in [(1, 3), (2, 2)]:
            run = f"FCRUN-{month}-v{version}"
            insert(
                db,
                "forecast_runs",
                id=run,
                generated_at=start + "T00:00:00+00:00",
                training_cutoff=shift(start, -1),
                target_start=start,
                target_end=end,
                method="trailing calendar-month mean of billed units",
                method_version=version,
                lookback_months=lookback,
                assumption=(
                    "Reconstructed historical run time. Missing months count as zero; excludes "
                    "ineligible source baskets. No target-period actuals are used."
                ),
            )
            for sku in products:
                units, total, last, digest = forecast_input(db, sku, start, lookback)
                identifier = f"FC-{sku}-{month}-v{version}"
                insert(
                    db,
                    "forecasts",
                    id=identifier,
                    run_id=run,
                    product_id=sku,
                    units=units,
                    training_units=total,
                    training_last_date=last,
                    input_sha256=digest,
                )
                insert(
                    db,
                    "sales_targets",
                    id=f"TARGET-{identifier}",
                    department_id="DEP-SALES",
                    forecast_id=identifier,
                    target_units=int(
                        (Decimal(units) * Decimal("1.10")).quantize(
                            Decimal(1), rounding=ROUND_HALF_UP
                        )
                    ),
                    assumption=(
                        "Simulated stretch target: forecast units * 1.10, half-up to a unit; not "
                        "an observed commitment"
                    ),
                )
    insert(
        db,
        "forecast_runs",
        id="DEMO-FCRUN-006",
        generated_at="2011-11-01T00:00:00+00:00",
        training_cutoff="2011-10-31",
        target_start="2011-11-01",
        target_end="2011-11-30",
        method="trailing calendar-month mean of billed units",
        method_version=1,
        lookback_months=3,
        assumption="Authored history: August, September and October each contain 1,000 units",
    )
    units, total, last, digest = forecast_input(db, "DEMO-SKU-FC", "2011-11-01", 3)
    insert(
        db,
        "forecasts",
        id="DEMO-FC-006",
        run_id="DEMO-FCRUN-006",
        product_id="DEMO-SKU-FC",
        units=units,
        training_units=total,
        training_last_date=last,
        input_sha256=digest,
    )
    insert(
        db,
        "sales_targets",
        id="TARGET-DEMO-FC-006",
        department_id="DEP-SALES",
        forecast_id="DEMO-FC-006",
        target_units=1100,
        assumption="Simulated 10 percent stretch above the frozen forecast",
    )


def populate(db, project, profile):
    contract = json.loads((project / "data/company/company.json").read_text("utf-8"))
    db.executescript(Path(__file__).with_name("schema.sql").read_text("utf-8"))
    seed_organization(db, contract, profile)
    source_counts = seed_observed(db, project, profile)
    seed_source_payments(db)
    seed_scenarios(db)
    seed_inventory(db)
    seed_forecasts(db)
    db.commit()
    return source_counts
