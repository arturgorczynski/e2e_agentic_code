"""Stage corrected 2026 directory facts and their matching account terms."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from acme.contemporary_directory import apply_directory_correction, plan_directory_correction
from acme.dataset import connect
from acme.directory_release import validate_directory_release
from acme.document_directory import build_directory_terms_bundle
from acme.document_revision import _assert_original_register, apply_revision_register


def prepare(project: Path, state: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Choose a new release-preview directory")
    output.mkdir(parents=True)
    staged = state / f".directory-preview-{uuid4().hex}.sqlite"
    source = connect(state / "company.sqlite", readonly=True)
    replacement = connect(staged)
    try:
        source.backup(replacement)
    finally:
        replacement.close()
        source.close()
    try:
        db = connect(staged)
        try:
            plans = plan_directory_correction(db)
            db.execute("BEGIN IMMEDIATE")
            changed = apply_directory_correction(db, plans)
            db.commit()
            after = plan_directory_correction(db)
            if any(item["status"] != "already_applied" for item in after):
                raise ValueError("Staged directory correction was incomplete")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        document_manifest = build_directory_terms_bundle(
            project / "artifacts/document-release-2026-r5",
            staged,
            output / "documents",
        )
        installed_catalog = state / "documents/catalog.json"
        if not installed_catalog.is_file():
            raise ValueError("The r5 document release must already be installed")
        originals = json.loads(installed_catalog.read_text("utf-8"))["documents"]
        revised = json.loads(
            (output / "documents/catalog.json").read_text("utf-8")
        )["documents"]
        db = connect(staged)
        try:
            db.execute("BEGIN IMMEDIATE")
            apply_revision_register(db, originals, revised)
            validation = validate_directory_release(db, revised, output / "documents")
            _assert_original_register(db, revised)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        report = {
            "status": "ready_for_date_gate",
            "not_before": "2026-10-21",
            "source_document_revision": "acme-documents-2026-r5",
            "accounts_reviewed": len(plans),
            "accounts_changed_in_preview": changed,
            "directory_changes": plans,
            "documents": document_manifest,
            "staged_validation": validation,
        }
        (output / "directory_plan.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return report
    finally:
        staged.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state = args.state_dir or project / "state"
    output = args.output_dir or project / "artifacts/directory-release-2026-r1"
    result = prepare(project, state, output)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "directory_changes"},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
