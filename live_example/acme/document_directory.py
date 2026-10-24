"""Build the controlled account-terms companion to the 2026 directory correction."""

import hashlib
import json
import shutil
from pathlib import Path

from acme.dataset import connect
from acme.document_extension import _account_facts
from acme.document_revision import _write_controlled, audit_revision_bundle

REVISION = "acme-documents-2026-r6"
EFFECTIVE_FROM = "2026-10-21"


def _updated_terms(body: str, old: dict, new: dict, email: str) -> str:
    """Replace exact directory statements, preserving commercial and case facts."""
    replacements = [
        (
            "This account-specific record applies to Acme account "
            f"`{old['id']}` from 2026-10-20.",
            "This account-specific record applies to Acme account "
            f"`{new['id']}` from {EFFECTIVE_FROM}.",
        ),
        (
            f"The account is classified as {old['segment'].lower()}",
            f"The account is classified as {new['segment'].lower()}",
        ),
        (
            f"its recorded address is {old['address']}, {old['country']}.",
            f"its recorded address is {new['address']}, {new['country']}.",
        ),
        (
            f"The listed customer contact is {old['contact_name']} "
            f"({old['contact_role']}); account manager "
            f"`{old['account_manager_id']}`",
            f"The listed customer contact is {new['contact_name']} "
            f"({new['contact_role']}), reachable at `{email}`; account manager "
            f"`{new['account_manager_id']}`",
        ),
    ]
    for before, after in replacements:
        if body.count(before) != 1:
            raise ValueError(f"Expected one account-terms phrase: {before[:75]}")
        body = body.replace(before, after)
    return body


def build_directory_terms_bundle(source: Path, database: Path, output: Path) -> dict:
    """Create a checked r6 release using the staged, corrected company database."""
    if output.exists():
        raise ValueError("Choose a new document-release directory")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != "acme-documents-2026-r5":
        raise ValueError("Expected the verified r5 document release")
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    shutil.copytree(source, output)
    register_path = output / "catalog.json"
    register = json.loads(register_path.read_text("utf-8"))
    revised = []
    db = connect(database, readonly=True)
    try:
        corrected = 0
        for item in register["documents"]:
            if item["status"] != "current" or not item["document_id"].startswith("TERMS-2026-"):
                revised.append(item)
                continue
            customer_id = item["record_links"].get("customer_id")
            new_facts = _account_facts(db, customer_id)
            contact = db.execute(
                "SELECT email FROM customer_contacts WHERE customer_id=? ORDER BY id LIMIT 1",
                (customer_id,),
            ).fetchone()
            if contact is None:
                raise ValueError(f"Account contact disappeared: {customer_id}")
            raw = (source / item["relative_path"]).read_text("utf-8")
            _, _, body = raw.split("---\n", 2)
            updated = _updated_terms(body, item["facts"], new_facts, contact["email"])
            revised.append(
                _write_controlled(
                    output,
                    {**item, "status": "superseded", "effective_until": EFFECTIVE_FROM},
                    body,
                )
            )
            revised.append(
                _write_controlled(
                    output,
                    {
                        **item,
                        "owner_employee_id": new_facts["account_manager_id"],
                        "version": item["version"] + 1,
                        "effective_from": EFFECTIVE_FROM,
                        "effective_until": None,
                        "status": "current",
                        "facts": {**new_facts, "contact_email": contact["email"]},
                        "revision": REVISION,
                    },
                    updated,
                )
            )
            corrected += 1
    finally:
        db.close()
    if corrected != 8:
        raise ValueError(f"Expected eight revised account terms, got {corrected}")
    register["revision"] = REVISION
    register["documents"] = sorted(revised, key=lambda d: (d["document_id"], d["version"]))
    register_path.write_text(
        json.dumps(register, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in revised}),
        "versions": len(revised),
        "revised_account_terms": corrected,
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"Directory terms bundle failed audit: {audit['issues']}")
    return manifest
