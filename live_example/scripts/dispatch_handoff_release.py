"""Prepare or install the audited r13 dispatch handoff documents."""

import argparse
import json
from pathlib import Path

from acme.dispatch_handoff_release import (
    build_dispatch_handoff_release,
    install_dispatch_handoff_release,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "install"))
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--support-source", type=Path)
    parser.add_argument("--operations-source", type=Path)
    parser.add_argument("--bundle-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state = (args.state_dir or project / "state").resolve()
    bundle = args.bundle_dir or project / "artifacts/dispatch-handoff-release-2026-r13/documents"
    if args.action == "prepare":
        source = args.source_dir or state / "documents"
        support = args.support_source or (
            project / "data/document_sources/revision_r13/support/CASE-PARTIAL-83DAA020DE34.md"
        )
        operations = args.operations_source or (
            project / "data/document_sources/revision_r13/operations/OPS-DISPATCH-83DAA020DE34.md"
        )
        result = build_dispatch_handoff_release(source, state, support, operations, bundle)
    else:
        result = install_dispatch_handoff_release(project, state, bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
