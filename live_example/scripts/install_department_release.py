"""Install the audited department-instruction release with a state backup."""

import argparse
import json
from pathlib import Path

from acme.department_release import install_department_release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--bundle-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state = args.state_dir or project / "state"
    bundle = args.bundle_dir or project / "artifacts/department-release-2026-r7/documents"
    print(json.dumps(install_department_release(project, state, bundle), indent=2))


if __name__ == "__main__":
    main()
