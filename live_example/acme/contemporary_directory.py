"""Preview and apply the authored 2026 account-directory correction.

The correction touches only the eight seeded fictional accounts. It refuses to
overwrite portal edits or other unexpected changes to their directory fields.
"""

import re

from acme.contemporary_identities import SEED_ACCOUNT_IDENTITIES


def _legacy_identity(name: str, suffix: str, manager_id: str) -> dict:
    city, postcode = (
        ("Bristol", "BS4 8QA"),
        ("Leeds", "LS7 3QJ"),
        ("Coventry", "CV3 4ZW"),
        ("Nottingham", "NG5 7JP"),
    )[int(suffix[:2], 16) % 4]
    street = ("Canal", "Market", "Foundry", "Orchard")[int(suffix[2:4], 16) % 4]
    domain = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "customer"
    return {
        "address": (
            f"Unit {1 + int(suffix[4:6], 16) % 24}, "
            f"{street} Trade Park, {city}, {postcode}"
        ),
        "contact_name": ("Mia Carter", "Leo Bennett", "Grace Turner", "Noah Ellis")[
            int(suffix[6:8], 16) % 4
        ],
        "contact_role": "Orders and purchasing",
        "contact_email": f"orders@{domain}-{suffix[:6].lower()}.example",
        "manager_id": manager_id,
        "segment": "Independent retail",
    }


def plan_directory_correction(db) -> list[dict]:
    """Compare every seeded account with both old and proposed directory facts."""
    fallback = db.execute(
        "SELECT e.id FROM employees e JOIN employee_assignments a "
        "ON a.employee_id=e.id AND a.valid_until IS NULL "
        "WHERE a.department_id='DEP-SALES' ORDER BY e.id LIMIT 1"
    ).fetchone()
    if fallback is None:
        raise ValueError("A current Sales account manager is required")
    plans = []
    for name, target in SEED_ACCOUNT_IDENTITIES.items():
        row = db.execute(
            "SELECT c.id,c.name,c.segment,c.account_manager_id,a.id AS address_id,"
            "a.label AS address,cc.id AS contact_id,cc.name AS contact_name,"
            "cc.email AS contact_email,cc.responsibility AS contact_role "
            "FROM customers c JOIN addresses a ON a.id=c.address_id "
            "JOIN customer_contacts cc ON cc.customer_id=c.id "
            "WHERE c.name=? AND c.provenance='fictional_contemporary_seed'",
            (name,),
        ).fetchall()
        if len(row) != 1:
            raise ValueError(f"Expected one seeded account and contact for {name}")
        account = row[0]
        suffix = account["id"].removeprefix("SCN-CUST-")
        if account["id"] == suffix:
            raise ValueError(f"Unexpected seeded account ID: {account['id']}")
        assigned = db.execute(
            "SELECT 1 FROM employee_assignments WHERE employee_id=? "
            "AND department_id='DEP-SALES' AND valid_until IS NULL",
            (target["manager_id"],),
        ).fetchone()
        if assigned is None:
            raise ValueError(f"Account manager is not currently in Sales: {target['manager_id']}")
        current = {
            "address": account["address"],
            "contact_name": account["contact_name"],
            "contact_role": account["contact_role"],
            "contact_email": account["contact_email"],
            "manager_id": account["account_manager_id"],
            "segment": account["segment"],
        }
        legacy = _legacy_identity(name, suffix, fallback["id"])
        if current == target:
            status = "already_applied"
        elif current == legacy:
            status = "ready"
        else:
            changed = [key for key in current if current[key] not in {legacy[key], target[key]}]
            raise ValueError(
                f"Seed directory has unrecognized edits for {account['id']}: "
                f"{', '.join(changed) or 'mixed old and new values'}"
            )
        plans.append(
            {
                "customer_id": account["id"],
                "address_id": account["address_id"],
                "contact_id": account["contact_id"],
                "name": name,
                "before": current,
                "after": target,
                "status": status,
            }
        )
    if len(plans) != 8:
        raise ValueError("Expected exactly eight contemporary seed accounts")
    return plans


def apply_directory_correction(db, plans: list[dict]) -> int:
    """Apply a checked plan inside the caller's SQLite transaction."""
    changed = 0
    for item in plans:
        if item["status"] == "already_applied":
            continue
        current = item["before"]
        target = item["after"]
        customer = db.execute(
            "UPDATE customers SET account_manager_id=?,segment=? WHERE id=? "
            "AND account_manager_id=? AND segment=?",
            (
                target["manager_id"],
                target["segment"],
                item["customer_id"],
                current["manager_id"],
                current["segment"],
            ),
        )
        address = db.execute(
            "UPDATE addresses SET label=? WHERE id=? AND label=?",
            (target["address"], item["address_id"], current["address"]),
        )
        contact = db.execute(
            "UPDATE customer_contacts SET name=?,email=?,responsibility=? "
            "WHERE id=? AND name=? AND email=? AND responsibility=?",
            (
                target["contact_name"],
                target["contact_email"],
                target["contact_role"],
                item["contact_id"],
                current["contact_name"],
                current["contact_email"],
                current["contact_role"],
            ),
        )
        if (customer.rowcount, address.rowcount, contact.rowcount) != (1, 1, 1):
            raise ValueError(f"Seed directory changed during migration: {item['customer_id']}")
        changed += 1
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Directory correction breaks a database reference")
    return changed
