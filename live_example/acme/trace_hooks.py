"""LangChain callbacks and a thin official-saver subclass for observable execution."""

from threading import RLock
from time import perf_counter

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages

from acme.tracing import PARENT, difference, record

SETTINGS = {
    "model",
    "model_name",
    "temperature",
    "top_p",
    "top_k",
    "num_ctx",
    "num_predict",
    "max_tokens",
    "max_output_tokens",
    "stop",
    "seed",
    "timeout",
    "request_timeout",
    "format",
    "reasoning_effort",
    "tool_choice",
    "parallel_tool_calls",
}


def message_snapshot(value):
    if hasattr(value, "update") and not isinstance(value, dict):
        value = value.update
    if isinstance(value, dict):
        value = value.get("messages", [])
    if not isinstance(value, (list, tuple)):
        return []
    return [message_to_dict(m) for m in value if isinstance(m, BaseMessage)]


def safe_settings(model=None, parameters=None):
    result = {key: getattr(model, key) for key in SETTINGS if getattr(model, key, None) is not None}
    result.update({key: value for key, value in (parameters or {}).items() if key in SETTINGS})
    return result


def model_catalog(model, middleware):
    """Register main and explicitly configured helper models without serializing clients."""
    candidates = [model]
    for item in middleware or []:
        candidates.extend(
            getattr(item, name, None) for name in ("model", "_summary_model", "summarizer")
        )
    catalog = []
    for candidate in candidates:
        while hasattr(candidate, "bound"):
            candidate = candidate.bound
        if candidate is not None:
            entry = {"class": type(candidate).__name__, "settings": safe_settings(candidate)}
            if entry not in catalog:
                catalog.append(entry)
    return catalog


class TraceCallbacks(BaseCallbackHandler):
    """Record native chain/model spans, including middleware helper models and retries."""

    raise_error = True
    run_inline = True

    def __init__(self, context, catalog=None):
        self.context = context
        self.catalog = catalog or []
        self.active = {}
        self.failed_attempts = {}
        self.lock = RLock()

    def begin(self, native_id, parent_run_id, kind, payload):
        identifier = "lc-" + str(native_id)
        parent = "lc-" + str(parent_run_id) if parent_run_id else self.context.execution_id
        # Keep both framework parentage and the application attempt relationship.
        payload["native_parent_id"] = parent
        if kind == "provider":
            parent = PARENT.get() or parent
        with self.lock:
            if kind == "provider":
                key = (payload.get("name"), payload.get("purpose"), payload.get("node"))
                payload["previous_failed_span_id"] = self.failed_attempts.pop(key, None)
            self.active[str(native_id)] = (perf_counter(), kind, identifier, parent, payload)
        record(self.context, kind + "_started", payload, span_id=identifier, parent_id=parent)

    def finish(self, native_id, output=None, error=None):
        with self.lock:
            active = self.active.pop(str(native_id), None)
        if active is None:
            return
        started, kind, identifier, parent, initial = active
        if kind == "provider" and error is not None:
            key = (initial.get("name"), initial.get("purpose"), initial.get("node"))
            with self.lock:
                self.failed_attempts[key] = identifier
        payload = output or {}
        if error is not None:
            payload = {"error_type": type(error).__name__, "message": str(error)}
        record(
            self.context,
            kind + ("_error" if error else "_finished"),
            payload,
            span_id=identifier,
            parent_id=parent,
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )
        if kind == "chain" and error is None and initial.get("messages"):
            update = payload.get("messages", [])
            if update:
                before = initial["messages"]
                patches = messages_from_dict(update)
                pending = set()
                for index, message in enumerate(patches):
                    if message.id is None:
                        message.id = f"trace-unassigned-{identifier}-{index}"
                        pending.add(message.id)
                after = message_snapshot(add_messages(messages_from_dict(before), patches))
                for message in after:
                    if message["data"].get("id") in pending:
                        message["data"]["id"] = None
                edits = difference(before, after)
                if edits:
                    record(
                        self.context,
                        "context_change",
                        {
                            "stage": initial["name"],
                            "before": before,
                            "after": after,
                            "changes": edits,
                            "source_span_id": identifier,
                            "meaning": "node input plus returned update; unassigned IDs stay null",
                        },
                        parent_id=identifier,
                    )

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        name = kwargs.get("name") or (serialized or {}).get("name") or "chain"
        self.begin(
            run_id,
            parent_run_id,
            "chain",
            {
                "name": name,
                "messages": message_snapshot(inputs),
            },
        )

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self.finish(run_id, {"messages": message_snapshot(outputs)})

    def on_chain_error(self, error, *, run_id, **kwargs):
        self.finish(run_id, error=error)

    def on_chat_model_start(
        self, serialized, messages, *, run_id, parent_run_id=None, metadata=None, **kwargs
    ):
        params = kwargs.get("invocation_params", {})
        metadata = metadata or {}
        name = (serialized or {}).get("name") or (serialized or {}).get("id", ["model"])[-1]
        model_class = (serialized or {}).get("id", [name])[-1]
        aliases = {
            "ls_model_name": "model",
            "ls_temperature": "temperature",
            "ls_max_tokens": "max_tokens",
            "ls_stop": "stop",
        }
        reported = {
            target: metadata[source] for source, target in aliases.items() if source in metadata
        }
        matches = [
            row["settings"]
            for row in self.catalog
            if row["class"] == model_class
            and (
                not reported.get("model")
                or reported["model"]
                in (row["settings"].get("model"), row["settings"].get("model_name"))
            )
        ]
        configured = matches[0] if len(matches) == 1 else {}
        settings = safe_settings(
            parameters={**configured, **reported, **(serialized or {}).get("kwargs", {}), **params}
        )
        self.begin(
            run_id,
            parent_run_id,
            "provider",
            {
                "name": name,
                "model_class": model_class,
                "purpose": (metadata or {}).get("lc_source", "main" if PARENT.get() else "helper"),
                "node": (metadata or {}).get("langgraph_node"),
                "messages": [message_snapshot(batch) for batch in messages],
                "settings": settings,
                "configuration_match": len(matches) == 1,
                "tools": params.get("tools", []),
            },
        )

    def on_llm_end(self, response, *, run_id, **kwargs):
        messages = [
            message_to_dict(g.message)
            for group in response.generations
            for g in group
            if hasattr(g, "message")
        ]
        self.finish(
            run_id,
            {
                "messages": messages,
                "provider_output": response.llm_output,
                "usage": [m["data"].get("usage_metadata") for m in messages],
            },
        )

    def on_llm_error(self, error, *, run_id, **kwargs):
        self.finish(run_id, error=error)

    def on_retry(self, retry_state, *, run_id, parent_run_id=None, **kwargs):
        record(
            self.context,
            "retry",
            {"native_run_id": str(run_id), "attempt": retry_state.attempt_number},
            parent_id="lc-" + str(parent_run_id or run_id),
        )

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        self.begin(
            run_id,
            parent_run_id,
            "native_tool",
            {
                "name": (serialized or {}).get("name"),
                "arguments": kwargs.get("inputs", input_str),
            },
        )

    def on_tool_end(self, output, *, run_id, **kwargs):
        value = message_to_dict(output) if isinstance(output, BaseMessage) else output
        self.finish(run_id, {"output": value})

    def on_tool_error(self, error, *, run_id, **kwargs):
        self.finish(run_id, error=error)


class TracedSqliteSaver(SqliteSaver):
    """Delegate persistence to the official saver, then record successful commits."""

    def put(self, config, checkpoint, metadata, new_versions):
        started = perf_counter()
        saved = super().put(config, checkpoint, metadata, new_versions)
        record(
            self.trace_context,
            "checkpoint_committed",
            {
                "checkpoint_id": checkpoint["id"],
                "parent_checkpoint_id": config.get("configurable", {}).get("checkpoint_id"),
                "namespace": config.get("configurable", {}).get("checkpoint_ns", ""),
                "step": metadata.get("step"),
                "source": metadata.get("source"),
                "messages": message_snapshot(checkpoint.get("channel_values", {})),
            },
            duration_ms=round((perf_counter() - started) * 1000, 3),
        )
        return saved

    def put_writes(self, config, writes, task_id, task_path=""):
        super().put_writes(config, writes, task_id, task_path)
        record(
            self.trace_context,
            "checkpoint_writes",
            {
                "checkpoint_id": config.get("configurable", {}).get("checkpoint_id"),
                "task_id": task_id,
                "task_path": task_path,
                "channels": [name for name, _ in writes],
            },
        )
