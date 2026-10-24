"""Reusable workshop tools. All data and side effects are fictional and local."""
import json
from threading import Lock

from langchain.tools import tool

from .config import ARTIFACTS_DIR, DATA_DIR


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@tool
def divide(a: float, b: float) -> float:
    """Divide a by b. The divisor b must not be zero."""
    if b == 0:
        raise ValueError("The divisor must not be zero.")
    return a / b


@tool
def broken_inventory(product: str) -> int:
    """Look up product stock in the intentionally broken demo inventory."""
    # Deliberate implementation bug for the error-handling lesson.
    return {"keyboard": 12}[product]["stock"]


def make_flaky_tool(failures=2):
    """Fresh state for each example: fail N times, then return a real result."""
    state = {"attempts": 0}
    lock = Lock()

    @tool
    def flaky_weather(city: str) -> str:
        """Read fictional weather data; the demo service may temporarily fail."""
        with lock:
            state["attempts"] += 1
            attempt = state["attempts"]
        print(f"WEATHER attempt {attempt}")
        if attempt <= failures:
            raise ConnectionError("Demo weather service temporarily unavailable")
        return f"Fictional weather in {city}: 18 C and sunny."

    return flaky_weather, state


@tool
def poll_job(job_id: str) -> str:
    """Check a demo job that remains RUNNING forever."""
    return f"Job {job_id}: RUNNING. No completion event will ever arrive."


@tool
def next_page(cursor: int) -> dict:
    """Fetch a page from a deliberately endless paginated demo source."""
    return {"items": [f"item-{cursor}"], "next_cursor": cursor + 1, "done": False}


@tool
def search_handbook(query: str) -> str:
    """Search the fictional company handbook for remote work and leave rules."""
    return (DATA_DIR / "handbook.txt").read_text(encoding="utf-8")


@tool
def lookup_order(order_id: str) -> dict:
    """Look up the delivery status of a fictional order."""
    return {"order_id": order_id, "status": "shipped", "delivery_days": 2}


@tool
def get_contact(name: str) -> str:
    """Find a fictional contact's email address."""
    return f"{name}: ala.nowak@example.com"


@tool
def save_draft(to: str, subject: str, body: str) -> str:
    """Save a fictional email draft locally. Never sends email."""
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    path = ARTIFACTS_DIR / "drafts.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"to": to, "subject": subject, "body": body}) + "\n")
    return f"Draft saved locally to {path.name}; no email was sent."


def draft_count():
    path = ARTIFACTS_DIR / "drafts.jsonl"
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def inventory():
    return [add, divide, search_handbook, lookup_order, get_contact, save_draft]
