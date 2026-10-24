"""Check catalog image mappings, file integrity, and recorded provenance.

Run after preparing the exercise database. Older images without per-asset
generation manifests remain visible in the report; their provenance is not
invented by this audit.
"""

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from acme.dataset import connect

PROJECT = Path(__file__).resolve().parents[1]
PUBLIC = PROJECT / "frontend" / "public"
MAPPING = PROJECT / "frontend" / "src" / "catalogVisuals.ts"
ENTRY = re.compile(r"^\s*'([^']+)': '(/images/[^']+)',?\s*$", re.MULTILINE)


def image_type(path: Path) -> str | None:
    header = path.read_bytes()[:12]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "WEBP"
    return None


def audit(database: Path) -> dict:
    """Audit live product names and static files without changing either."""
    source = MAPPING.read_text(encoding="utf-8")
    entries = ENTRY.findall(source)
    mapped = {}
    issues = []
    for key, url in entries:
        if key in mapped:
            issues.append(f"Duplicate image mapping: {key}")
        mapped[key] = url
    products = {key: url for key, url in mapped.items() if key.startswith(("UCI-SKU-", "SCN-SKU-"))}
    categories = {key: url for key, url in mapped.items() if key not in products}
    if not products or not categories:
        issues.append("Could not read both catalog image maps")

    for key, url in mapped.items():
        target = (PUBLIC / url.lstrip("/")).resolve()
        if not target.is_relative_to(PUBLIC.resolve()):
            issues.append(f"Image path escapes public directory: {key}")
            continue
        if not target.is_file():
            issues.append(f"Missing image file: {key} -> {url}")
            continue
        detected = image_type(target)
        if detected != target.suffix.lstrip(".").upper():
            issues.append(f"Image format does not match extension: {key} -> {url}")

    db = connect(database, readonly=True)
    try:
        rows = db.execute("SELECT id,name FROM products").fetchall()
        names = {row["id"]: row["name"] for row in rows}
        used_categories = {
            row[0] for row in db.execute(
                "SELECT DISTINCT c.name FROM categories c JOIN products p ON p.category_id=c.id"
            )
        }
    finally:
        db.close()
    for sku in products:
        if sku not in names:
            issues.append(f"Mapped SKU is absent from company database: {sku}")
    for category in sorted(used_categories - categories.keys()):
        issues.append(f"Product category has no image mapping: {category}")

    manifests = {}
    for path in sorted((PROJECT / "artifacts").glob("image-assets-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for asset in document.get("assets", []):
            sku = asset.get("sku") or asset.get("product_id")
            if not sku:
                issues.append(f"Manifest entry has no SKU: {path.name}")
                continue
            if sku in manifests:
                issues.append(f"SKU appears in two manifests: {sku}")
            manifests[sku] = path.name
            url = products.get(sku)
            if url is None:
                issues.append(f"Manifest SKU has no website mapping: {sku}")
                continue
            expected_path = (PUBLIC / url.lstrip("/")).resolve()
            recorded_path = asset.get("asset")
            if recorded_path and (PROJECT / recorded_path).resolve() != expected_path:
                issues.append(f"Manifest asset path differs from website mapping: {sku}")
            if not expected_path.is_file():
                continue
            contents = expected_path.read_bytes()
            if asset.get("bytes") is not None and asset["bytes"] != len(contents):
                issues.append(f"Manifest byte count differs from image: {sku}")
            if asset.get("sha256") and asset["sha256"] != hashlib.sha256(contents).hexdigest():
                issues.append(f"Manifest SHA-256 differs from image: {sku}")
            if asset.get("source_description") and names.get(sku) and (
                asset["source_description"].strip() != names[sku].strip()
            ):
                issues.append(f"Manifest product description differs from database: {sku}")

    inventory = []
    for sku, url in sorted(products.items()):
        image = PUBLIC / url.lstrip("/")
        inventory.append({
            "sku": sku,
            "database_description": names.get(sku),
            "website_image": url,
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest() if image.is_file() else None,
            "generation_manifest": manifests.get(sku),
        })

    return {
        "checked_on": date.today().isoformat(),
        "database": str(database.resolve()),
        "mapped_products": len(products),
        "mapped_historical_products": sum(sku.startswith("UCI-SKU-") for sku in products),
        "mapped_scenario_products": sum(sku.startswith("SCN-SKU-") for sku in products),
        "category_images": len(categories),
        "per_asset_manifest_products": len(manifests),
        "without_per_asset_manifest": sorted(products.keys() - manifests.keys()),
        "inventory": inventory,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=PROJECT / "state" / "company.sqlite")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.database)
    if args.output:
        output = args.output if args.output.is_absolute() else PROJECT / args.output
        if output.exists():
            raise FileExistsError(f"Choose a new report path: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
