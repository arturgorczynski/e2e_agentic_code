"""One model factory for all notebooks; root models.toml + root .env only."""
import os
from pathlib import Path
import tomllib

from dotenv import dotenv_values
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI

REPO_DIR = Path(__file__).resolve().parent
ENV_FILE = REPO_DIR / ".env"
CONFIG_FILE = REPO_DIR / "models.toml"


def required_env(name):
    # Read fresh; never search notebook folders or cache .env in os.environ.
    value = os.environ.get(name, dotenv_values(ENV_FILE).get(name))
    if not value or not value.strip():
        raise RuntimeError(f"Set {name} in .env at the project root.")
    return value


def settings():
    return tomllib.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def profile_for(role="main"):
    config = settings()
    name = config["selection"][role]
    if name not in config["profiles"]:
        raise ValueError(f"Unknown profile {name!r} for {role!r} in root models.toml")
    return name, config["profiles"][name]


def _selected_profile(role, profile, model=None):
    config = settings()
    name = profile if profile is not None else config["selection"][role]
    if name not in config["profiles"]:
        raise ValueError(f"Unknown profile {name!r} in root models.toml")
    spec = dict(config["profiles"][name])
    if model is not None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty model/deployment name.")
        field = "deployment" if spec["provider"] == "azure" else "model"
        spec.pop(f"{field}_env", None)
        spec[field] = model
    for key in list(spec):
        if key.endswith("_env"):
            spec[key[:-4]] = required_env(spec.pop(key))
    return name, spec


def get_model_name(role="main", *, profile=None, model=None):
    _, spec = _selected_profile(role, profile, model)
    return spec.get("model", spec.get("deployment"))


def get_model(role="main", *, profile=None, model=None, **overrides):
    """Use model= to override the configured name (deployment name for Azure).

    The selected role/profile still determines the provider and credentials.
    Omit model to use .env. The first positional argument remains the role.
    """
    if model is not None and {"deployment", "azure_deployment"} & overrides.keys():
        raise ValueError("Pass model or a deployment override, not both.")
    name, spec = _selected_profile(role, profile, model)
    provider = spec.pop("provider")
    spec.update(overrides)
    timeout = settings()["runtime"]["request_timeout"]
    print(f"MODEL [{role}] profile={name} provider={provider} "
          f"model={spec.get('model', spec.get('deployment'))}")
    if provider == "ollama":
        return ChatOllama(**spec, name=name, client_kwargs={"timeout": timeout})
    if provider == "openai":
        return ChatOpenAI(**spec, timeout=timeout, max_retries=0, name=name)
    if provider == "azure":
        spec["azure_deployment"] = spec.pop("deployment")
        return AzureChatOpenAI(**spec, timeout=timeout, max_retries=0, name=name)
    if provider == "anthropic":
        return ChatAnthropic(**spec, timeout=timeout, max_retries=0, name=name)
    raise ValueError(f"Unsupported provider: {provider}")


def get_json_model(role="main", *, profile=None, model=None):
    """Return a model configured for raw JSON examples."""
    _, spec = _selected_profile(role, profile, model)
    model = get_model(role, profile=profile, model=model)
    if spec["provider"] == "ollama":
        return model.bind(format="json")
    if spec["provider"] in {"openai", "azure"}:
        return model.bind(response_format={"type": "json_object"})
    print("Anthropic: prompt-only JSON for the manual example; validate the result.")
    return model


def provider_profile(lesson, allowed):
    """Provider-only lessons require explicit opt-in, not merely a present key."""
    config = settings()
    name = config["provider_lessons"][lesson]
    if not name:
        print(f"SKIPPED: select a profile in root models.toml [provider_lessons].{lesson}")
        return None
    if name not in config["profiles"]:
        raise ValueError(f"Unknown profile {name!r} in root models.toml")
    provider = config["profiles"][name]["provider"]
    if provider not in allowed:
        raise ValueError(f"{lesson} needs {allowed}; {name!r} uses {provider!r}.")
    return name


def run_config(thread_id=None):
    result = {"recursion_limit": settings()["runtime"]["recursion_limit"]}
    if thread_id:
        result["configurable"] = {"thread_id": thread_id}
    return result
