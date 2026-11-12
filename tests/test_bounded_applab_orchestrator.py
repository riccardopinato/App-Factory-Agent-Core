"""X10-013: offline contract/replay fixtures. No installed AppLab worker executed."""
import copy
import hashlib
import hmac
import time
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from scripts.agent_job_gateway import canonical, job_digest
from scripts.applab_queue_bridge import AppLabQueueBridge
from scripts.bounded_applab_orchestrator import BoundedAppLabOrchestrator, OrchestrationError

SHA = "a" * 40
KEY = b"trusted-test-key-only-not-production-1234"
JOB = {
    "schema_version": 1, "job_id": "x10-job-00001",
    "idempotency_key": "x10-delivery-0000001", "mode": "analyze",
    "target": {"repository": "example/app", "source_sha": SHA, "allowed_paths": ["lib"]},
    "request": {"summary": "Source-bound analysis"},
    "limits": {"timeout_seconds": 120, "max_attempts": 2},
}
POLICY = {"repositories": ["example/app"],
          "modes": ["analyze", "run_tests", "propose_diff", "prepare_pr"],
          "allowed_paths": ["lib"]}


class Store:
    def __init__(self):
        self.op = {"operation_id": "op_x10", "repository": "example/app",
                   "resolved_sha": SHA, "current_state": "PLANNING"}
    def get_operation(self, id):
        assert id == "op_x10"
        return dict(self.op)
    def rebuild_operation_state(self, id):
        return self.op["current_state"]


class Queue:
    def __init__(self, store):
        self.store = store
        self.items = {}
        self.recover_results = []
        self.lease = None
    def _entry(self, operation_id):
        if operation_id != "op_x10":
            return None
        return dict(self.lease) if self.lease is not None else None
    def enqueue(self, operation_id, *, now_ts, max_retries, ancestor_shas=None, ancestry_proven=False):
        status = "REPLAY" if operation_id in self.items else "INSERTED"
        self.items[operation_id] = "QUEUED"
        return {"status": status, "state": "QUEUED", "operation_id": operation_id}
    def recover_expired_leases(self, *, now_ts):
        prior, self.recover_results = self.recover_results, []
        return prior


def graph_factory(op, *, work_item_id, allow_code_edit, allow_draft_pr_steward):
    assert allow_draft_pr_steward is False
    allow = ["READ_REPOSITORY", "READ_EVIDENCE"]
    if allow_code_edit:
        allow.append("ALLOW_CODE_EDIT")
    return {"record_type": "APPLAB_WORK_ITEM", "work_item_id": work_item_id,
            "operation_id": op["operation_id"], "repository": op["repository"],
            "resolved_sha": op["resolved_sha"], "authority": "ORCHESTRATION_ONLY",
            "authority_envelope": {"allowed_capabilities": allow}}


def receipt(job):
    value = {"schema_version": 1, "job_sha256": job_digest(job),
             "repository": job["target"]["repository"],
             "source_sha": job["target"]["source_sha"],
             "mode": job["mode"], "allowed_paths": job["target"]["allowed_paths"],
             "reviewer": "separate-control-plane", "review_url": "https://github.com/example/app/pull/10",
             "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}
    value["hmac_sha256"] = hmac.new(KEY, canonical(value), hashlib.sha256).hexdigest()
    return value


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.queue = Queue(self.store)
        self.calls = []
        def binding(digest, opid, op):
            self.calls.append((digest, opid))
            return digest == job_digest(JOB) and opid == "op_x10"
        self.orch = BoundedAppLabOrchestrator(
            AppLabQueueBridge(self.store, self.queue),
            binding_verifier=binding, work_item_factory=graph_factory)
        self.claim = {"operation_id": "op_x10", "repository": "example/app",
                      "resolved_sha": SHA, "executor": "GITHUB_ACTIONS",
                      "worker_id": "gha-trusted", "lease_until": time.time() + 3600,
                      "dispatch_performed": False}
        self.queue.lease = {**self.claim, "state": "LEASED",
                            "leased_by": "gha-trusted"}

    def test_duplicate_delivery_replays_one_applab_operation(self):
        a = self.orch.stage(JOB, POLICY, "op_x10", now_ts=1)
        b = self.orch.stage(JOB, POLICY, "op_x10", now_ts=2)
        self.assertEqual([a["status"], b["status"]], ["INSERTED", "REPLAY"])
        self.assertEqual(len(self.queue.items), 1)
        self.assertFalse(b["automatic_dispatch"])

    def test_crash_recovery_delegates_to_same_applab_lease(self):
        self.orch.stage(JOB, POLICY, "op_x10", now_ts=1)
        self.queue.recover_results = [{"operation_id": "op_x10", "retry": True,
                                       "retry_count": 1, "available_at": 100}]
        result = self.orch.recover(now_ts=90)
        self.assertEqual(result["recovered"][0]["retry_count"], 1)
        self.assertEqual(self.orch.recover(now_ts=91)["recovered"], [])
        self.assertFalse(result["dispatch_performed"])

    def test_work_graph_intent_stable_across_repeated_lease_read(self):
        a = self.orch.prepare_claim(JOB, POLICY, "op_x10", self.claim, now_ts=1)
        b = self.orch.prepare_claim(JOB, POLICY, "op_x10", self.claim, now_ts=2)
        self.assertEqual(a["work_item"]["work_item_id"], b["work_item"]["work_item_id"])
        self.assertFalse(b["dispatch_performed"])
        self.assertFalse(b["auto_merge_performed"])

    def test_no_claim_of_another_operation_or_expired_lease(self):
        wrong = {**self.claim, "operation_id": "op_other"}
        with self.assertRaisesRegex(OrchestrationError, "CROSS_JOB_LEASE_MISMATCH"):
            self.orch.prepare_claim(JOB, POLICY, "op_x10", wrong, now_ts=1)
        with self.assertRaisesRegex(OrchestrationError, "LEASE_EXPIRED"):
            self.orch.prepare_claim(JOB, POLICY, "op_x10", self.claim,
                                    now_ts=self.claim["lease_until"])

    def test_copied_claim_without_persisted_lease_is_denied(self):
        self.queue.lease = None
        with self.assertRaisesRegex(OrchestrationError, "APPLAB_LEASE_NOT_FOUND"):
            self.orch.prepare_claim(JOB, POLICY, "op_x10", self.claim, now_ts=1)

    def test_stale_caller_timestamp_cannot_validate_currently_expired_lease(self):
        # The caller passes "now" from long before the real lease expired.
        # Compare current durable entry against the real process clock too.
        expired = time.time() - 10
        self.claim["lease_until"] = expired
        self.queue.lease["lease_until"] = expired
        with self.assertRaisesRegex(OrchestrationError, "APPLAB_LEASE_EXPIRED"):
            self.orch.prepare_claim(JOB, POLICY, "op_x10", self.claim, now_ts=1)

    def test_superseded_or_stolen_lease_is_denied(self):
        self.queue.lease["leased_by"] = "other-worker"
        with self.assertRaisesRegex(OrchestrationError, "APPLAB_LEASE_OWNER_OR_GENERATION"):
            self.orch.prepare_claim(JOB, POLICY, "op_x10", self.claim, now_ts=1)

    def test_cancelled_operation_blocks_preparing(self):
        self.store.op["current_state"] = "CANCELLED"
        with self.assertRaisesRegex(OrchestrationError, "APPLAB_OPERATION_NOT_ACTIVE"):
            self.orch.prepare_claim(JOB, POLICY, "op_x10", self.claim, now_ts=1)

    def test_expired_or_cancelled_lease_blocks_delayed_patch_before_worker(self):
        write = copy.deepcopy(JOB)
        write["mode"] = "propose_diff"
        o = BoundedAppLabOrchestrator(
            AppLabQueueBridge(self.store, self.queue),
            binding_verifier=lambda digest, opid, op: digest == job_digest(write),
            work_item_factory=graph_factory)
        self.store.op["current_state"] = "READY"
        proof = receipt(write)
        intent = o.prepare_claim(write, POLICY, "op_x10", self.claim, now_ts=1,
                                 receipt=proof, verifier_key=KEY)
        calls = []
        self.queue.lease["leased_by"] = "another-worker"
        with self.assertRaisesRegex(OrchestrationError, "APPLAB_LEASE_OWNER_OR_GENERATION"):
            o.propose_bounded_patch(
                intent, write, POLICY, receipt=proof, verifier_key=KEY,
                repo_root=None, patch_path=None, investigation={},
                attempt_number=1, bounded_worker=lambda *a, **k: calls.append(a))
        self.assertEqual(calls, [])
        self.queue.lease["leased_by"] = "gha-trusted"
        self.store.op["current_state"] = "CANCELLED"
        with self.assertRaisesRegex(OrchestrationError, "APPLAB_OPERATION_NOT_ACTIVE"):
            o.propose_bounded_patch(
                intent, write, POLICY, receipt=proof, verifier_key=KEY,
                repo_root=None, patch_path=None, investigation={},
                attempt_number=1, bounded_worker=lambda *a, **k: calls.append(a))
        self.assertEqual(calls, [])

    def test_lease_reassigned_during_workspace_preflight_never_enters_worker(self):
        write = copy.deepcopy(JOB)
        write["mode"] = "propose_diff"
        orch = BoundedAppLabOrchestrator(
            AppLabQueueBridge(self.store, self.queue),
            binding_verifier=lambda digest, opid, op: digest == job_digest(write),
            work_item_factory=graph_factory)
        self.store.op["current_state"] = "READY"
        proof = receipt(write)
        intent = orch.prepare_claim(write, POLICY, "op_x10", self.claim, now_ts=1,
                                    receipt=proof, verifier_key=KEY)
        calls = []
        def simulate_preflight_then_execute(*a, bounded_worker, **kw):
            self.queue.lease["leased_by"] = "recovery-worker"
            return bounded_worker(None, None, None, None, attempt_number=1)
        with patch("scripts.bounded_applab_orchestrator.propose_in_applab_workspace",
                   side_effect=simulate_preflight_then_execute):
            with self.assertRaisesRegex(OrchestrationError, "APPLAB_LEASE_OWNER_OR_GENERATION"):
                orch.propose_bounded_patch(
                    intent, write, POLICY, receipt=proof, verifier_key=KEY,
                    repo_root=None, patch_path=None, investigation={},
                    attempt_number=1, bounded_worker=lambda *a, **k: calls.append("executed"))
        self.assertEqual(calls, [])

    def test_cancelled_during_workspace_preflight_never_enters_worker(self):
        write = copy.deepcopy(JOB)
        write["mode"] = "propose_diff"
        orch = BoundedAppLabOrchestrator(
            AppLabQueueBridge(self.store, self.queue),
            binding_verifier=lambda digest, opid, op: digest == job_digest(write),
            work_item_factory=graph_factory)
        self.store.op["current_state"] = "READY"
        proof = receipt(write)
        intent = orch.prepare_claim(write, POLICY, "op_x10", self.claim, now_ts=1,
                                    receipt=proof, verifier_key=KEY)
        calls = []
        def simulate_preflight_then_execute(*a, bounded_worker, **kw):
            self.store.op["current_state"] = "CANCELLED"
            return bounded_worker(None, None, None, None, attempt_number=1)
        with patch("scripts.bounded_applab_orchestrator.propose_in_applab_workspace",
                   side_effect=simulate_preflight_then_execute):
            with self.assertRaisesRegex(OrchestrationError, "APPLAB_OPERATION_NOT_ACTIVE"):
                orch.propose_bounded_patch(
                    intent, write, POLICY, receipt=proof, verifier_key=KEY,
                    repo_root=None, patch_path=None, investigation={},
                    attempt_number=1, bounded_worker=lambda *a, **k: calls.append("executed"))
        self.assertEqual(calls, [])

    def test_trusted_mapping_needed_before_any_enqueue(self):
        bad = copy.deepcopy(JOB)
        bad["idempotency_key"] = "another-delivery-000001"
        with self.assertRaisesRegex(OrchestrationError, "TRUSTED_OPERATION_BINDING_REQUIRED"):
            self.orch.stage(bad, POLICY, "op_x10", now_ts=1)
        self.assertEqual(self.queue.items, {})

    def test_write_denied_without_external_scoped_receipt(self):
        write = copy.deepcopy(JOB)
        write["mode"] = "propose_diff"
        # Assume a separately trusted control plane has bound this exact
        # write-mode job to the operation. The policy must STILL deny it.
        o = BoundedAppLabOrchestrator(
            AppLabQueueBridge(self.store, self.queue),
            binding_verifier=lambda digest, opid, op: digest == job_digest(write) and opid == "op_x10",
            work_item_factory=graph_factory)
        self.assertEqual(o.stage(write, POLICY, "op_x10", now_ts=1)["state"], "BLOCKED")
        self.assertEqual(self.queue.items, {})
        with self.assertRaisesRegex(OrchestrationError, "JOB_NOT_AUTHORIZED"):
            o.prepare_claim(write, POLICY, "op_x10", self.claim, now_ts=2)

    def test_pr_mode_not_routed_even_if_allowlisted(self):
        pr = copy.deepcopy(JOB)
        pr["mode"] = "prepare_pr"
        with self.assertRaisesRegex(OrchestrationError, "NO_PR_OR_MERGE_ROUTING"):
            self.orch.stage(pr, POLICY, "op_x10", now_ts=1)

    def test_workgraph_never_mints_draft_pr_capability(self):
        def escalated(op, **kwargs):
            graph = graph_factory(op, **kwargs)
            graph["authority_envelope"]["allowed_capabilities"].append("CREATE_DRAFT_PR")
            return graph
        o = BoundedAppLabOrchestrator(
            AppLabQueueBridge(self.store, self.queue),
            binding_verifier=lambda *args: True, work_item_factory=escalated)
        with self.assertRaisesRegex(OrchestrationError, "WORKGRAPH_PRIVILEGE_ESCALATION"):
            o.prepare_claim(JOB, POLICY, "op_x10", self.claim, now_ts=1)

    def test_invalid_patch_intent_does_not_call_worker(self):
        calls = []
        with self.assertRaisesRegex(OrchestrationError, "INVALID_PATCH_INTENT"):
            self.orch.propose_bounded_patch(
                {"record_type": "X10_BOUNDED_DISPATCH_INTENT", "mode": "analyze"},
                JOB, POLICY, receipt=receipt(JOB), verifier_key=KEY,
                repo_root=None, patch_path=None, investigation={},
                attempt_number=1, bounded_worker=lambda *a, **k: calls.append(a))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
