"""One explicit model factory, adapted from the course's root model_config.py.

Configuration is read only when a function is called. The selected project_dir
defaults to the current directory; no parent-directory or notebook search occurs.
"""

import os
import tomllib
from pathlib import Path

from dotenv import dotenv_values
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI


def settings(project_dir: str | Path = ".") -> dict:
    """Read this project's TOML afresh; never create or modify configuration."""
    path = Path(project_dir).resolve() / "models.toml"
    if not path.is_file():
        raise FileNotFoundError(
            f"Configuration not found: {path}. Run from the Live Example directory "
            "or pass project_dir explicitly."
        )
    return tomllib.loads(path.read_text(encoding="utf-8"))


def get_model(
    role: str = "main",
    *,
    profile: str | None = None,
    model: str | None = None,
    project_dir: str | Path = ".",
    **overrides,
) -> BaseChatModel:
    """Construct a selected model without inference or implicit provider fallback.

    Process environment values take precedence over this project's .env. Unused
    profiles need no credentials. model= overrides the model/deployment name;
    role and profile still determine its provider, endpoint, and credentials.
    """
    root = Path(project_dir).resolve()
    config = settings(root)
    if profile is None:
        if role not in config["selection"]:
            raise ValueError(f"Unknown model role: {role!r}")
        profile = config["selection"][role]
    if profile not in config["profiles"]:
        raise ValueError(f"Unknown model profile: {profile!r}")
    spec = dict(config["profiles"][profile])
    provider = spec.pop("provider")
    if provider not in {"ollama", "openai", "anthropic", "azure"}:
        raise ValueError(f"Unsupported provider: {provider!r}")
    if {"provider", "name", "deployment", "azure_deployment"} & overrides.keys():
        raise ValueError("Select provider with profile= and deployment with model=.")
    if model is not None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty model/deployment name.")
        field = "deployment" if provider == "azure" else "model"
        spec.pop(f"{field}_env", None)
        spec[field] = model

    # Explicit path and no interpolation: never discover another project's .env.
    file_env = dotenv_values(root / ".env", interpolate=False)
    for key in list(spec):
        if key.endswith("_env"):
            variable = spec.pop(key)
            value = os.environ.get(variable, file_env.get(variable))
            if not value or not value.strip():
                raise RuntimeError(f"Set {variable} in {root / '.env'} or the process environment.")
            spec[key[:-4]] = value
    spec.update(overrides)
    timeout = config["runtime"]["request_timeout"]
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("runtime.request_timeout must be a positive number.")

    if provider == "ollama":
        client_options = {"timeout": timeout, **spec.pop("client_kwargs", {})}
        return ChatOllama(**spec, name=profile, client_kwargs=client_options)
    spec.setdefault("timeout", timeout)
    spec.setdefault("max_retries", 0)
    if provider == "openai":
        return ChatOpenAI(**spec, name=profile)
    if provider == "anthropic":
        return ChatAnthropic(**spec, name=profile)
    spec["azure_deployment"] = spec.pop("deployment")
    return AzureChatOpenAI(**spec, name=profile)
