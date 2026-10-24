"""Install and verify the fictional 2026 account-directory release."""

from datetime import date
from pathlib import Path

from acme.contemporary_directory import apply_directory_correction, plan_directory_correction
from acme.document_extension import _account_facts
from acme.document_revision import install_revision_bundle

RELEASE_DATE = date(2026, 10, 21)


def correct_directory(db) -> None:
    """Run inside the document installer's staged database transaction."""
    plans = plan_directory_correction(db)
    changed = apply_directory_correction(db, plans)
    if changed != 8:
        raise ValueError("The installed r5 terms expect eight old directory identities")


def validate_directory_release(db, catalog: list[dict], documents: Path) -> dict:
    """Check SQL, current account terms and the immutable 2011 archive boundary."""
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Staged company database failed integrity check")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Staged company database has broken references")
    terms = [
        item for item in catalog
        if item["status"] == "current" and item["document_id"].startswith("TERMS-2026-")
    ]
    if len(terms) != 8:
        raise ValueError("Expected eight current 2026 account terms")
    for item in terms:
        customer_id = item["record_links"]["customer_id"]
        actual = _account_facts(db, customer_id)
        facts = dict(item["facts"])
        email = facts.pop("contact_email")
        if facts != actual:
            raise ValueError(f"Account terms differ from SQL: {customer_id}")
        contact = db.execute(
            "SELECT email FROM customer_contacts WHERE customer_id=? ORDER BY id LIMIT 1",
            (customer_id,),
        ).fetchone()
        if contact is None or email != contact["email"]:
            raise ValueError(f"Account contact email differs from SQL: {customer_id}")
        register = db.execute(
            "SELECT d.owner_employee_id,v.relative_path,v.sha256 FROM documents d "
            "JOIN document_versions v ON v.document_id=d.id WHERE d.id=? AND v.version=?",
            (item["document_id"], item["version"]),
        ).fetchone()
        if register is None or register["owner_employee_id"] != actual["account_manager_id"]:
            raise ValueError(f"Account terms owner differs from SQL: {customer_id}")
        if (
            register["relative_path"] != item["relative_path"]
            or register["sha256"] != item["sha256"]
        ):
            raise ValueError(f"Account terms register differs from release: {customer_id}")
        body = (documents / item["relative_path"]).read_text("utf-8")
        for phrase in (actual["address"], actual["contact_name"], actual["contact_role"], email):
            if phrase not in body:
                raise ValueError(f"Account terms omit directory fact for {customer_id}: {phrase}")
    source_orders = db.execute(
        "SELECT COUNT(*) FROM orders WHERE source_invoice_no IS NOT NULL"
    ).fetchone()[0]
    source_lines = db.execute(
        "SELECT COUNT(*) FROM order_items WHERE source_row_id IS NOT NULL"
    ).fetchone()[0]
    if source_orders < 10000 or source_lines < 100000:
        raise ValueError("The 2011 source transaction archive is incomplete")
    return {
        "status": "ok",
        "account_terms_checked": len(terms),
        "source_orders": source_orders,
        "source_lines": source_lines,
    }


def install_directory_release(project: Path, state: Path, bundle: Path) -> dict:
    """Date-gated release with backup, optimistic guards and staged validation."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_transform=correct_directory,
        database_validator=validate_directory_release,
        not_before=RELEASE_DATE,
    )
