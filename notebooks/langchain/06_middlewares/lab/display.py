"""Visible requests/results, not hidden model reasoning."""
import inspect
import json
from collections.abc import Mapping
from contextlib import contextmanager
from html import escape
from pathlib import Path
from threading import Lock
from uuid import uuid4

from IPython import get_ipython
from IPython.display import HTML, display
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from .config import ARTIFACTS_DIR


def as_json(value):
    if isinstance(value, BaseMessage):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)


def _field(value, name, default=None):
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _clip(text, limit):
    if len(text) <= limit:
        return text
    return text[:limit] + f" … [{len(text) - limit:,} more characters]"


def _preview(value, max_chars, max_items, depth=0):
    """Bound nested data before serialization, including base64 and large arrays."""
    if isinstance(value, str):
        return _clip(value, max_chars)
    if isinstance(value, (Mapping, list, tuple)):
        if depth >= 4:
            return f"[{type(value).__name__}: {len(value):,} items]"
        if isinstance(value, Mapping):
            result = {}
            for index, (key, item) in enumerate(value.items()):
                if index == max_items:
                    result["…"] = f"{len(value) - max_items:,} more fields"
                    break
                result[_clip(str(key), max_chars)] = _preview(item, max_chars, max_items, depth + 1)
            return result
        result = [_preview(item, max_chars, max_items, depth + 1) for item in value[:max_items]]
        if len(value) > max_items:
            result.append(f"… [{len(value) - max_items:,} more items]")
        return result
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return _clip(str(value), max_chars)


def _json_text(value, truncate, max_chars, max_items):
    if truncate:
        value = _preview(value, max_chars, max_items)
    text = json.dumps(value, default=as_json, ensure_ascii=False, indent=2)
    return _clip(text, max_chars) if truncate else text


def _parsed(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            pass
    return value


def _message_data(message):
    if isinstance(message, str):
        return {"role": "user", "content": message}
    if isinstance(message, tuple) and len(message) == 2:
        return {"role": message[0], "content": message[1]}
    if isinstance(message, Mapping) and "data" in message and "type" in message:
        return {**message["data"], "type": message["type"]}
    return message


def _tool_call(call, truncate, max_chars, max_items):
    function = _field(call, "function") or call
    name = _field(function, "name", "unknown")
    args = _parsed(_field(function, "arguments", _field(function, "args", _field(function, "input", {}))))
    call_id = _field(call, "id", _field(call, "call_id", ""))
    suffix = f" [{call_id}]" if call_id else ""
    error = _field(call, "error")
    text = f"{'INVALID CALL' if error else 'CALL'} {name}{suffix}"
    if error:
        text += f"\nError: {error}"
    text += f"\n{_json_text(args, truncate, max_chars, max_items)}"
    return _clip(text, max_chars) if truncate else text


def _content_text(content, truncate, max_chars, max_items):
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        blocks = content[:max_items] if truncate else content
        for block in blocks:
            kind = _field(block, "type", "unknown")
            if isinstance(block, str):
                parts.append(block)
            elif kind in {"text", "input_text", "output_text"}:
                parts.append(str(_field(block, "text", "")))
            elif kind not in {"tool_use", "tool_call", "function_call"}:
                # Binary/media payloads and provider metadata are never expanded in compact mode.
                parts.append(f"[{kind} block]" if truncate else _json_text(block, False, max_chars, max_items))
        if truncate and len(content) > max_items:
            parts.append(f"… [{len(content) - max_items:,} more blocks]")
        text = "\n".join(parts)
    elif content is None:
        text = ""
    else:
        text = _json_text(content, truncate, max_chars, max_items)
    return _clip(text, max_chars) if truncate else text


def _message_rows(messages, truncate, max_chars, max_items):
    if max_chars < 80 or max_items < 1:
        raise ValueError("max_chars must be at least 80 and max_items at least 1")
    if isinstance(messages, Mapping) and "messages" in messages:
        messages = messages["messages"]
    elif isinstance(messages, (BaseMessage, Mapping, str)) or (
        isinstance(messages, tuple) and len(messages) == 2 and isinstance(messages[0], str)
    ):
        messages = [messages]
    names = {}
    for message in messages:
        message = _message_data(message)
        role = _field(message, "role", _field(message, "type", "message"))
        role = {"human": "user", "ai": "assistant"}.get(role, role)
        calls = _field(message, "tool_calls") or []
        if not calls:
            extra = _field(message, "additional_kwargs", {}) or {}
            calls = extra.get("tool_calls", [])
        content = _field(message, "content", "")
        if not calls and isinstance(content, list):
            calls = [block for block in content
                     if isinstance(block, Mapping) and block.get("type") in {"tool_use", "tool_call", "function_call"}]
        calls = [*calls, *(_field(message, "invalid_tool_calls", []) or [])]
        body = _content_text(content, truncate, max_chars, max_items)
        label = str(role).upper()
        if role == "tool":
            call_id = _field(message, "tool_call_id", "")
            name = _field(message, "name") or names.get(call_id, "unknown")
            label += f" · {name}" + (f" [{call_id}]" if call_id else "")
            label += f" · {_field(message, 'status', 'success')}"
            parsed = _parsed(content)
            if not isinstance(parsed, str):
                body = _json_text(parsed, truncate, max_chars, max_items)
        if calls:
            shown = calls[:max_items] if truncate else calls
            for call in calls:
                function = _field(call, "function") or call
                names[_field(call, "id", _field(call, "call_id", ""))] = _field(function, "name", "unknown")
            parts = [body] if body else []
            parts.extend(_tool_call(call, truncate, max_chars, max_items) for call in shown)
            if truncate and len(calls) > max_items:
                parts.append(f"… [{len(calls) - max_items:,} more tool calls]")
            body = "\n\n".join(parts)
        yield _clip(label, max_chars) if truncate else label, body or "(no text)"


def format_messages(messages, *, pretty=True, truncate=True, max_chars=600, max_items=8):
    """Return portable text for LangChain messages, serialized messages or agent state.

    Compact mode bounds each message/call, preserving execution order and call IDs.
    ``pretty=False`` returns complete message JSON. It does not mutate input.
    """
    if not pretty:
        return json.dumps(messages, default=as_json, ensure_ascii=False, indent=2)
    rows = list(_message_rows(messages, truncate, max_chars, max_items))
    return "\n\n".join(f"{index:02d}  {label}\n{body}" for index, (label, body) in enumerate(rows, 1)) or "No messages."


def show_messages(messages, *, pretty=True, truncate=True, max_chars=600, max_items=8):
    """Show a compact notebook timeline, with a text fallback outside Jupyter.

    Pass a message list, a slice such as ``result['messages'][-3:]``, or an agent
    result. Use ``truncate=False`` for full content, or ``pretty=False`` for JSON.
    """
    shell = get_ipython()
    if not pretty or shell is None or not getattr(shell, "kernel", None):
        print(format_messages(messages, pretty=pretty, truncate=truncate,
                              max_chars=max_chars, max_items=max_items))
        return
    rows = list(_message_rows(messages, truncate, max_chars, max_items))
    cards = []
    colors = {"USER": "#2563eb", "ASSISTANT": "#7c3aed", "TOOL": "#16836b", "SYSTEM": "#777"}
    for index, (label, body) in enumerate(rows, 1):
        color = colors.get(label.split()[0], "#777")
        cards.append(
            f'<section style="border-left:3px solid {color};padding:8px 12px;margin:10px 0">'
            f'<strong style="color:{color}">{index:02d} · {escape(label)}</strong>'
            '<pre style="white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0;'
            'font:inherit;font-family:monospace;max-height:24em;overflow:auto">'
            f'{escape(body)}</pre></section>'
        )
    display(HTML('<div aria-label="Execution history">' + ("".join(cards) or "No messages.") + '</div>'))


def show_source(item):
    target = getattr(item, "func", item)
    if isinstance(target, AgentMiddleware):
        # LangChain's function decorators return dynamically generated middleware.
        for hook in ("wrap_model_call", "wrap_tool_call", "before_agent", "before_model", "after_model", "after_agent"):
            closure = inspect.getclosurevars(getattr(target, hook)).nonlocals
            if "func" in closure:
                target = closure["func"]
                break
    print(inspect.getsource(target))


@contextmanager
def expect_error(error_type):
    try:
        yield
    except error_type as error:
        print(f"EXPECTED {type(error).__name__}: {error}")
    else:
        raise AssertionError(f"Expected {error_type.__name__}, but the call succeeded.")


class TraceMiddleware(AgentMiddleware):
    """Project-local trace: compact console history and complete JSON on disk."""

    def __init__(self, label, *, pretty=True, truncate=True, max_chars=400, max_items=8):
        if max_chars < 80 or max_items < 1:
            raise ValueError("max_chars must be at least 80 and max_items at least 1")
        self.label = label
        self.pretty = pretty
        self.truncate = truncate
        self.max_chars = max_chars
        self.max_items = max_items
        self.events = []
        self._lock = Lock()
        ARTIFACTS_DIR.mkdir(exist_ok=True)
        self.path = ARTIFACTS_DIR / f"{label}-{uuid4().hex[:8]}.txt"
        print("Execution log:", self.path)

    @property
    def name(self):
        return f"Trace_{self.label}"

    def emit(self, kind, payload):
        with self._lock:
            self.events.append({"kind": kind, "payload": payload})
            text = f"\n{'-' * 72}\n{len(self.events)}. {kind}\n"
            text += json.dumps(payload, default=as_json, ensure_ascii=False, indent=2)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(text + "\n")
            if self.pretty:
                summary = self._summary(kind, payload)
                print(f"\n{len(self.events):02d} · {self.label} · {kind}\n{summary}")
            else:
                print(text)

    def _summary(self, kind, payload):
        if kind == "MODEL REQUEST":
            tools = payload["tools"]
            shown = tools[:self.max_items] if self.truncate else tools
            names = [str(_field(_field(tool, "function") or tool, "name", _field(tool, "type", "unknown")))
                     for tool in shown]
            if self.truncate:
                names = [_clip(name, 80) for name in names]
            suffix = f" … [{len(tools) - len(shown)} more tools]" if len(tools) > len(shown) else ""
            system = "yes" if payload["system_message"] else "no"
            # Repeated histories and full schemas stay in the log, not in every notebook step.
            return (f"Model: {payload['model'] or 'unnamed'} · History: {len(payload['messages'])} messages"
                    f" · System instructions: {system}\nTools ({len(tools)}): {', '.join(names) or '(none)'}{suffix}")
        if kind in {"MODEL RESPONSE", "TOOL RESULT"} and (
            isinstance(payload, (BaseMessage, list))
            or (isinstance(payload, Mapping) and ("role" in payload or "type" in payload))
        ):
            return format_messages(payload, truncate=self.truncate,
                                   max_chars=self.max_chars, max_items=self.max_items)
        if kind == "TOOL REQUEST":
            return _tool_call(payload, self.truncate, self.max_chars, self.max_items)
        return _json_text(payload, self.truncate, self.max_chars, self.max_items)

    def _model_request(self, request):
        self.emit("MODEL REQUEST", {
            "model": getattr(request.model, "name", None) or getattr(request.model, "model_name", None)
                     or getattr(request.model, "model", None),
            "system_message": request.system_message,
            "messages": request.messages,
            "tools": [convert_to_openai_tool(t) if not isinstance(t, dict) else t
                      for t in request.tools],
        })

    def wrap_model_call(self, request, handler):
        self._model_request(request)
        try:
            response = handler(request)
        except Exception as error:
            self.emit("MODEL ERROR", {"type": type(error).__name__, "message": str(error)})
            raise
        self.emit("MODEL RESPONSE", response.result)
        return response

    def wrap_tool_call(self, request, handler):
        self.emit("TOOL REQUEST", request.tool_call)
        try:
            result = handler(request)
        except Exception as error:
            self.emit("TOOL ERROR", {"type": type(error).__name__, "message": str(error)})
            raise
        self.emit("TOOL RESULT", result)
        return result

    async def awrap_model_call(self, request, handler):
        self._model_request(request)
        try:
            response = await handler(request)
        except Exception as error:
            self.emit("MODEL ERROR", {"type": type(error).__name__, "message": str(error)})
            raise
        self.emit("MODEL RESPONSE", response.result)
        return response

    async def awrap_tool_call(self, request, handler):
        self.emit("TOOL REQUEST", request.tool_call)
        try:
            result = await handler(request)
        except Exception as error:
            self.emit("TOOL ERROR", {"type": type(error).__name__, "message": str(error)})
            raise
        self.emit("TOOL RESULT", result)
        return result
