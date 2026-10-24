"""Install the prepared 2026 account directory when its effective date arrives."""

import argparse
import json
from pathlib import Path

from acme.directory_release import install_directory_release


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("."))
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--bundle-dir", type=Path)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state = args.state_dir or project / "state"
    bundle = args.bundle_dir or project / "artifacts/directory-release-2026-r2/documents"
    print(json.dumps(install_directory_release(project, state, bundle), indent=2))


if __name__ == "__main__":
    main()
