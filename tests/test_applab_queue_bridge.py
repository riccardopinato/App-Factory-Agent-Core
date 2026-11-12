import copy
import unittest

from scripts.applab_queue_bridge import AppLabQueueBridge, BridgeError

SHA = "a" * 40
JOB = {
    "schema_version": 1, "job_id": "job-00001",
    "idempotency_key": "delivery-0012345", "mode": "analyze",
    "target": {"repository": "riccardopinato/World-Days",
               "source_sha": SHA, "allowed_paths": ["lib"]},
    "request": {"summary": "Source-bound read-only inventory"},
    "limits": {"timeout_seconds": 120, "max_attempts": 2}
}
POLICY = {"repositories": ["riccardopinato/World-Days"],
          "modes": ["analyze", "prepare_pr"], "allowed_paths": ["lib"]}


class FakeStore:
    def __init__(self):
        self.state = "QUEUED"
        self.rebuild = "QUEUED"
        self.operation = {"operation_id": "op-00001", "repository": JOB["target"]["repository"],
                          "resolved_sha": SHA, "current_state": self.state}
    def get_operation(self, operation_id):
        if operation_id != self.operation["operation_id"]:
            raise ValueError("not persisted")
        return {**self.operation, "current_state": self.state}
    def rebuild_operation_state(self, operation_id):
        return self.rebuild


class FakeAppLabQueue:
    def __init__(self, store):
        self.store = store
        self.queue = {}
        self.calls = 0
        self.expired = []
    def enqueue(self, operation_id, *, now_ts, max_retries, ancestor_shas=None,
                ancestry_proven=False):
        self.calls += 1
        if operation_id in self.queue:
            return {"status": "REPLAY", "state": self.queue[operation_id],
                    "operation_id": operation_id}
        self.queue[operation_id] = "QUEUED"
        return {"status": "INSERTED", "state": "QUEUED", "operation_id": operation_id}
    def recover_expired_leases(self, *, now_ts):
        result = list(self.expired)
        self.expired = []
        return result


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.queue = FakeAppLabQueue(self.store)
        self.bridge = AppLabQueueBridge(self.store, self.queue)

    def test_double_delivery_is_backend_replay(self):
        a = self.bridge.enqueue_admitted(JOB, POLICY, "op-00001", now_ts=10)
        b = self.bridge.enqueue_admitted(JOB, POLICY, "op-00001", now_ts=11)
        self.assertEqual([a["status"], b["status"]], ["INSERTED", "REPLAY"])
        self.assertEqual(len(self.queue.queue), 1)
        self.assertFalse(a["dispatch_performed"])

    def test_requires_persisted_matching_source(self):
        bad = copy.deepcopy(JOB)
        bad["target"]["source_sha"] = "b" * 40
        with self.assertRaisesRegex(BridgeError, "SOURCE_IDENTITY_MISMATCH"):
            self.bridge.enqueue_admitted(bad, POLICY, "op-00001", now_ts=10)
        self.assertEqual(self.queue.calls, 0)

    def test_denied_job_has_no_backend_side_effects(self):
        bad = copy.deepcopy(JOB)
        bad["mode"] = "prepare_pr"
        result = self.bridge.enqueue_admitted(bad, POLICY, "op-00001", now_ts=10)
        self.assertEqual(result["reason"], "TRUSTED_APPROVAL_REQUIRED")
        self.assertEqual(self.queue.calls, 0)

    def test_cannot_claim_unproven_ancestry(self):
        with self.assertRaisesRegex(BridgeError, "UNTRUSTED_ANCESTRY"):
            self.bridge.enqueue_admitted(JOB, POLICY, "op-00001", now_ts=10,
                                         ancestor_shas={"b" * 40})
        self.assertEqual(self.queue.calls, 0)

    def test_replayable_checkpoint_and_corruption_fail_closed(self):
        self.assertTrue(self.bridge.checkpoint("op-00001", JOB)["replay_verified"])
        self.store.state = "RUNNING"
        with self.assertRaisesRegex(BridgeError, "TRANSITION_LEDGER_DRIFT"):
            self.bridge.checkpoint("op-00001", JOB)

    def test_expired_lease_delegated_not_dispatched(self):
        self.queue.expired = [{"operation_id": "op-00001", "retry": True,
                               "retry_count": 1, "available_at": 120}]
        result = self.bridge.recover(now_ts=50)
        self.assertEqual(len(result["recovered"]), 1)
        self.assertFalse(result["dispatch_performed"])
        self.assertEqual(self.bridge.recover(now_ts=55)["recovered"], [])

    def test_invalid_timestamp_and_queue_mismatch(self):
        for stamp in [float("nan"), -1, "1", True]:
            with self.assertRaisesRegex(BridgeError, "INVALID_CLOCK"):
                self.bridge.recover(now_ts=stamp)
        with self.assertRaisesRegex(BridgeError, "APPLAB_STORE_QUEUE_MISMATCH"):
            AppLabQueueBridge(FakeStore(), self.queue)

    def test_backend_not_invoked_for_policy_scope_refusal(self):
        bad = copy.deepcopy(JOB)
        bad["target"]["allowed_paths"] = ["docs"]
        result = self.bridge.enqueue_admitted(bad, POLICY, "op-00001", now_ts=10)
        self.assertEqual(result["reason"], "PATH_OUT_OF_SCOPE")
        self.assertEqual(self.queue.calls, 0)


if __name__ == "__main__":
    unittest.main()
