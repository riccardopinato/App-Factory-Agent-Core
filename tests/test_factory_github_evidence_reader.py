"""GitHub PR/CI connector and v0.2 gateway composition tests (offline)."""
from datetime import datetime, timezone
import json
import unittest

from scripts.factory_github_evidence_reader import (
    GitHubEvidenceConnector, GitHubEvidenceReaderError
)
from scripts.factory_status_v02 import FactoryEvidenceGateway

REPO = "riccardopinato/App-Factory-Agent-Core"
SHA = "a" * 40
BASE = "b" * 40
NOW = datetime(2026, 11, 14, 3, tzinfo=timezone.utc)


class Fetch:
    def __init__(self):
        self.urls = []
        self.pr = {"number": 26, "draft": False, "state": "open",
                   "head": {"sha": SHA}, "base": {"sha": BASE,
                   "repo": {"full_name": REPO}},
                   "user": {"login": "test"}, "body": "UNTRUSTED_MARKDOWN"}
        self.ci = {"total_count": 2, "workflow_runs": [
            {"name": "CI", "id": 12, "head_sha": SHA, "status": "completed", "conclusion": "success"},
            {"name": "Source", "id": 13, "head_sha": SHA, "status": "completed", "conclusion": "success"},
        ]}

    def __call__(self, url):
        self.urls.append(url)
        return {"result": {"content": json.dumps(
            self.pr if "/pulls/" in url else self.ci)}}


class Store:
    def get_operation(self, operation_id):
        return {"operation_id": operation_id, "repository": REPO,
                "resolved_sha": SHA, "current_state": "QUEUED"}


class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.fetch = Fetch()
        self.read = GitHubEvidenceConnector(
            trusted_fetch=self.fetch, allowed_repositories=[REPO], now=lambda: NOW)

    def test_real_github_shape_composes_with_existing_gateway(self):
        gw = FactoryEvidenceGateway(
            allowed_repositories=[REPO],
            github_head_reader=lambda _: {},
            applab_store=Store(),
            trusted_pr_reader=self.read.read_pr,
            trusted_ci_reader=self.read.read_ci,
        )
        out = gw.pull_request_evidence(REPO, 26, expected_head_sha=SHA, now=NOW)
        self.assertEqual(out["ci_state"], "ALL_OBSERVED_CHECKS_SUCCESS")
        self.assertEqual(len(out["checks"]), 2)
        self.assertNotIn("UNTRUSTED_MARKDOWN", str(out))
        self.assertFalse(out["review_verified"])
        self.assertEqual(self.fetch.urls, [
            "https://api.github.com/repos/" + REPO + "/pulls/26",
            "https://api.github.com/repos/" + REPO +
            "/actions/runs?head_sha=" + SHA + "&event=pull_request&per_page=32",
        ])

    def test_host_allowlist_rejects_before_fetch(self):
        with self.assertRaisesRegex(GitHubEvidenceReaderError, "NOT_AUTHORIZED"):
            self.read.read_pr("unknown/unapproved", 26)
        self.assertEqual(self.fetch.urls, [])

    def test_pr_repo_forgery_rejected(self):
        self.fetch.pr["base"]["repo"]["full_name"] = "forged/repo"
        with self.assertRaisesRegex(GitHubEvidenceReaderError, "REPOSITORY_MISMATCH"):
            self.read.read_pr(REPO, 26)

    def test_ci_sha_forgery_and_truncation(self):
        self.fetch.ci["workflow_runs"][0]["head_sha"] = "f" * 40
        with self.assertRaisesRegex(GitHubEvidenceReaderError, "CI_SHA_MISMATCH"):
            self.read.read_ci(REPO, SHA)
        self.fetch.ci["workflow_runs"][0]["head_sha"] = SHA
        self.fetch.ci["total_count"] = 33
        with self.assertRaisesRegex(GitHubEvidenceReaderError, "CI_INCOMPLETE_OR_UNBOUNDED"):
            self.read.read_ci(REPO, SHA)

    def test_incomplete_run_page_within_limit_is_rejected(self):
        self.fetch.ci["total_count"] = 2
        self.fetch.ci["workflow_runs"] = self.fetch.ci["workflow_runs"][:1]
        with self.assertRaisesRegex(GitHubEvidenceReaderError, "CI_INCOMPLETE_OR_UNBOUNDED"):
            self.read.read_ci(REPO, SHA)

    def test_default_clocks_compose_without_future_error(self):
        adapter = GitHubEvidenceConnector(
            trusted_fetch=self.fetch, allowed_repositories=[REPO])
        gw = FactoryEvidenceGateway(
            allowed_repositories=[REPO], github_head_reader=lambda _: {},
            applab_store=Store(), trusted_pr_reader=adapter.read_pr,
            trusted_ci_reader=adapter.read_ci)
        out = gw.pull_request_evidence(REPO, 26)
        self.assertEqual(out["ci_state"], "ALL_OBSERVED_CHECKS_SUCCESS")

    def test_bad_provider_response_does_not_serialize_raw_payload(self):
        self.fetch.ci = {"total_count": 1, "workflow_runs": [
            {"name": "CI", "id": 1, "head_sha": "mismatch" }]}
        with self.assertRaisesRegex(GitHubEvidenceReaderError, "CI_SHA_MISMATCH"):
            self.read.read_ci(REPO, SHA)


if __name__ == "__main__":
    unittest.main()
