"""Bounded company tools over local SQLite, documents, and write proposals."""

import hashlib
import json
import re
import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

from pydantic import ValidationError

from acme.app_store import AccessDenied, authorize, event, execution_lock, json_text, now
from acme.business_insights import validate_period
from acme.company_data import AS_OF
from acme.company_documents import metadata_and_body
from acme.company_queries import QUERIES, query
from acme.dataset import connect
from acme.demo_identity import kind_for_actor, persona
from acme.tool_schemas import INPUTS, Page, Record, SourceRef, ToolError, ToolResult
from acme.tracing import span

MAX_RESULT_BYTES = 48000
ORDER_REFERENCE_NOTE = (
    "source_invoice_no is an archived retail source identifier, not the Acme invoice "
    "relationship. A NULL value does not prove that this order has no invoice. "
    "Check invoices by order_id with finance.read; otherwise attribute an invoice "
    "claim to the document that reports it."
)
PURCHASE_REFERENCE_NOTE = (
    "Purchase-order provenance describes how the order was modeled or initially "
    "seeded. Its narrative may predate later goods receipts. Current ordered, "
    "received and outstanding quantities are calculated from all linked lines "
    "and receipts; verify warehouse arrival through matching stock movements."
)


def money_display(fields):
    """Keep exact stored pence and add explicit GBP strings for readable answers."""
    formatted = {
        key.removesuffix("_pence") + "_gbp": f"{Decimal(value) / 100:.2f}"
        for key, value in fields.items()
        if key.endswith("_pence") and isinstance(value, int)
    }
    return {**fields, **formatted}


def result(records=None, sources=None, **kwargs):
    if "facts" in kwargs:
        kwargs["facts"] = money_display(kwargs["facts"])
    return ToolResult(
        status="ok",
        integration="simulated_company_sqlite",
        records=records or [],
        sources=sources or [],
        **kwargs,
    )


def lookup(context, args):
    permission, sql, _, _, _ = QUERIES[args.entity]
    rows, evidence = query(
        context, "lookup:" + args.entity, sql + " WHERE id=?", (args.record_id,), permission
    )
    if not rows:
        return ToolResult(
            status="empty", integration="simulated_company_sqlite", facts={"found": False}
        )
    fields = rows[0]
    if args.entity == "invoices":
        reference_date = (
            date.today()
            if str(fields.get("provenance", "")).startswith("fictional_contemporary_")
            else date.fromisoformat(AS_OF)
        )
        fields["days_overdue"] = (
            max(0, (reference_date - date.fromisoformat(fields["due_on"])).days)
            if fields["outstanding_pence"]
            else 0
        )
        fields["business_reference"] = reference_date.isoformat()
    return result(
        [Record(entity=args.entity, id=fields["id"], fields=money_display(fields))],
        [
            SourceRef(kind="record", entity=args.entity, id=fields["id"]),
            SourceRef(kind="query", id=evidence),
        ],
        facts={
            "found": True,
            **({"source_invoice_no_note": ORDER_REFERENCE_NOTE} if args.entity == "orders" else {}),
            **(
                {"purchase_provenance_note": PURCHASE_REFERENCE_NOTE}
                if args.entity == "purchase_orders" else {}
            ),
        },
    )


def list_records(context, args):
    permission, sql, parent, status, text = QUERIES[args.entity]
    authorize(context, permission)
    if args.customer_id is not None and args.entity not in {"orders", "invoices", "payments"}:
        raise ValueError(f"customer_id is not supported for {args.entity}")
    if args.goods_receipt_id is not None or args.shipment_item_id is not None:
        if args.entity != "stock_movements":
            raise ValueError(
                "Receipt and shipment-item links are supported only for stock_movements"
            )
        if args.goods_receipt_id is not None and args.shipment_item_id is not None:
            raise ValueError("Filter by one stock-movement link at a time")
    if args.entity == "invoices" and args.parent_id is not None:
        mistaken_customer, _ = query(
            context,
            "invoice_parent_type_check",
            "SELECT id FROM customers WHERE id=?",
            (args.parent_id,),
            permission,
        )
        if mistaken_customer:
            raise ValueError(
                "For invoices, parent_id must be an order ID; use customer_id "
                "to list all invoices for a customer"
            )
    predicates, parameters = [], []
    for value, column, name in [
        (args.parent_id, parent, "parent_id"),
        (args.status, status, "status"),
    ]:
        if value is not None:
            if column is None:
                raise ValueError(f"{name} is not supported for {args.entity}")
            predicates.append(f"{column}=?")
            parameters.append(value)
    if args.customer_id is not None:
        predicates.append(
            "order_id IN (SELECT id FROM orders WHERE customer_id=?)"
            if args.entity == "invoices"
            else "customer_id=?"
        )
        parameters.append(args.customer_id)
    for value, column in (
        (args.goods_receipt_id, "goods_receipt_id"),
        (args.shipment_item_id, "shipment_item_id"),
    ):
        if value is not None:
            predicates.append(f"{column}=?")
            parameters.append(value)
    if args.query is not None:
        if text is None:
            raise ValueError(f"query is not supported for {args.entity}")
        predicates.append(f"{text} LIKE ? ESCAPE '\\'")
        parameters.append(
            "%" + args.query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
    where = " WHERE " + " AND ".join(predicates) if predicates else ""
    total, _ = query(
        context,
        "count:" + args.entity,
        f"SELECT COUNT(*) AS total FROM ({sql}{where})",
        parameters,
        permission,
    )
    cursor_where = where + (" AND " if where else " WHERE ") + "id>?"
    rows, evidence = query(
        context,
        "list:" + args.entity,
        sql + cursor_where + " ORDER BY id LIMIT ?",
        [*parameters, args.after, args.limit + 1],
        permission,
    )
    more = len(rows) > args.limit
    rows = rows[: args.limit]
    return ToolResult(
        status="ok" if rows else "empty",
        integration="simulated_company_sqlite",
        records=[
            Record(entity=args.entity, id=row["id"], fields=money_display(row)) for row in rows
        ],
        sources=[SourceRef(kind="query", id=evidence)],
        page=Page(
            returned=len(rows),
            total=total[0]["total"],
            has_more=more,
            next_cursor=rows[-1]["id"] if more else None,
        ),
        facts=(
            {"source_invoice_no_note": ORDER_REFERENCE_NOTE} if args.entity == "orders"
            else {"purchase_provenance_note": PURCHASE_REFERENCE_NOTE}
            if args.entity == "purchase_orders" else {}
        ),
    )


def business_summary(context, args):
    ranking = args.report == "customer_orders"
    range_sources = []
    earliest = None
    if ranking and (not args.start_date or not args.end_date):
        span, evidence = query(
            context,
            "customer_order_history_start",
            "SELECT MIN(ordered_at) AS first_order,MAX(ordered_at) AS last_order FROM orders",
            (),
            "commercial.read",
        )
        earliest = span[0]["first_order"]
        if earliest is None:
            raise ValueError("No company orders are available")
        range_sources.append(SourceRef(kind="query", id=evidence))
    args = args.model_copy(
        update={
            "start_date": args.start_date or earliest or "2011-11-01",
            "end_date": args.end_date
            or (max(AS_OF, span[0]["last_order"]) if ranking else "2011-11-30"),
        }
    )
    start, end = date.fromisoformat(args.start_date), date.fromisoformat(args.end_date)
    if start > end or end > date.today():
        raise ValueError("Use an ordered date range ending no later than today")
    if ranking:
        rows, evidence = query(
            context,
            "customer_order_ranking",
            "SELECT c.id,c.name,COUNT(*) AS order_count FROM orders o "
            "JOIN customers c ON c.id=o.customer_id "
            "WHERE substr(o.ordered_at,1,10) BETWEEN ? AND ? "
            "AND (? IS NULL OR c.id=?) GROUP BY c.id,c.name "
            "ORDER BY order_count DESC,c.id LIMIT 10",
            (args.start_date, args.end_date, args.customer_id, args.customer_id),
            "commercial.read",
        )
        return result(
            records=[Record(entity="customers", id=row["id"], fields=row) for row in rows],
            sources=[*range_sources, SourceRef(kind="query", id=evidence)],
            facts={
                "start_date": args.start_date,
                "end_date": args.end_date,
                "metric": "count of company orders, including every status",
                "scope": "all matching orders; top 10 customers; ties ordered by customer ID",
            },
        )
    if args.report in {"sales", "receivables"}:
        permission = "analytics.read" if args.report == "sales" else "finance.read"
        sql = (
            "SELECT COUNT(*) AS invoice_count,COALESCE(SUM(i.total_pence),0) AS invoiced_pence,"
            "COALESCE(SUM(i.outstanding_pence),0) AS outstanding_pence "
            "FROM invoice_balances i JOIN orders o ON o.id=i.order_id "
            "WHERE i.posted_on BETWEEN ? AND ? AND (? IS NULL OR o.customer_id=?)"
        )
        if args.report == "sales":
            sql = (
                "SELECT COUNT(*) AS invoice_count,COALESCE(SUM(i.total_pence-"
                "COALESCE((SELECT SUM(amount_pence) FROM credit_notes c "
                "WHERE c.invoice_id=i.id),0)),0) "
                "AS sales_pence FROM invoices i JOIN orders o ON o.id=i.order_id "
                "WHERE i.posted_on BETWEEN ? AND ? AND (? IS NULL OR o.customer_id=?)"
            )
        rows, evidence = query(
            context,
            args.report,
            sql,
            (args.start_date, args.end_date, args.customer_id, args.customer_id),
            permission,
        )
        facts = {
            **rows[0],
            "currency": "GBP",
            "start_date": args.start_date,
            "end_date": args.end_date,
            "basis": "invoice cohort less related credits within the selected date range",
            "historical_source_reference": AS_OF,
        }
    else:
        if not args.forecast_id:
            raise ValueError("forecast_id is required for a forecast summary")
        today = date.today().isoformat()
        rows, evidence = query(
            context,
            "forecast_summary",
            "SELECT f.id,f.product_id,f.units,r.id AS run_id,r.training_cutoff,"
            "r.target_start,r.target_end,"
            "COALESCE((SELECT SUM(ii.quantity) FROM invoice_items ii "
            "JOIN invoices i ON i.id=ii.invoice_id "
            "JOIN order_items oi ON oi.id=ii.order_item_id WHERE oi.product_id=f.product_id "
            "AND i.posted_on BETWEEN r.target_start AND r.target_end "
            "AND i.posted_on <= CASE WHEN substr(r.target_end,1,4)='2011' "
            "THEN ? ELSE ? END),0) AS actual_units "
            "FROM forecasts f JOIN forecast_runs r ON r.id=f.run_id WHERE f.id=?",
            (AS_OF, today, args.forecast_id),
            "analytics.read",
        )
        if not rows:
            return ToolResult(
                status="empty", integration="simulated_company_sqlite", facts={"found": False}
            )
        facts = rows[0]
        reference = AS_OF if facts["target_end"][:4] == "2011" else today
        facts["period_complete"] = facts["target_end"] <= reference
        facts["business_reference"] = reference
        facts["observed_through"] = min(facts["target_end"], reference)
        facts["actual_units_basis"] = (
            "completed target period" if facts["period_complete"] else "partial period to date"
        )
        facts["error_units"] = (
            facts["actual_units"] - facts["units"] if facts["period_complete"] else None
        )
        facts["error_percent"] = (
            str(Decimal(facts["error_units"]) * 100 / facts["units"])
            if facts["period_complete"] and facts["units"]
            else None
        )
    return result(sources=[SourceRef(kind="query", id=evidence)], facts=facts)


def cash_activity(context, args):
    """Trace fixed SQL behind the same dated money measures as portal Insights."""
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    validate_period(start, end, args.cohort)
    cohort_sql = "LIKE" if args.cohort == "contemporary" else "NOT LIKE"
    start_text, end_text = start.isoformat(), end.isoformat()
    sources = []

    def total(label, sql):
        rows, evidence = query(
            context, label, sql, (start_text, end_text), "finance.read"
        )
        sources.append(SourceRef(kind="query", id=evidence))
        return rows[0]

    billed = total(
        "cash_activity:invoices",
        "SELECT COUNT(*) AS invoice_count,COALESCE(SUM(i.total_pence),0) "
        "AS gross_billed_pence,COALESCE(SUM(i.outstanding_pence),0) "
        "AS current_outstanding_for_invoice_cohort_pence "
        "FROM invoice_balances i WHERE i.posted_on BETWEEN ? AND ? "
        f"AND i.provenance {cohort_sql} 'fictional_contemporary_%'",
    )
    credits = total(
        "cash_activity:credits",
        "SELECT COALESCE(SUM(c.amount_pence),0) AS credits_issued_pence "
        "FROM credit_notes c WHERE c.issued_on BETWEEN ? AND ? "
        f"AND c.provenance {cohort_sql} 'fictional_contemporary_%'",
    )
    received = total(
        "cash_activity:payments",
        "SELECT COUNT(*) AS payment_count,COALESCE(SUM(p.amount_pence),0) "
        "AS customer_cash_received_pence FROM payments p "
        "WHERE p.received_on BETWEEN ? AND ? "
        f"AND p.provenance {cohort_sql} 'fictional_contemporary_%'",
    )
    expense_count = cash_outflow = cash_difference = None
    category_records = []
    ledger_available = False
    if args.cohort == "contemporary":
        available, evidence = query(
            context, "cash_activity:ledger_available",
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='company_expenses'",
            (), "finance.read",
        )
        sources.append(SourceRef(kind="query", id=evidence))
        ledger_available = bool(available)
        if ledger_available:
            expenses = total(
                "cash_activity:expenses",
                "SELECT COUNT(*) AS expense_count,COALESCE(SUM(amount_pence),0) "
                "AS recorded_cash_outflow_pence FROM company_expenses "
                "WHERE paid_on BETWEEN ? AND ?",
            )
            expense_count = expenses["expense_count"]
            cash_outflow = expenses["recorded_cash_outflow_pence"]
            cash_difference = received["customer_cash_received_pence"] - cash_outflow
            categories, evidence = query(
                context, "cash_activity:expense_categories",
                "SELECT category,COUNT(*) AS expense_count,SUM(amount_pence) "
                "AS amount_pence FROM company_expenses WHERE paid_on BETWEEN ? AND ? "
                "GROUP BY category ORDER BY amount_pence DESC,category",
                (start_text, end_text), "finance.read",
            )
            sources.append(SourceRef(kind="query", id=evidence))
            category_records = [
                Record(
                    entity="expense_category", id=row["category"],
                    fields=money_display({
                        "expense_count": row["expense_count"],
                        "amount_pence": row["amount_pence"],
                    }),
                ) for row in categories
            ]
    return result(
        records=category_records,
        sources=sources,
        facts={
            "cohort": args.cohort,
            "start_date": start_text,
            "end_date": end_text,
            "currency": "GBP",
            "invoice_count": billed["invoice_count"],
            "gross_billed_pence": billed["gross_billed_pence"],
            "credits_issued_pence": credits["credits_issued_pence"],
            "net_billing_activity_pence": (
                billed["gross_billed_pence"] - credits["credits_issued_pence"]
            ),
            "payment_count": received["payment_count"],
            "customer_cash_received_pence": received["customer_cash_received_pence"],
            "current_outstanding_for_invoice_cohort_pence": (
                billed["current_outstanding_for_invoice_cohort_pence"]
            ),
            "expense_ledger_available": ledger_available,
            "expense_count": expense_count,
            "recorded_cash_outflow_pence": cash_outflow,
            "recorded_cash_difference_pence": cash_difference,
            "measure_note": (
                "Net billing is dated invoice postings less dated credits. "
                "Contemporary customer receipts are authored fictional scenario "
                "events. Historical customer remittances are modeled from source-era "
                "patterns. Neither is observed bank evidence. "
                "Outstanding is the current balance for invoices posted in this period. "
                "The authored 2026 expense ledger is incomplete; recorded cash "
                "difference is not company profit. Historical outflows are unavailable."
            ),
        },
    )


def document_root(context):
    revised = context.state / "documents"
    return revised if (revised / "installed.json").is_file() else context.data / "documents"


def accessible_documents(context, effective_on=None):
    actor = authorize(context)
    portal_kind = kind_for_actor(context.state, actor["id"])
    customer_id = (
        persona(context.project, context.state, context.session_token)["subject_id"]
        if portal_kind == "customer"
        else None
    )
    catalog = json.loads((document_root(context) / "catalog.json").read_text("utf-8"))["documents"]
    permitted = [
        doc
        for doc in catalog
        if (
            (
                portal_kind == "customer"
                and (
                    (doc["category"] == "policies" and doc["access_scope"] == "general")
                    or (
                        doc["category"] == "customer_terms"
                        and doc["record_links"].get("customer_id") == customer_id
                    )
                )
            )
            or (
                portal_kind != "customer"
                and f"documents.{doc['access_scope']}" in actor["permissions"]
            )
        )
        and (
            effective_on is None
            or (
                doc["effective_from"] <= effective_on
                and (doc["effective_until"] is None or doc["effective_until"] >= effective_on)
            )
        )
    ]
    if effective_on is None:
        return permitted
    # A correction may supersede a document on the same calendar day. The
    # register keeps both versions; date-based reading chooses the highest one.
    latest = {}
    for doc in permitted:
        older = latest.get(doc["document_id"])
        if older is None or doc["version"] > older["version"]:
            latest[doc["document_id"]] = doc
    return list(latest.values())


def document_body(context, doc):
    root = document_root(context)
    path = (root / doc["relative_path"]).resolve()
    if not path.is_relative_to((root / "content").resolve()):
        raise ValueError("Document path outside corpus")
    if hashlib.sha256(path.read_bytes()).hexdigest() != doc["sha256"]:
        raise ValueError("Document content differs from its fixed catalog")
    return metadata_and_body(path)[1]


def search_documents(context, args):
    date.fromisoformat(args.effective_on)
    tokens = sorted(set(re.findall(r"[a-z0-9]+", args.query.lower())))
    if not tokens:
        raise ValueError("Search must contain letters or numbers")
    record_mention = (
        re.compile(
            rf"(?<![a-z0-9_-]){re.escape(args.mentions_record_id)}(?![a-z0-9_-])",
            re.IGNORECASE,
        )
        if args.mentions_record_id is not None
        else None
    )
    matches = []
    for doc in accessible_documents(context, args.effective_on):
        body = document_body(context, doc)
        if record_mention is not None and not record_mention.search(body):
            continue
        words = re.findall(r"[a-z0-9]+", body.lower())
        title = set(re.findall(r"[a-z0-9]+", doc["title"].lower()))
        score = sum(min(words.count(token), 5) + 4 * (token in title) for token in tokens)
        if score:
            first = min(
                (body.lower().find(token) for token in tokens if token in body.lower()), default=0
            )
            excerpt = body[max(0, first - 80) : max(0, first - 80) + 600]
            matches.append((score, doc, excerpt))
    matches.sort(key=lambda row: (-row[0], row[1]["document_id"], row[1]["version"]))
    selected = matches[args.offset : args.offset + args.limit]
    event(
        context,
        "retrieval",
        {
            "integration": "mock_rag_text_search",
            "query": args.query,
            "mentions_record_id": args.mentions_record_id,
            "effective_on": args.effective_on,
            "ranking": "token frequency capped at 5 + title bonus 4",
            "matched_permitted_documents": len(matches),
            "returned_versions": [f"{d['document_id']}:v{d['version']}" for _, d, _ in selected],
        },
    )
    more = args.offset + len(selected) < len(matches)
    return ToolResult(
        status="ok" if selected else "empty",
        integration="mock_rag_text_search",
        records=[
            Record(
                entity="document",
                id=doc["document_id"],
                fields={
                    "title": doc["title"],
                    "version": doc["version"],
                    "excerpt": excerpt,
                    "score": score,
                    "effective_from": doc["effective_from"],
                    "effective_until": doc["effective_until"],
                    "access_scope": doc["access_scope"],
                },
            )
            for score, doc, excerpt in selected
        ],
        sources=[
            SourceRef(kind="document", id=doc["document_id"], version=doc["version"])
            for _, doc, _ in selected
        ],
        page=Page(
            returned=len(selected),
            total=len(matches),
            has_more=more,
            next_cursor=args.offset + len(selected) if more else None,
        ),
    )


def read_document(context, args):
    doc = next(
        (
            d
            for d in accessible_documents(context)
            if d["document_id"] == args.document_id and d["version"] == args.version
        ),
        None,
    )
    if doc is None:
        raise AccessDenied("Document version unavailable to this account")
    body = document_body(context, doc)
    excerpt = body[args.offset : args.offset + args.max_chars]
    more = args.offset + len(excerpt) < len(body)
    event(
        context,
        "document_read",
        {
            "integration": "mock_rag_text_search",
            "document_id": args.document_id,
            "version": args.version,
            "offset": args.offset,
            "returned_chars": len(excerpt),
        },
    )
    return ToolResult(
        status="ok" if excerpt else "empty",
        integration="mock_rag_text_search",
        records=[
            Record(
                entity="document",
                id=args.document_id,
                fields={
                    "version": args.version,
                    "title": doc["title"],
                    "content": excerpt,
                    "status": doc["status"],
                    "effective_from": doc["effective_from"],
                    "effective_until": doc["effective_until"],
                },
            )
        ],
        sources=[SourceRef(kind="document", id=args.document_id, version=args.version)],
        page=Page(
            returned=len(excerpt),
            total=len(body),
            has_more=more,
            next_cursor=args.offset + len(excerpt) if more else None,
        ),
    )


def list_document_versions(context, args):
    """List only metadata of versions this selected persona may already read."""
    versions = sorted(
        (
            doc for doc in accessible_documents(context)
            if doc["document_id"] == args.document_id
        ),
        key=lambda doc: doc["version"],
    )
    if not versions:
        raise AccessDenied("Document versions unavailable to this account")
    selected = versions[args.offset : args.offset + args.limit]
    event(
        context,
        "document_versions_listed",
        {
            "document_id": args.document_id,
            "offset": args.offset,
            "returned_versions": [doc["version"] for doc in selected],
            "total_accessible_versions": len(versions),
        },
    )
    more = args.offset + len(selected) < len(versions)
    return ToolResult(
        status="ok" if selected else "empty",
        integration="mock_rag_text_search",
        records=[
            Record(
                entity="document_version",
                id=f"{doc['document_id']}:v{doc['version']}",
                fields={
                    "document_id": doc["document_id"],
                    "version": doc["version"],
                    "title": doc["title"],
                    "status": doc["status"],
                    "effective_from": doc["effective_from"],
                    "effective_until": doc["effective_until"],
                    "access_scope": doc["access_scope"],
                },
            )
            for doc in selected
        ],
        page=Page(
            returned=len(selected),
            total=len(versions),
            has_more=more,
            next_cursor=args.offset + len(selected) if more else None,
        ),
        facts={
            "basis": "authorized document catalog metadata only; bodies not read",
            "same_day_order": "version number orders revisions sharing an effective date",
        },
    )


def run_analysis(context, args):
    with localcontext() as arithmetic:
        arithmetic.prec = 50
        return _run_analysis(context, args)


def _run_analysis(context, args):
    authorize(context)
    if any(len(value) > 40 for value in args.values):
        raise ValueError("Each decimal operand is limited to 40 characters")
    values = [Decimal(value) for value in args.values]
    if any(
        not value.is_finite() or abs(value) > Decimal("1e15") or value.as_tuple().exponent < -12
        for value in values
    ):
        raise ValueError("Use finite decimals within 1e15 and at most 12 fractional places")
    if args.operation == "sum":
        answer = sum(values)
    else:
        if len(values) != 2:
            raise ValueError("This operation needs exactly two values")
        before, after = values
        answer = (
            before - after
            if args.operation in {"difference", "available_stock"}
            else ((after - before) * 100 / before if before else None)
        )
    return ToolResult(
        status="ok",
        integration="local_analysis",
        facts={
            "value": str(answer) if answer is not None else None,
            "defined": answer is not None,
            "operation": args.operation,
        },
    )


def validate_sources(context, sources):
    for source in sources:
        if source.kind == "record":
            if source.entity not in QUERIES:
                raise ValueError("Unknown source entity")
            args = INPUTS["lookup_record"](entity=source.entity, record_id=source.id)
            if lookup(context, args).status == "empty":
                raise ValueError("Report source record is absent")
        elif source.kind == "document":
            if source.version is None:
                raise ValueError("A document source needs its exact version")
            doc = next(
                (
                    d
                    for d in accessible_documents(context)
                    if d["document_id"] == source.id and d["version"] == source.version
                ),
                None,
            )
            if doc is None:
                raise AccessDenied("Report document unavailable")
            document_body(context, doc)
        else:
            db = connect(context.state / "events.sqlite", readonly=True)
            try:
                row = db.execute(
                    "SELECT payload_json FROM events WHERE id=? AND thread_id=? AND kind='sql'",
                    (source.id, context.thread_id),
                ).fetchone()
            finally:
                db.close()
            if row is None:
                raise AccessDenied("Query source unavailable in this conversation")
            authorize(context, json.loads(row[0])["permission"])


def propose(context, kind, args):
    actor = proposal_actor(context, kind)
    payload = json_text(args.model_dump())
    key = json_text([context.thread_id, context.run_id, kind, payload])
    identifier = "op-" + hashlib.sha256(key.encode()).hexdigest()[:32]
    db = connect(context.state / "app.sqlite", readonly=True)
    try:
        existing = db.execute(
            "SELECT status FROM operations WHERE id=? AND thread_id=? AND owner_id=?",
            (identifier, context.thread_id, actor["id"]),
        ).fetchone()
    finally:
        db.close()
    if existing:
        return proposal_result(identifier, kind, existing["status"])
    if kind == "save_report":
        validate_sources(context, args.sources)
    elif kind == "update_ticket":
        rows, _ = query(
            context,
            "ticket_proposal",
            "SELECT id,status FROM tickets WHERE id=?",
            (args.ticket_id,),
            "support.read",
        )
        if not rows or rows[0]["status"] != args.expected_status:
            raise ValueError("Ticket missing or expected status changed")
    else:
        validate_delete_target(context, args)
    db = connect(context.state / "app.sqlite")
    try:
        db.execute(
            "INSERT OR IGNORE INTO operations VALUES(?,?,?,?,?,?,'pending',?,NULL,NULL)",
            (identifier, context.thread_id, actor["id"], context.run_id, kind, payload, now()),
        )
        row = db.execute(
            "SELECT status,result_json FROM operations WHERE id=?", (identifier,)
        ).fetchone()
        db.commit()
    finally:
        db.close()
    event(
        context,
        "approval_requested",
        {
            "operation_id": identifier,
            "kind": kind,
            "arguments": args.model_dump(),
            "status": row["status"],
        },
    )
    return proposal_result(identifier, kind, row["status"])


def proposal_result(identifier, kind, status):
    return ToolResult(
        status="pending_approval" if status == "pending" else "ok",
        integration="local_report_store" if kind == "save_report" else "simulated_company_sqlite",
        operation_id=identifier,
        facts={
            "operation_status": status,
            "saved": status == "approved" and kind != "simulate_delete",
            "deleted": False,
            "simulation": kind == "simulate_delete",
        },
    )


def proposal_actor(context, kind):
    if kind == "save_report":
        return authorize(context, "report.save")
    if kind == "update_ticket":
        return authorize(context, "support.update")
    if kind == "simulate_delete":
        actor = authorize(context)
        if actor["access_profile"] not in {"super_user", "admin"}:
            raise AccessDenied("Select the superuser persona for deletion simulations")
        return actor
    raise ValueError("Unknown proposal kind")


def validate_delete_target(context, args):
    """Check a target exists using read-only paths; never execute a DELETE."""
    if args.target_kind == "record":
        if not args.entity or not args.record_id or args.document_id or args.version:
            raise ValueError("Record simulation needs entity and record_id only")
        permission, sql, _, _, _ = QUERIES[args.entity]
        rows, _ = query(
            context, "simulated_delete_preview", sql + " WHERE id=?", (args.record_id,), permission
        )
        if not rows:
            raise ValueError("Target record not found")
    else:
        if not args.document_id or args.version is None or args.entity or args.record_id:
            raise ValueError("Document simulation needs document_id and version only")
        item = next(
            (
                doc
                for doc in accessible_documents(context)
                if doc["document_id"] == args.document_id and doc["version"] == args.version
            ),
            None,
        )
        if item is None:
            raise ValueError("Target document version not found")
        document_body(context, item)


def inspect_operation(context, operation_id):
    actor = authorize(context)
    db = connect(context.state / "app.sqlite", readonly=True)
    try:
        row = db.execute(
            "SELECT * FROM operations WHERE id=? AND thread_id=? AND owner_id=?",
            (operation_id, context.thread_id, actor["id"]),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise AccessDenied("Operation unavailable")
    return dict(row)


def decide(context, operation_id, decision, edited_arguments=None):
    row = inspect_operation(context, operation_id)
    origin = replace(
        context, run_id=row["run_id"], execution_id=context.execution_id or context.run_id
    )
    with span(
        origin,
        "approval",
        {"operation_id": operation_id, "decision": decision, "origin_run_id": row["run_id"]},
    ):
        return _decide(origin, operation_id, decision, edited_arguments)


def _decide(context, operation_id, decision, edited_arguments=None):
    """Authenticated application endpoint, intentionally NOT a model tool."""
    if decision not in {"approve", "reject"}:
        raise ValueError("Decision must be approve or reject")
    if edited_arguments is not None and decision != "approve":
        raise ValueError("Edits apply only to an approval")
    if edited_arguments is not None and len(json_text(edited_arguments).encode()) > 32000:
        raise ValueError("Edited arguments exceed 32000 bytes")
    with execution_lock(context.state):
        row = inspect_operation(context, operation_id)
        proposal_actor(context, row["kind"])
        if row["status"] != "pending":
            event(
                context,
                "approval_replayed",
                {"operation_id": operation_id, "stored_status": row["status"]},
            )
            return json.loads(row["result_json"])
        original = json.loads(row["payload_json"])
        args = INPUTS[row["kind"]].model_validate(
            original if edited_arguments is None else edited_arguments
        )
        if decision == "approve" and row["kind"] == "save_report":
            validate_sources(context, args.sources)
        if decision == "approve" and row["kind"] == "simulate_delete":
            validate_delete_target(context, args)
        db = connect(context.state / "app.sqlite")
        try:
            db.execute(
                "ATTACH DATABASE ? AS company", (str((context.state / "company.sqlite").resolve()),)
            )
            db.execute("BEGIN IMMEDIATE")
            outcome = {
                "operation_id": operation_id,
                "decision": decision,
                "saved": False,
                "original_arguments": original,
                "decided_arguments": args.model_dump(),
                "edited": original != args.model_dump(),
            }
            if decision == "approve":
                if row["kind"] == "save_report":
                    report_id = "report-" + operation_id[3:]
                    db.execute(
                        "INSERT INTO reports VALUES(?,?,?,?,?,?,?,?)",
                        (
                            report_id,
                            operation_id,
                            context.thread_id,
                            row["owner_id"],
                            args.title,
                            args.body,
                            json_text([s.model_dump() for s in args.sources]),
                            now(),
                        ),
                    )
                    outcome.update(saved=True, report_id=report_id)
                elif row["kind"] == "update_ticket":
                    changed = db.execute(
                        "UPDATE company.tickets SET status=? WHERE id=? AND status=?",
                        (args.new_status, args.ticket_id, args.expected_status),
                    ).rowcount
                    if changed != 1:
                        raise ValueError("Ticket changed since proposal; request a fresh proposal")
                    db.execute(
                        "INSERT INTO company.ticket_events VALUES(?,?,?,?,?)",
                        (operation_id, args.ticket_id, "2011-12-09", args.new_status, args.reason),
                    )
                    outcome.update(saved=True, ticket_id=args.ticket_id, status=args.new_status)
                else:
                    outcome.update(
                        simulated=True,
                        deleted=False,
                        target_kind=args.target_kind,
                        target_id=args.record_id or args.document_id,
                    )
            db.execute(
                "UPDATE operations SET status=?,decided_at=?,result_json=? WHERE id=?",
                (
                    "approved" if decision == "approve" else "rejected",
                    now(),
                    json_text(outcome),
                    operation_id,
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        event(context, "business_decision", outcome)
        if outcome.get("simulated"):
            event(context, "deletion_simulated", outcome)
        return outcome


def read_report(context, report_id):
    actor = authorize(context)
    db = connect(context.state / "app.sqlite", readonly=True)
    try:
        row = db.execute(
            "SELECT * FROM reports WHERE id=? AND owner_id=? AND thread_id=?",
            (report_id, actor["id"], context.thread_id),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        raise AccessDenied("Report unavailable")
    validate_sources(
        context, [SourceRef.model_validate(s) for s in json.loads(row["sources_json"])]
    )
    return dict(row)


def execute(context, name, arguments):
    # Direct calls and native ToolNode calls share the same observable service boundary.
    try:
        authorize(context)
    except (AccessDenied, ValueError):
        return _execute(context, name, arguments)
    with span(context, "tool", {"tool": name}):
        output = _execute(context, name, arguments)
        if output["status"] == "error":
            event(context, "tool_error", {"tool": name, "error": output["error"]})
        return output


def _execute(context, name, arguments):
    """One validation/authorization boundary for direct tests and model tool calls."""
    logged_arguments = arguments
    try:
        authorize(context)
        argument_bytes = len(json_text(arguments).encode())
        if argument_bytes > 32000:
            logged_arguments = {"omitted": "input exceeds 32000 bytes", "bytes": argument_bytes}
            raise ValueError("Tool arguments must not exceed 32000 bytes")
        if name not in INPUTS:
            raise ValueError("Unknown tool")
        args = INPUTS[name].model_validate(arguments)
        handlers = {
            "lookup_record": lookup,
            "list_records": list_records,
            "business_summary": business_summary,
            "cash_activity": cash_activity,
            "search_documents": search_documents,
            "list_document_versions": list_document_versions,
            "read_document": read_document,
            "run_analysis": run_analysis,
        }
        output = (
            propose(context, name, args)
            if name in {"save_report", "update_ticket", "simulate_delete"}
            else handlers[name](context, args)
        )
    except (AccessDenied, ValueError, InvalidOperation, sqlite3.Error) as exc:
        code = (
            "access_denied"
            if isinstance(exc, AccessDenied)
            else "data_error"
            if isinstance(exc, sqlite3.Error)
            else "invalid_arguments"
        )
        message = (
            "Invalid tool arguments; inspect the tool schema"
            if isinstance(exc, ValidationError)
            else str(exc)[:300]
        )
        output = ToolResult(
            status="error",
            integration="simulated_company_sqlite",
            error=ToolError(code=code, message=message),
        )
    if len(output.model_dump_json().encode()) > MAX_RESULT_BYTES:
        output = ToolResult(
            status="error",
            integration="simulated_company_sqlite",
            error=ToolError(code="too_large", message="Use a smaller page or excerpt"),
        )
    # Do not create private events for an unauthenticated or cross-owner request.
    try:
        authorize(context)
    except (AccessDenied, ValueError):
        return output.model_dump()
    event(
        context,
        "tool_result",
        {"tool": name, "arguments": logged_arguments, "result": output.model_dump()},
    )
    return output.model_dump()
