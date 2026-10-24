"""Explicit build, validation and exercise-state lifecycle; no startup generation."""

import gzip
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from acme.company_data import AS_OF, VERSION, populate
from acme.company_documents import build_documents
from acme.company_validation import logical_manifest, validate_company
from acme.source_data import sha256, verify_prepared, write_json


def connect(path, readonly=False):
    path = Path(path).resolve()
    db = sqlite3.connect(path.as_uri() + "?mode=ro" if readonly else str(path), uri=readonly)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def build_dataset(project, output, profile="full"):
    """Write a new baseline bundle. Never replace an existing baseline or corpus."""
    if profile not in {"full", "fixture"}:
        raise ValueError("Profile must be full or fixture")
    baseline = output / "company/baseline"
    documents = output / "documents"
    if (
        baseline.exists()
        or (documents / "catalog.json").exists()
        or (documents / "content").exists()
    ):
        raise ValueError(
            "Output already contains a baseline or corpus. Choose a new output directory."
        )
    baseline.mkdir(parents=True)
    database = baseline / "company.sqlite"
    db = connect(database)
    try:
        counts = populate(db, project, profile)
        doc_count, version_count = build_documents(db, project, documents, profile)
        db.commit()
        validation = validate_company(db, project, documents, profile)
        content = logical_manifest(db)
        db.execute("VACUUM")
    finally:
        db.close()
    compressed = baseline / "company.sqlite.gz"
    with database.open("rb") as source, compressed.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as target:
            shutil.copyfileobj(source, target)
    manifest = {
        "dataset_version": VERSION,
        "schema_version": 1,
        "profile": profile,
        "business_reference": AS_OF,
        "source_zip_sha256": json.loads(
            (project / "data/sources/download_receipt.json").read_text("utf-8")
        )["sha256"],
        "schema_sha256": sha256(Path(__file__).with_name("schema.sql")),
        "database_sha256": sha256(database),
        "database_bytes": database.stat().st_size,
        "archive_sha256": sha256(compressed),
        "archive_bytes": compressed.stat().st_size,
        "documents_catalog_sha256": sha256(documents / "catalog.json"),
        **content,
    }
    write_json(baseline / "manifest.json", manifest)
    write_json(
        baseline / "preparation_report.json",
        {
            "dataset_version": VERSION,
            "profile": profile,
            **counts,
            "documents": doc_count,
            "document_versions": version_count,
            "rules": [
                (
                    "complete eligible UCI baskets only; original quantities, dates and decimal "
                    "prices retained"
                ),
                (
                    "one reconstructed order per invoice; modeled weekday acceptance one to "
                    "four working days before observed posting"
                ),
                (
                    "fictional labels, category assignments, suppliers, payment terms and all "
                    "operational events"
                ),
                "one half-up rounding per posted GBP line; no VAT interpretation asserted",
                (
                    "partial dispatch for lines >=48 units, followed by a varied weekday "
                    "second consignment when it existed at the business cutoff"
                ),
                (
                    "fictional account remittance weekdays, invoice-level timing and varied "
                    "installments; one receipt may allocate across several invoices"
                ),
                (
                    "modest opening stock and supplier-specific weekly, carton-sized receipts "
                    "retrospectively reconstruct a nonnegative stock ledger; future unshipped "
                    "orders are not invented as historical opening stock"
                ),
                "fictional carrier assignments and weekday delivery intervals vary by consignment",
                (
                    "sampled service cases follow first dispatch or invoice posting, rotate "
                    "across support staff, and use varied working-day review intervals"
                ),
                (
                    "forecasts query only billed units before their target start; future actuals "
                    "are evaluation only"
                ),
                (
                    "DEMO namespace supplies authored scenario records, separate from observed "
                    "customer IDs"
                ),
            ],
            "excluded_source_records": (
                "Remain intact in the separate G03 staging dataset; no inferred "
                "cancellation-to-sale or return links"
            ),
            "startup": (
                "Initialize by verified decompression, not regeneration; documents are fixed "
                "Markdown artifacts"
            ),
        },
    )
    write_json(baseline / "validation_report.json", validation)
    database.unlink()
    return {
        "dataset_version": VERSION,
        "profile": profile,
        "content_sha256": content["content_sha256"],
        "table_counts": validation["table_counts"],
        "documents": validation["documents"],
    }


def baseline_manifest(data):
    folder = data / "company/baseline"
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    if manifest["dataset_version"] != VERSION or manifest["schema_version"] != 1:
        raise ValueError("Unsupported baseline version; existing exercise state was not changed")
    if manifest["schema_sha256"] != sha256(Path(__file__).with_name("schema.sql")):
        raise ValueError("Baseline schema differs from this application version")
    if sha256(folder / "company.sqlite.gz") != manifest["archive_sha256"]:
        raise ValueError("Baseline archive checksum mismatch")
    if sha256(data / "documents/catalog.json") != manifest["documents_catalog_sha256"]:
        raise ValueError("Document catalog checksum mismatch")
    for item in json.loads((data / "documents/catalog.json").read_text("utf-8"))["documents"]:
        path = (data / "documents" / item["relative_path"]).resolve()
        if not path.is_relative_to((data / "documents/content").resolve()):
            raise ValueError("Document path leaves the corpus")
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Document content checksum mismatch: {path.name}")
    return manifest


def unpack_database(data, destination, manifest):
    with (
        gzip.open(data / "company/baseline/company.sqlite.gz", "rb") as source,
        destination.open("xb") as target,
    ):
        shutil.copyfileobj(source, target)
    if sha256(destination) != manifest["database_sha256"]:
        raise ValueError("Uncompressed baseline checksum mismatch")


def verify_dataset(project, data):
    manifest = baseline_manifest(data)
    verify_prepared(project / "data/company/prepared")
    receipt = json.loads((project / "data/sources/download_receipt.json").read_text("utf-8"))
    if manifest["source_zip_sha256"] != receipt["sha256"]:
        raise ValueError("Company source identity differs from the pinned public dataset")
    with tempfile.TemporaryDirectory(prefix="acme-verify-") as temporary:
        database = Path(temporary) / "company.sqlite"
        unpack_database(data, database, manifest)
        db = connect(database, readonly=True)
        try:
            report = validate_company(db, project, data / "documents", manifest["profile"])
            logical = logical_manifest(db)
            if (
                logical["content_sha256"] != manifest["content_sha256"]
                or logical["tables"] != manifest["tables"]
            ):
                raise ValueError("Logical records differ from the content manifest")
        finally:
            db.close()
    return report


def initialize_state(project, state, reset=False, data=None):
    """Preserve existing exercises. Reset replaces only this named company database."""
    data = data or project / "data"
    manifest = baseline_manifest(data)
    state.mkdir(parents=True, exist_ok=True)
    database = state / "company.sqlite"
    receipt = state / "baseline.json"
    if database.exists() and not reset:
        if not receipt.exists():
            raise ValueError(
                "Existing exercise database has no baseline receipt; preserved unchanged"
            )
        current = json.loads(receipt.read_text("utf-8"))
        if current["content_sha256"] != manifest["content_sha256"]:
            raise ValueError(
                (
                    "Exercise state uses a different baseline; preserved unchanged. Use an "
                    "explicit reset if intended."
                )
            )
        return {"status": "preserved", "database": str(database)}
    # Exclusive lock prevents simultaneous initialization/reset. A failed operation
    # leaves the prior database in place. Never delete another process's lock.
    lock = state / ".company-initialize.lock"
    with lock.open("x"):
        pass
    try:
        with tempfile.TemporaryDirectory(prefix=".company-build-", dir=state) as temporary:
            replacement = Path(temporary) / "company.sqlite"
            unpack_database(data, replacement, manifest)
            replacement.replace(database)
            write_json(
                receipt,
                {
                    "dataset_version": VERSION,
                    "content_sha256": manifest["content_sha256"],
                    "profile": manifest["profile"],
                },
            )
    finally:
        lock.unlink()
    return {"status": "reset" if reset else "initialized", "database": str(database)}
