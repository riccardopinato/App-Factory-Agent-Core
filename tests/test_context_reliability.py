import unittest

from scripts.context_reliability import (
    MAX_RETRIES, is_sha, retry_policy, reconcile, semantic_review,
    safe_public_status, validate_receipt,
)

A = "a" * 40
B = "b" * 40


class ContextReliabilityTest(unittest.TestCase):
    def base(self, **overrides):
        args = dict(source_sha=A, base_sha=B, branch_exists=True,
                    snapshot_changed=True, open_pr=False, can_push=True,
                    can_create_pr=True, event="schedule")
        args.update(overrides)
        return reconcile(**args)

    def test_retry_is_bounded(self):
        self.assertEqual(retry_policy(429, 1)["delay_seconds"], 2)
        self.assertEqual(retry_policy(503, 2, 900)["delay_seconds"], 120)
        self.assertEqual(retry_policy(503, MAX_RETRIES)["reason"], "RETRY_BUDGET_EXHAUSTED")
        self.assertFalse(retry_policy(403, 1)["retry"])
        self.assertFalse(retry_policy(422, 1)["retry"])

    def test_bad_sha_and_event_fail_closed(self):
        self.assertEqual(self.base(source_sha="bad")["state"], "BLOCKED_BAD_SHA")
        self.assertEqual(self.base(event="pull_request")["state"], "BLOCKED_UNSUPPORTED_EVENT")

    def test_source_failure_does_not_overwrite(self):
        self.assertEqual(self.base(read_ok=False)["action"], "NONE")

    def test_branch_conflict_fails_closed(self):
        self.assertEqual(self.base(branch_conflict=True)["state"], "BLOCKED_BRANCH_CONFLICT")

    def test_permission_and_recovery(self):
        self.assertEqual(self.base(can_push=False)["state"], "BLOCKED_PUSH_PERMISSION")
        self.assertEqual(self.base(can_create_pr=False)["action"], "PRESERVE_BOT_BRANCH")
        self.assertEqual(self.base(snapshot_changed=False)["action"], "CREATE_BOT_PR")

    def test_idempotence(self):
        self.assertEqual(self.base(snapshot_changed=False, open_pr=True, source_sha=B)["action"], "NONE")
        self.assertEqual(self.base(snapshot_changed=False, branch_exists=False)["action"], "NONE")
        self.assertEqual(self.base(open_pr=True)["state"], "PR_UPDATE_PENDING")

    def test_no_automatic_promotion(self):
        q = semantic_review(A, ["README.md", "golden/EXAMPLE.txt"],
                            ["https://github.com/owner/repo/commit/" + A])
        self.assertTrue(q["requires_human_review"])
        self.assertEqual(q["protected_paths"], ["golden/EXAMPLE.txt"])
        self.assertIsNone(q["inferred_evidence"])
        self.assertFalse(q["auto_merge"])
        self.assertFalse(q["auto_promote"])

    def test_no_change(self):
        self.assertEqual(semantic_review(A, [])["state"], "NO_CHANGE")

    def test_reject_path_traversal_and_bad_refs(self):
        for path in ("../private", "/etc/shadow"):
            with self.assertRaises(ValueError):
                semantic_review(A, [path])
        with self.assertRaises(ValueError):
            semantic_review(A, ["README.md"], ["http://example.com"])

    def test_private_repo_redacted(self):
        x = safe_public_status(repository="riccardopinato/private-secret",
                               visibility="private", workflow_state="BLOCKED",
                               source_url="https://github.com/riccardopinato/private-secret/actions")
        self.assertIsNone(x["repository"])
        self.assertIsNone(x["source_url"])

    def test_receipt_requires_independent_success(self):
        q = {"commit_sha": A, "event": "push", "run_url": "https://github.com/a/b/actions/runs/1", "result": "success"}
        self.assertTrue(validate_receipt(q))
        q["evidence_level"] = "CI_VERIFIED"
        self.assertFalse(validate_receipt(q))
        q.pop("evidence_level")
        q["result"] = "queued"
        self.assertFalse(validate_receipt(q))


if __name__ == "__main__":
    unittest.main()
