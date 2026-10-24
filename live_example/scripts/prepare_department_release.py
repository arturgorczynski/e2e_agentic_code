"""Build a new versioned candidate for the ten department instructions."""

import argparse
import json
from pathlib import Path

from acme.department_release import build_department_release


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
    source = args.source_dir or project / "artifacts/directory-release-2026-r2/documents"
    authored = args.authored_dir or project / "data/document_sources/revision_r7/departments"
    output = args.output_dir or project / "artifacts/department-release-2026-r7/documents"
    print(json.dumps(build_department_release(source, state, authored, output), indent=2))


if __name__ == "__main__":
    main()
