"""FastAPI surface for the local Acme Wholesale React demo website."""

import json
import re
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from acme.app_store import AccessDenied, list_threads, new_thread
from acme.business_insights import (
    expense_history,
    financial_activity,
    order_history,
    order_history_detail,
)
from acme.company_data import AS_OF
from acme.company_tools import accessible_documents, document_body, document_root
from acme.database_editor import (
    RecordConflict,
    delete_row,
    relationships,
    row_dependencies,
    save_row,
    table_schema,
)
from acme.dataset import connect
from acme.execution_inspector import (
    conversations as inspect_conversations,
)
from acme.execution_inspector import (
    events as inspect_events,
)
from acme.execution_inspector import (
    snapshot as inspect_snapshot,
)
from acme.order_journey import order_journey
from acme.portal_data import (
    browse,
    customer_invoice,
    customer_order,
    customer_summary,
    edit_customer_address,
    edit_customer_contact,
    edits,
    employee_options,
    employees,
    objects,
    product_detail,
    products,
    query_sql,
    record,
    superuser_focuses,
)
from acme.portal_identity import initialize, persona, select
from acme.purchase_journey import purchase_journey
from acme.reset_company import preview as preview_company_reset
from acme.reset_company import reset as reset_company
from acme.scenarios import audit_contemporary_history, create_customer_scenario, customer_candidates
from acme.tool_catalog import EXAMPLES, TOOLS, run_tool, tool_details
from acme.ui_service import LearningService

OBJECT_PERMISSION = {
    "company_expenses": "finance.read",
    "credit_notes": "finance.read",
    "invoice_items": "finance.read",
    "invoices": "finance.read",
    "invoice_balances": "finance.read",
    "payment_allocations": "finance.read",
    "payments": "finance.read",
    "goods_receipts": "operations.read",
    "inventory": "operations.read",
    "order_fulfillment": "operations.read",
    "purchase_order_items": "operations.read",
    "purchase_orders": "operations.read",
    "shipment_items": "operations.read",
    "shipments": "operations.read",
    "stock_movements": "operations.read",
    "suppliers": "operations.read",
    "warehouses": "operations.read",
    "forecasts": "analytics.read",
    "forecast_runs": "analytics.read",
    "monthly_customer_sales": "analytics.read",
    "sales_targets": "analytics.read",
    "ticket_events": "support.read",
    "tickets": "support.read",
    "document_links": "super_user",
    "document_versions": "super_user",
    "documents": "super_user",
}


class PersonaChoice(BaseModel):
    kind: str
    subject_id: str = ""


class ScenarioInput(BaseModel):
    name: str
    order_count: int = 0
    items_per_order: int = 1
    total_pence: int = 0
    cancelled_count: int = 0
    fulfilled_count: int = 0
    payment_profile: Literal["settled", "partial", "unpaid"] = "settled"


class ResetInput(BaseModel):
    stamp: str
    preserve: list[str] = Field(default_factory=list)


class ChatInput(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None
    submission_id: str | None = None


class ToolInput(BaseModel):
    arguments: dict = Field(default_factory=dict)


class SqlInput(BaseModel):
    sql: str


class AddressInput(BaseModel):
    label: str
    country: str


class ContactInput(BaseModel):
    name: str
    responsibility: str


class RowCreateInput(BaseModel):
    values: dict[str, object]


class RowUpdateInput(BaseModel):
    values: dict[str, object]
    expected: dict[str, object]


class RowDeleteInput(BaseModel):
    expected: dict[str, object]


class DecisionInput(BaseModel):
    decision: str
    arguments: dict | None = None


def create_portal(project: Path, state: Path, data: Path) -> FastAPI:
    project, state, data = project.resolve(), state.resolve(), data.resolve()
    initialize(state)
    service = LearningService(project, state, data)

    @asynccontextmanager
    async def lifespan(_app):
        service.start()
        try:
            yield
        finally:
            service.close()

    app = FastAPI(title="Acme Wholesale local demo", lifespan=lifespan)

    @app.exception_handler(AccessDenied)
    async def access_error(_request, exc):
        return Response(
            json.dumps({"detail": str(exc)}), status_code=403, media_type="application/json"
        )

    @app.exception_handler(ValueError)
    async def value_error(_request, exc):
        return Response(
            json.dumps({"detail": str(exc)}), status_code=400, media_type="application/json"
        )

    @app.exception_handler(RecordConflict)
    async def record_conflict(_request, exc):
        return Response(
            json.dumps({"detail": str(exc)}), status_code=409, media_type="application/json"
        )

    def session(request: Request) -> tuple[str, dict]:
        token = request.cookies.get("acme_portal", "")
        return token, persona(project, state, token)

    def internal(request: Request) -> tuple[str, dict]:
        token, selected = session(request)
        if selected["kind"] not in {"employee", "super_user"}:
            raise AccessDenied("Select an employee or superuser persona")
        return token, selected

    def allow_object(selected: dict, name: str):
        requirement = OBJECT_PERMISSION.get(name, "commercial.read")
        if selected["kind"] != "super_user" and requirement not in selected["permissions"]:
            raise AccessDenied(f"This persona cannot inspect {name}")

    def document_view(document: dict, selected: dict, tags: list[str] | None = None) -> dict:
        if document["category"] == "customer_terms":
            visibility = "Linked customer · employees · superuser"
        elif document["category"] == "policies" and document["access_scope"] == "general":
            visibility = "Customers · employees · superuser"
        else:
            visibility = f"Employees with {document['access_scope']} scope · superuser"
        return {**document, "visibility_label": visibility, "tags": tags or []}

    def document_tags(document: dict) -> list[str]:
        """Topic facets describe the document's subject, not boilerplate mentions."""
        title = document["title"].casefold()
        patterns = {
            "order": r"\border\w*\b",
            "payment": r"\b(?:payment|receivable|settlement)\w*\b",
            "stock": r"\b(?:stock|inventory|replenish)\w*\b",
            "shipment": r"\b(?:shipment|dispatch|delivery|fulfill|consignment)\w*\b",
            "return": r"\breturn\w*\b",
            "forecast": r"\bforecast\w*\b",
            "supplier": r"\bsupplier\w*\b",
            "invoice": r"\binvoice\w*\b",
            "customer": r"\bcustomer\w*\b",
            "pricing": r"\bpric\w*\b",
            "support": r"\bsupport\w*\b",
            "credit": r"\bcredit\w*\b",
        }
        found = {topic for topic, pattern in patterns.items() if re.search(pattern, title)}
        category_topics = {
            "incident_notes": "support",
            "planning_commentary": "forecast",
            "procurement_cases": "supplier",
            "product_guides": "product",
            "customer_terms": "customer",
        }
        if document["category"] in category_topics:
            found.add(category_topics[document["category"]])
        linked_topics = {
            "order_id": "order",
            "invoice_id": "invoice",
            "ticket_id": "support",
            "forecast_id": "forecast",
            "product_id": "product",
            "customer_id": "customer",
            "warehouse_id": "stock",
        }
        found.update(linked_topics[key] for key in document["record_links"] if key in linked_topics)
        found.add(document["category"].replace("_", " "))
        found.update(key.removesuffix("_id").replace("_", " ") for key in document["record_links"])
        return sorted(found)

    @app.get("/api/bootstrap")
    def bootstrap(request: Request):
        selected = None
        try:
            selected = session(request)[1]
        except AccessDenied:
            pass
        db = connect(state / "company.sqlite", readonly=True)
        try:
            counts = {
                name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in ("customers", "products", "orders", "employees")
            }
        finally:
            db.close()
        return {
            "persona": selected,
            "counts": counts,
            "business_date": AS_OF,
            "contemporary_date": date.today().isoformat(),
        }

    @app.get("/api/personas/search")
    def persona_search(
        kind: str,
        q: str = "",
        min_orders: int = 0,
        max_orders: int | None = None,
        status: str = "",
        sort: str = "orders_desc",
        period: str = "all",
        department: str = "",
        location: str = "",
        job_title: str = "",
        min_customers: int = 0,
        active_only: bool = False,
    ):
        if kind == "customer":
            return customer_candidates(state, q, min_orders, max_orders, status, sort, period)
        if kind == "employee":
            return employees(
                state,
                q,
                department=department,
                location=location,
                job_title=job_title,
                min_customers=min_customers,
                sort=sort
                if sort in {"customers_desc", "customers_asc", "name", "hired"}
                else "customers_desc",
            )
        if kind == "super_user":
            return superuser_focuses(
                state,
                q,
                sort if sort in {"name", "customers_desc", "orders_desc"} else "name",
                active_only,
            )
        raise ValueError("Unknown persona kind")

    @app.get("/api/personas/options")
    def persona_options():
        return employee_options(state)

    @app.post("/api/personas/scenarios")
    def create_scenario(payload: ScenarioInput):
        return create_customer_scenario(
            state,
            payload.name,
            payload.order_count,
            payload.items_per_order,
            payload.total_pence,
            payload.cancelled_count,
            payload.fulfilled_count,
            payload.payment_profile,
        )

    @app.post("/api/personas/select")
    def select_persona(choice: PersonaChoice, response: Response):
        token, selected = select(project, state, choice.kind, choice.subject_id)
        response.set_cookie("acme_portal", token, httponly=True, samesite="lax", max_age=28800)
        return selected

    @app.get("/api/products")
    def catalog(q: str = "", page: int = 1):
        return products(state, q, page)

    @app.get("/api/products/{product_id}")
    def catalog_detail(product_id: str):
        result = product_detail(state, product_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Product not found")
        return result

    @app.get("/api/customer")
    def customer_home(
        request: Request,
        orders_page: int = Query(default=1, ge=1, le=10000),
        invoices_page: int = Query(default=1, ge=1, le=10000),
    ):
        _token, selected = session(request)
        if selected["kind"] != "customer":
            raise AccessDenied("Select a customer persona")
        return customer_summary(state, selected["subject_id"], orders_page, invoices_page)

    @app.get("/api/customer/orders/{order_id}")
    def order_detail(request: Request, order_id: str):
        _token, selected = session(request)
        if selected["kind"] != "customer":
            raise AccessDenied("Select a customer persona")
        return customer_order(state, selected["subject_id"], order_id)

    @app.get("/api/customer/invoices/{invoice_id}")
    def invoice_detail(
        request: Request,
        invoice_id: str,
        page: int = Query(default=1, ge=1, le=10000),
    ):
        _token, selected = session(request)
        if selected["kind"] != "customer":
            raise AccessDenied("Select a customer persona")
        result = customer_invoice(state, selected["subject_id"], invoice_id, page)
        if result is None:
            raise HTTPException(status_code=404, detail="Invoice not found for selected customer")
        return result

    @app.get("/api/employee")
    def employee_home(request: Request):
        _token, selected = internal(request)
        db = connect(state / "company.sqlite", readonly=True)
        try:
            focus = selected["subject_id"] if selected["kind"] == "super_user" else "all"
            recent_orders = [
                dict(row)
                for row in db.execute(
                    "SELECT o.id,o.ordered_at,o.status,c.name AS customer "
                    "FROM orders o JOIN customers c ON c.id=o.customer_id "
                    "WHERE (?='all' OR EXISTS (SELECT 1 FROM employee_assignments a "
                    "WHERE a.employee_id=c.account_manager_id AND a.department_id=? "
                    "AND a.valid_until IS NULL)) "
                    "ORDER BY o.ordered_at DESC LIMIT 12",
                    (focus, focus),
                )
            ]
            counts = {
                name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in ("customers", "orders", "invoices", "tickets")
            }
        finally:
            db.close()
        return {
            "persona": selected,
            "counts": counts,
            "recent_orders": recent_orders,
            "order_focus": focus,
        }

    @app.get("/api/insights/finance")
    def insights_finance(
        request: Request, start: date, end: date,
        cohort: Literal["historical", "contemporary"] = "contemporary",
    ):
        _token, selected = internal(request)
        permissions = set(selected["permissions"])
        if selected["kind"] != "super_user" and not (
            {"finance.read", "analytics.read"} & permissions
        ):
            raise AccessDenied("Select a finance, analytics or superuser persona")
        return financial_activity(
            state, start, end, cohort,
            include_settlement=selected["kind"] == "super_user"
            or "finance.read" in permissions,
        )

    @app.get("/api/insights/orders")
    def insights_orders(
        request: Request, start: date, end: date,
        cohort: Literal["historical", "contemporary"] = "contemporary",
        page: int = Query(default=1, ge=1, le=10000),
        status: str = "", customer_id: str = "", q: str = "",
    ):
        _token, selected = internal(request)
        if selected["kind"] != "super_user" and "commercial.read" not in selected["permissions"]:
            raise AccessDenied("This persona cannot inspect company orders")
        return order_history(
            state, start, end, cohort, page=page, status=status,
            customer_id=customer_id, search=q,
        )

    @app.get("/api/insights/expenses")
    def insights_expenses(
        request: Request, start: date, end: date,
        cohort: Literal["historical", "contemporary"] = "contemporary",
        page: int = Query(default=1, ge=1, le=10000), category: str = "", q: str = "",
    ):
        _token, selected = internal(request)
        if selected["kind"] != "super_user" and "finance.read" not in selected["permissions"]:
            raise AccessDenied("Select finance or superuser to inspect cash expenses")
        return expense_history(state, start, end, cohort, page=page, category=category, search=q)

    @app.get("/api/insights/orders/{order_id}")
    def insights_order_detail(request: Request, order_id: str):
        _token, selected = internal(request)
        if selected["kind"] != "super_user" and "commercial.read" not in selected["permissions"]:
            raise AccessDenied("This persona cannot inspect company orders")
        permissions = set(selected["permissions"])
        if selected["kind"] == "super_user":
            permissions.update({"operations.read", "finance.read"})
        detail = order_history_detail(state, order_id, permissions)
        if detail is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return detail

    @app.get("/api/documents")
    def documents(
        request: Request,
        q: str = "",
        category: str = "",
        keyword: str = "",
        tag: str = "",
        scope: str = "",
        status: str = "",
        owner: str = "",
        linked_type: str = "",
        effective_on: date | None = None,
        sort: str = "title",
    ):
        if len(q) > 200 or len(keyword) > 200:
            raise ValueError("Document search text must be at most 200 characters")
        token, selected = session(request)
        context = service.company_context(token, service.playground(token))
        all_rows = accessible_documents(context)
        rows = (
            accessible_documents(context, effective_on.isoformat())
            if effective_on else all_rows
        )
        if q:
            rows = [
                d for d in rows
                if q.casefold() in (d["title"] + " " + d["document_id"]).casefold()
            ]
        if category:
            rows = [d for d in rows if d["category"] == category]
        if tag:
            rows = [d for d in rows if tag in document_tags(d)]
        if scope:
            rows = [d for d in rows if d["access_scope"] == scope]
        if status:
            rows = [d for d in rows if d["status"] == status]
        if owner:
            rows = [d for d in rows if d["owner_employee_id"] == owner]
        if linked_type:
            rows = [d for d in rows if linked_type in d["record_links"]]
        if keyword:
            needle = keyword.casefold()
            rows = [d for d in rows if needle in document_body(context, d).casefold()]
        if sort == "newest":
            rows.sort(
                key=lambda item: (item["effective_from"], item["version"]), reverse=True
            )
        elif sort == "title":
            rows.sort(key=lambda item: (item["title"], item["version"]))
        else:
            raise ValueError("Unknown document sort")
        return {
            "documents": [
                document_view(row, selected, document_tags(row)) for row in rows
            ],
            "total": len(rows),
            "effective_on": effective_on.isoformat() if effective_on else None,
            "categories": sorted({row["category"] for row in all_rows}),
        }

    @app.get("/api/documents/categories")
    def document_categories(request: Request):
        token, _selected = session(request)
        context = service.company_context(token, service.playground(token))
        rows = accessible_documents(context)
        return {
            "categories": sorted({row["category"] for row in rows}),
            "tags": sorted(
                {tag for row in rows for tag in document_tags(row)}
            ),
            "scopes": sorted({row["access_scope"] for row in rows}),
            "statuses": sorted({row["status"] for row in rows}),
            "owners": sorted({row["owner_employee_id"] for row in rows}),
            "linked_types": sorted({key for row in rows for key in row["record_links"]}),
        }

    @app.get("/api/documents/{document_id}/{version}")
    def document_detail(request: Request, document_id: str, version: int):
        token, selected = session(request)
        context = service.company_context(token, service.playground(token))
        item = next(
            (
                d
                for d in accessible_documents(context)
                if d["document_id"] == document_id and d["version"] == version
            ),
            None,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Document version unavailable")
        body = document_body(context, item)
        return {
            "metadata": document_view(item, selected, document_tags(item)),
            "markdown": body,
        }

    @app.get("/api/documents/{document_id}/{version}/download")
    def document_download(request: Request, document_id: str, version: int):
        token, _selected = session(request)
        context = service.company_context(token, service.playground(token))
        item = next(
            (
                d
                for d in accessible_documents(context)
                if d["document_id"] == document_id and d["version"] == version
            ),
            None,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Document version unavailable")
        path = document_root(context) / item["relative_path"]
        document_body(context, item)
        return FileResponse(
            path, filename=f"{document_id}.v{version}.md", media_type="text/markdown"
        )

    @app.get("/api/tools")
    def tools_list(request: Request):
        _token, selected = internal(request)
        result = []
        for name, title, description in TOOLS:
            long_description, _example, schema = tool_details(name)
            result.append(
                {
                    "name": name,
                    "title": title,
                    "description": description,
                    "detail": long_description,
                    "schema": schema,
                    "example": EXAMPLES[name],
                }
            )
        return {"tools": result, "persona": selected}

    @app.post("/api/tools/{name}/run")
    def tool_run(request: Request, name: str, payload: ToolInput):
        token, _selected = internal(request)
        if name not in {item[0] for item in TOOLS}:
            raise HTTPException(status_code=404, detail="Unknown tool")
        context = service.company_context(token, service.playground(token))
        output = run_tool(context, name, payload.arguments)
        return output.model_dump(mode="json") if hasattr(output, "model_dump") else output

    @app.get("/api/database/objects")
    def database_objects(request: Request):
        _token, selected = internal(request)
        return [
            item
            for item in objects(state)
            if selected["kind"] == "super_user"
            or OBJECT_PERMISSION.get(item["name"], "commercial.read") in selected["permissions"]
        ]

    @app.get("/api/database/relationships")
    def database_relationships(request: Request):
        visible = {item["name"] for item in database_objects(request)}
        return relationships(state, visible)

    @app.get("/api/database/audit-modern")
    def database_audit_modern(request: Request):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to audit all company records")
        return audit_contemporary_history(state)

    @app.get("/api/database/schema/{name}")
    def database_schema(request: Request, name: str):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to inspect editable table fields")
        return table_schema(state, name)

    @app.post("/api/database/rows/{name}")
    def database_create_row(request: Request, name: str, payload: RowCreateInput):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to change company data")
        return save_row(state, name, payload.values, selected["display_name"])

    @app.get("/api/database/rows/{name}/{identifier}/dependencies")
    def database_row_dependencies(request: Request, name: str, identifier: str):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to inspect row dependencies")
        return row_dependencies(state, name, identifier)

    @app.patch("/api/database/rows/{name}/{identifier}")
    def database_update_row(request: Request, name: str, identifier: str, payload: RowUpdateInput):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to change company data")
        return save_row(
            state,
            name,
            payload.values,
            selected["display_name"],
            identifier=identifier,
            expected=payload.expected,
        )

    @app.delete("/api/database/rows/{name}/{identifier}")
    def database_delete_row(request: Request, name: str, identifier: str, payload: RowDeleteInput):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to change company data")
        return delete_row(state, name, identifier, payload.expected, selected["display_name"])

    @app.get("/api/database/reset-preview")
    def database_reset_preview(request: Request):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to preview company reset")
        return preview_company_reset(state, data)

    @app.post("/api/database/reset")
    def database_reset(request: Request, payload: ResetInput):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to reset company data")
        return reset_company(state, data, payload.stamp, payload.preserve)

    @app.get("/api/database/{name}")
    def database_browse(
        request: Request,
        name: str,
        q: str = "",
        column: str = "",
        value: str = "",
        page: int = 1,
        size: int = 25,
    ):
        _token, selected = internal(request)
        allow_object(selected, name)
        return browse(
            state, name, search=q, filter_column=column, filter_value=value, page=page, size=size
        )

    @app.get("/api/database/order-journey/{identifier}")
    def database_order_journey(request: Request, identifier: str):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to inspect the full order journey")
        journey = order_journey(state, identifier)
        if journey is None:
            raise HTTPException(status_code=404, detail="Order not found")
        return journey

    @app.get("/api/database/purchase-journey/{identifier}")
    def database_purchase_journey(request: Request, identifier: str):
        _token, selected = internal(request)
        allow_object(selected, "purchase_orders")
        journey = purchase_journey(state, identifier)
        if journey is None:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        return journey

    @app.get("/api/database/{name}/{identifier}")
    def database_record(request: Request, name: str, identifier: str):
        _token, selected = internal(request)
        allow_object(selected, name)
        item = record(state, name, identifier)
        if item is None:
            raise HTTPException(status_code=404, detail="Record not found")
        return item

    @app.post("/api/database/query")
    def sql_query(request: Request, payload: SqlInput):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser for arbitrary SQL exploration")
        return query_sql(state, payload.sql)

    @app.post("/api/database/customers/{customer_id}/address")
    def customer_address(request: Request, customer_id: str, payload: AddressInput):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to edit company data")
        return edit_customer_address(
            state, customer_id, payload.label, payload.country, selected["display_name"]
        )

    @app.post("/api/database/contacts/{contact_id}")
    def contact_edit(request: Request, contact_id: str, payload: ContactInput):
        _token, selected = internal(request)
        if selected["kind"] != "super_user":
            raise AccessDenied("Select superuser to edit company data")
        return edit_customer_contact(
            state, contact_id, payload.name, payload.responsibility, selected["display_name"]
        )

    @app.get("/api/edits")
    def edit_history(request: Request):
        internal(request)
        return edits(state)

    @app.get("/api/conversations")
    def conversations(request: Request):
        token, _selected = session(request)
        return list_threads(project, state, token)

    @app.get("/api/execution/conversations")
    def execution_conversations(request: Request):
        _token, selected = session(request)
        return inspect_conversations(state, selected)

    @app.get("/api/execution/conversations/{thread_id}")
    def execution_snapshot(request: Request, thread_id: str):
        _token, selected = session(request)
        return inspect_snapshot(state, selected, thread_id)

    @app.get("/api/execution/conversations/{thread_id}/events")
    def execution_events(request: Request, thread_id: str, after: int = 0):
        _token, selected = session(request)
        return inspect_events(state, selected, thread_id, after)

    @app.post("/api/conversations")
    def create_conversation(request: Request):
        token, selected = session(request)
        title = "Customer assistant" if selected["kind"] == "customer" else "Employee assistant"
        return {"thread_id": new_thread(project, state, token, title, mode="company")}

    @app.post("/api/chat")
    def chat(request: Request, payload: ChatInput):
        token, _selected = session(request)
        thread_id = payload.thread_id or new_thread(
            project, state, token, "New conversation", mode="company"
        )
        identifier = payload.submission_id or uuid4().hex
        service.submit_chat(token, thread_id, payload.text, identifier)
        return {"thread_id": thread_id, "submission_id": identifier, "status": "queued"}

    @app.get("/api/conversations/{thread_id}")
    def conversation(request: Request, thread_id: str):
        token, _selected = session(request)
        return service.snapshot(token, thread_id)

    @app.get("/api/conversations/{thread_id}/events")
    def conversation_events(
        request: Request, thread_id: str, kind: str = "", text: str = "", after: int = 0
    ):
        token, _selected = session(request)
        return service.inspect(token, thread_id, kind, text, after)

    @app.post("/api/conversations/{thread_id}/operations/{identifier}")
    def operation_decide(request: Request, thread_id: str, identifier: str, payload: DecisionInput):
        token, _selected = internal(request)
        return service.decision(token, thread_id, identifier, payload.decision, payload.arguments)

    dist = project / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str):
            target = dist / path
            if path and target.is_file() and target.resolve().is_relative_to(dist.resolve()):
                media_type = "image/webp" if target.suffix.lower() == ".webp" else None
                return FileResponse(target, media_type=media_type)
            return FileResponse(dist / "index.html")

    return app
