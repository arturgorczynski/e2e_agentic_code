"""Explicit fault injection and a scripted model for reproducible loop demos."""
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from .data import scripted_conversation


class FailFirstModelCalls(AgentMiddleware):
    def __init__(self, failures=2):
        self.failures = failures
        self.attempts = 0

    def wrap_model_call(self, request, handler):
        self.attempts += 1
        print(f"INJECTED NETWORK FAILURE test: attempt {self.attempts}")
        if self.attempts <= self.failures:
            raise ConnectionError("Injected model endpoint outage")
        return handler(request)


class FailPrimaryModel(AgentMiddleware):
    def __init__(self, primary):
        self.primary = primary

    def wrap_model_call(self, request, handler):
        if request.model is self.primary:
            print("INJECTED FAILURE: primary endpoint")
            raise ConnectionError("Injected primary endpoint outage")
        return handler(request)


class FailModelAfterToolLimit(AgentMiddleware):
    """Fail one model only after a named tool has been blocked by its call limit."""

    def __init__(self, primary, tool_name):
        self.primary = primary
        self.tool_name = tool_name

    def wrap_model_call(self, request, handler):
        limit_error = any(
            isinstance(message, ToolMessage)
            and message.name == self.tool_name
            and message.status == "error"
            and "Tool call limit exceeded" in str(message.content)
            for message in request.messages
        )
        if request.model is self.primary and limit_error:
            print(f"INJECTED FAILURE: {self.tool_name} limit requires another model")
            raise ConnectionError("Injected primary model failure after tool limit")
        return handler(request)


class ScriptedModel(BaseChatModel):
    """A test double, NOT an LLM. Responses and repetitions are explicit."""
    responses: list[AIMessage]
    repeat_last: bool = False
    name: str = "scripted"
    _index: int = PrivateAttr(default=0)

    @property
    def _llm_type(self):
        return "workshop-scripted-test-double"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self._index >= len(self.responses) and not self.repeat_last:
            raise RuntimeError("Scripted responses exhausted; this is not an LLM.")
        response = self.responses[min(self._index, len(self.responses) - 1)].model_copy(deep=True)
        self._index += 1
        response.id = f"script-{uuid4().hex}"
        for call in response.tool_calls:
            call["id"] = f"call-{uuid4().hex}"
        return ChatResult(generations=[ChatGeneration(message=response)])


def tool_request(name, **args):
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": "replaced-at-runtime", "type": "tool_call"}
    ])


def looping_model(tool_name="poll_job", *, name="scripted-loop", **args):
    print("SCRIPTED TEST DOUBLE: always requests a tool; no external model call.")
    return ScriptedModel(name=name, responses=[tool_request(tool_name, **args)], repeat_last=True)


def scripted_model(name):
    print(f"SCRIPTED TEST DOUBLE: {name}; responses loaded from data/scripted_responses.json")
    return ScriptedModel(responses=scripted_conversation(name))


def tool_error_message(error, request):
    return f"{request.tool_call['name']} failed with {type(error).__name__}. Explain the failure."
