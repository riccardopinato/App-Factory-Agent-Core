"""X10-014: negative and replay boundary tests. Simulated transport only."""
import hashlib
import hmac
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from scripts.agent_job_gateway import canonical, job_digest
from scripts.agent_pr_steward_adapter import (
    AgentPRGateError, propose_draft_pr, assess_exact_head_evidence,
)

SHA = "a" * 40
NEXT = "c" * 40
KEY = b"only-for-synthetic-tests-not-a-real-secret-123456"
PATCH = b"diff --git a/lib/a.py b/lib/a.py\n"
P_SHA = hashlib.sha256(PATCH).hexdigest()
JOB = {
    "schema_version": 1, "job_id": "x10-job-00015",
    "idempotency_key": "x10-idempotency-000015",
    "mode": "prepare_pr",
    "target": {"repository": "example/app", "source_sha": SHA,
               "allowed_paths": ["lib"]},
    "request": {"summary": "Create proposed draft PR"},
    "limits": {"timeout_seconds": 120, "max_attempts": 2},
}
POLICY = {"repositories": ["example/app"], "modes": ["prepare_pr"],
          "allowed_paths": ["lib"]}


def approved(job=JOB):
    r = {"schema_version": 1, "job_sha256": job_digest(job),
         "repository": job["target"]["repository"],
         "source_sha": job["target"]["source_sha"],
         "mode": job["mode"], "allowed_paths": job["target"]["allowed_paths"],
         "reviewer": "independent-control-plane",
         "review_url": "https://github.com/example/app/pull/42",
         "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=12)).isoformat()}
    r["hmac_sha256"] = hmac.new(KEY, canonical(r), hashlib.sha256).hexdigest()
    return r


def trusted(operation_id, digest):
    return {
        "operation_id": operation_id,
        "job_sha256": digest,
        "repository": "example/app", "source_sha": SHA,
        "root_work_item_id": "wrk_x10", "root_source_sha": SHA,
        "work_item": {
            "work_item_id": "wrk_x10",
            "repository": "example/app", "resolved_sha": SHA,
            "authority_envelope": {
                "allowed_capabilities": ["READ_REPOSITORY", "ALLOW_CODE_EDIT",
                                         "CREATE_DRAFT_PR", "UPDATE_DRAFT_PR"]}},
        "repair_result": {
            "record_type": "BOUNDED_FIX_RESULT_V60C",
            "state": "READY_FOR_VERIFICATION",
            "repository": "example/app", "resolved_sha": SHA,
            "work_item_id": "wrk_x10", "attempt_number": 1,
            "result_patch_sha256": P_SHA, "changed_files": ["lib/a.py"]},
    }


def fake_remote(root, work, repair, patch, **kwargs):
    return {
        "schema_version": 1, "record_type": "DRAFT_PR_MATERIALIZATION_V60E",
        "authority": "DRAFT_BRANCH_AND_PR_ONLY", "state": "DRAFT_PR_CREATED",
        "repository": "example/app", "work_item_id": "wrk_x10",
        "parent_sha": SHA, "result_patch_sha256": P_SHA,
        "chain_attempt_number": kwargs["chain_attempt_number"],
        "target_base_branch": "main", "repaired_source_sha": NEXT,
        "remote_branch_sha": NEXT, "repair_branch": "applab/repair/wrk_x10-a",
        "pr_url": "https://github.com/example/app/pull/43",
        "merge_performed": False, "release_performed": False,
        "self_approval_performed": False,
    }


class AgentPRAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = Path(self.tmp.name) / "repair.patch"
        self.patch.write_bytes(PATCH)
        self.run = Mock(side_effect=fake_remote)

    def propose(self, **overrides):
        opts = dict(
            job=JOB, policy=POLICY, receipt=approved(), verifier_key=KEY,
            operation_id="op_x10", trusted_operation_loader=trusted,
            pinned_applab_execute_remote=self.run,
            repo_root=Path(self.tmp.name), patch_path=self.patch,
            chain_attempt_number=1, target_base_branch="main",
            title="Fix bounded test", body="Source-bound draft only",
        )
        opts.update(overrides)
        return propose_draft_pr(**opts)

    def test_valid_scoped_proposal_never_claims_merge(self):
        x = self.propose()
        self.assertEqual(x["state"], "DRAFT_PR_RECORDED_NOT_APPROVED")
        self.assertEqual(x["pr_head_sha"], NEXT)
        self.assertFalse(x["merge_authorized"])
        self.run.assert_called_once()

    def test_bad_or_missing_approval_never_invokes_transport(self):
        with self.assertRaisesRegex(AgentPRGateError, "TRUSTED_PR_APPROVAL_REQUIRED"):
            self.propose(receipt=None)
        self.run.assert_not_called()

    def test_wrong_mode_rejected(self):
        bad = dict(JOB, mode="propose_diff")
        with self.assertRaisesRegex(AgentPRGateError, "WRONG_MODE"):
            self.propose(job=bad)
        self.run.assert_not_called()

    def test_untrusted_operation_binding_rejected(self):
        def forged(op, digest):
            x = trusted(op, digest)
            x["job_sha256"] = "0" * 64
            return x
        with self.assertRaisesRegex(AgentPRGateError, "UNBOUND_OPERATION"):
            self.propose(trusted_operation_loader=forged)
        self.run.assert_not_called()

    def test_capability_escalation_rejected(self):
        def forged(op, digest):
            x = trusted(op, digest)
            x["work_item"]["authority_envelope"]["allowed_capabilities"].append("SELF_MERGE")
            return x
        with self.assertRaisesRegex(AgentPRGateError, "DRAFT_PR_CAPABILITY_DENIED"):
            self.propose(trusted_operation_loader=forged)
        self.run.assert_not_called()

    def test_diff_sha_tamper_rejected(self):
        self.patch.write_bytes(b"tampered patch")
        with self.assertRaisesRegex(AgentPRGateError, "PATCH_PROVENANCE_MISMATCH"):
            self.propose()
        self.run.assert_not_called()

    def test_retry_budget_rejected(self):
        with self.assertRaisesRegex(AgentPRGateError, "RETRY_BUDGET_EXCEEDED"):
            self.propose(chain_attempt_number=3)

    def test_secondary_attempt_requires_update_capability(self):
        def loader(op, digest):
            x = trusted(op, digest)
            x["repair_result"]["attempt_number"] = 2
            x["work_item"]["authority_envelope"]["allowed_capabilities"].remove("UPDATE_DRAFT_PR")
            return x
        with self.assertRaisesRegex(AgentPRGateError, "DRAFT_PR_CAPABILITY_DENIED"):
            self.propose(chain_attempt_number=2, trusted_operation_loader=loader)
        self.run.assert_not_called()

    def test_worker_claiming_merge_is_rejected(self):
        def untrusted(*a, **kw):
            x = fake_remote(*a, **kw)
            x["merge_performed"] = True
            return x
        self.run.side_effect = untrusted
        with self.assertRaisesRegex(AgentPRGateError, "UNTRUSTED_APPLAB_PR_RESULT"):
            self.propose()


class ExactHeadEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.mat = {"pr_head_sha": NEXT, "repository": "example/app",
                    "repair_branch": "applab/repair/wrk_x10-a"}
        self.pr = {"head_sha": NEXT, "state": "open", "draft": True,
                   "repository": "example/app", "head_branch": self.mat["repair_branch"],
                   "base_branch": "main"}
        self.checks = [{"head_sha": NEXT, "name": name, "status": "completed",
                        "conclusion": "success"} for name in ("CI", "security")]
        self.rev = {"commit_sha": NEXT, "status": "completed",
                    "has_any_findings": False, "has_unresolved_findings": False,
                    "independent": True}

    def assess(self, **extra):
        opts = dict(materialized=self.mat, pr=self.pr,
                    check_runs=self.checks, required_contexts=("CI", "security"),
                    review=self.rev)
        opts.update(extra)
        return assess_exact_head_evidence(**opts)

    def test_clean_evidence_still_does_not_merge(self):
        x = self.assess()
        self.assertEqual(x["state"], "SOURCE_CI_REVIEW_EVIDENCE_PRESENT")
        self.assertFalse(x["merge_performed"])
        self.assertFalse(x["certified"])

    def test_skipped_check_fails_closed(self):
        self.checks[0]["conclusion"] = "skipped"
        self.assertEqual(self.assess()["state"], "PENDING_INDEPENDENT_GATE")

    def test_stale_check_fails_closed(self):
        self.checks[0]["head_sha"] = SHA
        self.assertEqual(self.assess()["state"], "PENDING_INDEPENDENT_GATE")

    def test_duplicate_status_fails_closed(self):
        self.checks.append(dict(self.checks[0]))
        self.assertEqual(self.assess()["state"], "PENDING_INDEPENDENT_GATE")

    def test_stale_review_fails_closed(self):
        self.rev["commit_sha"] = SHA
        self.assertEqual(self.assess()["state"], "PENDING_INDEPENDENT_GATE")

    def test_pr_head_changed_fails_closed(self):
        self.pr["head_sha"] = SHA
        self.assertEqual(self.assess()["state"], "PENDING_INDEPENDENT_GATE")

    def test_missing_independent_review_fails_closed(self):
        self.rev["independent"] = False
        self.assertEqual(self.assess()["state"], "PENDING_INDEPENDENT_GATE")


if __name__ == "__main__":
    unittest.main()
