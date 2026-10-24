"""Small model-facing interface to fixed local analysis. No generated host code."""

import json
import time
from typing import Literal

from pydantic import Field

from acme.app_store import AccessDenied, authorize, event
from acme.jobs import (
    cancel_job,
    job_record,
    list_files,
    list_jobs,
    prepare_sales_csv,
    read_file,
    start_csv_job,
)
from acme.tool_schemas import Arguments
from acme.tracing import span


class WorkspaceInput(Arguments):
    action: Literal["prepare_sales", "list", "analyze", "status", "read", "cancel"]
    file_id: str | None = Field(default=None, max_length=100)
    job_id: str | None = Field(default=None, max_length=100)
    operation: Literal["numeric_summary", "group_sum"] = "numeric_summary"
    value_column: str = Field(default="sales_pence", max_length=100)
    group_column: str | None = Field(default=None, max_length=100)


def workspace_action(context, arguments):
    """Wait for a bounded CSV job so its answer is useful in the same agent turn."""
    authorize(context)
    with span(context, "workspace_tool", {"arguments": arguments}):
        try:
            args = WorkspaceInput.model_validate(arguments)
            if args.action == "prepare_sales":
                result = {"file_id": prepare_sales_csv(context), "units": "GBP pence"}
            elif args.action == "list":
                result = {"files": list_files(context), "jobs": list_jobs(context)}
            elif args.action == "read":
                record, content = read_file(context, args.file_id)
                result = {
                    "file_id": args.file_id,
                    "name": record["name"],
                    "content": content.decode("utf-8", errors="replace")[:6000],
                    "truncated": len(content.decode("utf-8", errors="replace")) > 6000,
                    "source": json.loads(record["source_json"]),
                }
            elif args.action == "cancel":
                result = cancel_job(context, args.job_id)
            elif args.action == "status":
                result = job_record(context, args.job_id)
            else:
                identifier = start_csv_job(
                    context, args.file_id, args.operation, args.value_column, args.group_column
                )
                until = time.monotonic() + 15
                result = job_record(context, identifier)
                while result["status"] in {"queued", "running", "publishing", "cancel_requested"}:
                    if time.monotonic() >= until:
                        result = {
                            "job_id": identifier,
                            "status": result["status"],
                            "message": "Still finalizing; use status. No second job needed.",
                        }
                        break
                    time.sleep(0.05)
                    result = job_record(context, identifier)
            payload = {"integration": "bounded_local_analysis", "result": result}
            if len(json.dumps(payload)) > 24000:
                payload = {
                    "integration": "bounded_local_analysis",
                    "truncated": True,
                    "message": "Use read for the result files shown in the workspace.",
                }
            event(context, "workspace_result", payload)
            return payload
        except (ValueError, AccessDenied, TypeError) as exc:
            result = {"integration": "bounded_local_analysis", "error": str(exc)[:500]}
            event(context, "workspace_error", result)
            return result
