"""Small custom middleware; the final notebook prints and exercises this source."""
from dataclasses import dataclass
from typing import NotRequired

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    before_model,
    dynamic_prompt,
    wrap_tool_call,
)
from langchain_core.messages import AIMessage, ToolMessage


@dataclass
class Audience:
    language: str = "Polish"


@dynamic_prompt
def audience_prompt(request):
    return f"You are a concise tutor. Answer in {request.runtime.context.language}."


@wrap_tool_call
def small_numbers_only(request, handler):
    args = request.tool_call["args"]
    if request.tool_call["name"] == "add" and any(abs(v) > 100 for v in args.values()):
        return ToolMessage(content="Use numbers between -100 and 100 in this lesson.",
                           tool_call_id=request.tool_call["id"], status="error")
    return handler(request)


class LifecycleMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime):
        print("1. before_agent: one invocation begins")

    def before_model(self, state, runtime):
        print("2. before_model: next model call")

    def wrap_model_call(self, request, handler):
        print("3. wrap_model_call: enter")
        response = handler(request)
        print("4. wrap_model_call: exit")
        return response

    def after_model(self, state, runtime):
        print("5. after_model: inspect the latest AI message")

    def wrap_tool_call(self, request, handler):
        print("6. wrap_tool_call: enter", request.tool_call["name"])
        result = handler(request)
        print("7. wrap_tool_call: exit")
        return result

    def after_agent(self, state, runtime):
        print("8. after_agent: invocation finished")


class WrapperOrder(AgentMiddleware):
    def __init__(self, label):
        self.label = label

    @property
    def name(self):
        return f"Wrapper_{self.label}"

    def wrap_model_call(self, request, handler):
        print(f"ENTER {self.label}")
        result = handler(request)
        print(f"EXIT {self.label}")
        return result


def demo_namespace(runtime):
    """Fixed fictional user for the shared-store lesson."""
    return ("middleware-workshop", "demo-user")


def show_evaluation(evaluation, history=None):
    if history is not None:
        history.append(evaluation)
    print("GRADER:", evaluation)


def check_onboarding(text):
    """Independent checks for this toy rubric; no model judgment involved."""
    lines = [line for line in text.splitlines() if line.strip()]
    return {"mentions_handbook": "handbook" in text.lower(),
            "mentions_laptop": "laptop" in text.lower(),
            "exactly_two_lines": len(lines) == 2}


class CountState(AgentState):
    model_visits: NotRequired[int]


@before_model(state_schema=CountState)
def count_model_visits(state, runtime):
    """A node hook returns a partial state update, merged into graph state."""
    return {"model_visits": state.get("model_visits", 0) + 1}


@before_model(can_jump_to=["end"])
def answer_ping_locally(state, runtime):
    """Short-circuit a known request without invoking a model."""
    if state["messages"][-1].content.strip().lower() == "ping":
        return {"messages": [AIMessage(content="pong")], "jump_to": "end"}
