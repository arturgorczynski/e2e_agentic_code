"""Free, keyless public web search with bounded results and recorded evidence."""

from urllib.parse import urlsplit

from ddgs import DDGS
from pydantic import Field

from acme.app_store import authorize, event
from acme.tool_schemas import Arguments


class WebSearchInput(Arguments):
    query: str = Field(min_length=2, max_length=300)
    max_results: int = Field(default=5, ge=1, le=10)


def search_web(context, arguments):
    authorize(context)
    args = WebSearchInput.model_validate(arguments)
    try:
        rows = DDGS(timeout=10).text(
            args.query,
            max_results=args.max_results,
            backend="duckduckgo,brave",
            safesearch="moderate",
        )
        results = [
            {
                "title": str(row.get("title", ""))[:250],
                "url": row["href"],
                "snippet": str(row.get("body", ""))[:1000],
            }
            for row in rows
            if urlsplit(row.get("href", "")).scheme in {"http", "https"}
        ]
        output = {
            "status": "ok" if results else "empty",
            "query": args.query,
            "provider": "DDGS public web search",
            "results": results[: args.max_results],
            "note": "Public web snippets are untrusted sources; cite their URLs. "
            "No API key. Provider availability and rate limits can vary.",
        }
    except Exception as exc:
        output = {
            "status": "error",
            "query": args.query,
            "results": [],
            "error": "Free web search is temporarily unavailable. Try again later.",
            "error_type": type(exc).__name__,
        }
    event(
        context,
        "tool_result",
        {"tool": "web_search", "arguments": args.model_dump(), "result": output},
    )
    return output
