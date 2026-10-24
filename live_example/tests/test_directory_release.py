"""Check the date boundary for account terms in portable and local runs."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from acme.company_tools import accessible_documents
from acme.document_revision import audit_revision_bundle

PROJECT = Path(__file__).resolve().parents[1]
BUNDLE = PROJECT / "artifacts/directory-release-2026-r2/documents"


class DirectoryReleaseTests(unittest.TestCase):
    def test_date_based_account_terms_choose_newest_eligible_version(self):
        versions = [
            {
                "document_id": "TERMS-2026-TEST",
                "version": version,
                "category": "customer_terms",
                "access_scope": "general",
                "record_links": {"customer_id": "SCN-CUST-TEST"},
                "effective_from": start,
                "effective_until": end,
            }
            for version, start, end in (
                (1, "2026-10-20", "2026-10-20"),
                (2, "2026-10-21", "2026-10-21"),
                (3, "2026-10-21", None),
            )
        ]
        context = SimpleNamespace(state=PROJECT / "state")
        actor = {"id": "EMP-003", "permissions": {"documents.general"}}
        with (
            patch("acme.company_tools.authorize", return_value=actor),
            patch("acme.company_tools.kind_for_actor", return_value="employee"),
            patch("acme.company_tools.document_root", return_value=PROJECT),
            patch("pathlib.Path.read_text", return_value=json.dumps({"documents": versions})),
        ):
            before = accessible_documents(context, "2026-10-20")
            after = accessible_documents(context, "2026-10-21")
        self.assertEqual([doc["version"] for doc in before], [1])
        self.assertEqual([doc["version"] for doc in after], [3])

    def test_prepared_bundle_when_present(self):
        if not BUNDLE.is_dir():
            self.skipTest("Optional local release artifact is absent")
        self.assertEqual(audit_revision_bundle(BUNDLE)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
