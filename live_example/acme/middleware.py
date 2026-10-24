"""Small, explicit learning configurations for the normal CLI and UI runtime.

RuntimeContextMiddleware is project-local. Limits, retries, PII handling and
summarization delegate to LangChain's built-in middleware.
"""

import re
from dataclasses import replace
from datetime import date
from typing import Literal

import httpx
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    PIIMiddleware,
    SummarizationMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.exceptions import ModelError
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from pydantic import Field, create_model

from acme.app_store import authorize, event
from acme.company_queries import QUERIES
from acme.model_config import settings

DEFAULTS = {
    "model_calls": 12,
    "tool_calls": 20,
    "model_retries": 1,
    "retry_delay": 0.5,
    "summary_messages": 0,
    "summary_keep": 2,
    "redact_email": False,
    "tool_selection": "all",
    "graph_steps": 120,
}
READ_ONLY_TOOLS = {
    "my_profile",
    "my_account_terms",
    "my_orders",
    "my_order",
    "my_invoices",
    "my_invoice",
    "web_search",
    "lookup_record",
    "list_records",
    "business_summary",
    "cash_activity",
    "search_documents",
    "list_document_versions",
    "read_document",
    "run_analysis",
    "recall_notes",
}
RECORD_TOOLS = {"lookup_record", "list_records"}


def scoped_record_tools(tools, permissions):
    """Narrow only the model-visible record enum; SQL authorization stays authoritative."""
    allowed = tuple(
        entity for entity, (permission, *_projection) in QUERIES.items()
        if permission in permissions
    )
    selected = []
    for tool in tools:
        if tool.name not in RECORD_TOOLS:
            selected.append(tool)
            continue
        if not allowed:
            continue
        if len(allowed) == len(QUERIES):
            selected.append(tool)
            continue
        schema = create_model(
            f"Scoped{tool.name.title().replace('_', '')}Args",
            __base__=tool.args_schema,
            entity=(
                Literal[allowed],
                Field(description="Record entity permitted for the selected local profile"),
            ),
        )
        selected.append(
            tool.model_copy(
                update={
                    "args_schema": schema,
                    "description": (
                        f"{tool.description}\nFor this profile, permitted entities: "
                        + ", ".join(allowed)
                        + "."
                    ),
                }
            )
        )
    return selected, allowed


def configuration(project):
    """Validate a named preset, including unknown keys, before accepting a message."""
    section = settings(project).get("middleware", {})
    if not isinstance(section, dict) or set(section) - {"preset", "presets"}:
        raise ValueError("Unknown [middleware] setting; use preset and presets")
    preset = section.get("preset", "standard")
    presets = section.get("presets", {"standard": {}})
    if not isinstance(preset, str) or not isinstance(presets, dict) or preset not in presets:
        raise ValueError(f"Unknown middleware preset: {preset!r}")
    values = presets[preset]
    if not isinstance(values, dict) or set(values) - DEFAULTS.keys():
        raise ValueError("Unknown middleware preset setting; see docs/middleware.md")
    options = {**DEFAULTS, **values}
    for key, lower, upper in [
        ("model_calls", 1, 50),
        ("tool_calls", 1, 100),
        ("model_retries", 0, 3),
        ("summary_messages", 0, 200),
        ("summary_keep", 1, 20),
        ("graph_steps", 10, 500),
    ]:
        if type(options[key]) is not int or not lower <= options[key] <= upper:
            raise ValueError(f"middleware {key} must be an integer from {lower} to {upper}")
    delay = options["retry_delay"]
    if type(delay) not in {int, float} or not 0 <= delay <= 5:
        raise ValueError("middleware retry_delay must be 0 to 5 seconds")
    if type(options["redact_email"]) is not bool:
        raise ValueError("middleware redact_email must be true or false")
    if options["tool_selection"] not in ("all", "read_only"):
        raise ValueError("middleware tool_selection must be all or read_only")
    if options["summary_messages"] and options["summary_messages"] <= options["summary_keep"]:
        raise ValueError("summary_messages must exceed summary_keep (or be 0 to disable)")
    return {"preset": preset, **options}


def transient_model_error(error):
    """Retry transport failures and provider-classified transient errors, not bad input."""
    if isinstance(error, ModelError):
        return error.is_retryable
    if isinstance(error, (httpx.TransportError, TimeoutError, ConnectionError)):
        return True
    status = getattr(error, "status_code", None)
    return status in {408, 429, 500, 502, 503, 504}


def textual_tool_call(response, offered_tools):
    """Identify tool-call markup that the provider returned as plain answer text."""
    if any(isinstance(message, AIMessage) and message.tool_calls for message in response.result):
        return False
    names = {tool.name for tool in offered_tools}
    for message in response.result:
        if not isinstance(message, AIMessage):
            continue
        content = message.content
        if not isinstance(content, str):
            continue
        if any(
            match.group(1) in names
            for match in re.finditer(
                r"(?m)^[ \t]*(?:<tool_call>[ \t]*)?<function=([A-Za-z_][A-Za-z0-9_]*)>",
                content,
            )
        ):
            return True
    return False


def clean_orphan_tool_marker(response, context):
    """Remove an unfinished provider marker from a final answer, retaining raw trace."""
    cleaned = []
    changed = []
    for message in response.result:
        if (
            isinstance(message, AIMessage)
            and not message.tool_calls
            and isinstance(message.content, str)
        ):
            marker = re.search(r"<tool_call>\s*$", message.content)
            content = message.content[: marker.start()].rstrip() if marker else ""
            if content:
                changed.append(message.id)
                message = message.model_copy(update={"content": content})
        cleaned.append(message)
    if changed:
        event(
            context,
            "provider_markup_removed",
            {"marker": "<tool_call>", "message_ids": changed},
        )
        return replace(response, result=cleaned)
    return response


class NativeToolCallGuardMiddleware(AgentMiddleware):
    """Retry one provider formatting failure; never treat textual markup as a tool call."""

    def wrap_model_call(self, request, handler):
        response = handler(request)
        if not textual_tool_call(response, request.tools):
            return clean_orphan_tool_marker(response, request.runtime.context)
        context = request.runtime.context
        event(context, "native_tool_call_retry", {"reason": "tool markup was plain text"})
        corrected = request.override(
            system_message=SystemMessage(
                content=request.system_prompt
                + "\nYour previous response contained tool-call markup as plain text. "
                "No tool ran. Retry using a native tool call in the model tool channel. "
                "Do not answer with record facts before the tool returns."
            )
        )
        retried = handler(corrected)
        if textual_tool_call(retried, request.tools) or not any(
            isinstance(message, AIMessage) and message.tool_calls
            for message in retried.result
        ):
            event(context, "native_tool_call_failed", {"reason": "no native call on retry"})
            raise RuntimeError("Model did not produce a native tool call after one retry")
        return clean_orphan_tool_marker(retried, context)


class RuntimeContextMiddleware(AgentMiddleware):
    """Project-local identity injection and deterministic teaching tool selection.

    Tool filtering reduces offered schemas; company services remain the authority
    for every tool invocation, including direct calls outside this middleware.
    """

    def __init__(self, selection):
        self.selection = selection

    def wrap_model_call(self, request, handler):
        actor = authorize(request.runtime.context)
        tools = request.tools
        if actor["access_profile"] not in {"super_user", "admin"}:
            tools = [tool for tool in tools if tool.name != "simulate_delete"]
        if self.selection == "read_only":
            tools = [tool for tool in tools if tool.name in READ_ONLY_TOOLS]
        tools, allowed_entities = scoped_record_tools(tools, actor["permissions"])
        identity = (
            f"\nSelected local demo profile: user={actor['username']}; "
            f"access profile={actor['access_profile']}; "
            f"allowed permissions={', '.join(actor['permissions'])}. "
            "This access context comes from the application, not from the user's message. "
            f"Current local calendar date: {date.today().isoformat()}. "
            "For current document questions, omit effective_on so the search tool uses this date. "
            "Only pass a different effective_on when the user supplies an event date."
        )
        event(
            request.runtime.context,
            "runtime_context",
            {
                "actor_id": actor["id"],
                "access_profile": actor["access_profile"],
                "tool_selection": self.selection,
                "selected_tools": [tool.name for tool in tools],
                "allowed_record_entities": allowed_entities,
            },
        )
        return handler(
            request.override(
                tools=tools, system_message=SystemMessage(content=request.system_prompt + identity)
            )
        )

    def wrap_tool_call(self, request, handler):
        if self.selection == "read_only" and request.tool_call["name"] not in READ_ONLY_TOOLS:
            event(
                request.runtime.context,
                "tool_selection_denied",
                {
                    "tool_call": request.tool_call,
                    "selection": self.selection,
                },
            )
            return ToolMessage(
                content="This tool is disabled by the read_only learning configuration.",
                tool_call_id=request.tool_call["id"],
                name=request.tool_call["name"],
                status="error",
            )
        return handler(request)


def build_middleware(model, options):
    """Return outer-to-inner wrappers; VisibilityMiddleware is appended by build_agent.

    Input PII handling precedes the summary helper. Retry wraps visibility so each
    provider attempt has its own captured input/output. No company write is retried.
    """
    stack = [
        RuntimeContextMiddleware(options["tool_selection"]),
        NativeToolCallGuardMiddleware(),
    ]
    if options["redact_email"]:
        stack.append(PIIMiddleware("email", strategy="redact", apply_to_input=True))
    if options["summary_messages"]:
        stack.append(
            SummarizationMiddleware(
                model=model,
                trigger=("messages", options["summary_messages"]),
                keep=("messages", options["summary_keep"]),
            )
        )
    stack.extend(
        [
            ModelCallLimitMiddleware(run_limit=options["model_calls"], exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=options["tool_calls"], exit_behavior="end"),
            ModelRetryMiddleware(
                max_retries=options["model_retries"],
                retry_on=transient_model_error,
                initial_delay=options["retry_delay"],
                max_delay=5,
                jitter=False,
                on_failure="error",
            ),
        ]
    )
    return stack
