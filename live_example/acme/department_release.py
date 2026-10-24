"""Versioned editorial release for the ten Acme department instructions.

Authored practice sections live under ``data/document_sources/revision_r7``.
The builder preserves the r6 remit and all older versions; installation uses
the normal staged SQLite/document transaction and a full backup.
"""

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

REVISION = "acme-documents-2026-r7"
PARENT = "acme-documents-2026-r6"
EFFECTIVE_FROM = "2026-10-21"
HEADINGS = (
    "## Daily controls",
    "## Handoffs and exceptions",
    "## Information handling",
)
OLD_BOILERPLATE = (
    "Start from the primary business record, check its linked evidence",
    "Share source records under their document and business scopes",
)


def _department_facts(db, identifier: str) -> dict:
    row = db.execute(
        "SELECT id,name,responsibility FROM departments WHERE id=?", (identifier,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown department: {identifier}")
    headcount = db.execute(
        "SELECT COUNT(*) FROM employee_assignments "
        "WHERE department_id=? AND valid_until IS NULL",
        (identifier,),
    ).fetchone()[0]
    return {**dict(row), "headcount": headcount}


def _authored_body(current: str, authored: str) -> str:
    if [line for line in authored.splitlines() if line.startswith("## ")] != list(HEADINGS):
        raise ValueError("Department source must have the three named practice sections")
    if any(current.count(heading) != 1 for heading in HEADINGS):
        raise ValueError("Current department document has unexpected sections")
    if any(phrase in authored for phrase in OLD_BOILERPLATE):
        raise ValueError("Authored source repeats the superseded boilerplate")
    remit = current.split(HEADINGS[0], 1)[0]
    return remit.rstrip() + "\n\n" + authored.strip() + "\n"


def build_department_release(source: Path, state: Path, authored: Path, output: Path) -> dict:
    """Make a new r7 candidate from an audited r6 bundle and current SQL facts."""
    if output.exists():
        raise ValueError("Choose a new output directory; releases are immutable")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != PARENT:
        raise ValueError("Expected a verified r6 document bundle")
    catalog = json.loads((source / "catalog.json").read_text("utf-8"))
    current = [
        item
        for item in catalog["documents"]
        if item["status"] == "current" and item["category"] == "department_instructions"
    ]
    if len(current) != 10:
        raise ValueError("Expected ten current department instructions")
    expected_sources = {f"{item['document_id']}.md" for item in current}
    if {path.name for path in authored.glob("*.md")} != expected_sources:
        raise ValueError("Authored department files do not match the current catalog")
    db = connect(state / "company.sqlite", readonly=True)
    try:
        for item in current:
            if item["facts"] != _department_facts(db, item["facts"]["id"]):
                raise ValueError(
                    f"Department SQL differs from document facts: {item['document_id']}"
                )
    finally:
        db.close()
    shutil.copytree(source, output)
    replacements = {}
    review = []
    for item in current:
        raw = (source / item["relative_path"]).read_text("utf-8")
        _, _, old_body = raw.split("---\n", 2)
        authored_path = authored / f"{item['document_id']}.md"
        body = _authored_body(old_body, authored_path.read_text("utf-8"))
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
            body,
        )
        replacements[item["document_id"]] = (older, newer)
        review.append(
            {
                "document_id": item["document_id"],
                "old_version": older["version"],
                "new_version": newer["version"],
                "authored_source": authored_path.relative_to(
                    authored.parent.parent.parent.parent
                ).as_posix(),
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
        "revised_department_instructions": len(review),
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
        raise ValueError(f"Department release failed bundle audit: {audit['issues']}")
    return manifest


def validate_department_release(db, catalog: list[dict], documents: Path) -> dict:
    """Check installed prose against the live department assignments and register."""
    current = [
        item
        for item in catalog
        if item["status"] == "current" and item["category"] == "department_instructions"
    ]
    if len(current) != 10:
        raise ValueError("Expected ten current department instructions")
    bodies = []
    for item in current:
        if item["revision"] != REVISION or item["version"] != 4:
            raise ValueError(f"Department document was not revised: {item['document_id']}")
        if item["facts"] != _department_facts(db, item["facts"]["id"]):
            raise ValueError(f"Department facts differ from SQL: {item['document_id']}")
        body = (documents / item["relative_path"]).read_text("utf-8").split("---\n", 2)[2]
        if any(body.count(heading) != 1 for heading in HEADINGS):
            raise ValueError(f"Department sections missing: {item['document_id']}")
        if any(phrase in body for phrase in OLD_BOILERPLATE):
            raise ValueError(f"Old boilerplate remains: {item['document_id']}")
        if item["facts"]["id"] not in body or str(item["facts"]["headcount"]) not in body:
            raise ValueError(f"Department body omits directory facts: {item['document_id']}")
        bodies.append(body)
    if len(set(bodies)) != 10:
        raise ValueError("Department instructions are not distinct")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Department release breaks database relationships")
    return {"status": "ok", "departments_checked": 10}


def install_department_release(project: Path, state: Path, bundle: Path) -> dict:
    return install_revision_bundle(
        project,
        state,
        bundle,
        database_validator=validate_department_release,
        not_before=date.fromisoformat(EFFECTIVE_FROM),
    )
