"""Workshop paths; model configuration is shared with the entire project."""
from pathlib import Path
import sys

LESSON_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = LESSON_DIR.parents[2]

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from model_config import (  # noqa: E402,F401
    get_model, get_json_model, get_model_name, profile_for,
    provider_profile, required_env, run_config, settings,
)

DATA_DIR = LESSON_DIR / "data"
ARTIFACTS_DIR = LESSON_DIR / "artifacts"
