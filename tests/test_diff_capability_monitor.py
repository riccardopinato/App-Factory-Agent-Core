"""X10-041 synthetic event/diff fixtures; no network or real GitHub event."""
import copy
import unittest

from scripts.diff_capability_monitor import analyze, MonitorError

A = "a" * 40
B = "b" * 40
EVENT = {"repository": "example/app", "ref": "refs/heads/main",
         "base_sha": A, "head_sha": B}
TRUST = {"authenticated": True, "exact_head_resolved": True,
         "diff_provenance_verified": True, "no_unauthorized_repo_scope": True}
DIFF = {
    "trusted": True, "status": "ok", "too_large": False,
    "base_sha": A, "head_sha": B, "file_count": 2,
    "files": [
        {"path": "lib/notifications/push_alarm.dart", "status": "M",
         "additions": 8, "deletions": 3},
        {"path": "test/settings_test.dart", "status": "A",
         "additions": 7, "deletions": 0},
    ],
}


class MonitorTests(unittest.TestCase):
    def assess(self, event=None, diff=None, trust=None, verified_head_sha=B):
        return analyze(event if event is not None else EVENT,
                       diff if diff is not None else DIFF,
                       trust=trust if trust is not None else TRUST,
                       verified_head_sha=verified_head_sha)

    def test_deterministic_idempotency_across_identical_delivery(self):
        a = self.assess()
        b = self.assess()
        self.assertEqual(a, b)
        self.assertEqual(a["authority"], "ADVISORY_ONLY")
        self.assertEqual(a["changed_file_count"], 2)
        self.assertIn("notifications", a["signals"][0]["signals"])
        self.assertTrue(a["requires_cap_registry_match"])
        self.assertFalse(a["automated_pr_created"])
        self.assertNotIn("hunks", a)

    def test_different_commit_has_different_monitor_key(self):
        event = {**EVENT, "head_sha": "c" * 40}
        diff = {**DIFF, "head_sha": "c" * 40}
        self.assertNotEqual(self.assess()["monitor_key"],
                            self.assess(event, diff, verified_head_sha="c" * 40)["monitor_key"])

    def test_untrusted_authentication_or_baseline_denied(self):
        for field in TRUST:
            trust = dict(TRUST)
            trust[field] = False
            with self.assertRaisesRegex(MonitorError, "TRUST_PROOF_REQUIRED"):
                self.assess(trust=trust)
        with self.assertRaisesRegex(MonitorError, "EVENT_SHA_NOT_PINNED"):
            self.assess(verified_head_sha="c" * 40)
        with self.assertRaisesRegex(MonitorError, "DIFF_IDENTITY_MISMATCH"):
            self.assess(diff={**DIFF, "base_sha": "c" * 40})

    def test_dirty_or_truncated_diff_denied(self):
        for value in (
            {**DIFF, "trusted": False},
            {**DIFF, "too_large": True},
            {**DIFF, "semantic_diff_truncated": True},
        ):
            with self.assertRaisesRegex(MonitorError, "DIFF_UNTRUSTED_OR_TRUNCATED"):
                self.assess(diff=value)

    def test_rejects_duplicate_and_unsafe_paths(self):
        for path in ("../secret", "lib/../secret", ".github/workflows/build.yml",
                     "lib/.env", "/absolute/path", "lib/back\\slash.dart"):
            value = copy.deepcopy(DIFF)
            value["files"][0]["path"] = path
            with self.assertRaisesRegex(MonitorError, "UNSAFE_CHANGED_PATH"):
                self.assess(diff=value)
        duplicate = copy.deepcopy(DIFF)
        duplicate["files"][1]["path"] = duplicate["files"][0]["path"]
        with self.assertRaisesRegex(MonitorError, "DUPLICATE_CHANGED_PATH"):
            self.assess(diff=duplicate)

    def test_diff_size_and_count_bounded(self):
        with self.assertRaisesRegex(MonitorError, "DIFF_FILE_COUNT_DRIFT"):
            self.assess(diff={**DIFF, "file_count": 999})
        huge = copy.deepcopy(DIFF)
        huge["file_count"] = 201
        huge["files"] = [{"path": f"lib/a{i}.dart", "status": "M",
                          "additions": 1, "deletions": 0} for i in range(201)]
        with self.assertRaisesRegex(MonitorError, "DIFF_INVALID_SIZE"):
            self.assess(diff=huge)

    def test_untrusted_rename_predecessor_denied(self):
        v = copy.deepcopy(DIFF)
        v["files"][0]["previous_path"] = "../old_name"
        v["files"][0]["status"] = "R"
        with self.assertRaisesRegex(MonitorError, "UNSAFE_RENAME_PATH"):
            self.assess(diff=v)

    def test_sensitive_current_and_previous_path_metadata_are_hashed(self):
        value = copy.deepcopy(DIFF)
        current = "lib/auth/access_token_ghp_SECRET123456.json"
        previous = "lib/auth/private_user_email_example_com.json"
        value["files"][0]["path"] = current
        value["files"][0]["previous_path"] = previous
        value["files"][0]["status"] = "R"
        result = self.assess(diff=value)
        rendered = str(result)
        for secret in ("ghp_SECRET123456", "private_user_email", current, previous):
            self.assertNotIn(secret, rendered)
        self.assertTrue(all("path_sha256" in row and "path" not in row
                            for row in result["signals"]))
        self.assertEqual(result["authority"], "ADVISORY_ONLY")

    def test_never_disclose_raw_hunks_or_source_data(self):
        v = copy.deepcopy(DIFF)
        v["hunks"] = ["+SECRET_TOKEN=do_not_copy", "+users private data"]
        result = self.assess(diff=v)
        self.assertNotIn("SECRET_TOKEN", str(result))
        self.assertNotIn("private data", str(result))
        self.assertEqual(result["authority"], "ADVISORY_ONLY")


if __name__ == "__main__":
    unittest.main()
