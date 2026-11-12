"""X10-016 fail-closed contract tests, strictly synthetic."""
import copy
import unittest
from unittest.mock import Mock

from scripts.agent_specialist_adapters import (
    SpecialistAdapterError, research_intake, delegate_qa,
)

SHA = "a" * 40
OTHER = "b" * 40
JOB = {
    "schema_version": 1, "job_id": "x10-016-job",
    "idempotency_key": "specialist-x10-016-job",
    "mode": "analyze",
    "target": {"repository": "example/app", "source_sha": SHA,
               "allowed_paths": ["lib"]},
    "request": {"summary": "Review reusable source"},
    "limits": {"timeout_seconds": 120, "max_attempts": 1},
}
POLICY = {"repositories": ["example/app"], "modes": ["analyze", "run_tests"],
          "allowed_paths": ["lib"]}
CAND = {"schema_version": 1, "intent": "OSS_DONOR_RESEARCH",
        "candidates": [{"repository": "example/donor", "source_sha": OTHER,
                        "path": "lib/feature.dart", "kind": "code"}]}


def resolver(repo, sha):
    return {"repository": repo, "source_sha": sha, "authenticated": True,
            "exact_source": True, "license_spdx": "MIT"}


def qa_job():
    job = copy.deepcopy(JOB)
    job["mode"] = "run_tests"
    return job


def route():
    return {"schema_version": 1, "record_type": "APP_FACTORY_X10_QA_ROUTE",
            "authority": "ROUTE_ONLY", "state": "PENDING_TRUSTED_EXECUTOR",
            "repository": "example/app", "source_sha": SHA,
            "effective_mode": "fast", "test_executed": False,
            "certification_granted": False, "store_release_granted": False}


def delegate(planned, *, runner):
    assert planned["state"] == "PENDING_TRUSTED_EXECUTOR"
    return runner(planned)


def reported(planned):
    return {"schema_version": 1, "record_type": "APP_FACTORY_X10_QA_RECEIPT",
            "repository": planned["repository"], "source_sha": planned["source_sha"],
            "analysis_mode": planned["effective_mode"], "state": "RUNNER_REPORTED_ONLY",
            "independent_provenance_verified": False, "certification_granted": False,
            "store_release_granted": False, "run_url": "",
            "gate_results": {"visual_qa": "PASS"}}


class ResearchAdapterTests(unittest.TestCase):
    def test_candidates_are_only_proposals(self):
        r = research_intake(JOB, POLICY, research_input=copy.deepcopy(CAND),
                            trusted_source_resolver=resolver)
        self.assertEqual(r["state"], "CANDIDATES_REQUIRE_REVIEW")
        self.assertFalse(r["golden_promoted"])
        self.assertFalse(r["license_verified"])
        self.assertEqual(r["candidates"][0]["declared_license_spdx"], "MIT")
        self.assertIn(OTHER, r["candidates"][0]["source_url"])

    def test_untrusted_source_rejected(self):
        probe = Mock(return_value={**resolver("example/donor", OTHER),
                                   "authenticated": False})
        with self.assertRaisesRegex(SpecialistAdapterError, "RESEARCH_SOURCE_NOT_VERIFIED"):
            research_intake(JOB, POLICY, research_input=CAND, trusted_source_resolver=probe)

    def test_scope_policy_denies_before_resolver(self):
        blocked = copy.deepcopy(POLICY)
        blocked["repositories"] = ["example/other"]
        probe = Mock(side_effect=AssertionError("should never call"))
        with self.assertRaisesRegex(SpecialistAdapterError, "READ_POLICY_DENIED"):
            research_intake(JOB, blocked, research_input=CAND, trusted_source_resolver=probe)
        probe.assert_not_called()

    def test_duplicate_candidates_rejected(self):
        x = copy.deepcopy(CAND)
        x["candidates"].append(copy.deepcopy(x["candidates"][0]))
        with self.assertRaisesRegex(SpecialistAdapterError, "DUPLICATE_RESEARCH_CANDIDATE"):
            research_intake(JOB, POLICY, research_input=x, trusted_source_resolver=resolver)

    def test_finance_live_or_credential_path_rejected(self):
        for path in ["lib/finance_live/key.dart", "../.env", "lib/../../secrets/key.py"]:
            x = copy.deepcopy(CAND)
            x["candidates"][0]["path"] = path
            with self.assertRaisesRegex(SpecialistAdapterError, "SOURCE_OR_PATH_INVALID"):
                research_intake(JOB, POLICY, research_input=x,
                                trusted_source_resolver=resolver)

    def test_wrong_mode_rejected(self):
        x = copy.deepcopy(JOB)
        x["mode"] = "prepare_pr"
        with self.assertRaisesRegex(SpecialistAdapterError, "SPECIALIST_JOB_MODE_INVALID"):
            research_intake(x, POLICY, research_input=CAND, trusted_source_resolver=resolver)

    def test_unexpected_source_fields_rejected(self):
        x = copy.deepcopy(CAND)
        x["candidates"][0]["secret"] = "test"
        with self.assertRaisesRegex(SpecialistAdapterError, "RESEARCH_CANDIDATE_SCHEMA_INVALID"):
            research_intake(JOB, POLICY, research_input=x, trusted_source_resolver=resolver)


class QAAdapterTests(unittest.TestCase):
    def test_admitted_run_is_still_report_only(self):
        result = delegate_qa(qa_job(), POLICY, route=route(),
                             pinned_applab_delegate=delegate, authorized_runner=reported)
        self.assertEqual(result["state"], "AWAITING_INDEPENDENT_EVIDENCE")
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["certification_granted"])
        self.assertEqual(result["reported_gate_results"]["visual_qa"], "PASS")

    def test_stale_source_fails_before_delegate(self):
        x = route()
        x["source_sha"] = OTHER
        mock = Mock(side_effect=AssertionError("must not be invoked"))
        with self.assertRaisesRegex(SpecialistAdapterError, "QA_ROUTE_UNTRUSTED_OR_STALE"):
            delegate_qa(qa_job(), POLICY, route=x,
                        pinned_applab_delegate=mock, authorized_runner=reported)
        mock.assert_not_called()

    def test_self_granted_certification_rejected(self):
        x = route()
        x["certification_granted"] = True
        with self.assertRaisesRegex(SpecialistAdapterError, "QA_ROUTE_UNTRUSTED_OR_STALE"):
            delegate_qa(qa_job(), POLICY, route=x,
                        pinned_applab_delegate=delegate, authorized_runner=reported)

    def test_forged_runtime_receipt_rejected(self):
        def fake(planned):
            return {**reported(planned), "certification_granted": True}
        with self.assertRaisesRegex(SpecialistAdapterError, "QA_DELEGATE_RECEIPT_INVALID"):
            delegate_qa(qa_job(), POLICY, route=route(),
                        pinned_applab_delegate=delegate, authorized_runner=fake)

    def test_runner_refusal_is_not_suppressed(self):
        def fail(_):
            raise PermissionError("access denied")
        with self.assertRaises(PermissionError):
            delegate_qa(qa_job(), POLICY, route=route(),
                        pinned_applab_delegate=delegate, authorized_runner=fail)


if __name__ == "__main__":
    unittest.main()
