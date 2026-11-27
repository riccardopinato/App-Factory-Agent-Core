"""GitHub connector branch-reader tests: no network or credentials."""
import json
from datetime import datetime, timezone
import unittest

from scripts.factory_github_connector_reader import (
    GitHubConnectorHeadReader, GitHubConnectorReaderError,
)
from scripts.factory_readonly_gateway import FactoryReadOnlyGateway

REPO = "riccardopinato/AppLab"
SHA = "b" * 40
NOW = datetime(2026, 11, 14, 1, tzinfo=timezone.utc)


class FakeFetch:
    def __init__(self):
        self.urls = []
        self.response = {"result": {"content": json.dumps({
            "name": "main", "commit": {"sha": SHA, "url": "not a source of trust"}
        })}}
    def __call__(self, url):
        self.urls.append(url)
        return self.response


class Store:
    def get_operation(self, operation_id):
        return {"operation_id": operation_id, "repository": REPO,
                "resolved_sha": SHA, "current_state": "QUEUED"}


class ConnectorReaderTests(unittest.TestCase):
    def setUp(self):
        self.fetch = FakeFetch()
        self.reader = GitHubConnectorHeadReader(
            trusted_fetch=self.fetch, branches={REPO: "main"},
            now=lambda: NOW)

    def test_actual_connector_shape_and_gateway_integration(self):
        gateway = FactoryReadOnlyGateway(
            allowed_repositories=[REPO], github_head_reader=self.reader,
            applab_store=Store())
        result = gateway.repository_status(REPO, now=NOW)
        self.assertEqual(result["head_sha"], SHA)
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(self.fetch.urls,
                         ["https://api.github.com/repos/riccardopinato/AppLab/branches/main"])

    def test_real_default_clocks_do_not_reject_live_head_as_future(self):
        reader = GitHubConnectorHeadReader(
            trusted_fetch=self.fetch, branches={REPO: "main"})
        gateway = FactoryReadOnlyGateway(
            allowed_repositories=[REPO], github_head_reader=reader,
            applab_store=Store())
        result = gateway.repository_status(REPO)
        self.assertEqual(result["head_sha"], SHA)
        batch = gateway.repositories_status([REPO])
        self.assertEqual(batch["repositories"][0]["head_sha"], SHA)

    def test_unapproved_repo_does_not_invoke_connector(self):
        with self.assertRaisesRegex(GitHubConnectorReaderError, "NOT_AUTHORIZED"):
            self.reader("riccardopinato/Notes-Ecosistema")
        self.assertEqual(self.fetch.urls, [])

    def test_forged_ref_or_sha_rejected(self):
        self.fetch.response["result"]["content"] = json.dumps(
            {"name": "evil", "commit": {"sha": SHA}})
        with self.assertRaisesRegex(GitHubConnectorReaderError, "REF_MISMATCH"):
            self.reader(REPO)
        self.fetch.response["result"]["content"] = json.dumps(
            {"name": "main", "commit": {"sha": "a" * 39}})
        with self.assertRaisesRegex(GitHubConnectorReaderError, "SHA_INVALID"):
            self.reader(REPO)

    def test_invalid_provider_or_untrusted_branch_policy(self):
        for value in ["../evil", "main//bad", ".hidden/../main", "/main"]:
            with self.subTest(value=value):
                with self.assertRaisesRegex(GitHubConnectorReaderError, "INVALID_PINNED"):
                    GitHubConnectorHeadReader(
                        trusted_fetch=self.fetch, branches={REPO: value})
        with self.assertRaisesRegex(GitHubConnectorReaderError, "MISSING_TRUSTED_PROVIDER"):
            GitHubConnectorHeadReader(trusted_fetch=None, branches={REPO: "main"})

    def test_provider_failure_and_bad_shape(self):
        self.fetch.response = {"content": "{}"}
        with self.assertRaisesRegex(GitHubConnectorReaderError, "RESPONSE_INVALID"):
            self.reader(REPO)
        self.fetch.response = {"result": {"content": "not json"}}
        with self.assertRaisesRegex(GitHubConnectorReaderError, "JSON_INVALID"):
            self.reader(REPO)

    def test_branch_name_is_percent_encoded_not_url_controllable(self):
        fetch = FakeFetch()
        fetch.response = {"result": {"content": json.dumps({
            "name": "release/v1", "commit": {"sha": SHA}})}}
        reader = GitHubConnectorHeadReader(trusted_fetch=fetch,
                  branches={REPO: "release/v1"}, now=lambda: NOW)
        reader(REPO)
        self.assertEqual(fetch.urls, [
            "https://api.github.com/repos/riccardopinato/AppLab/branches/release%2Fv1"])


if __name__ == "__main__":
    unittest.main()
