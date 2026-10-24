"""Start the local Acme Wholesale website and API."""

import argparse
from pathlib import Path

import uvicorn

from acme.portal import create_portal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    project = args.project_dir.resolve()
    state, data = args.state_dir or project / "state", args.data_dir or project / "data"
    app = create_portal(project, state.resolve(), data.resolve())
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
