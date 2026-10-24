"""Explicit persona-scoped learning notes in a persistent LangGraph store."""

import re
from contextlib import contextmanager

from langgraph.store.sqlite import SqliteStore

from acme.app_store import authorize, event, now


def namespace(context):
    actor = authorize(context)
    return ("acme", "persona_preferences", actor["id"])


def clean_topic(topic):
    value = topic.strip().casefold()
    if not 2 <= len(value) <= 40 or not re.fullmatch(r"[\w -]+", value):
        raise ValueError("Memory topic must be 2-40 letters, numbers, spaces, '-' or '_'")
    return value


def remember(context, store, topic, note):
    """Save one explicitly requested preference; never infer memories automatically."""
    key = clean_topic(topic)
    content = note.strip()
    if not 3 <= len(content) <= 500:
        raise ValueError("Preference note must be 3-500 characters")
    if re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", content):
        raise ValueError("Do not store email addresses in a preference note")
    if re.search(r"\b(?:UCI|DEMO)-(?:CUST|ORD|INV|SKU)-[\w-]+\b", content, re.I):
        raise ValueError("Use live company tools for record facts, not long-term notes")
    target = namespace(context)
    store.put(target, key, {"topic": key, "note": content, "updated_at": now()})
    event(context, "memory_saved", {"topic": key, "namespace_owner": target[-1]})
    return {"status": "saved", "topic": key, "scope": "selected persona across conversations"}


def recall(context, store, topic=None, limit=10):
    target = namespace(context)
    if not 1 <= limit <= 20:
        raise ValueError("Memory limit must be 1-20")
    if topic:
        key = clean_topic(topic)
        item = store.get(target, key)
        items = [item] if item else []
    else:
        items = store.search(target, limit=limit)
    notes = [item.value for item in items]
    event(context, "memory_recalled", {"count": len(notes), "topic": topic or ""})
    return {"notes": notes, "count": len(notes), "scope": "selected persona"}


@contextmanager
def open_memory(state):
    """The SQLite store survives server restarts; no vector index or Docker."""
    with SqliteStore.from_conn_string(str(state / "memory.sqlite")) as store:
        store.setup()
        yield store
