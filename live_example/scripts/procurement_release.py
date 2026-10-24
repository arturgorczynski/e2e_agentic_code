"""Prepare or install the audited r9 supplier-review wording correction."""

import argparse
import json
from pathlib import Path

from acme.procurement_release import build_procurement_release, install_procurement_release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "install"))
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--authored-file", type=Path)
    parser.add_argument("--bundle-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state = args.state_dir or project / "state"
    bundle = args.bundle_dir or project / "artifacts/procurement-release-2026-r9/documents"
    if args.action == "prepare":
        source = args.source_dir or state / "documents"
        authored = args.authored_file or (
            project / "data/document_sources/revision_r9/procurement/PROCURE-79511D9988BA.md"
        )
        result = build_procurement_release(source, state, authored, bundle)
    else:
        result = install_procurement_release(project, state, bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
