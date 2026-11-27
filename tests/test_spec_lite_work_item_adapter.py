"""Offline Spec Lite -> existing AppLab WorkItem binding admission vectors."""
import copy
import hashlib
import hmac
import json
import pathlib
import unittest
from datetime import datetime, timedelta, timezone

from scripts.agent_job_gateway import canonical, job_digest
from scripts.spec_lite_work_item_adapter import SpecBindingError, project_spec_job_binding

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = "e7903b33f9bd03a969f039d8c20292532a92951c"
FACTORY = "8b3d9263ad1a72f3b8a43273550fe43646780d78"
REPO = "riccardopinato/App-Factory-Agent-Core"
KEY = b"fixture-trusted-only-for-tests-no-real-secret"


def manifest() -> dict:
    src = json.loads((ROOT / "docs/spec_lite/agent-orchestration-contract/manifest.json").read_text())
    src["factory"]["sha"] = FACTORY
    src["canonical_refs"]["factory_current"]["sha"] = FACTORY
    src["target"]["source_sha"] = SOURCE
    src["canonical_refs"]["product_bible"]["sha"] = SOURCE
    src["canonical_refs"]["roadmap"]["sha"] = SOURCE
    src["canonical_refs"]["agents"]["sha"] = SOURCE
    # Normalize historical PROPOSED fixture in memory; do not rewrite archived pilot evidence.
    # SOURCE_TEST was declared in the historical manifest but not mapped to an AC.
    src["requirements"][0]["acceptance"].append({
        "id": "AC-005", "criterion": "Source-level projection preserves work item identity.",
        "evidence_type": "SOURCE_TEST",
    })
    return src


def job(mode="analyze", paths=None):
    return {
        "schema_version": 1, "job_id": "job-fsl-step4", "idempotency_key": "idempotent-fsl-job-step4",
        "target": {"repository": REPO, "source_sha": SOURCE,
                   "allowed_paths": paths if paths is not None else ["tests/test_bounded_applab_orchestrator.py"]},
        "mode": mode, "request": {"summary": "Read-only traceability of existing approved WorkItem"},
        "limits": {"timeout_seconds": 180, "max_attempts": 2},
    }


def policy():
    return {"repositories": [REPO],
            "modes": ["analyze", "run_tests", "propose_diff", "prepare_pr"],
            "allowed_paths": ["tests", "docs"]}


def work_item():
    return {"record_type": "APPLAB_WORK_ITEM", "repository": REPO, "resolved_sha": SOURCE,
            "work_item_id": "wrk-fsl-step4", "operation_id": "op-fsl-step4",
            "authority": "ORCHESTRATION_ONLY",
            "authority_envelope": {"allowed_capabilities": ["READ_REPOSITORY", "READ_EVIDENCE"]}}


def bind(m=None, j=None, w=None, **kw):
    m = m if m is not None else manifest()
    j = j if j is not None else job()
    w = w if w is not None else work_item()
    return project_spec_job_binding(
        m, j, policy(), w, expected_factory_sha=FACTORY, expected_source_sha=SOURCE,
        validate_applab_work_item=kw.pop("validate_applab_work_item", lambda item: True), **kw
    )


class SpecLiteBindingTests(unittest.TestCase):
    def assertDeny(self, fragment, **args):
        with self.assertRaises(SpecBindingError) as caught:
            bind(**args)
        self.assertIn(fragment, str(caught.exception))


    def test_existing_historical_unmapped_required_kind_is_rejected(self):
        raw = json.loads((ROOT / "docs/spec_lite/agent-orchestration-contract/manifest.json").read_text())
        m = manifest()
        m["requirements"][0]["acceptance"] = raw["requirements"][0]["acceptance"]
        self.assertDeny("REQUIRED_CHECK_UNMAPPED", m=m)

    def test_duplicate_required_kind_is_rejected(self):
        m = manifest()
        m["validation"]["required_checks"].append("UNIT_TEST")
        self.assertDeny("DUPLICATE_REQUIRED_CHECK", m=m)

    def test_delta_lineage_is_traced_but_not_trusted(self):
        m = manifest()
        m["requirements"][0]["delta"] = {
            "operation": "MODIFIED",
            "previous": {"spec_id": m["spec_id"], "requirement_id": "FR-001",
                         "source_sha": "1" * 40},
            "reason": "Source-only delta lineage comparison across bounded adapters.",
        }
        projection = bind(m=m)
        self.assertEqual(projection["delta_lineage"][0]["operation"], "MODIFIED")
        self.assertEqual(projection["delta_lineage"][0]["previous"]["source_sha"], "1"*40)
        self.assertFalse(projection["previous_state_verified"])

    def test_delta_without_prior_identity_is_denied(self):
        m = manifest()
        m["requirements"][0]["delta"] = {
            "operation": "MODIFIED", "previous": None,
            "reason": "Source-only comparison without canonical record must block.",
        }
        self.assertDeny("PREVIOUS_REQUIREMENT_IDENTITY_REQUIRED", m=m)

    def test_delta_with_unpinned_current_state_is_denied(self):
        m = manifest()
        m["requirements"][0]["delta"] = {
            "operation": "MODIFIED",
            "previous": {"spec_id": m["spec_id"], "requirement_id": "FR-001",
                         "source_sha": SOURCE},
            "reason": "Current source reference cannot masquerade as prior state.",
        }
        self.assertDeny("DELTA_NOT_PINNED_TO_PRIOR_STATE", m=m)

    def test_delta_replay_conflict_tracks_prior_identity(self):
        m = manifest()
        m["requirements"][0]["delta"] = {
            "operation": "ADDED", "previous": None,
            "reason": "New optional traceable requirement with no canonical predecessor.",
        }
        first = bind(m=m)
        changed = copy.deepcopy(m)
        changed["requirements"][0]["delta"]["reason"] += " changed"
        self.assertDeny("REPLAY_IDENTITY_CONFLICT", m=changed,
                        trusted_prior_binding=first)

    def test_readonly_projection_has_no_runtime_or_approval_claim(self):
        p = bind()
        self.assertEqual(p["authority"], "TRACE_ONLY")
        self.assertEqual(len(p["acceptance"]), 5)
        self.assertFalse(p["dispatch_performed"])
        self.assertFalse(p["runtime_verified"])
        self.assertFalse(p["certified"])
        self.assertFalse(p["side_effects_performed"])

    def test_identical_replay_is_stable_and_read_only(self):
        first = bind()
        retry = bind(trusted_prior_binding=first)
        self.assertEqual(first["binding_id"], retry["binding_id"])
        self.assertEqual(retry["replay_status"], "IDENTICAL_REPLAY")

    def test_replay_changed_spec_refused_without_new_queue(self):
        earlier = bind()
        changed = manifest()
        changed["requirements"][0]["acceptance"][0]["criterion"] += " changed"
        self.assertDeny("REPLAY_IDENTITY_CONFLICT", m=changed, trusted_prior_binding=earlier)

    def test_untrusted_or_out_of_scope_path_denied(self):
        self.assertDeny("SPEC_SCOPE_DENIED", j=job(paths=["scripts/private.py"]))
        self.assertDeny("UNSAFE_JOB_PATH", j=job(paths=["../secret"]))

    def test_forbidden_nested_directory_blocks_parent_job_scope(self):
        m = manifest()
        m["scope"]["allowed_paths"] = ["docs/**"]
        m["scope"]["forbidden_paths"] = ["docs/private/**"]
        j = job(paths=["docs"])
        self.assertDeny("SPEC_SCOPE_DENIED", m=m, j=j)

    def test_forbidden_exact_file_blocks_recursive_parent_scope(self):
        m = manifest()
        m["scope"]["allowed_paths"] = ["docs/**"]
        m["scope"]["forbidden_paths"] = ["docs/secrets.txt"]
        self.assertDeny("SPEC_SCOPE_DENIED", m=m, j=job(paths=["docs"]))

    def test_safe_sibling_of_forbidden_tree_is_accepted(self):
        m = manifest()
        m["scope"]["allowed_paths"] = ["docs/**"]
        m["scope"]["forbidden_paths"] = ["docs/private/**"]
        p = bind(m=m, j=job(paths=["docs/public"]))
        self.assertEqual(p["authority"], "TRACE_ONLY")

    def test_job_wildcard_untrusted_scope_refused(self):
        m = manifest()
        m["scope"]["allowed_paths"] = ["docs/**"]
        self.assertDeny("UNSAFE_JOB_PATH", m=m, j=job(paths=["docs/**"]))

    def test_source_sha_mismatch_refused(self):
        m = manifest()
        m["target"]["source_sha"] = "b" * 40
        self.assertDeny("SOURCE_OR_REPOSITORY_MISMATCH", m=m)
        w = work_item()
        w["resolved_sha"] = "b" * 40
        self.assertDeny("APPLAB_WORKITEM_IDENTITY_MISMATCH", w=w)

    def test_factory_sha_drift_refused(self):
        m = manifest()
        m["factory"]["sha"] = "b" * 40
        self.assertDeny("FACTORY_SPEC_DRIFT", m=m)

    def test_missing_required_test_kind_denied(self):
        m = manifest()
        m["validation"]["required_checks"] = ["SOURCE_TEST"]
        self.assertDeny("ACCEPTANCE_TEST_GAP", m=m)

    def test_missing_acceptance_denied(self):
        m = manifest()
        m["requirements"][0]["acceptance"] = []
        self.assertDeny("ACCEPTANCE_MISSING", m=m)

    def test_read_workitem_cannot_contain_edit_capability(self):
        w = work_item()
        w["authority_envelope"]["allowed_capabilities"].append("ALLOW_CODE_EDIT")
        self.assertDeny("WORKITEM_UNEXPECTED_CAPABILITIES", w=w)

    def test_untrusted_applab_callback_denied(self):
        self.assertDeny("APPLAB_WORKITEM_VALIDATION_REQUIRED",
                        validate_applab_work_item=lambda item: False)

    def test_write_requires_independent_product_approval(self):
        self.assertDeny("TRUSTED_PRODUCT_APPROVAL_REQUIRED", j=job(mode="propose_diff"))

    def test_write_manifest_marker_does_not_replace_trusted_decision(self):
        m = manifest()
        m["approval"] = {"status": "APPROVED", "decision_ref": "https://github.com/a/b/issues/42"}
        m["requirements"][0]["status"] = "APPROVED"
        self.assertDeny("TRUSTED_PRODUCT_APPROVAL_REQUIRED", m=m, j=job(mode="propose_diff"))

    def test_trusted_product_lookup_does_not_replace_signed_gateway_receipt(self):
        m = manifest()
        m["approval"] = {"status": "APPROVED", "decision_ref": "https://github.com/a/b/issues/42"}
        m["requirements"][0]["status"] = "APPROVED"
        self.assertDeny("AGENT_GATEWAY_DENIED:TRUSTED_APPROVAL_REQUIRED", m=m, j=job(mode="propose_diff"),
                        trusted_product_decision=lambda _: True)

    def test_write_binding_requires_matching_applab_capability(self):
        m = manifest()
        m["approval"] = {"status": "APPROVED", "decision_ref": "https://github.com/a/b/issues/42"}
        m["requirements"][0]["status"] = "APPROVED"
        j = job(mode="propose_diff")
        now = datetime.now(timezone.utc)
        signed = {"schema_version": 1, "job_sha256": job_digest(j), "repository": REPO,
                  "source_sha": SOURCE, "mode": "propose_diff",
                  "allowed_paths": j["target"]["allowed_paths"], "reviewer": "test-maintainer",
                  "review_url": "https://github.com/a/b/pull/42",
                  "expires_at": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")}
        signed["hmac_sha256"] = hmac.new(KEY, canonical(signed), hashlib.sha256).hexdigest()
        self.assertDeny("WORKITEM_WRITE_CAPABILITY_REQUIRED", m=m, j=j, receipt=signed,
                        verifier_key=KEY, trusted_product_decision=lambda _: True)

    def test_valid_signed_write_remains_trace_only_not_dispatch(self):
        m = manifest()
        m["approval"] = {"status": "APPROVED", "decision_ref": "https://github.com/a/b/issues/42"}
        m["requirements"][0]["status"] = "APPROVED"
        j = job(mode="propose_diff")
        now = datetime.now(timezone.utc)
        signed = {"schema_version": 1, "job_sha256": job_digest(j), "repository": REPO,
                  "source_sha": SOURCE, "mode": "propose_diff",
                  "allowed_paths": j["target"]["allowed_paths"], "reviewer": "test-maintainer",
                  "review_url": "https://github.com/a/b/pull/42",
                  "expires_at": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")}
        signed["hmac_sha256"] = hmac.new(KEY, canonical(signed), hashlib.sha256).hexdigest()
        w = work_item()
        w["authority_envelope"]["allowed_capabilities"].append("ALLOW_CODE_EDIT")
        result = bind(m=m, j=j, w=w, receipt=signed, verifier_key=KEY,
                      trusted_product_decision=lambda _: True)
        self.assertFalse(result["dispatch_performed"])
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(result["authority"], "TRACE_ONLY")


if __name__ == "__main__":
    unittest.main()
