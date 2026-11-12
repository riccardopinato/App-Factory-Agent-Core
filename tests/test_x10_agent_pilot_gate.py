"""X10-046/047 contract tests using synthetic input, NOT live Windows agent."""
import copy
import unittest
from scripts.x10_agent_pilot_gate import assess, PilotEvidenceError

A = {
    "task_id": "X10-046", "repository": "example/applab",
    "base_sha": "a"*40, "pr_head_sha": "b"*40, "operation_id": "opA",
    "worker_run_url": "https://ci.example/worker/1",
    "qa_run_url": "https://github.com/example/applab/actions/runs/123",
    "pr_url": "https://github.com/example/applab/pull/7",
    "changed_files": ["test/safe_test.py"], "changed_line_count": 30,
    "attempt_count": 1, "risk": "LOW", "draft_pr_only": True,
    "agent_patch_applied": True, "independent_qa_state": "PASS",
    "codex_review_state": "NO_FINDINGS", "human_acceptance": True,
    "merge_performed": False, "release_performed": False,
}
B = {**A, "task_id": "X10-047", "repository": "example/other",
     "base_sha": "c"*40, "pr_head_sha": "d"*40,
     "operation_id": "opB", "pr_url": "https://github.com/example/other/pull/8",
     "qa_run_url": "https://github.com/example/other/actions/runs/125"}

def resolved(item):
    return {**{k: item[k] for k in (
        "task_id", "repository", "base_sha", "pr_head_sha", "operation_id",
        "worker_run_url", "qa_run_url", "pr_url")},
        "verified": True, "independent_review_verified": True}

class PilotTests(unittest.TestCase):
    def test_two_pilots_still_not_self_certified(self):
        result = assess([copy.deepcopy(A), copy.deepcopy(B)],
                        trusted_evidence_resolver=resolved)
        self.assertTrue(result["two_repos_distinct"])
        self.assertFalse(result["real_windows_worker_verified_by_this_module"])
        self.assertFalse(result["merge_authorized"])

    def test_second_requires_accepted_first(self):
        a = {**A, "human_acceptance": False}
        with self.assertRaisesRegex(PilotEvidenceError, "PILOT_A_HUMAN_GATE_NOT_ACCEPTED"):
            assess([a, B], trusted_evidence_resolver=resolved)

    def test_same_repo_rejected(self):
        b = {**B, "repository": A["repository"],
             "pr_url": A["pr_url"]}
        with self.assertRaisesRegex(PilotEvidenceError, "PILOT_REPOSITORY_MUST_DIFFER"):
            assess([A, b], trusted_evidence_resolver=resolved)

    def test_independent_verifier_must_bind_worker_identity(self):
        def drift(item):
            return {**resolved(item), "operation_id": "forged"}
        with self.assertRaisesRegex(PilotEvidenceError, "PILOT_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED"):
            assess([A], trusted_evidence_resolver=drift)

    def test_sensitive_paths_refused(self):
        for path in ["AGENTS.md", ".github/workflows/ci.yml", "../secrets/.env"]:
            r = {**A, "changed_files": [path]}
            with self.assertRaisesRegex(PilotEvidenceError, "PILOT_PATHS_NOT_SAFE"):
                assess([r], trusted_evidence_resolver=resolved)

    def test_unsafe_attempt_or_risk_refused(self):
        for bad in ({"attempt_count": 3}, {"risk": "HIGH"},
                    {"changed_line_count": 251}):
            with self.assertRaisesRegex(PilotEvidenceError, "PILOT_SCOPE_OR_ATTEMPT_BUDGET_INVALID"):
                assess([{**A, **bad}], trusted_evidence_resolver=resolved)

    def test_self_approved_or_failed_qa_refused(self):
        for bad in ({"independent_qa_state": "UNKNOWN"},
                    {"codex_review_state": "RUNNING"}, {"merge_performed": True},
                    {"agent_patch_applied": False}):
            with self.assertRaisesRegex(PilotEvidenceError, "PILOT_WORKER_OR_QA_NOT_VERIFIED"):
                assess([{**A, **bad}], trusted_evidence_resolver=resolved)
