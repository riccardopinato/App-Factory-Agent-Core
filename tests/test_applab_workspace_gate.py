import copy
import hashlib
import hmac
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.agent_job_gateway import canonical, job_digest
from scripts.applab_workspace_gate import propose_in_applab_workspace, WorkspaceGateError

KEY = b"k" * 40
POLICY = {"repositories": ["example/app"], "modes": ["propose_diff"], "allowed_paths": ["lib"]}


def command(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo = root / "source"
        self.repo.mkdir()
        command(self.repo, "init")
        command(self.repo, "config", "user.name", "test")
        command(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "lib").mkdir()
        (self.repo / "lib/client.py").write_text("value = 1\n")
        command(self.repo, "add", ".")
        command(self.repo, "commit", "-m", "base")
        self.sha = command(self.repo, "rev-parse", "HEAD")
        self.patch = root / "change.patch"
        self.patch.write_text("diff --git a/lib/client.py b/lib/client.py\n")
        self.job = {
            "schema_version": 1, "job_id": "job-1234567",
            "idempotency_key": "idem-123456789", "mode": "propose_diff",
            "target": {"repository": "example/app", "source_sha": self.sha,
                       "allowed_paths": ["lib"]},
            "request": {"summary": "One file bounded improvement"},
            "limits": {"timeout_seconds": 120, "max_attempts": 2},
        }
        self.work = {"repository": "example/app", "resolved_sha": self.sha,
                     "work_item_id": "work-1",
                     "authority_envelope": {"allowed_capabilities": ["ALLOW_CODE_EDIT"]}}
        self.investigation = {"repository": "example/app", "resolved_sha": self.sha}
        self.calls = 0

    def receipt(self, job=None):
        j = job or self.job
        expires = (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat()
        payload = {"schema_version": 1, "job_sha256": job_digest(j),
                   "repository": j["target"]["repository"], "source_sha": j["target"]["source_sha"],
                   "mode": j["mode"], "allowed_paths": j["target"]["allowed_paths"],
                   "reviewer": "independent-approver",
                   "review_url": "https://github.com/example/app/pull/1",
                   "expires_at": expires}
        payload["hmac_sha256"] = hmac.new(KEY, canonical(payload), hashlib.sha256).hexdigest()
        return payload

    def worker(self, repo, patch, work_item, investigation, *, attempt_number):
        self.calls += 1
        return {"schema_version": 1, "record_type": "BOUNDED_FIX_RESULT_V60C",
                "authority": "BRANCH_WORKSPACE_ONLY",
                "state": "READY_FOR_VERIFICATION",
                "repository": "example/app", "resolved_sha": self.sha,
                "work_item_id": "work-1", "attempt_number": attempt_number,
                "remote_write_performed": False, "verification_authority": "UNCHANGED",
                "merge_performed": False, "release_performed": False,
                "mutation_scope": "EPHEMERAL_LOCAL_WORKTREE_ONLY",
                "changed_files": ["lib/client.py"], "changed_lines": 2}

    def call(self, **overrides):
        opts = dict(job=self.job, policy=POLICY, receipt=self.receipt(),
                    verifier_key=KEY, repo_root=self.repo, patch_path=self.patch,
                    work_item=self.work, investigation=self.investigation,
                    attempt_number=1, bounded_worker=self.worker)
        opts.update(overrides)
        return propose_in_applab_workspace(**opts)

    def test_scoped_result_is_still_verification_pending(self):
        result = self.call()
        self.assertEqual(result["next_gate"], "INDEPENDENT_APPLAB_VERIFICATION")
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(self.calls, 1)
        self.assertEqual(command(self.repo, "rev-parse", "HEAD"), self.sha)

    def test_denies_untrusted_or_absent_approval(self):
        with self.assertRaisesRegex(WorkspaceGateError, "TRUSTED_SCOPED_APPROVAL_REQUIRED"):
            self.call(receipt=None)
        self.assertEqual(self.calls, 0)

    def test_changed_source_sha_refused(self):
        bad = copy.deepcopy(self.job)
        bad["target"]["source_sha"] = "f" * 40
        with self.assertRaisesRegex(WorkspaceGateError, "SOURCE_HEAD_CHANGED"):
            self.call(job=bad, receipt=self.receipt(bad))
        self.assertEqual(self.calls, 0)

    def test_dirty_source_refused(self):
        (self.repo / "lib/client.py").write_text("value = 2\n")
        with self.assertRaisesRegex(WorkspaceGateError, "SOURCE_CHECKOUT_DIRTY"):
            self.call()
        self.assertEqual(self.calls, 0)

    def test_patch_must_be_outside_source(self):
        nested = self.repo / "change.patch"
        nested.write_text("data")
        with self.assertRaisesRegex(WorkspaceGateError, "PATCH_INSIDE_SOURCE_TREE"):
            self.call(patch_path=nested)
        self.assertEqual(self.calls, 0)

    def test_denies_out_of_scope_patch_result(self):
        def escape(*a, **kw):
            d = self.worker(*a, **kw)
            d["changed_files"] = ["secrets/.env"]
            return d
        with self.assertRaisesRegex(WorkspaceGateError, "WORKSPACE_CHANGE_OUT_OF_SCOPE"):
            self.call(bounded_worker=escape)

    def test_denies_claimed_remote_write(self):
        def forged(*a, **kw):
            d = self.worker(*a, **kw)
            d["remote_write_performed"] = True
            return d
        with self.assertRaisesRegex(WorkspaceGateError, "WORKER_RESULT_AUTHORITY_MISMATCH"):
            self.call(bounded_worker=forged)

    def test_denies_missing_edit_capability(self):
        bad = copy.deepcopy(self.work)
        bad["authority_envelope"]["allowed_capabilities"] = []
        with self.assertRaisesRegex(WorkspaceGateError, "WORK_GRAPH_CODE_EDIT_DENIED"):
            self.call(work_item=bad)
        self.assertEqual(self.calls, 0)

    def test_attempt_limit_is_bounded(self):
        with self.assertRaisesRegex(WorkspaceGateError, "ATTEMPT_BUDGET_EXCEEDED"):
            self.call(attempt_number=3)
        self.assertEqual(self.calls, 0)


if __name__ == "__main__":
    unittest.main()
