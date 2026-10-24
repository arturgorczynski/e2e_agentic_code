"""Build the r8 correction for three Acme procedures."""

import argparse
import json
from pathlib import Path

from acme.procedure_release import build_procedure_release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--authored-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state = args.state_dir or project / "state"
    source = args.source_dir or state / "documents"
    authored = args.authored_dir or project / "data/document_sources/revision_r8/procedures"
    output = args.output_dir or project / "artifacts/procedure-release-2026-r8/documents"
    print(json.dumps(build_procedure_release(source, state, authored, output), indent=2))


if __name__ == "__main__":
    main()
