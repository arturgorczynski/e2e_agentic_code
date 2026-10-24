"""The model sees only record entities that its selected profile can query."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from acme.agent import (
    list_document_versions,
    list_records,
    lookup_record,
    my_invoice,
    my_invoices,
    my_orders,
    remember_note,
    search_documents,
)
from acme.company_queries import QUERIES
from acme.middleware import RuntimeContextMiddleware, scoped_record_tools


class ScopedRecordToolTests(unittest.TestCase):
    def test_read_only_customer_still_sees_owned_invoice_reads(self):
        request = SimpleNamespace(
            tools=[my_orders, my_invoices, my_invoice, remember_note],
            runtime=SimpleNamespace(context=object()),
            system_prompt="Customer assistant",
            override=lambda **changes: SimpleNamespace(**changes),
        )
        actor = {
            "id": "USR-CUSTOMER",
            "username": "sample-customer",
            "access_profile": "customer",
            "permissions": set(),
        }
        with patch("acme.middleware.authorize", return_value=actor), patch(
            "acme.middleware.event"
        ):
            offered = RuntimeContextMiddleware("read_only").wrap_model_call(
                request, lambda effective: [tool.name for tool in effective.tools]
            )
        self.assertEqual(offered, ["my_orders", "my_invoices", "my_invoice"])
        invoice_call = SimpleNamespace(
            tool_call={"name": "my_invoice", "id": "call-invoice"},
            runtime=SimpleNamespace(context=object()),
        )
        self.assertEqual(
            RuntimeContextMiddleware("read_only").wrap_tool_call(
                invoice_call, lambda _request: "executed"
            ),
            "executed",
        )
        write_call = SimpleNamespace(
            tool_call={"name": "remember_note", "id": "call-write"},
            runtime=SimpleNamespace(context=object()),
        )
        with patch("acme.middleware.event"):
            denied = RuntimeContextMiddleware("read_only").wrap_tool_call(
                write_call, lambda _request: self.fail("write handler must not run")
            )
        self.assertEqual(denied.status, "error")

    def test_read_only_agent_can_discover_document_revisions(self):
        request = SimpleNamespace(
            tools=[search_documents, list_document_versions, remember_note],
            runtime=SimpleNamespace(context=object()),
            system_prompt="Company assistant",
            override=lambda **changes: SimpleNamespace(**changes),
        )
        actor = {
            "id": "USR-EMPLOYEE",
            "username": "sample-employee",
            "access_profile": "employee",
            "permissions": {"commercial.read", "documents.general"},
        }
        with patch("acme.middleware.authorize", return_value=actor), patch(
            "acme.middleware.event"
        ):
            offered = RuntimeContextMiddleware("read_only").wrap_model_call(
                request, lambda effective: [tool.name for tool in effective.tools]
            )
        self.assertEqual(offered, ["search_documents", "list_document_versions"])

    def test_support_schema_excludes_finance_and_operations_without_mutating_tools(self):
        original = [lookup_record, list_records, search_documents]
        original_enum = lookup_record.tool_call_schema.model_json_schema()["properties"]["entity"][
            "enum"
        ]
        scoped, allowed = scoped_record_tools(original, {"commercial.read", "support.read"})
        expected = tuple(
            entity
            for entity, (permission, *_rest) in QUERIES.items()
            if permission in {"commercial.read", "support.read"}
        )
        self.assertEqual(allowed, expected)
        self.assertIs(scoped[2], search_documents)
        self.assertEqual(
            lookup_record.tool_call_schema.model_json_schema()["properties"]["entity"]["enum"],
            original_enum,
        )
        for tool in scoped[:2]:
            exposed = tool.tool_call_schema.model_json_schema()["properties"]["entity"]["enum"]
            self.assertEqual(exposed, list(expected))
            self.assertNotIn("invoices", exposed)
            self.assertNotIn("shipments", exposed)
            with self.assertRaises(ValidationError):
                tool.tool_call_schema.model_validate({"entity": "invoices", "record_id": "X"})

    def test_full_and_empty_scopes_keep_the_correct_tool_set(self):
        tools = [lookup_record, list_records, search_documents]
        all_permissions = {definition[0] for definition in QUERIES.values()}
        full, allowed = scoped_record_tools(tools, all_permissions)
        self.assertEqual(allowed, tuple(QUERIES))
        self.assertIs(full[0], lookup_record)
        self.assertIs(full[1], list_records)
        empty, allowed = scoped_record_tools(tools, set())
        self.assertEqual(allowed, ())
        self.assertEqual(empty, [search_documents])


if __name__ == "__main__":
    unittest.main()
