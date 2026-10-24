"""Improve authored demo labels in an existing exercise database without resetting it.

Dry-run is the default. --apply creates a SQLite online backup before one
transaction. Only values still matching the v1 generator are changed, so
customer edits and later manual classifications are preserved.
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from acme.company_data import CATEGORIES, category_for, customer_address, customer_name

OLD_PREFIXES = (
    "Ashfield",
    "Brookside",
    "Cedar",
    "Elmbridge",
    "Harbour",
    "Kingswell",
    "Meadow",
    "Northgate",
    "Oakridge",
    "Riverside",
    "Stonebridge",
    "Westhaven",
)
OLD_TRADES = ("Home Stores", "Gift Trading", "Housewares")
OLD_ADDRESS = "Fictional billing contact; street and postal code intentionally unspecified"


def old_name(sequence):
    return f"{OLD_PREFIXES[sequence % len(OLD_PREFIXES)]} {OLD_TRADES[sequence % 3]} {sequence:04}"


def old_category(description):
    for identifier, _, rule, _ in CATEGORIES[:-1]:
        if any(word in description.upper() for word in rule.split("|")):
            return identifier
    return "CAT-HOME"


def changes(db):
    customers = []
    addresses = []
    contacts = []
    observed_number = 0
    rows = db.execute(
        "SELECT c.id,c.source_customer_id,c.name,c.address_id,a.label,a.country,cc.email "
        "FROM customers c JOIN addresses a ON a.id=c.address_id "
        "LEFT JOIN customer_contacts cc ON cc.customer_id=c.id ORDER BY c.rowid"
    )
    for row in rows:
        identifier, source, name, address_id, label, country, email = row
        if source is not None:
            observed_number += 1
            sequence = observed_number
        elif identifier.startswith("DEMO-CUST-"):
            sequence = 9000 + int(identifier.rsplit("-", 1)[-1])
        else:
            continue
        if name == old_name(sequence):
            customers.append((customer_name(sequence), identifier))
        if address_id == f"ADDR-{identifier}" and label == OLD_ADDRESS:
            addresses.append(
                (
                    customer_address(country, sequence),
                    "source country; fictional billing location" if source else "authored scenario",
                    address_id,
                )
            )
        old_email = f"accounts.{identifier.lower()}@customer.example"
        if email == old_email:
            contacts.append(
                (
                    f"accounts.{identifier.lower()}@customers.example",
                    ("Purchasing", "Accounts payable", "Order coordination")[sequence % 3],
                    f"CONTACT-{identifier}",
                    old_email,
                )
            )

    supplier_for = {item[0]: f"SUP-{index:02}" for index, item in enumerate(CATEGORIES, 1)}
    products = []
    for identifier, name, category, supplier in db.execute(
        "SELECT id,name,category_id,supplier_id FROM products"
    ):
        previous = old_category(name)
        revised = category_for(name)
        if category == previous and revised != previous:
            products.append((revised, supplier_for[revised], identifier, supplier))
    return customers, addresses, contacts, products


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "state/company.sqlite",
    )
    parser.add_argument("--apply", action="store_true", help="Back up and update the database")
    args = parser.parse_args()
    database = args.database.resolve()
    db = sqlite3.connect(
        f"file:{database.as_posix()}?mode={'rw' if args.apply else 'ro'}", uri=True
    )
    try:
        people, addresses, contacts, products = changes(db)
        report = {
            "database": str(database),
            "customer_names": len(people),
            "billing_addresses": len(addresses),
            "contact_candidates": len(contacts),
            "product_categories": len(products),
            "preview": {
                "customers": people[:3],
                "addresses": addresses[:2],
                "products": products[:5],
            },
        }
        if args.apply and any((people, addresses, contacts, products)):
            backup = (
                database.parent
                / "backups"
                / (
                    "company-before-enrichment-"
                    + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    + ".sqlite"
                )
            )
            backup.parent.mkdir(exist_ok=True)
            with sqlite3.connect(backup) as copy:
                db.backup(copy)
            report["backup"] = str(backup)
            db.execute("BEGIN IMMEDIATE")
            try:
                db.executemany("UPDATE customers SET name=? WHERE id=?", people)
                db.executemany("UPDATE addresses SET label=?,provenance=? WHERE id=?", addresses)
                db.executemany(
                    "UPDATE customer_contacts SET email=?,responsibility=? WHERE id=? AND email=?",
                    contacts,
                )
                db.executemany(
                    "UPDATE products SET category_id=?,supplier_id=? WHERE id=? AND supplier_id=?",
                    products,
                )
                violations = db.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise ValueError(f"Foreign-key violations after enrichment: {violations[:3]}")
                db.commit()
            except Exception:
                db.rollback()
                raise
            report["applied"] = True
        else:
            report["applied"] = False
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
