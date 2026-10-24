"""Package contemporary account terms as a successor to the 2026 document release."""

import hashlib
import json
import shutil
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import _write_controlled, audit_revision_bundle

REVISION = "acme-documents-2026-r3"
EFFECTIVE_FROM = "2026-10-20"


def _account_facts(db, customer_id: str) -> dict:
    account = db.execute(
        "SELECT c.id,c.name,c.segment,c.payment_terms_days,c.account_manager_id,"
        "a.label AS address,a.country FROM customers c JOIN addresses a "
        "ON a.id=c.address_id WHERE c.id=? AND c.provenance='fictional_contemporary_seed'",
        (customer_id,),
    ).fetchone()
    if account is None:
        raise ValueError(f"Contemporary seed account missing: {customer_id}")
    history = db.execute(
        "SELECT COUNT(*) AS orders,MIN(ordered_at) AS first_order,"
        "MAX(ordered_at) AS last_order FROM orders WHERE customer_id=?",
        (customer_id,),
    ).fetchone()
    contact = db.execute(
        "SELECT name,responsibility FROM customer_contacts WHERE customer_id=? ORDER BY id LIMIT 1",
        (customer_id,),
    ).fetchone()
    case = db.execute(
        "SELECT t.id,t.topic,t.status FROM tickets t JOIN orders o ON o.id=t.order_id "
        "WHERE o.customer_id=? AND t.provenance='fictional_contemporary_seed' "
        "ORDER BY t.opened_on DESC,t.id LIMIT 1",
        (customer_id,),
    ).fetchone()
    return {
        **dict(account),
        **dict(history),
        "contact_name": contact["name"] if contact else "Account contact pending",
        "contact_role": contact["responsibility"] if contact else "Purchasing",
        "case_id": case["id"] if case else None,
        "case_topic": case["topic"] if case else None,
        "case_status": case["status"] if case else None,
    }


def _render_terms(f: dict) -> str:
    case = (
        f"The current exercise record also contains service case `{f['case_id']}` "
        f"({f['case_topic'].replace('_', ' ')}, {f['case_status'].replace('_', ' ')}). "
        "Its status is a service workflow status; consult the linked order and invoice "
        "before describing any commercial adjustment."
        if f["case_id"]
        else (
            "Open a service case against the exact order when a delivery or condition issue arises."
        )
    )
    return (
        f"# Account terms and service record: {f['name']}\n\n"
        f"## Document control and scope\n\nThis account-specific record applies to "
        f"Acme account `{f['id']}` from {EFFECTIVE_FROM}. The named business, contact and "
        "addresses are fictional training data. Identify the selected account before "
        "sharing its records; a similar trading name does not establish ownership. "
        f"The account is classified as {f['segment'].lower()} and its recorded address "
        f"is {f['address']}, {f['country']}. Confirm delivery instructions against the "
        "individual order rather than treating this address as proof of dispatch.\n\n"
        f"## Ordering and fulfilment\n\nThe exercise history currently covers "
        f"{f['orders']} orders dated {f['first_order']} through {f['last_order']}. "
        "Each accepted order retains its own product codes, quantities, price strings "
        "and status history. A confirmed order, a shipment and a delivered consignment "
        "are separate events. Refer any quantity or delivery dispute to the order ID "
        "and shipment lines. Product substitution or a revised delivery commitment "
        "requires a separately recorded decision by the responsible team.\n\n"
        f"## Invoices and settlement\n\nThe account's recorded invoice term is "
        f"{f['payment_terms_days']} calendar days from posting. The due date printed on "
        "an individual invoice controls that invoice's exercise balance. Finance "
        "checks receipts against payment allocations; an order total or incoming "
        "payment alone does not prove that every invoice is settled. Credit notes "
        "are separately numbered adjustments and do not by themselves prove that "
        "money was refunded or stock was returned.\n\n"
        f"## Service route and record ownership\n\nThe listed customer contact is "
        f"{f['contact_name']} ({f['contact_role']}); account manager "
        f"`{f['account_manager_id']}` coordinates sales questions. Support records "
        "delivery and condition reports, Warehouse Operations confirms physical "
        f"movements, and Finance owns invoice and credit decisions. {case} "
        "Keep the original event dates and the ID of every supporting record in "
        "the customer response. This document is an account snapshot, not a live "
        "balance statement or a promise of stock availability.\n"
    )


def build_contemporary_terms_bundle(source: Path, state: Path, output: Path) -> dict:
    """Create a new immutable full register, retaining every r2 document byte."""
    if output.exists():
        raise ValueError("Choose a new document-release directory")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != "acme-documents-2026-r2":
        raise ValueError("Expected the verified r2 document release")
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    shutil.copytree(source, output)
    register_path = output / "catalog.json"
    register = json.loads(register_path.read_text("utf-8"))
    db = connect(state / "company.sqlite", readonly=True)
    try:
        accounts = db.execute(
            "SELECT id FROM customers WHERE provenance='fictional_contemporary_seed' ORDER BY id"
        ).fetchall()
        if len(accounts) != 8:
            raise ValueError("Expected eight contemporary seed accounts for account terms")
        for account in accounts:
            facts = _account_facts(db, account["id"])
            identifier = "TERMS-2026-" + facts["id"].removeprefix("SCN-CUST-")
            register["documents"].append(
                _write_controlled(
                    output,
                    {
                        "document_id": identifier,
                        "title": f"Account terms: {facts['name']}",
                        "category": "customer_terms",
                        "owner_employee_id": facts["account_manager_id"],
                        "access_scope": "general",
                        "version": 1,
                        "effective_from": EFFECTIVE_FROM,
                        "effective_until": None,
                        "status": "current",
                        "record_links": {"customer_id": facts["id"]},
                        "facts": facts,
                        "revision": REVISION,
                    },
                    _render_terms(facts),
                )
            )
    finally:
        db.close()
    register["revision"] = REVISION
    register["documents"].sort(key=lambda item: (item["document_id"], item["version"]))
    register_path.write_text(
        json.dumps(register, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in register["documents"]}),
        "versions": len(register["documents"]),
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"New document bundle failed audit: {audit['issues']}")
    return manifest
