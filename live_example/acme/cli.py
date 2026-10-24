"""Small command entry point for setup, company data, conversations and execution."""

import argparse
import json
from pathlib import Path

from acme import __version__
from acme.chat_cli import add_chat_commands, run_chat_command
from acme.dataset import build_dataset, initialize_state, verify_dataset
from acme.document_business import build_business_notes_bundle
from acme.document_extension import build_contemporary_terms_bundle
from acme.document_revision import (
    audit_revision_bundle,
    audit_revision_preview,
    build_revision_bundle,
    build_revision_preview,
    install_revision_bundle,
)
from acme.scenarios import (
    align_contemporary_seed_dates,
    audit_contemporary_history,
    seed_contemporary_cases,
    seed_contemporary_history,
    seed_contemporary_planning,
    seed_contemporary_purchasing,
)
from acme.setup_cli import add_setup_commands, run_setup_command
from acme.source_data import fetch_source, prepare_source, verify_prepared


def main(argv: list[str] | None = None) -> None:
    """Inspect the package or prepare public source data without loading a model."""
    parser = argparse.ArgumentParser(
        prog="acme",
        description="Acme Wholesale — company data and learning foundations.",
        epilog=(
            "Company integrations are simulated SQLite; document retrieval is mock RAG. "
            "Start with setup, doctor, then serve."
        ),
    )
    parser.add_argument("--version", action="version", version=f"acme {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    data = subparsers.add_parser("data", help="Prepare or verify the public transaction dataset")
    data.add_argument("action", choices=["fetch", "prepare", "verify"])
    data.add_argument("--project-dir", type=Path, default=Path("."))
    data.add_argument(
        "--output-dir",
        type=Path,
        help="Alternate preparation/verification directory (for reproducibility checks)",
    )
    company = subparsers.add_parser("company", help="Build, verify or initialize company data")
    company.add_argument(
        "action",
        choices=[
            "build",
            "verify",
            "init",
            "reset",
            "seed-modern",
            "seed-modern-cases",
            "seed-modern-purchasing",
            "seed-modern-planning",
            "align-modern-dates",
            "audit-modern",
            "docs-preview",
            "docs-audit",
            "docs-bundle",
            "docs-terms-bundle",
            "docs-business-bundle",
            "docs-bundle-audit",
            "docs-install",
        ],
    )
    company.add_argument("--project-dir", type=Path, default=Path("."))
    company.add_argument("--output-dir", type=Path, help="New data bundle directory for build")
    company.add_argument(
        "--data-dir", type=Path, help="Prepared data bundle to verify or initialize"
    )
    company.add_argument(
        "--state-dir", type=Path, help="Exercise state directory (default: state/)"
    )
    company.add_argument("--profile", choices=["full", "fixture"], default="full")
    company.add_argument(
        "--yes", action="store_true", help="Explicitly confirm company-state reset"
    )
    add_chat_commands(subparsers)
    add_setup_commands(subparsers)
    args = parser.parse_args(argv)
    if args.command in {"setup", "doctor", "serve"}:
        try:
            run_setup_command(args)
        except (ValueError, PermissionError, RuntimeError, OSError) as exc:
            parser.error(str(exc))
    elif args.command == "data":
        root = args.project_dir.resolve()
        if args.action == "fetch":
            print(fetch_source(root))
        elif args.action == "prepare":
            print(json.dumps(prepare_source(root, args.output_dir)["counts"], indent=2))
        else:
            print(
                json.dumps(
                    verify_prepared(args.output_dir or root / "data/company/prepared"), indent=2
                )
            )
    elif args.command == "company":
        root = args.project_dir.resolve()
        if args.action == "build":
            output = args.output_dir or root / "artifacts" / f"build-{args.profile}"
            result = build_dataset(root, output, args.profile)
        elif args.action == "docs-preview":
            output = args.output_dir or root / "artifacts" / "document-revision-preview-2026-r2"
            result = build_revision_preview(root, output)
        elif args.action == "docs-audit":
            output = args.output_dir or root / "artifacts" / "document-revision-preview-2026-r2"
            result = audit_revision_preview(root, output, args.state_dir or root / "state")
        elif args.action == "docs-bundle":
            preview = root / "artifacts" / "document-revision-preview-2026-r2"
            output = args.output_dir or root / "artifacts" / "document-release-2026-r2"
            result = build_revision_bundle(root, preview, output, args.state_dir or root / "state")
        elif args.action == "docs-terms-bundle":
            source = root / "artifacts" / "document-release-2026-r2"
            output = args.output_dir or root / "artifacts" / "document-release-2026-r3"
            result = build_contemporary_terms_bundle(
                source, args.state_dir or root / "state", output
            )
        elif args.action == "docs-business-bundle":
            source = root / "artifacts" / "document-release-2026-r3"
            output = args.output_dir or root / "artifacts" / "document-release-2026-r4"
            result = build_business_notes_bundle(source, args.state_dir or root / "state", output)
        elif args.action == "docs-bundle-audit":
            output = args.output_dir or root / "artifacts" / "document-release-2026-r2"
            result = audit_revision_bundle(output)
        elif args.action == "docs-install":
            output = args.output_dir or root / "artifacts" / "document-release-2026-r2"
            result = install_revision_bundle(root, args.state_dir or root / "state", output)
        elif args.action == "verify":
            result = verify_dataset(root, args.data_dir or root / "data")
            result = {
                key: result[key] for key in ("status", "profile", "table_counts", "documents")
            }
        elif args.action == "seed-modern":
            result = seed_contemporary_history(args.state_dir or root / "state")
        elif args.action == "seed-modern-cases":
            result = seed_contemporary_cases(args.state_dir or root / "state")
        elif args.action == "seed-modern-purchasing":
            result = seed_contemporary_purchasing(args.state_dir or root / "state")
        elif args.action == "seed-modern-planning":
            result = seed_contemporary_planning(args.state_dir or root / "state")
        elif args.action == "align-modern-dates":
            result = align_contemporary_seed_dates(args.state_dir or root / "state")
        elif args.action == "audit-modern":
            result = audit_contemporary_history(args.state_dir or root / "state")
        else:
            if args.action == "reset" and not args.yes:
                parser.error("Reset replaces company exercise state. Repeat with --yes to confirm.")
            result = initialize_state(
                root,
                args.state_dir or root / "state",
                reset=args.action == "reset",
                data=args.data_dir,
            )
        print(json.dumps(result, indent=2))
    elif args.command in {"account", "login", "threads", "chat", "tool", "operation", "report"}:
        try:
            print(json.dumps(run_chat_command(args), indent=2, ensure_ascii=False))
        except (ValueError, PermissionError, RuntimeError) as exc:
            parser.error(str(exc))
    else:
        parser.print_help()
