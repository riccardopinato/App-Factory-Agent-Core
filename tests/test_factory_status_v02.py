"""Offline evidence tests: no GitHub network, no AppLab queue mutation."""
from datetime import datetime, timezone, timedelta
import unittest

from scripts.factory_status_v02 import FactoryEvidenceGateway, EvidenceGatewayError
from scripts.factory_readonly_gateway import StatusGatewayError

REPO = "riccardopinato/AppLab"
SHA = "a" * 40
BASE = "b" * 40
NOW = datetime(2026, 11, 14, 3, 30, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self):
        self.calls = 0
    def get_operation(self, operation_id):
        self.calls += 1
        return {"operation_id": operation_id, "repository": REPO,
                "resolved_sha": SHA, "current_state": "SUCCEEDED",
                "payload_json": "DATABASE_SECRET_DO_NOT_LEAK"}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.store = FakeStore()
        def gh(repo):
            raise AssertionError("main HEAD reader must not be used for PR status")
        def pr(repo, num):
            self.calls.append(("pr", repo, num))
            return self.pr_data
        def ci(repo, sha):
            self.calls.append(("ci", repo, sha))
            return self.ci_data
        self.pr_data = {"authenticated": True, "repository": REPO,
                        "number": 27, "head_sha": SHA, "base_sha": BASE,
                        "state": "open", "draft": False,
                        "observed_at": NOW.isoformat(), "access_token": "SECRET"}
        self.ci_data = {"authenticated": True, "repository": REPO, "head_sha": SHA,
                        "observed_at": NOW.isoformat(), "runs": [
                            {"name": "Validate context contracts", "run_id": 456,
                             "status": "completed", "conclusion": "success"}],
                        "payload": "NOT_FOR_OUTPUT"}
        self.gw = FactoryEvidenceGateway(
            allowed_repositories=[REPO],
            github_head_reader=gh, applab_store=self.store,
            trusted_pr_reader=pr, trusted_ci_reader=ci)

    def test_success_is_report_only_not_merge_permission(self):
        result = self.gw.pull_request_evidence(REPO, 27, expected_head_sha=SHA, now=NOW)
        self.assertEqual(result["ci_state"], "ALL_OBSERVED_CHECKS_SUCCESS")
        self.assertEqual(result["head_sha"], SHA)
        self.assertFalse(result["review_verified"])
        self.assertFalse(result["exact_head_gate_verified"])
        self.assertFalse(result["certification_granted"])
        self.assertFalse(result["external_write_performed"])
        self.assertEqual(result["blockers"], ["REVIEW_AND_BRANCH_GATES_NOT_VERIFIED"])
        self.assertNotIn("SECRET", str(result))

    def test_ci_failure_missing_or_pending_never_ready(self):
        for runs, label in [
            ([], "NO_CHECKS_OBSERVED"),
            ([{"name": "Build", "run_id": 99, "status": "in_progress", "conclusion": None}], "CHECKS_PENDING"),
            ([{"name": "Build", "run_id": 99, "status": "completed", "conclusion": "failure"}], "NON_SUCCESS_REPORTED"),
            ([{"name": "Build", "run_id": 99, "status": "completed", "conclusion": "skipped"}], "NON_SUCCESS_REPORTED"),
        ]:
            with self.subTest(label=label):
                self.ci_data["runs"] = runs
                out = self.gw.pull_request_evidence(REPO, 27, now=NOW)
                self.assertEqual(out["ci_state"], label)
                self.assertIn(label, out["blockers"])

    def test_draft_pr_has_separate_blocker(self):
        self.pr_data["draft"] = True
        out = self.gw.pull_request_evidence(REPO, 27, now=NOW)
        self.assertIn("DRAFT_PR", out["blockers"])

    def test_pr_identity_checks_before_ci_lookup(self):
        self.pr_data["head_sha"] = "c" * 40
        with self.assertRaisesRegex(EvidenceGatewayError, "PR_HEAD_CHANGED"):
            self.gw.pull_request_evidence(REPO, 27, expected_head_sha=SHA, now=NOW)
        self.assertEqual(len(self.calls), 1)

    def test_ci_identity_mismatch_refused(self):
        self.ci_data["head_sha"] = "c" * 40
        with self.assertRaisesRegex(EvidenceGatewayError, "CI_SOURCE_IDENTITY_MISMATCH"):
            self.gw.pull_request_evidence(REPO, 27, now=NOW)

    def test_stale_provenance_rejected(self):
        self.ci_data["observed_at"] = (NOW - timedelta(hours=1)).isoformat()
        with self.assertRaisesRegex(EvidenceGatewayError, "STALE"):
            self.gw.pull_request_evidence(REPO, 27, now=NOW)

    def test_printable_unicode_workflow_name_is_accepted(self):
        self.ci_data["runs"][0]["name"] = "Factory gateway — pinned AppLab store integration"
        result = self.gw.pull_request_evidence(REPO, 27, now=NOW)
        self.assertEqual(result["ci_state"], "ALL_OBSERVED_CHECKS_SUCCESS")
        self.assertEqual(result["checks"][0]["name"], "Factory gateway — pinned AppLab store integration")
        self.ci_data["runs"][0]["name"] = "Build\\nInjected"
        with self.assertRaisesRegex(EvidenceGatewayError, "CI_RUN_MALFORMED"):
            self.gw.pull_request_evidence(REPO, 27, now=NOW)

    def test_duplicate_run_fails_closed(self):
        self.ci_data["runs"] *= 2
        with self.assertRaisesRegex(EvidenceGatewayError, "CI_RUN_MALFORMED"):
            self.gw.pull_request_evidence(REPO, 27, now=NOW)

    def test_invalid_run_shape_rejected(self):
        self.ci_data["runs"] = [{"name": "Build", "run_id": 123,
                                  "status": "in_progress", "conclusion": "success"}]
        with self.assertRaisesRegex(EvidenceGatewayError, "CI_RUN_MALFORMED"):
            self.gw.pull_request_evidence(REPO, 27, now=NOW)

    def test_batch_denies_unlisted_before_fetch(self):
        reqs = [{"repository": REPO, "number": 27, "expected_head_sha": SHA},
                {"repository": "riccardopinato/World-Days", "number": 1,
                 "expected_head_sha": SHA}]
        with self.assertRaisesRegex(StatusGatewayError, "NOT_AUTHORIZED"):
            self.gw.pull_request_batch(reqs, now=NOW)
        self.assertEqual(self.calls, [])

    def test_batch_dedup_and_normalized(self):
        req = {"repository": REPO, "number": 27, "expected_head_sha": SHA}
        with self.assertRaisesRegex(EvidenceGatewayError, "DUPLICATE_PR"):
            self.gw.pull_request_batch([req, req], now=NOW)
        out = self.gw.pull_request_batch([req], now=NOW)
        self.assertEqual(out["items"][0]["pr_number"], 27)

    def test_checkpoint_uses_canonical_applab_not_ci(self):
        ck = self.gw.operation_checkpoint("op-123", repository=REPO, source_sha=SHA)
        self.assertEqual(ck["applab_state"], "SUCCEEDED")
        self.assertFalse(ck["recovery_verified"])
        self.assertFalse(ck["next_action_authorized"])
        self.assertEqual(self.store.calls, 1)
        self.assertNotIn("DATABASE_SECRET", str(ck))

    def test_input_and_provider_failures_do_not_expose_details(self):
        with self.assertRaisesRegex(EvidenceGatewayError, "INVALID_PR_NUMBER"):
            self.gw.pull_request_evidence(REPO, True, now=NOW)
        def fail_pr(*_args):
            raise ValueError("TOKEN_SECRET_DB_PATH")
        self.gw._pr = fail_pr
        with self.assertRaisesRegex(EvidenceGatewayError, "PR_PROVIDER_UNAVAILABLE") as ctx:
            self.gw.pull_request_evidence(REPO, 27, now=NOW)
        self.assertNotIn("TOKEN_SECRET_DB_PATH", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
