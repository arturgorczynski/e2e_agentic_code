"""Prepare or install the audited r14 two-receipt settlement exercise."""

import argparse
import json
from pathlib import Path

from acme.settlement_release import build_settlement_release, install_settlement_release


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
    state = (args.state_dir or project / "state").resolve()
    bundle = args.bundle_dir or project / "artifacts/settlement-release-2026-r14/documents"
    if args.action == "prepare":
        source = args.source_dir or state / "documents"
        authored = args.authored_file or (
            project / "data/document_sources/revision_r14/finance/FIN-SETTLE-83DAA020DE34-01.md"
        )
        result = build_settlement_release(source, state, authored, bundle)
    else:
        result = install_settlement_release(project, state, bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
