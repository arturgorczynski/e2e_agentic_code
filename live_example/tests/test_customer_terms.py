"""Current account terms must be chosen for the server-bound customer."""

import unittest
from unittest.mock import patch

from acme.customer_tools import current_terms


class CustomerTermsTests(unittest.TestCase):
    def test_reads_only_the_selected_customers_current_version(self):
        own = {
            "category": "customer_terms",
            "record_links": {"customer_id": "CUST-1"},
            "document_id": "TERMS-CUST-1",
            "version": 3,
        }
        other = {
            "category": "customer_terms",
            "record_links": {"customer_id": "CUST-2"},
            "document_id": "TERMS-CUST-2",
            "version": 7,
        }
        context = object()
        with (
            patch("acme.customer_tools._customer", return_value="CUST-1"),
            patch("acme.customer_tools.accessible_documents", return_value=[other, own]) as docs,
            patch("acme.customer_tools.execute", return_value={"status": "ok"}) as read,
            patch("acme.customer_tools.event"),
        ):
            result = current_terms(context)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(docs.call_args.args[0], context)
        self.assertRegex(docs.call_args.args[1], r"^\d{4}-\d{2}-\d{2}$")
        read.assert_called_once_with(
            context,
            "read_document",
            {"document_id": "TERMS-CUST-1", "version": 3, "max_chars": 6000},
        )

    def test_account_without_current_terms_reports_empty_without_opening_another_document(self):
        with (
            patch("acme.customer_tools._customer", return_value="CUST-1"),
            patch("acme.customer_tools.accessible_documents", return_value=[]),
            patch("acme.customer_tools.execute") as read,
            patch("acme.customer_tools.event"),
        ):
            result = current_terms(object())
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["records"], [])
        read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
