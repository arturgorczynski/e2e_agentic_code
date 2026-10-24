"""Opt-in browser acceptance server: scripted model, real tools and a 30-second tool.

Run with the installed environment: python scripts/serve_browser_fixture.py.
Uses its own fixture data/state under artifacts/browser_fixture and port 7863.
Login: taylor.analyst / browser-fixture-only. This is not the learner's model server.
Choose Company assistant and send any message to exercise slow search and approval.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import gradio as gr
import uvicorn
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from acme.app_store import provision
from acme.company_tools import execute
from acme.dataset import build_dataset, initialize_state
from acme.runtime import submit
from acme.web import create_web_app

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts/browser_fixture"
ORIGINAL_POPEN = subprocess.Popen


class BrowserFixtureModel(BaseChatModel):
    """No provider calls: deterministic slow-tool and approval browser exercise."""

    @property
    def _llm_type(self):
        return "browser-acceptance-fixture"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        last = messages[-1]
        if isinstance(last, ToolMessage) and last.name == "save_report":
            reply = AIMessage(content="Browser fixture finished. Review the report in Approvals.")
        elif isinstance(last, ToolMessage) and last.name == "search_documents":
            result = json.loads(last.content)
            reply = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "save_report",
                        "id": "fixture-proposal",
                        "args": {
                            "title": "Browser recovery report",
                            "body": "Fixture policy review.",
                            "sources": result["sources"][:1],
                        },
                    }
                ],
            )
        else:
            reply = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "id": "fixture-search",
                        "args": {"query": "returns", "effective_on": "2011-11-01"},
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=reply)])


def slow_execute(context, name, arguments):
    if name == "search_documents":
        time.sleep(30)
    return execute(context, name, arguments)


def fixture_worker():
    payload = json.loads(sys.stdin.buffer.read(100000))
    request = payload["request"]
    with patch("acme.agent.execute", slow_execute):
        submit(
            Path(payload["project"]),
            Path(payload["state"]),
            Path(payload["data"]),
            payload["token"],
            request["thread_id"],
            request["submission_id"],
            request["user_text"],
            resume=bool(request["resume"]),
            model=BrowserFixtureModel(),
        )


def fixture_popen(arguments, *args, **kwargs):
    if arguments[-2:] == ["-m", "acme.ui_worker"]:
        arguments = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker"]
    return ORIGINAL_POPEN(arguments, *args, **kwargs)


def main():
    if "--worker" in sys.argv:
        fixture_worker()
        return
    data, state = FIXTURE / "data", FIXTURE / "state"
    if not (state / "app.sqlite").exists():
        build_dataset(ROOT, data, "fixture")
        initialize_state(ROOT, state, data=data)
        provision(ROOT, state, "taylor.analyst", "browser-fixture-only")
    app = create_web_app(ROOT, state, data, gr=gr)
    print("SCRIPTED BROWSER FIXTURE: http://127.0.0.1:7863", flush=True)
    with patch("acme.ui_service.subprocess.Popen", fixture_popen):
        uvicorn.run(app, host="127.0.0.1", port=7863, log_level="warning")


if __name__ == "__main__":
    main()
