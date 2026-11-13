import unittest

try:
    from scripts.x10_windows_job_adapter import (
        LegacyJobInvalid, evaluate_legacy_candidate, propose_canonical_job
    )
except ModuleNotFoundError:
    from x10_windows_job_adapter import (
        LegacyJobInvalid, evaluate_legacy_candidate, propose_canonical_job
    )

ROW = {'repo': 'riccardopinato/180FlipCharge', 'issue': 6,
       'base_sha': 'a' * 40, 'pr_sha': 'b' * 40,
       'file': 'app/src/main/java/com/flipcharge/app/AppStrings.kt',
       'task': 'Add KDoc only.'}
POLICY = {'repositories': ['riccardopinato/180FlipCharge'],
          'modes': ['analyze', 'prepare_pr'],
          'allowed_paths': ['app/src/main/java/com/flipcharge/app']}


class AdapterTests(unittest.TestCase):
    def test_read_only_admission(self):
        got = evaluate_legacy_candidate(ROW, POLICY)
        self.assertTrue(got['decision']['authorized'])
        self.assertEqual(got['decision']['state'], 'ADMITTED_FOR_ISOLATED_READ')
        self.assertFalse(got['writes_performed'])

    def test_pr_requires_independent_approval(self):
        got = evaluate_legacy_candidate(ROW, POLICY, mode='prepare_pr')
        self.assertFalse(got['decision']['authorized'])
        self.assertEqual(got['decision']['reason'], 'TRUSTED_APPROVAL_REQUIRED')

    def test_identity_stable_and_source_pinned(self):
        a = propose_canonical_job(ROW)
        b = propose_canonical_job(dict(ROW, pr_sha='c'*40))
        self.assertEqual(a['idempotency_key'], b['idempotency_key'])
        self.assertEqual(a['target']['source_sha'], 'a'*40)

    def test_no_extra_repo(self):
        with self.assertRaises(LegacyJobInvalid):
            propose_canonical_job(dict(ROW, repo='attacker/repo'))

    def test_disallow_protected_paths(self):
        with self.assertRaises(LegacyJobInvalid):
            propose_canonical_job(dict(ROW, file='AGENTS.md'))

    def test_no_missing_base_sha(self):
        with self.assertRaises(LegacyJobInvalid):
            propose_canonical_job(dict(ROW, base_sha=''))

    def test_replay_idempotent(self):
        self.assertEqual(propose_canonical_job(dict(ROW))['job_id'],
                         propose_canonical_job(dict(ROW))['job_id'])


if __name__ == '__main__':
    unittest.main()
