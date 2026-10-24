"""Public tool arguments and bounded result envelope; identity is never an argument."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Entity = Literal[
    "customers",
    "orders",
    "order_items",
    "products",
    "employees",
    "invoices",
    "invoice_items",
    "payments",
    "payment_allocations",
    "credit_notes",
    "company_expenses",
    "shipments",
    "shipment_items",
    "stock_movements",
    "inventory",
    "purchase_orders",
    "purchase_order_items",
    "goods_receipts",
    "tickets",
    "ticket_events",
    "forecasts",
    "forecast_runs",
    "sales_targets",
]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)


class LookupInput(Arguments):
    entity: Entity
    record_id: str = Field(min_length=1, max_length=200)


class ListInput(Arguments):
    entity: Entity
    parent_id: str | None = Field(default=None, max_length=200)
    goods_receipt_id: str | None = Field(
        default=None,
        max_length=200,
        description="Exact goods receipt link; supported only for stock_movements",
    )
    shipment_item_id: str | None = Field(
        default=None,
        max_length=200,
        description="Exact shipment-item link; supported only for stock_movements",
    )
    customer_id: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Customer filter for orders, invoices or payments; "
            "invoices.parent_id is an order"
        ),
    )
    status: str | None = Field(default=None, max_length=30)
    query: str | None = Field(default=None, max_length=100)
    after: str = Field(default="", max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


class SummaryInput(Arguments):
    report: Literal["sales", "receivables", "forecast", "customer_orders"]
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    customer_id: str | None = Field(default=None, max_length=100)
    forecast_id: str | None = Field(default=None, max_length=150)


class CashActivityInput(Arguments):
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    cohort: Literal["historical", "contemporary"]


class SearchInput(Arguments):
    query: str = Field(min_length=1, max_length=200)
    mentions_record_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Keep only permitted documents whose body mentions this complete record ID",
    )
    effective_on: str = Field(
        default_factory=lambda: date.today().isoformat(), pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    offset: int = Field(default=0, ge=0, le=200)
    limit: int = Field(default=5, ge=1, le=10)


class ReadInput(Arguments):
    document_id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1, le=1000)
    offset: int = Field(default=0, ge=0, le=100000)
    max_chars: int = Field(default=4000, ge=1, le=6000)


class DocumentVersionsInput(Arguments):
    document_id: str = Field(min_length=1, max_length=100)
    offset: int = Field(default=0, ge=0, le=1000)
    limit: int = Field(default=20, ge=1, le=50)


class AnalysisInput(Arguments):
    operation: Literal["sum", "difference", "percentage_change", "available_stock"]
    values: list[str] = Field(min_length=1, max_length=100)


class SourceRef(Arguments):
    kind: Literal["record", "document", "query"]
    id: str = Field(min_length=1, max_length=200)
    entity: str = Field(default="", max_length=40)
    version: int | None = Field(default=None, ge=1, le=1000)


class ReportInput(Arguments):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=6000)
    sources: list[SourceRef] = Field(min_length=1, max_length=12)


class TicketInput(Arguments):
    ticket_id: str = Field(min_length=1, max_length=150)
    expected_status: Literal["open"]
    new_status: Literal["in_progress"]
    reason: str = Field(min_length=5, max_length=500)


class SimulatedDeleteInput(Arguments):
    target_kind: Literal["record", "document"]
    entity: Entity | None = None
    record_id: str | None = Field(default=None, max_length=200)
    document_id: str | None = Field(default=None, max_length=100)
    version: int | None = Field(default=None, ge=1, le=1000)
    reason: str = Field(min_length=5, max_length=500)


class Page(BaseModel):
    returned: int
    total: int
    next_cursor: str | int | None = None
    has_more: bool = False


class ToolError(BaseModel):
    code: Literal[
        "invalid_arguments", "access_denied", "not_found", "conflict", "too_large", "data_error"
    ]
    message: str


class Record(BaseModel):
    entity: str
    id: str
    fields: dict[str, str | int | bool | None]


class ToolResult(BaseModel):
    status: Literal["ok", "empty", "error", "pending_approval"]
    integration: Literal[
        "simulated_company_sqlite", "mock_rag_text_search", "local_analysis", "local_report_store"
    ]
    records: list[Record] = Field(default_factory=list, max_length=50)
    facts: dict[str, str | int | bool | None] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list, max_length=100)
    page: Page | None = None
    error: ToolError | None = None
    operation_id: str | None = None


INPUTS = {
    "lookup_record": LookupInput,
    "list_records": ListInput,
    "business_summary": SummaryInput,
    "cash_activity": CashActivityInput,
    "search_documents": SearchInput,
    "list_document_versions": DocumentVersionsInput,
    "read_document": ReadInput,
    "run_analysis": AnalysisInput,
    "save_report": ReportInput,
    "update_ticket": TicketInput,
    "simulate_delete": SimulatedDeleteInput,
}
