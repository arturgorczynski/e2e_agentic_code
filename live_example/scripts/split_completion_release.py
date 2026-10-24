"""Prepare or install the audited r15 supplier receipt completion."""

import argparse
import json
from pathlib import Path

from acme.split_completion_release import (
    build_split_completion_release,
    install_split_completion_release,
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
    bundle = args.bundle_dir or project / "artifacts/split-completion-release-2026-r15/documents"
    if args.action == "prepare":
        source = args.source_dir or state / "documents"
        authored = args.authored_file or (
            project / "data/document_sources/revision_r15/procurement/PROCURE-SPLIT-75F3A546B17E.md"
        )
        result = build_split_completion_release(source, state, authored, bundle)
    else:
        result = install_split_completion_release(project, state, bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
