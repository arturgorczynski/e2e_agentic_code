"""Audited r8 corrections for three source-versus-scenario procedures."""

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

from acme.dataset import connect
from acme.document_revision import (
    _write_controlled,
    audit_revision_bundle,
    install_revision_bundle,
)

REVISION = "acme-documents-2026-r8"
PARENT = "acme-documents-2026-r7"
EFFECTIVE_FROM = "2026-10-21"
TARGETS = {
    "PROC-009": ("stock_movements", "DEP-LOGISTICS"),
    "PROC-011": ("ticket_events", "DEP-SUPPORT"),
    "PROC-014": ("price_history", "DEP-SALES"),
}


def _check_sample(db, item: dict) -> None:
    identifier = item["document_id"]
    table, department = TARGETS[identifier]
    if item["category"] != "procedures" or item["record_links"] != {
        "department_id": department
    }:
        raise ValueError(f"Unexpected procedure owner or link: {identifier}")
    facts = item["facts"]
    if facts["sample_table"] != table:
        raise ValueError(f"Unexpected sample table: {identifier}")
    sample_id = facts["sample_id"]
    if "DEMO-" not in sample_id:
        raise ValueError(f"Expected an authored scenario sample: {identifier}")
    if table == "stock_movements":
        row = db.execute(
            "SELECT kind,shipment_item_id FROM stock_movements WHERE id=?", (sample_id,)
        ).fetchone()
        valid = (
            row is not None
            and row["kind"] == "dispatch"
            and (row["shipment_item_id"] or "").startswith("DEMO-")
        )
    elif table == "ticket_events":
        row = db.execute(
            "SELECT ticket_id FROM ticket_events WHERE id=?", (sample_id,)
        ).fetchone()
        valid = row is not None and row["ticket_id"].startswith("DEMO-")
    else:
        row = db.execute(
            "SELECT price_kind,source_row_id FROM price_history WHERE id=?", (sample_id,)
        ).fetchone()
        valid = row is not None and row["price_kind"] == "fixture" and row[
            "source_row_id"
        ] is None
    if not valid:
        raise ValueError(f"Procedure sample no longer matches SQL: {identifier}")


def _check_body(item: dict, body: str) -> None:
    identifier = item["document_id"]
    if not body.startswith("# ") or item["facts"]["sample_id"] not in body:
        raise ValueError(f"Procedure omits its controlled sample: {identifier}")
    if "Historical reference record" in body:
        raise ValueError(f"Procedure mislabels an authored sample: {identifier}")
    if "authored" not in body:
        raise ValueError(f"Procedure omits the sample's authored provenance: {identifier}")
    for heading in (
        "## Use and owner",
        "## Review steps",
        "## Decision and exception",
        "## Handoff record",
    ):
        if body.count(heading) != 1:
            raise ValueError(f"Procedure section missing or repeated: {identifier}")
    if identifier == "PROC-014" and not all(
        term in body for term in ("price_kind", "source_row_id", "fixture")
    ):
        raise ValueError("Price procedure must distinguish fixtures from source rows")
    if identifier == "PROC-009" and "inventory.as_of" not in body:
        raise ValueError("Stock procedure must match the inventory reference date")


def build_procedure_release(source: Path, state: Path, authored: Path, output: Path) -> dict:
    """Build an immutable r8 candidate from the installed audited r7 bundle."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected a verified r7 document bundle")
    catalog = json.loads((source / "catalog.json").read_text(encoding="utf-8"))
    current = {
        item["document_id"]: item
        for item in catalog["documents"]
        if item["status"] == "current" and item["document_id"] in TARGETS
    }
    if set(current) != set(TARGETS):
        raise ValueError("Expected the three current scenario procedure documents")
    if {path.name for path in authored.glob("*.md")} != {
        f"{identifier}.md" for identifier in TARGETS
    }:
        raise ValueError("Authored procedure files do not match the correction list")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        for item in current.values():
            _check_sample(db, item)
    finally:
        db.close()
    bodies = {}
    for identifier, item in current.items():
        body = (authored / f"{identifier}.md").read_text(encoding="utf-8")
        _check_body(item, body)
        bodies[identifier] = body
    shutil.copytree(source, output)
    (output / "installed.json").unlink(missing_ok=True)
    replacements = {}
    review = []
    for identifier, item in current.items():
        old_body = (source / item["relative_path"]).read_text(encoding="utf-8").split(
            "---\n", 2
        )[2]
        older = _write_controlled(
            output,
            {**item, "status": "superseded", "effective_until": EFFECTIVE_FROM},
            old_body,
        )
        newer = _write_controlled(
            output,
            {
                **item,
                "version": item["version"] + 1,
                "status": "current",
                "effective_from": EFFECTIVE_FROM,
                "effective_until": None,
                "revision": REVISION,
            },
            bodies[identifier],
        )
        replacements[identifier] = (older, newer)
        review.append(
            {
                "document_id": identifier,
                "previous_version": older["version"],
                "new_version": newer["version"],
                "source": f"data/document_sources/revision_r8/procedures/{identifier}.md",
                "correction": "Distinguish authored DEMO scenario records from observed UCI data",
            }
        )
    revised = []
    for item in catalog["documents"]:
        if item["status"] == "current" and item["document_id"] in replacements:
            revised.extend(replacements[item["document_id"]])
        else:
            revised.append(item)
    revised.sort(key=lambda item: (item["document_id"], item["version"]))
    catalog.update({"revision": REVISION, "documents": revised})
    catalog_path = output / "catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in revised}),
        "versions": len(revised),
        "revised_procedures": len(review),
        "effective_from": EFFECTIVE_FROM,
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output / "editorial_review.json").write_text(
        json.dumps(review, indent=2) + "\n", encoding="utf-8"
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"Procedure release failed bundle audit: {audit['issues']}")
    return manifest


def validate_procedure_release(db, catalog: list[dict], documents: Path) -> dict:
    """Check the installed procedure bodies and their live scenario examples."""
    current = {
        item["document_id"]: item
        for item in catalog
        if item["status"] == "current" and item["document_id"] in TARGETS
    }
    if set(current) != set(TARGETS):
        raise ValueError("Expected three corrected current procedures")
    for identifier, item in current.items():
        if item["version"] != 4 or item["revision"] != REVISION:
            raise ValueError(f"Procedure version was not advanced: {identifier}")
        _check_sample(db, item)
        body = (documents / item["relative_path"]).read_text(encoding="utf-8").split(
            "---\n", 2
        )[2]
        _check_body(item, body)
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Procedure release breaks database relationships")
    return {"status": "ok", "procedures_checked": len(current)}


def install_procedure_release(project: Path, state: Path, bundle: Path) -> dict:
    """Install r8 using the staged revision transaction and a full backup."""
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_validator=validate_procedure_release,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
