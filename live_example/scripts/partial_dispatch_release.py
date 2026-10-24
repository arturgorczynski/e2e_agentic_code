"""Prepare or install the audited r12 partial-dispatch exercise."""

import argparse
import json
from pathlib import Path

from acme.partial_dispatch_release import (
    build_partial_dispatch_release,
    install_partial_dispatch_release,
)


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
    bundle = args.bundle_dir or project / "artifacts/partial-dispatch-release-2026-r12/documents"
    if args.action == "prepare":
        source = args.source_dir or state / "documents"
        authored = args.authored_file or (
            project / "data/document_sources/revision_r12/support/CASE-PARTIAL-83DAA020DE34.md"
        )
        result = build_partial_dispatch_release(source, state, authored, bundle)
    else:
        result = install_partial_dispatch_release(project, state, bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
