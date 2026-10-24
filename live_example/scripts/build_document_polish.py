"""Issue a controlled editorial correction to the installed Acme document set."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from acme.document_revision import _write_controlled, audit_revision_bundle

REVISION = "acme-documents-2026-r5"
PREVIOUS_END = "2026-10-20"
EFFECTIVE_FROM = "2026-10-21"


def polish(item: dict, body: str) -> tuple[str, list[str]]:
    """Edit presentation only; leave IDs, dates, amounts and linked facts intact."""
    rules = []

    def replace(old: str, new: str, label: str) -> None:
        nonlocal body
        if old in body:
            body = body.replace(old, new)
            rules.append(label)

    category = item["category"]
    if category == "incident_notes":
        replace("a invoice copy case", "an invoice copy request", "grammar: invoice request")
        replace(
            "The buyer reported: Buyer reports crushed packaging.",
            "The customer reported crushed packaging.",
            "case report wording",
        )
        revised, count = re.subn(
            r"The buyer reported: Buyer asks for the posted invoice and order reference "
            r"for ([A-Z0-9-]+)\.",
            r"The customer requested a copy of the posted invoice and the order "
            r"reference for \1.",
            body,
        )
        if count:
            body = revised
            rules.append("invoice request wording")
        replace("the in_progress transition", "a move to in progress", "case state wording")
        replace("The recorded review instruction was: ", "Required review: ", "review instruction")
    elif category == "procedures":
        revised, count = re.subn(
            r"Historical reference record `[A-Z0-9-]+` shows the expected identifier "
            r"format; it is not a substitute for the case at hand\.",
            "Use the record ID supplied with the case, then verify the linked "
            "account and event dates.",
            body,
        )
        if count:
            body = revised
            rules.append("remove teaching reference")
        replace(
            "When the question spans 2011 source history and contemporary fictional "
            "records, name each period separately.",
            "If the question spans archival 2011 and current records, present each "
            "period with its own dates and IDs.",
            "archive distinction",
        )
        replace("in_progress", "in progress", "state wording")
        replace(
            "Fictional account names and contacts are reference labels, not verified identities.",
            "Account names and contacts are directory labels; verify the selected "
            "account ID before disclosing a record.",
            "identity wording",
        )
    elif category == "department_instructions":
        replace(
            "Historical 2011 records and contemporary fictional scenarios need "
            "separate dates and provenance in cross-period analysis.",
            "Keep archival 2011 and current records in separate dated cohorts "
            "for cross-period analysis.",
            "cohort wording",
        )
    elif category == "customer_terms":
        replace(
            "The fictional company name and contact details are local account "
            "labels; confirm the selected account ID before sharing an order or document.",
            "Confirm the selected account ID before sharing an order or document; "
            "a similar trading name is insufficient.",
            "account identity wording",
        )
        replace(
            "Contemporary fictional accounts have separate dated histories; do not "
            "merge them into this 2011 account's source cohort.",
            "Current accounts have separate dated histories; do not merge them "
            "into this account's 2011 archive cohort.",
            "archive distinction",
        )
        replace(
            "The named business, contact and addresses are fictional training data.",
            "The named business, contact and addresses identify this account within the portal.",
            "account identification",
        )
        replace("exercise history", "recorded history", "history wording")
        replace("exercise balance", "balance", "balance wording")
        replace("current exercise record", "current account record", "service wording")
    elif category == "procurement_cases":
        replace("this fictional 2026 review", "this supplier review", "review scope")
        replace(
            "This document records exercise evidence at issue date; it is not a "
            "supplier acknowledgement or a customer delivery promise.",
            "This review records the evidence available at issue date; it is "
            "neither a supplier acknowledgement nor a customer delivery promise.",
            "evidence wording",
        )
        replace("current database status", "recorded status", "status wording")
        replace(
            "The recorded purchasing context says: ",
            "Purchasing recorded: ",
            "purchasing note wording",
        )
    elif category == "planning_commentary":
        replace("selected training period", "selected lookback period", "lookback wording")
        replace("the training total", "the billed unit total", "calculation wording")
        replace("Fictional contemporary review: ", "", "assumption wording")
        replace("Fictional planning target", "Planning target", "target wording")
        replace(
            "This is a fictional contemporary planning exercise, separate from "
            "the 2011 source archive.",
            "This run covers the current account cohort; the 2011 archive is "
            "excluded from its inputs.",
            "cohort wording",
        )
    elif category == "policies":
        replace("in_progress", "in progress", "state wording")
        replace(
            "Label reports about 2011 source history and contemporary fictional "
            "records separately, including their reference dates.",
            "Label archival 2011 and current records separately in reports, "
            "including their reference dates.",
            "archive distinction",
        )
        replace(
            "Keep source-history records from 2011 distinct from contemporary "
            "fictional history when presenting a timeline or report.",
            "Keep archival 2011 records distinct from current activity in timelines and reports.",
            "archive distinction",
        )
    return body, rules


def build(source: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Choose a new release directory")
    parent = audit_revision_bundle(source)
    if parent["status"] != "ok" or parent["revision"] != "acme-documents-2026-r4":
        raise ValueError("Expected the verified r4 document release")
    parent_manifest = json.loads((source / "release_manifest.json").read_text("utf-8"))
    shutil.copytree(source, output)
    catalog_path = output / "catalog.json"
    register = json.loads(catalog_path.read_text("utf-8"))
    revised = []
    review = []
    for item in register["documents"]:
        if item["status"] != "current":
            revised.append(item)
            continue
        raw = (source / item["relative_path"]).read_text("utf-8")
        _, _, body = raw.split("---\n", 2)
        cleaned, rules = polish(item, body)
        review.append(
            {"document_id": item["document_id"], "category": item["category"], "changes": rules}
        )
        if not rules:
            revised.append(item)
            continue
        revised.append(
            _write_controlled(
                output,
                {**item, "status": "superseded", "effective_until": PREVIOUS_END},
                body,
            )
        )
        revised.append(
            _write_controlled(
                output,
                {
                    **item,
                    "version": item["version"] + 1,
                    "status": "current",
                    "effective_from": EFFECTIVE_FROM,
                    "effective_until": None,
                    "revision": REVISION,
                },
                cleaned,
            )
        )
    revised.sort(key=lambda item: (item["document_id"], item["version"]))
    register["revision"] = REVISION
    register["documents"] = revised
    catalog_path.write_text(
        json.dumps(register, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "editorial_review.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest = {
        "revision": REVISION,
        "parent_catalog_sha256": parent_manifest["catalog_sha256"],
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "document_ids": len({item["document_id"] for item in revised}),
        "versions": len(revised),
        "reviewed_current_documents": len(review),
        "editorially_revised_documents": sum(bool(row["changes"]) for row in review),
    }
    (output / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    audit = audit_revision_bundle(output)
    if audit["status"] != "ok":
        raise ValueError(f"Editorial bundle failed audit: {audit['issues']}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
