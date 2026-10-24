"""Draft a controlled 2026 editorial revision without altering the v8 corpus."""

import hashlib
import json
import os
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from acme.company_documents import PROCEDURES
from acme.dataset import connect

REVISION = "acme-documents-2026-r2"
SOURCE_REFERENCE = "2011-12-09"
REVISION_START = "2026-10-20"
PREVIOUS_END = "2026-10-19"

DEPARTMENT_PRACTICE = {
    "DEP-ANALYTICS": (
        "Maintain forecast runs, the input cutoffs behind them, and comparable period reports.",
        "Send Sales the invoice cohort and uncertainty behind a proposed explanation.",
    ),
    "DEP-FINANCE": (
        "Reconcile invoice lines, receipts, allocations and credit notes before issuing a balance.",
        "Refer returns to Support and Warehouse Operations; a credit is not a stock receipt.",
    ),
    "DEP-IT": (
        "Maintain the local application, profile configuration, data backups and operational logs.",
        "Record failed jobs and access changes with time and affected service.",
    ),
    "DEP-LEADERSHIP": (
        "Own policy decisions, material exceptions and the review of cross-team operating risks.",
        "Require the responsible team, supporting record IDs and a decision date on escalations.",
    ),
    "DEP-LOGISTICS": (
        "Track dispatched consignments, carrier references and documented delivery events.",
        "Escalate a disputed delivery with its shipment ID and carrier evidence to Support.",
    ),
    "DEP-PEOPLE": (
        "Maintain employee assignments, effective dates and onboarding responsibilities.",
        "Confirm the current assignment before asking IT to change an application profile.",
    ),
    "DEP-PURCHASE": (
        "Track supplier terms, open purchase lines, expected dates and received quantities.",
        "Give Warehouse Operations the outstanding line quantity and revised supplier evidence.",
    ),
    "DEP-SALES": (
        "Maintain account context, order intake and the handoff of customer requests.",
        "Confirm product and order IDs before discussing quantity, availability or changes.",
    ),
    "DEP-SUPPORT": (
        "Record customer reports, evidence requests, ticket events and confirmed outcomes.",
        "Refer physical condition to Warehouse Operations and money decisions to Finance.",
    ),
    "DEP-WAREHOUSE": (
        "Reconcile receipts, picks, shipment lines, reservations and stock movements.",
        "Report a quantity or condition discrepancy with the product, warehouse and event IDs.",
    ),
}

PROCEDURE_REPHRASING = {
    "the learning tool inventory does not edit orders": (
        "order amendment requires an approved business process"
    ),
    "The assistant reads evidence but cannot allocate or move money": (
        "Finance posts allocations through its approved settlement process"
    ),
    "the assistant cannot place or accelerate a purchase order": (
        "Purchasing owns supplier follow-up and purchase-order amendments"
    ),
    "Synthetic names and contact addresses are training labels, not discovered identities": (
        "Fictional account names and contacts are reference labels, not verified identities"
    ),
    "Show the concrete report title, contents, source versions and operation ID "
    "to the conversation owner": (
        "Show the proposed title, contents, source versions and operation ID to the report owner"
    ),
    "Use the business reference date for today": "Use the reference date applicable to the event",
}


def _clean(text: str) -> str:
    for old, new in PROCEDURE_REPHRASING.items():
        text = text.replace(old, new)
    return text


def _money(pence: int) -> str:
    return f"GBP {pence / 100:,.2f}"


def render_procedure(item: dict) -> str:
    index = int(item["document_id"].split("-")[1]) - 1
    title, role, action, control, table = PROCEDURES[index]
    sample = item["facts"]["sample_id"]
    return (
        f"# {title}\n\n"
        f"## Use and owner\n\nThe {role.title()} team uses this procedure when a request concerns "
        f"`{table}`. Confirm the acting account or employee and identify the relevant record "
        f"before giving a status, amount or next step. Historical reference record `{sample}` "
        f"shows the expected identifier format; it is not a substitute for the case at hand.\n\n"
        f"## Review steps\n\n1. Open the `{table}` record and record its ID, effective date and "
        f"current state.\n2. Follow the linked order, account, product or financial entries needed "
        f"to check ownership and chronology.\n3. {_clean(action)}\n4. Record any missing "
        f"source and seek the responsible team's confirmation before making a commitment.\n\n"
        f"## Decision and exception\n\n{_clean(control)} An unresolved mismatch stays visible "
        f"with the conflicting IDs and amounts. A proposed correction needs a separate "
        f"authorized decision; a drafted answer is not evidence of a completed posting.\n\n"
        f"## Handoff record\n\nRecord who reviewed the case, the reference date, all supporting "
        f"IDs, the decision owner and the next action. When the question spans 2011 source "
        f"history and contemporary fictional records, name each period separately.\n"
    )


def render_product(item: dict) -> str:
    f = item["facts"]
    return (
        f"# Product handling and history: {f['name']}\n\n"
        f"## Identification\n\nUse stock code `{f['id']}` for this {f['category'].lower()} item. "
        f"Its historical selected order history contains {f['observed_lines']:,} lines and "
        f"{f['ordered_units']:,} units between {f['first_order']} and {f['last_order']}. "
        f"Descriptions and prices on individual source lines take precedence over a shortened "
        f"catalog label when investigating a particular transaction.\n\n"
        f"## Handling and dispatch check\n\n{f['handling_note']} Confirm the exact stock "
        f"code, count and packaging condition before a pick is released. Similar catalog names "
        f"do not establish matching dimensions, materials or compliance properties. Refer a "
        f"substitution to the product owner if those specifications are unavailable.\n\n"
        f"## Historical stock snapshot\n\nAt the 9 December 2011 reference date, "
        f"the Coventry model recorded {f['on_hand']:,} units on hand, {f['reserved']:,} "
        f"reserved and {f['available']:,} available. This is a historical position; "
        f"obtain a newly verified warehouse position before quoting present availability. "
        f"Supplier `{f['supplier_id']}` is the assigned sourcing contact. An open purchase "
        f"order is inbound evidence, not stock received or a guaranteed delivery date.\n\n"
        f"## Price and evidence control\n\nPrice-history rows retain the observed decimal "
        f"string and source-row ID. They show past transaction prices, not an approved current "
        f"quotation. Cite the exact order line and observation date in a pricing query; do "
        f"not infer tax treatment or product specifications from the catalog name.\n"
    )


def render_terms(item: dict) -> str:
    f = item["facts"]
    return (
        f"# Account record: {f['name']}\n\n"
        f"## Account and coverage\n\n`{f['id']}` identifies this {f['segment'].lower()} "
        f"account in Acme's historical trading records. Its source country is "
        f"{f['country']}. The fictional company name and contact details are local account "
        f"labels; confirm the selected account ID before sharing an order or document. "
        f"This record covers {f['orders']} selected orders from {f['first_order']} through "
        f"{f['last_order']}, not a claim about trading activity after that date.\n\n"
        f"## Commercial terms\n\nThe recorded invoice term is "
        f"{f['payment_terms_days']} calendar days from posting. Check the invoice's own "
        f"due date and the policy version applicable to a dispute. A shipment record, invoice "
        f"posting and payment receipt represent separate events. Do not describe an invoice "
        f"as paid without allocation evidence.\n\n"
        f"## Service and exceptions\n\nSales coordinates account and order questions. Support "
        f"reviews delivery or condition reports against the exact shipment and ticket. Finance "
        f"owns allocation and credit-note details. A country label does not provide a verified "
        f"street address or delivery promise. Preserve cancelled and partially supplied orders "
        f"in their recorded states.\n\n"
        f"## Record control\n\nUse the linked order, invoice and shipment IDs in any "
        f"customer-facing explanation. Contemporary fictional accounts have separate dated "
        f"histories; do not merge them into this 2011 account's source cohort.\n"
    )


def render_department(item: dict) -> str:
    f = item["facts"]
    practice, handoff = DEPARTMENT_PRACTICE[f["id"]]
    return (
        f"# {f['name']}: operating instruction\n\n"
        f"## Remit\n\nDepartment `{f['id']}` owns {f['responsibility'].lower()}. "
        f"The directory snapshot links {f['headcount']} people to this function. Consult "
        f"each employee's assignment dates and location before routing current work; "
        f"headcount in a historical snapshot is not a staffing guarantee for today.\n\n"
        f"## Daily controls\n\n{practice} Start from the primary business record, "
        f"check its linked evidence and record the review date. A summary or message is not "
        f"proof that an order, payment, ticket or stock entry changed. Keep the original event "
        f"sequence when a later decision supersedes an earlier one.\n\n"
        f"## Handoffs and exceptions\n\n{handoff} State the accountable team, "
        f"record IDs, unresolved facts and agreed next review. Raise a material discrepancy "
        f"before using the affected figure in a customer commitment or management report.\n\n"
        f"## Information handling\n\nShare source records under their document and business "
        f"scopes. Employee assignment data supports work routing, not access to private "
        f"conversations or reports. Historical 2011 records and contemporary fictional "
        f"scenarios need separate dates and provenance in cross-period analysis.\n"
    )


def render_incident(item: dict) -> str:
    f = item["facts"]
    report, _, instruction = f["description"].partition(". ")
    timeline = "\n".join(
        f"- **{event['occurred_on']} — {event['status'].replace('_', ' ')}:** {event['note']}"
        for event in f["events"]
    )
    topic_review = {
        "invoice_copy": (
            "Check that the supplied copy carries the original invoice identifier. "
            "A duplicate is not a second charge or proof of settlement."
        ),
        "damaged_goods": (
            "Compare the buyer's photographs and quantity report with the shipment lines. "
            "A credit or physical return requires a separate record."
        ),
        "split_consignment": (
            "Compare ordered units with each shipment line before describing the outstanding "
            "quantity or estimating another dispatch."
        ),
    }.get(
        f["topic"], "Review the linked order and supporting event records before closing the case."
    )
    return (
        f"# Service case record: {f['id']}\n\n"
        f"## Case identity\n\nAccount `{f['customer_id']}` raised a {f['topic'].replace('_', ' ')} "
        f"case about order `{f['order_id']}` on {f['opened_on']}. The buyer reported: "
        f"{report}. Keep the customer's statement distinct from shipment, invoice "
        f"and stock evidence.\n\n"
        f"## Recorded timeline\n\n{timeline}\n\nThe last recorded status is "
        f"**{f['status'].replace('_', ' ')}**. This status describes the service case; "
        f"it does not automatically change the order or invoice.\n\n"
        f"## Evidence and decision\n\nThe recorded review instruction was: {instruction} "
        f"{topic_review} Record the source ID for each "
        f"confirmed fact and identify any evidence still requested. If a correction, credit "
        f"or stock movement is needed, assign it to the owning team and cite the resulting "
        f"record only after it exists.\n\n"
        f"## Handoff\n\nRetain the original report, event order and outcome with this "
        f"ticket. Do not infer a customer promise from a supplier ETA or close a case "
        f"because a draft response was prepared.\n"
    )


def render_plan(item: dict) -> str:
    f = item["facts"]
    complete = f["target_end"] <= SOURCE_REFERENCE
    return (
        f"# Forecast review: {f['product_id']} / {f['target_start']}\n\n"
        f"## Recorded run\n\nForecast `{f['id']}` belongs to run `{f['run_id']}` "
        f"and estimates **{f['units']} units** for {f['target_start']} through "
        f"{f['target_end']}. Method version {f['method_version']} uses "
        f"{f['lookback_months']} preceding complete months with {f['training_units']} "
        f"billed units in the selected training period. The information cutoff is "
        f"{f['training_cutoff']}.\n\n"
        f"## Reproduction and controls\n\nUse only this product's invoice lines "
        f"posted by the cutoff and before the target starts. Include missing months as zero, "
        f"divide by the lookback length and round the final units half up. Input fingerprint "
        f"`{f['input_sha256']}` identifies the frozen source lines. Later actual sales "
        f"cannot be inserted into this run.\n\n"
        f"## Interpretation\n\nThis is an estimate of units, not a supplier order or "
        f"delivery commitment. Compare a second version only for the same product and "
        f"target period, showing both cutoffs and input sets. Promotions, shortages and "
        f"excluded transactions are outside this method. A different version is not "
        f"automatically more accurate.\n\n"
        f"## Review after the period\n\nThe target period is "
        f"{'complete' if complete else 'incomplete'} at the 9 December 2011 historical "
        f"reference date. Once complete, calculate actual billed units minus forecast "
        f"units; percentage error divides by the forecast and is undefined for a zero "
        f"forecast. Keep the original run and record later evaluation separately.\n"
    )


RENDERERS = {
    "procedures": render_procedure,
    "product_guides": render_product,
    "customer_terms": render_terms,
    "department_instructions": render_department,
    "incident_notes": render_incident,
    "planning_commentary": render_plan,
}


def build_revision_preview(project: Path, output: Path) -> dict:
    """Write distinct Markdown drafts; refuse to overwrite any previous review."""
    if output.exists():
        raise ValueError("Choose a new revision-preview directory")
    catalog = json.loads((project / "data/documents/catalog.json").read_text("utf-8"))["documents"]
    current = [item for item in catalog if item["status"] == "current"]
    staged = project / "data/document_sources/revision_v9"
    written = []
    output.mkdir(parents=True)
    for item in current:
        category = item["category"]
        identifier = item["document_id"]
        if category == "policies":
            body = (staged / "core" / f"{identifier}.md").read_text("utf-8")
            body = body.replace("{{WINDOW_DAYS}}", "30")
        else:
            body = RENDERERS[category](item)
        destination = output / category / f"{identifier}.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body, encoding="utf-8", newline="\n")
        written.append({"id": identifier, "category": category, "words": len(body.split())})
    for path in sorted((staged / "cases").glob("*.md")):
        destination = output / "contemporary_cases" / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text("utf-8")
        destination.write_text(text, encoding="utf-8", newline="\n")
        written.append(
            {"id": path.stem, "category": "contemporary_cases", "words": len(text.split())}
        )
    report = {"revision": REVISION, "documents": len(written), "items": written}
    (output / "review_manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {
        "revision": REVISION,
        "documents": len(written),
        "categories": sorted({x["category"] for x in written}),
    }


def audit_revision_preview(project: Path, output: Path, state: Path | None = None) -> dict:
    """Check every draft against the source register and linked modern case rows."""
    original = json.loads((project / "data/documents/catalog.json").read_text("utf-8"))["documents"]
    current = {item["document_id"]: item for item in original if item["status"] == "current"}
    manifest = json.loads((output / "review_manifest.json").read_text("utf-8"))
    issues = []
    expected = set(current) | {
        path.stem for path in (project / "data/document_sources/revision_v9/cases").glob("*.md")
    }
    actual = {item["id"] for item in manifest["items"]}
    if expected != actual or len(manifest["items"]) != len(expected):
        issues.append("Draft inventory differs from the current register and case sources")
    for item in manifest["items"]:
        identifier = item["id"]
        path = output / item["category"] / f"{identifier}.md"
        if not path.is_file():
            issues.append(f"Missing document: {identifier}")
            continue
        body = path.read_text("utf-8")
        if len(body.split()) < 150 or not body.startswith("# "):
            issues.append(f"Short or malformed document: {identifier}")
        if any(term in body.lower() for term in ("{{window_days}}", "learning assistant", "tbd")):
            issues.append(f"Unfinished language: {identifier}")
        if identifier in current:
            source = current[identifier]
            links = source["record_links"]
            required = (
                [source["facts"]["sample_id"]]
                if source["category"] == "procedures"
                else []
                if source["category"] == "policies"
                else list(links.values())
            )
            for linked_id in required:
                if linked_id not in body:
                    issues.append(f"Linked record absent from {identifier}: {linked_id}")
    if state is not None:
        db = connect(state / "company.sqlite", readonly=True)
        try:
            for item in manifest["items"]:
                if item["category"] != "contemporary_cases":
                    continue
                identifier = item["id"]
                row = db.execute(
                    "SELECT t.id,o.id AS order_id,i.id AS invoice_id,i.total_pence,"
                    "b.outstanding_pence,s.id AS shipment_id,c.id AS credit_id "
                    "FROM tickets t JOIN orders o ON o.id=t.order_id JOIN invoices i "
                    "ON i.order_id=o.id JOIN invoice_balances b ON b.id=i.id "
                    "JOIN shipments s ON s.order_id=o.id LEFT JOIN credit_notes c "
                    "ON c.invoice_id=i.id WHERE t.id=?",
                    (identifier,),
                ).fetchone()
                if row is None:
                    issues.append(f"No linked live case: {identifier}")
                    continue
                body = " ".join(
                    (output / "contemporary_cases" / f"{identifier}.md").read_text("utf-8").split()
                )
                for field in ("order_id", "invoice_id", "shipment_id", "credit_id"):
                    if row[field] and row[field] not in body:
                        issues.append(f"Missing {field} in {identifier}")
                if _money(row["total_pence"]) not in body:
                    issues.append(f"Incorrect invoice total in {identifier}")
                if row["outstanding_pence"] and _money(row["outstanding_pence"]) not in body:
                    issues.append(f"Incorrect outstanding amount in {identifier}")
        finally:
            db.close()
    return {
        "status": "ok" if not issues else "invalid",
        "revision": manifest["revision"],
        "documents": len(manifest["items"]),
        "issues": issues,
    }


def _write_controlled(folder: Path, metadata: dict, body: str) -> dict:
    relative = f"content/{metadata['document_id']}.v{metadata['version']}.md"
    metadata = {**metadata, "relative_path": relative}
    text = (
        "---\n"
        + json.dumps(
            {
                key: value
                for key, value in metadata.items()
                if key not in {"title", "relative_path", "sha256"}
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n---\n"
        + body.strip()
        + "\n"
    )
    path = folder / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {**metadata, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build_revision_bundle(project: Path, preview: Path, output: Path, state: Path) -> dict:
    """Package old and revised versions in a new immutable candidate directory."""
    if output.exists():
        raise ValueError("Choose a new document-release directory")
    audit = audit_revision_preview(project, preview, state)
    if audit["status"] != "ok":
        raise ValueError("Document preview has unresolved audit issues")
    base = project / "data/documents"
    originals = json.loads((base / "catalog.json").read_text("utf-8"))["documents"]
    catalog = []
    output.mkdir(parents=True)
    for item in originals:
        raw = (base / item["relative_path"]).read_text("utf-8")
        _, metadata_text, body = raw.split("---\n", 2)
        metadata = json.loads(metadata_text)
        if item["status"] == "current":
            metadata["status"] = "superseded"
            metadata["effective_until"] = PREVIOUS_END
            entry = _write_controlled(
                output,
                {**item, **metadata},
                body,
            )
        else:
            destination = output / item["relative_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(raw, encoding="utf-8", newline="\n")
            entry = dict(item)
        catalog.append(entry)
        if item["status"] != "current":
            continue
        revised = (preview / item["category"] / f"{item['document_id']}.md").read_text("utf-8")
        new_version = item["version"] + 1
        catalog.append(
            _write_controlled(
                output,
                {
                    **item,
                    "version": new_version,
                    "effective_from": REVISION_START,
                    "effective_until": None,
                    "status": "current",
                    "revision": REVISION,
                },
                revised,
            )
        )
    db = connect(state / "company.sqlite", readonly=True)
    try:
        for source in sorted((preview / "contemporary_cases").glob("*.md")):
            ticket_id = source.stem
            ticket = db.execute(
                "SELECT t.id,t.order_id,t.assigned_employee_id FROM tickets t WHERE t.id=? "
                "AND t.provenance='fictional_contemporary_seed'",
                (ticket_id,),
            ).fetchone()
            if ticket is None:
                raise ValueError(f"Case disappeared before bundling: {ticket_id}")
            identifier = "CASE-" + ticket_id.removeprefix("SCN-TKT-")
            catalog.append(
                _write_controlled(
                    output,
                    {
                        "document_id": identifier,
                        "title": source.read_text("utf-8").splitlines()[0].removeprefix("# "),
                        "category": "incident_notes",
                        "owner_employee_id": ticket["assigned_employee_id"],
                        "access_scope": "support",
                        "version": 1,
                        "effective_from": REVISION_START,
                        "effective_until": None,
                        "status": "current",
                        "record_links": {
                            "ticket_id": ticket_id,
                            "order_id": ticket["order_id"],
                        },
                        "facts": {"ticket_id": ticket_id, "order_id": ticket["order_id"]},
                        "revision": REVISION,
                    },
                    source.read_text("utf-8"),
                )
            )
    finally:
        db.close()
    catalog.sort(key=lambda item: (item["document_id"], item["version"]))
    register = {
        "revision": REVISION,
        "source_dataset_version": "acme-company-v8",
        "historical_reference": SOURCE_REFERENCE,
        "effective_from": REVISION_START,
        "documents": catalog,
    }
    register_path = output / "catalog.json"
    register_path.write_text(
        json.dumps(register, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "revision": REVISION,
        "catalog_sha256": hashlib.sha256(register_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in catalog}),
        "versions": len(catalog),
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def audit_revision_bundle(bundle: Path) -> dict:
    """Validate every content hash, version interval and register field."""
    manifest = json.loads((bundle / "release_manifest.json").read_text("utf-8"))
    catalog_path = bundle / "catalog.json"
    catalog = json.loads(catalog_path.read_text("utf-8"))["documents"]
    issues = []
    if hashlib.sha256(catalog_path.read_bytes()).hexdigest() != manifest["catalog_sha256"]:
        issues.append("Catalog checksum mismatch")
    if len(catalog) != manifest["versions"]:
        issues.append("Version count mismatch")
    by_id = {}
    for item in catalog:
        identifier = item["document_id"]
        by_id.setdefault(identifier, []).append(item)
        path = (bundle / item["relative_path"]).resolve()
        if not path.is_relative_to((bundle / "content").resolve()) or not path.is_file():
            issues.append(f"Invalid content path: {identifier}:v{item['version']}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            issues.append(f"Content checksum mismatch: {identifier}:v{item['version']}")
        try:
            _, metadata_text, body = path.read_text("utf-8").split("---\n", 2)
            metadata = json.loads(metadata_text)
        except (ValueError, json.JSONDecodeError):
            issues.append(f"Malformed metadata: {identifier}:v{item['version']}")
            continue
        for key in (
            "document_id",
            "version",
            "effective_from",
            "effective_until",
            "status",
            "category",
            "owner_employee_id",
            "access_scope",
            "record_links",
            "facts",
        ):
            if metadata.get(key) != item.get(key):
                issues.append(f"Metadata mismatch: {identifier}:v{item['version']}:{key}")
        if not body.strip().startswith("# "):
            issues.append(f"Body has no title: {identifier}:v{item['version']}")
    if len(by_id) != manifest["document_ids"]:
        issues.append("Document ID count mismatch")
    for identifier, versions in by_id.items():
        versions.sort(key=lambda item: item["version"])
        if [item["version"] for item in versions] != list(range(1, len(versions) + 1)):
            issues.append(f"Non-contiguous versions: {identifier}")
        if sum(item["status"] == "current" for item in versions) != 1:
            issues.append(f"Current-version count is not one: {identifier}")
        for older, later in zip(versions, versions[1:]):
            if later["effective_from"] < older["effective_from"]:
                issues.append(f"Version dates run backwards: {identifier}")
            if (
                older["effective_until"] is None
                or older["effective_until"] > later["effective_from"]
            ):
                issues.append(f"Overlapping effective intervals: {identifier}")
    return {
        "status": "ok" if not issues else "invalid",
        "revision": manifest["revision"],
        "document_ids": len(by_id),
        "versions": len(catalog),
        "issues": issues,
    }


def _assert_original_register(db, originals: list[dict]) -> None:
    """Protect installed versions and each document's current metadata."""
    for item in originals:
        row = db.execute(
            "SELECT status,effective_from,effective_until,relative_path,sha256 "
            "FROM document_versions WHERE document_id=? AND version=?",
            (item["document_id"], item["version"]),
        ).fetchone()
        if row is None or any(row[key] != item[key] for key in row.keys()):
            raise ValueError(
                f"Document register was edited after installation: "
                f"{item['document_id']}:v{item['version']}"
            )
        if item["status"] == "current":
            owner = db.execute(
                "SELECT title,category,owner_employee_id,access_scope FROM documents WHERE id=?",
                (item["document_id"],),
            ).fetchone()
            if owner is None or any(owner[key] != item[key] for key in owner.keys()):
                raise ValueError(f"Current document metadata was edited: {item['document_id']}")
    for identifier in {item["document_id"] for item in originals}:
        item = next(row for row in originals if row["document_id"] == identifier)
        links = db.execute(
            "SELECT customer_id,product_id,department_id,warehouse_id,ticket_id,forecast_id,"
            "invoice_id,order_id FROM document_links WHERE document_id=?",
            (identifier,),
        ).fetchall()
        actual = {
            key: value for link in links for key, value in dict(link).items() if value is not None
        }
        if actual != item["record_links"]:
            raise ValueError(f"Document links were edited after v8: {identifier}")


def apply_revision_register(db, originals: list[dict], revised: list[dict]) -> None:
    """Apply the checked release rows to an isolated SQLite copy."""
    original_keys = {(item["document_id"], item["version"]) for item in originals}
    original_ids = {item["document_id"] for item in originals}
    _assert_original_register(db, originals)
    for item in revised:
        identifier = item["document_id"]
        version = item["version"]
        if (identifier, version) in original_keys:
            db.execute(
                "UPDATE document_versions SET status=?,effective_until=?,relative_path=?,"
                "sha256=? WHERE document_id=? AND version=?",
                (
                    item["status"],
                    item["effective_until"],
                    item["relative_path"],
                    item["sha256"],
                    identifier,
                    version,
                ),
            )
    for item in revised:
        identifier = item["document_id"]
        version = item["version"]
        if (identifier, version) in original_keys:
            continue
        if identifier not in original_ids:
            db.execute(
                "INSERT INTO documents VALUES(?,?,?,?,?)",
                (
                    identifier,
                    item["title"],
                    item["category"],
                    item["owner_employee_id"],
                    item["access_scope"],
                ),
            )
            for index, (column, value) in enumerate(item["record_links"].items(), 1):
                db.execute(
                    f"INSERT INTO document_links(id,document_id,{column}) VALUES(?,?,?)",
                    (f"{identifier}:LINK-{index}", identifier, value),
                )
            original_ids.add(identifier)
        db.execute(
            "INSERT INTO document_versions VALUES(?,?,?,?,?,?,?,?)",
            (
                f"{identifier}:v{version}",
                identifier,
                version,
                item["effective_from"],
                item["effective_until"],
                item["status"],
                item["relative_path"],
                item["sha256"],
            ),
        )
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Document release creates broken company references")
    for item in revised:
        if item["status"] != "current":
            continue
        db.execute(
            "UPDATE documents SET title=?,category=?,owner_employee_id=?,access_scope=? "
            "WHERE id=?",
            (
                item["title"],
                item["category"],
                item["owner_employee_id"],
                item["access_scope"],
                item["document_id"],
            ),
        )
        count = db.execute(
            "SELECT COUNT(*) FROM document_versions WHERE document_id=? AND status='current'",
            (item["document_id"],),
        ).fetchone()[0]
        if count != 1:
            raise ValueError(f"Document lacks exactly one current version: {item['document_id']}")


def install_revision_bundle(
    project: Path,
    state: Path,
    bundle: Path,
    *,
    database_transform=None,
    database_validator=None,
    not_before: date | None = None,
) -> dict:
    """Install a verified release into exercise state with a full database backup."""
    if not_before is not None and date.today() < not_before:
        raise ValueError(f"Document release cannot be installed before {not_before.isoformat()}")
    audit = audit_revision_bundle(bundle)
    if audit["status"] != "ok":
        raise ValueError("Document release bundle failed audit")
    live_documents = state / "documents"
    marker = live_documents / "installed.json"
    release_manifest = json.loads((bundle / "release_manifest.json").read_text("utf-8"))
    upgrading = marker.is_file()
    if marker.is_file():
        installed = json.loads(marker.read_text("utf-8"))
        if installed["catalog_sha256"] == release_manifest["catalog_sha256"]:
            return {"status": "already_installed", "revision": audit["revision"]}
        if installed["catalog_sha256"] != release_manifest.get("parent_catalog_sha256"):
            raise ValueError("Document release is not a verified successor to the installed one")
    elif live_documents.exists():
        raise ValueError("Unfinished document installation exists; inspect before retrying")
    source_catalog = live_documents if upgrading else project / "data/documents"
    originals = json.loads((source_catalog / "catalog.json").read_text("utf-8"))["documents"]
    revised = json.loads((bundle / "catalog.json").read_text("utf-8"))["documents"]
    database = state / "company.sqlite"
    stamp = (database.stat().st_size, database.stat().st_mtime_ns)
    backup = (
        state
        / "backups"
        / (
            "document-release-"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid4().hex[:6]
        )
    )
    backup.mkdir(parents=True, exist_ok=False)
    staged_db = state / f".company-docs-{uuid4().hex}.sqlite"
    staged_documents = state / f".documents-{uuid4().hex}"
    source = connect(database, readonly=True)
    replacement = connect(staged_db)
    try:
        source.backup(replacement)
    finally:
        replacement.close()
        source.close()
    shutil.copy2(staged_db, backup / "company.sqlite")
    if upgrading:
        shutil.copytree(live_documents, backup / "documents")
    shutil.copytree(bundle, staged_documents)
    db = connect(staged_db)
    try:
        db.execute("BEGIN IMMEDIATE")
        if database_transform is not None:
            database_transform(db)
        apply_revision_register(db, originals, revised)
        if database_validator is not None:
            database_validator(db, revised, staged_documents)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if (database.stat().st_size, database.stat().st_mtime_ns) != stamp:
        raise ValueError("Company data changed during document installation; live state preserved")
    os.replace(staged_db, database)
    retired_documents = backup / "retired_documents"
    try:
        if upgrading:
            live_documents.rename(retired_documents)
        staged_documents.rename(live_documents)
    except Exception:
        if upgrading and retired_documents.is_dir() and not live_documents.exists():
            retired_documents.rename(live_documents)
        shutil.copy2(backup / "company.sqlite", database)
        raise
    marker.write_text(
        json.dumps(
            {
                "revision": audit["revision"],
                "catalog_sha256": release_manifest["catalog_sha256"],
                "installed_at_utc": datetime.now(UTC).isoformat(),
                "backup": str(backup),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "status": "installed",
        "revision": audit["revision"],
        "document_ids": audit["document_ids"],
        "versions": audit["versions"],
        "backup": str(backup),
    }
