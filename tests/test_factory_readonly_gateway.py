"""Offline negative controls for bounded factory status projection."""
from datetime import datetime, timezone, timedelta
import unittest

from scripts.factory_readonly_gateway import FactoryReadOnlyGateway, StatusGatewayError

REPO = "riccardopinato/AppLab"
OTHER = "riccardopinato/World-Days"
SHA = "a" * 40
NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
OP = "op-20261114-001"


class FakeStore:
    def __init__(self):
        self.calls = 0
        self.payload = {
            "operation_id": OP, "repository": REPO, "resolved_sha": SHA,
            "current_state": "QUEUED", "payload_json": "sensitive raw content",
            "access_token": "MUST_NEVER_LEAK",
        }

    def get_operation(self, key):
        self.calls += 1
        return dict(self.payload)


class FakeGithub:
    def __init__(self):
        self.calls = []
        self.result = {
            "authenticated": True, "repository": REPO,
            "head_sha": SHA, "observed_at": "2026-11-14T00:00:00+00:00",
            "secret": "MUST_NEVER_LEAK",
        }

    def __call__(self, repo):
        self.calls.append(repo)
        return dict(self.result)


class ReadOnlyGatewayTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGithub()
        self.store = FakeStore()
        self.gateway = FactoryReadOnlyGateway(
            allowed_repositories=[REPO], github_head_reader=self.gh,
            applab_store=self.store)

    def test_trusted_repo_source_identity_and_reporting(self):
        out = self.gateway.repository_status(REPO, now=NOW)
        self.assertEqual(out["head_sha"], SHA)
        self.assertFalse(out["ci_verified"])
        self.assertFalse(out["runtime_verified"])
        self.assertNotIn("secret", str(out))
        self.assertEqual(self.gh.calls, [REPO])

    def test_source_auth_and_sha_are_fail_closed(self):
        self.gh.result["authenticated"] = False
        with self.assertRaisesRegex(StatusGatewayError, "NOT_AUTHENTICATED"):
            self.gateway.repository_status(REPO, now=NOW)
        self.gh.result["authenticated"] = True
        self.gh.result["head_sha"] = "b" * 39
        with self.assertRaisesRegex(StatusGatewayError, "IDENTITY_MISMATCH"):
            self.gateway.repository_status(REPO, now=NOW)

    def test_stale_and_future_source_rejected(self):
        self.gh.result["observed_at"] = (NOW - timedelta(seconds=901)).isoformat()
        with self.assertRaisesRegex(StatusGatewayError, "STALE_OR_FUTURE"):
            self.gateway.repository_status(REPO, now=NOW)
        self.gh.result["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(StatusGatewayError, "STALE_OR_FUTURE"):
            self.gateway.repository_status(REPO, now=NOW)

    def test_batch_pre_admission_no_cross_repo_leak(self):
        with self.assertRaisesRegex(StatusGatewayError, "NOT_AUTHORIZED"):
            self.gateway.repositories_status([REPO, OTHER], now=NOW)
        self.assertEqual(self.gh.calls, [])
        with self.assertRaisesRegex(StatusGatewayError, "DUPLICATE_REPOSITORY"):
            self.gateway.repositories_status([REPO, REPO], now=NOW)

    def test_backend_operation_state_only_and_no_leaked_payload(self):
        out = self.gateway.operation_status(OP, repository=REPO, source_sha=SHA)
        self.assertEqual(out["applab_state"], "QUEUED")
        self.assertEqual(out["evidence"], "CANONICAL_APPLAB_STORE_REPORTED")
        self.assertNotIn("MUST_NEVER_LEAK", str(out))
        self.assertFalse(out["certification_granted"])
        self.assertFalse(out["external_write_performed"])

    def test_protect_cross_repo_and_wrong_sha(self):
        with self.assertRaisesRegex(StatusGatewayError, "NOT_AUTHORIZED"):
            self.gateway.operation_status(OP, repository=OTHER, source_sha=SHA)
        self.assertEqual(self.store.calls, 0)
        with self.assertRaisesRegex(StatusGatewayError, "SOURCE_MISMATCH"):
            self.gateway.operation_status(OP, repository=REPO, source_sha="b" * 40)
        self.assertEqual(self.store.calls, 1)

    def test_bad_job_id_and_backend_forgery(self):
        with self.assertRaisesRegex(StatusGatewayError, "INVALID_OPERATION_ID"):
            self.gateway.operation_status("../secret", repository=REPO, source_sha=SHA)
        self.assertEqual(self.store.calls, 0)
        self.store.payload["current_state"] = "RUNNING;rm -rf"
        with self.assertRaisesRegex(StatusGatewayError, "STATE_INVALID"):
            self.gateway.operation_status(OP, repository=REPO, source_sha=SHA)

    def test_state_succeeded_never_certifies_evidence(self):
        self.store.payload["current_state"] = "SUCCEEDED"
        out = self.gateway.operation_status(OP, repository=REPO, source_sha=SHA)
        self.assertFalse(out["ci_verified"])
        self.assertFalse(out["certification_granted"])

    def test_missing_host_provider_is_rejected(self):
        with self.assertRaisesRegex(StatusGatewayError, "READ_PROVIDERS_MISSING"):
            FactoryReadOnlyGateway(allowed_repositories=[REPO],
                                  github_head_reader=lambda _: {},
                                  applab_store=object())


if __name__ == "__main__":
    unittest.main()
