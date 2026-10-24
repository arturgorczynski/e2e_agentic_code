"""Reproducible, standard-library-only preparation of the UCI retail workbook.

This is a dataset import, not an application database or a RAG index. Importing
this module performs no I/O. Network access occurs only in fetch_source().
"""

import csv
import gzip
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/352/online%2Bretail"
RECIPE_VERSION = "uci-retail-v1"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
HEADERS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]
FIELDS = [
    "source_row_id",
    "invoice_no",
    "stock_code",
    "description",
    "quantity",
    "invoice_date_local",
    "unit_price_gbp",
    "customer_id",
    "country",
    "transaction_kind",
    "duplicate_of",
    "issues",
]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def fetch_source(project_dir: Path) -> Path:
    """Download the official archive once and pin its identity in a receipt."""
    folder = project_dir / "data/sources/raw"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "online_retail.zip"
    receipt_path = project_dir / "data/sources/download_receipt.json"
    if path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if sha256(path) != receipt["sha256"]:
            raise ValueError("Cached source checksum differs from the pinned download receipt.")
        return path
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Acme-learning-data/0.1"})
    partial = path.with_suffix(".part")
    try:
        with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
            metadata = {
                "url": SOURCE_URL,
                "resolved_url": response.url,
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "sha256": sha256(partial),
                "bytes": partial.stat().st_size,
            }
        if receipt_path.exists():
            pinned = json.loads(receipt_path.read_text(encoding="utf-8"))
            if metadata["sha256"] != pinned["sha256"]:
                raise ValueError("Upstream source changed. Review it as a new dataset version.")
        partial.replace(path)
        if not receipt_path.exists():
            write_json(receipt_path, metadata)
    finally:
        partial.unlink(missing_ok=True)
    return path


def workbook_rows(workbook: bytes):
    """Read the known eight-column worksheet without editing the source XLSX."""
    with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
        book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        properties = book.find(f"{NS}workbookPr")
        if properties is not None and properties.get("date1904") in {"1", "true"}:
            raise ValueError("Unexpected workbook date system")
        strings = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(item.itertext()) for item in strings]
        with archive.open("xl/worksheets/sheet1.xml") as stream:
            sheet_data = None
            for event, element in ElementTree.iterparse(stream, events=("start", "end")):
                if event == "start" and element.tag == f"{NS}sheetData":
                    sheet_data = element
                if event != "end" or element.tag != f"{NS}row":
                    continue
                values = [None] * 8
                for cell in element:
                    column = re.match(r"[A-Z]+", cell.attrib["r"])[0]
                    if len(column) != 1 or column > "H":
                        raise ValueError("Unexpected source column")
                    value = cell.find(f"{NS}v")
                    if value is not None:
                        text = value.text
                        if cell.get("t") == "s":
                            text = shared[int(text)]
                        values[ord(column) - ord("A")] = text
                yield int(element.attrib["r"]), values
                element.clear()
                sheet_data.clear()


def normalize(row_number: int, values: list) -> dict:
    invoice, stock, description, quantity, serial, price, customer, country = values
    quantity_value = Decimal(quantity)
    if quantity_value != quantity_value.to_integral_value():
        raise ValueError(f"Fractional source quantity at row {row_number}")
    quantity = int(quantity_value)
    timestamp = datetime(1899, 12, 30) + timedelta(seconds=round(Decimal(serial) * 86400))
    unit_price = Decimal(price)
    customer = str(int(Decimal(customer))) if customer is not None else ""
    kind = (
        "cancellation"
        if invoice.startswith("C")
        else ("sale" if invoice.isdigit() else "adjustment")
    )
    issues = []
    for field, value in [
        ("customer", customer),
        ("description", description),
        ("country", country),
        ("stock", stock),
    ]:
        if not value:
            issues.append(f"missing_{field}")
    if quantity <= 0:
        issues.append("nonpositive_quantity")
    if unit_price <= 0:
        issues.append("nonpositive_price")
    if not re.fullmatch(r"\d{5}[A-Za-z]*", stock or ""):
        issues.append("nonstandard_stock_code")
    return {
        "source_row_id": f"UCI352:Sheet1:{row_number}",
        "invoice_no": invoice,
        "stock_code": stock or "",
        "description": description or "",
        "quantity": quantity,
        "invoice_date_local": timestamp.isoformat(),
        "unit_price_gbp": format(unit_price, "f"),
        "customer_id": customer,
        "country": country or "",
        "transaction_kind": kind,
        "duplicate_of": "",
        "issues": issues,
    }


def prepare_source(project_dir: Path, output_dir: Path | None = None) -> dict:
    """Prepare all rows; classify whole invoice groups without deleting anomalies."""
    source_dir = project_dir / "data/sources"
    receipt = json.loads((source_dir / "download_receipt.json").read_text(encoding="utf-8"))
    archive_path = source_dir / "raw/online_retail.zip"
    if sha256(archive_path) != receipt["sha256"]:
        raise ValueError("Source checksum mismatch; refusing preparation")
    with zipfile.ZipFile(archive_path) as archive:
        workbook = archive.read("Online Retail.xlsx")
    output_dir = output_dir or project_dir / "data/company/prepared"
    output_dir.mkdir(parents=True, exist_ok=True)
    counts, missing, kinds, monthly, countries = (Counter() for _ in range(5))
    prices, quantities, dates = [], [], []
    customers, products, seen, invoices = set(), set(), {}, {}
    csv_path = output_dir / "transactions.csv.gz"
    # Empty gzip filename and mtime=0 make compressed bytes reproducible.
    with (
        csv_path.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
    ):
        with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
            writer = csv.DictWriter(text, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            for row_number, values in workbook_rows(workbook):
                if row_number == 1:
                    if values != HEADERS:
                        raise ValueError(f"Unexpected source headers: {values}")
                    continue
                row = normalize(row_number, values)
                key = tuple(row[field] for field in FIELDS[1:9])
                if key in seen:
                    row["duplicate_of"] = seen[key]
                    row["issues"].append("exact_duplicate")
                    counts["exact_duplicate_rows_after_first"] += 1
                else:
                    seen[key] = row["source_row_id"]
                counts["rows"] += 1
                for issue in row["issues"]:
                    missing[issue] += 1
                kinds[row["transaction_kind"]] += 1
                monthly[row["invoice_date_local"][:7]] += 1
                countries[row["country"]] += 1
                price = Decimal(row["unit_price_gbp"])
                prices.append(price)
                quantities.append(row["quantity"])
                dates.append(row["invoice_date_local"])
                if row["customer_id"]:
                    customers.add(row["customer_id"])
                products.add(row["stock_code"])
                counts["negative_price"] += price < 0
                counts["zero_price"] += price == 0
                counts["negative_quantity"] += row["quantity"] < 0
                counts["zero_quantity"] += row["quantity"] == 0
                counts["prices_beyond_two_decimal_places"] += price != price.quantize(
                    Decimal("0.01")
                )
                residual = abs(price - price.quantize(Decimal("0.01")))
                counts["near_cent_serialization_residuals"] += (
                    0 < residual <= Decimal("0.0000000001")
                )
                counts["material_subpenny_prices"] += residual > Decimal("0.0000000001")
                counts["quantity_abs_over_1000"] += abs(row["quantity"]) > 1000
                counts["unit_price_over_1000"] += price > 1000
                group = invoices.setdefault(
                    row["invoice_no"],
                    {
                        "row_count": 0,
                        "customers": set(),
                        "countries": set(),
                        "kind": row["transaction_kind"],
                        "issues": set(),
                        "source_signed_value_gbp": Decimal(0),
                    },
                )
                group["row_count"] += 1
                group["customers"].add(row["customer_id"])
                group["countries"].add(row["country"])
                group["issues"].update(row["issues"])
                group["source_signed_value_gbp"] += price * row["quantity"]
                row["issues"] = "|".join(row["issues"])
                writer.writerow(row)
    invoice_path = output_dir / "invoice_groups.csv.gz"
    group_fields = [
        "invoice_no",
        "row_count",
        "transaction_kind",
        "customer_ids",
        "countries",
        "eligible_sale",
        "issues",
        "source_signed_value_gbp",
    ]
    with (
        invoice_path.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
    ):
        with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
            writer = csv.DictWriter(text, fieldnames=group_fields, lineterminator="\n")
            writer.writeheader()
            for invoice, group in sorted(invoices.items()):
                if len(group["customers"]) != 1 or len(group["countries"]) != 1:
                    group["issues"].add("inconsistent_invoice_identity")
                eligible = group["kind"] == "sale" and not group["issues"]
                counts["eligible_sale_invoices"] += bool(eligible)
                counts["eligible_sale_rows"] += group["row_count"] if eligible else 0
                writer.writerow(
                    {
                        "invoice_no": invoice,
                        "row_count": group["row_count"],
                        "transaction_kind": group["kind"],
                        "customer_ids": "|".join(sorted(group["customers"])),
                        "countries": "|".join(sorted(group["countries"])),
                        "eligible_sale": int(bool(eligible)),
                        "issues": "|".join(sorted(group["issues"])),
                        "source_signed_value_gbp": str(group["source_signed_value_gbp"]),
                    }
                )
    profile = {
        "recipe_version": RECIPE_VERSION,
        "source_zip_sha256": receipt["sha256"],
        "source_workbook_sha256": hashlib.sha256(workbook).hexdigest(),
        "source_workbook_bytes": len(workbook),
        "source_sheet": "Sheet1",
        "counts": {
            **dict(counts),
            "invoice_groups": len(invoices),
            "identified_customers": len(customers),
            "stock_codes": len(products),
        },
        "issues": dict(missing),
        "transaction_kinds": dict(kinds),
        "time_range_local": {"min": min(dates), "max": max(dates)},
        "unit_price_gbp": {"min": str(min(prices)), "max": str(max(prices))},
        "quantity": {"min": min(quantities), "max": max(quantities)},
        "monthly_rows": dict(monthly),
        "country_rows": dict(countries),
        "selection": (
            "All source rows retained in source order; no row-level filtering or deduplication."
        ),
        "eligibility": (
            "Whole numeric sale invoice, positive price/quantity, complete identity/description, "
            "standard stock codes, no duplicates or inconsistent invoice identity."
        ),
        "value_semantics": (
            "Signed quantity * source unit price; not asserted to be net revenue, VAT, "
            "cash received, or an audited invoice total."
        ),
        "price_precision_note": (
            "Preserve raw XLSX numeric text. Beyond-two-decimal values include binary "
            "serialization residuals; near-cent threshold is 1e-10 GBP, not a cleaning rule."
        ),
    }
    write_json(output_dir / "profile.json", profile)
    manifest = {
        "dataset_version": RECIPE_VERSION,
        "source_zip_sha256": receipt["sha256"],
        "source_workbook_sha256": profile["source_workbook_sha256"],
        "source_page": SOURCE_PAGE,
        "license": "CC-BY-4.0",
        "files": {
            path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in [csv_path, invoice_path, output_dir / "profile.json"]
        },
    }
    write_json(output_dir / "manifest.json", manifest)
    return profile


def verify_prepared(folder: Path) -> dict:
    """Verify shipped artifacts and complete invoice membership without the XLSX."""
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    required_files = {"transactions.csv.gz", "invoice_groups.csv.gz", "profile.json"}
    if set(manifest["files"]) != required_files:
        raise ValueError("Prepared manifest must contain exactly the three dataset artifacts")
    for name, entry in manifest["files"].items():
        if Path(name).name != name:
            raise ValueError("Manifest contains a non-local path")
        if sha256(folder / name) != entry["sha256"]:
            raise ValueError(f"Prepared artifact checksum mismatch: {name}")
        if (folder / name).stat().st_size != entry["bytes"]:
            raise ValueError(f"Prepared artifact size mismatch: {name}")
    counts = Counter()
    with gzip.open(folder / "transactions.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        for expected_row, row in enumerate(csv.DictReader(stream), start=2):
            if row["source_row_id"] != f"UCI352:Sheet1:{expected_row}":
                raise ValueError("Missing, reordered, or duplicate source row identifier")
            counts[row["invoice_no"]] += 1
    with gzip.open(folder / "invoice_groups.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        groups = list(csv.DictReader(stream))
    if (
        len({g["invoice_no"] for g in groups}) != len(groups)
        or {g["invoice_no"] for g in groups} != set(counts)
        or any(counts[g["invoice_no"]] != int(g["row_count"]) for g in groups)
    ):
        raise ValueError("Incomplete invoice group")
    profile = json.loads((folder / "profile.json").read_text(encoding="utf-8"))
    if sum(counts.values()) != profile["counts"]["rows"]:
        raise ValueError("Profile row count does not match prepared records")
    if len(groups) != profile["counts"]["invoice_groups"]:
        raise ValueError("Profile invoice count does not match prepared records")
    eligible = [group for group in groups if group["eligible_sale"] == "1"]
    if (
        len(eligible) != profile["counts"]["eligible_sale_invoices"]
        or sum(int(g["row_count"]) for g in eligible) != profile["counts"]["eligible_sale_rows"]
    ):
        raise ValueError("Profile eligibility counts do not match complete invoice groups")
    return {
        "verified_rows": sum(counts.values()),
        "verified_invoice_groups": len(groups),
        "dataset_version": manifest["dataset_version"],
    }
