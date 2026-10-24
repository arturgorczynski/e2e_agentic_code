"""Check the new authored corpus against the shipped catalog and access rules."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from acme.company_tools import accessible_documents, document_body
from acme.dataset import baseline_manifest

PROJECT = Path(__file__).resolve().parents[1]
NEW_IDS = {
    "FIN-YTD-2011",
    "FIN-RECEIVABLES-2011",
    "FIN-CASH-2011",
    "SCI-FORECAST-2011",
    "SCI-STOCK-2011",
    "SCI-QUALITY-2011",
}


class RagCorpusTests(unittest.TestCase):
    def setUp(self):
        self.context = SimpleNamespace(
            project=PROJECT,
            data=PROJECT / "data",
            state=PROJECT / "state",
            session_token="test-token",
        )

    def test_new_versions_have_verified_bodies_and_baseline_manifest(self):
        baseline_manifest(PROJECT / "data")
        catalog = json.loads((PROJECT / "data/documents/catalog.json").read_text("utf-8"))
        selected = [doc for doc in catalog["documents"] if doc["document_id"] in NEW_IDS]
        self.assertEqual({doc["document_id"] for doc in selected}, NEW_IDS)
        self.assertTrue(all(doc["version"] == 1 for doc in selected))
        for doc in selected:
            with self.subTest(document=doc["document_id"]):
                body = document_body(self.context, doc)
                self.assertIn(doc["title"].split(":")[-1].split()[0].lower(), body.lower())
                self.assertGreater(len(body.split()), 400)

    def test_employee_scopes_filter_before_reading(self):
        cases = {
            "finance": (
                {"documents.finance"},
                {"FIN-YTD-2011", "FIN-RECEIVABLES-2011", "FIN-CASH-2011"},
            ),
            "analytics": ({"documents.analytics"}, {"SCI-FORECAST-2011"}),
            "operations": ({"documents.operations"}, {"SCI-STOCK-2011", "SCI-QUALITY-2011"}),
            "general": ({"documents.general"}, set()),
        }
        for label, (permissions, expected) in cases.items():
            with (
                self.subTest(role=label),
                patch(
                    "acme.company_tools.authorize",
                    return_value={"id": label, "permissions": permissions},
                ),
                patch("acme.company_tools.kind_for_actor", return_value="employee"),
            ):
                visible = accessible_documents(self.context, "2011-12-09")
                self.assertEqual({doc["document_id"] for doc in visible} & NEW_IDS, expected)

    def test_customer_cannot_retrieve_internal_reports(self):
        actor = {"id": "customer", "permissions": {"documents.general"}}
        with (
            patch("acme.company_tools.authorize", return_value=actor),
            patch("acme.company_tools.kind_for_actor", return_value="customer"),
            patch("acme.company_tools.persona", return_value={"subject_id": "CUST-1"}),
        ):
            visible = accessible_documents(self.context, "2011-12-09")
        self.assertFalse({doc["document_id"] for doc in visible} & NEW_IDS)


if __name__ == "__main__":
    unittest.main()
