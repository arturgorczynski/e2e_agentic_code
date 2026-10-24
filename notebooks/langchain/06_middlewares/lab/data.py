"""All example inputs come from editable, reusable fixture files."""
import json

from langchain_core.messages import convert_to_messages

from .config import DATA_DIR


def prompt(name):
    return json.loads((DATA_DIR / "prompts.json").read_text(encoding="utf-8"))[name]


def conversation(name="project"):
    raw = json.loads((DATA_DIR / "conversations.json").read_text(encoding="utf-8"))
    return convert_to_messages(raw[name])


def text_fixture(name):
    return (DATA_DIR / name).read_text(encoding="utf-8")


def tool_conversation():
    raw = json.loads((DATA_DIR / "tool_history.json").read_text(encoding="utf-8"))
    return convert_to_messages(raw)


def scripted_conversation(name):
    raw = json.loads((DATA_DIR / "scripted_responses.json").read_text(encoding="utf-8"))
    return convert_to_messages(raw[name])


def cache_context():
    """A long, stable prefix from the same reusable workshop fixtures."""
    archive = "\n\n".join(
        "\n".join(f"{m.type}: {m.content}" for m in conversation(name))
        for name in ("project", "incident", "hiring")
    )
    return "Answer using this fictional handbook and reference archive.\n\n" + text_fixture("handbook.txt") + "\n\n" + archive
