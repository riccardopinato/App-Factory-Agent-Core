"""Factory Spec Lite -> existing AppLab WorkItem reference (X10/Step 4).

No scheduling, shell, mutation, evidence verification or approval issuance. A
trusted caller obtains the immutable operation/work item from AppLab and
provides the real AppLab validator plus an independently authenticated
product-decision lookup. All actual job admission delegates to X10-010.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

try:
    from scripts.agent_job_gateway import evaluate, job_digest, safe_path
except ModuleNotFoundError:
    from agent_job_gateway import evaluate, job_digest, safe_path

SHA = re.compile(r"^[0-9a-f]{40}$")
SPEC = re.compile(r"^FSL-[A-Z0-9][A-Z0-9-]{5,63}$")
RID = re.compile(r"^FR-[0-9]{3}$")
ACID = re.compile(r"^AC-[0-9]{3}$")
CHECKS = frozenset({
    "SOURCE_TEST", "UNIT_TEST", "INTEGRATION_TEST", "RUNTIME_TEST",
    "DEVICE_TEST", "PROVIDER_TEST", "MANUAL_ACCEPTANCE"
})
MUTATING = frozenset({"propose_diff", "prepare_pr"})
NO_READ_EDIT = frozenset({"ALLOW_CODE_EDIT", "CREATE_DRAFT_PR", "UPDATE_DRAFT_PR"})


class SpecBindingError(ValueError):
    """Proposed bridge rejected; AppLab and Agent gateway remain authorities."""


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _covered(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        base = pattern[:-3]
        return path == base or path.startswith(base + "/")
    return path == pattern


def _overlaps_recursive_scope(job_path: str, excluded: str) -> bool:
    """A requested directory grants recursive access; descendants also matter."""
    excluded_root = excluded[:-3] if excluded.endswith("/**") else excluded
    return (job_path == excluded_root
            or job_path.startswith(excluded_root + "/")
            or excluded_root.startswith(job_path + "/"))


def project_spec_job_binding(
    manifest: dict[str, Any],
    job: dict[str, Any],
    trusted_policy: dict[str, Any],
    work_item: dict[str, Any],
    *,
    expected_factory_sha: str,
    expected_source_sha: str,
    validate_applab_work_item: Callable[[dict[str, Any]], bool],
    trusted_prior_binding: dict[str, Any] | None = None,
    trusted_product_decision: Callable[[dict[str, Any]], bool] | None = None,
    receipt: dict[str, Any] | None = None,
    verifier_key: bytes | None = None,
) -> dict[str, Any]:
    """Build read-only traceability projection after existing authority gates.

    The caller MUST bind the work_item to a persisted AppLab operation using
    the existing queue/lease machinery. Passing a custom validation function
    must not be interpreted as runtime execution or product authorization.
    """
    if not all(isinstance(v, dict) for v in (manifest, job, trusted_policy, work_item)):
        raise SpecBindingError("MALFORMED_INPUT")
    if not (isinstance(expected_factory_sha, str) and SHA.fullmatch(expected_factory_sha)
            and isinstance(expected_source_sha, str) and SHA.fullmatch(expected_source_sha)):
        raise SpecBindingError("TRUSTED_BASELINE_REQUIRED")
    target = manifest.get("target", {})
    factory = manifest.get("factory", {})
    refs = manifest.get("canonical_refs", {})
    if not all(isinstance(x, dict) for x in (target, factory, refs)):
        raise SpecBindingError("INVALID_MANIFEST")
    if (manifest.get("schema_version") != 1
        or not isinstance(manifest.get("spec_id"), str)
        or not SPEC.fullmatch(manifest["spec_id"])
        or factory.get("repository") != "riccardopinato/App-Factory-Core"
        or factory.get("sha") != expected_factory_sha
        or refs.get("factory_current", {}).get("sha") != expected_factory_sha
        or refs.get("factory_current", {}).get("path") != "CURRENT.yaml"):
        raise SpecBindingError("FACTORY_SPEC_DRIFT")
    if (target.get("source_sha") != expected_source_sha
        or target.get("repository") != job.get("target", {}).get("repository")
        or job.get("target", {}).get("source_sha") != expected_source_sha):
        raise SpecBindingError("SOURCE_OR_REPOSITORY_MISMATCH")
    if manifest.get("mode") not in {"FAST", "STANDARD", "CONTROLLED"}:
        raise SpecBindingError("UNSUPPORTED_SPEC_MODE")
    flags = manifest.get("risk", {})
    if not isinstance(flags, dict) or set(flags) != {
        "data_loss","security","billing","native_lifecycle","migration","sensitive_data","release"
    } or not all(type(v) is bool for v in flags.values()):
        raise SpecBindingError("BAD_RISK_PROFILE")
    if any(flags.values()) and manifest["mode"] != "CONTROLLED":
        raise SpecBindingError("HIGH_RISK_MODE_MISMATCH")

    scope = manifest.get("scope", {})
    if not isinstance(scope, dict):
        raise SpecBindingError("SCOPE_MISSING")
    allow = scope.get("allowed_paths")
    deny = scope.get("forbidden_paths")
    paths = job.get("target", {}).get("allowed_paths", [])
    if not isinstance(allow, list) or not allow or not isinstance(deny, list) or not isinstance(paths, list) or not paths:
        raise SpecBindingError("SCOPE_MISSING")
    if any(not isinstance(p, str) or not safe_path(p) or "*" in p for p in paths):
        raise SpecBindingError("UNSAFE_JOB_PATH")
    if any(not isinstance(p, str) or not p or ".." in p.split("/") or p.startswith("/") or "\\" in p
           or ("*" in p and not p.endswith("/**")) for p in allow + deny):
        raise SpecBindingError("UNSAFE_SPEC_PATH")
    if any(not any(_covered(p, allowed) for allowed in allow)
           or any(_overlaps_recursive_scope(p, blocked) for blocked in deny) for p in paths):
        raise SpecBindingError("SPEC_SCOPE_DENIED")

    requirements = manifest.get("requirements")
    checks = manifest.get("validation", {})
    if not isinstance(requirements, list) or not requirements or not isinstance(checks, dict):
        raise SpecBindingError("REQUIREMENTS_MISSING")
    required = checks.get("required_checks")
    if not isinstance(required, list) or not required or not set(required).issubset(CHECKS):
        raise SpecBindingError("TEST_POLICY_MISSING")
    if len(set(required)) != len(required):
        raise SpecBindingError("DUPLICATE_REQUIRED_CHECK")
    ids: set[str] = set()
    ac_ids: set[str] = set()
    criteria: list[dict[str, str]] = []
    delta_lineage: list[dict[str, Any]] = []
    for req in requirements:
        if not isinstance(req, dict) or not RID.fullmatch(str(req.get("id",""))) or req["id"] in ids:
            raise SpecBindingError("DUPLICATE_OR_INVALID_REQUIREMENT")
        ids.add(req["id"])
        if req.get("conflicts_with"):
            raise SpecBindingError("UNRESOLVED_REQUIREMENT_CONFLICT")
        change = req.get("delta")
        if change is not None:
            if not isinstance(change, dict) or set(change) != {"operation", "previous", "reason"}:
                raise SpecBindingError("INVALID_REQUIREMENT_DELTA")
            operation, previous = change.get("operation"), change.get("previous")
            if operation not in {"ADDED", "MODIFIED", "REMOVED", "RENAMED"}:
                raise SpecBindingError("INVALID_REQUIREMENT_DELTA")
            if not isinstance(change.get("reason"), str) or len(change["reason"]) < 12:
                raise SpecBindingError("INVALID_REQUIREMENT_DELTA")
            if operation == "ADDED":
                if previous is not None:
                    raise SpecBindingError("ADDED_DELTA_WITH_PREVIOUS")
            else:
                if (not isinstance(previous, dict)
                    or set(previous) != {"spec_id", "requirement_id", "source_sha"}
                    or not SPEC.fullmatch(str(previous.get("spec_id", "")))
                    or not RID.fullmatch(str(previous.get("requirement_id", "")))
                    or not SHA.fullmatch(str(previous.get("source_sha", "")))):
                    raise SpecBindingError("PREVIOUS_REQUIREMENT_IDENTITY_REQUIRED")
                if (previous["spec_id"] == manifest["spec_id"]
                    and previous["requirement_id"] == req["id"]
                    and previous["source_sha"] == expected_source_sha):
                    raise SpecBindingError("DELTA_NOT_PINNED_TO_PRIOR_STATE")
            if operation == "REMOVED" and manifest["mode"] == "FAST":
                raise SpecBindingError("REMOVAL_NOT_FAST")
            delta_lineage.append({
                "requirement_id": req["id"], "operation": operation,
                "previous": previous, "previous_state_verified": False
            })
        ac_list = req.get("acceptance")
        if not isinstance(ac_list, list) or not ac_list:
            raise SpecBindingError("ACCEPTANCE_MISSING")
        for ac in ac_list:
            if (not isinstance(ac, dict)
                or not ACID.fullmatch(str(ac.get("id","")))
                or ac["id"] in ac_ids):
                raise SpecBindingError("DUPLICATE_OR_INVALID_ACCEPTANCE")
            ac_ids.add(ac["id"])
            if ac.get("evidence_type") not in required:
                raise SpecBindingError("ACCEPTANCE_TEST_GAP")
            criteria.append({"requirement_id": req["id"], "acceptance_id": ac["id"],
                             "required_check": ac["evidence_type"]})

    # A declared required kind without an AC may falsely suggest complete coverage.
    if set(required) - {criterion["required_check"] for criterion in criteria}:
        raise SpecBindingError("REQUIRED_CHECK_UNMAPPED")

    write = job.get("mode") in MUTATING
    approval = manifest.get("approval", {})
    if write and (
        not isinstance(approval, dict) or approval.get("status") != "APPROVED"
        or any(req.get("status") != "APPROVED" for req in requirements)
        or not callable(trusted_product_decision)
        or trusted_product_decision(manifest) is not True
    ):
        raise SpecBindingError("TRUSTED_PRODUCT_APPROVAL_REQUIRED")
    if write and manifest["mode"] == "CONTROLLED" and (
        checks.get("manual_gate") is not True or
        not isinstance(checks.get("rollback_plan"), str) or len(checks["rollback_plan"]) < 30
    ):
        raise SpecBindingError("CONTROLLED_GATES_MISSING")
    decision = evaluate(job, trusted_policy, receipt=receipt, verifier_key=verifier_key)
    if decision.get("authorized") is not True:
        raise SpecBindingError("AGENT_GATEWAY_DENIED:" + str(decision.get("reason")))
    if not callable(validate_applab_work_item) or validate_applab_work_item(work_item) is not True:
        raise SpecBindingError("APPLAB_WORKITEM_VALIDATION_REQUIRED")
    if (work_item.get("record_type") != "APPLAB_WORK_ITEM"
        or work_item.get("repository") != target["repository"]
        or work_item.get("resolved_sha") != expected_source_sha
        or work_item.get("authority") != "ORCHESTRATION_ONLY"
        or not isinstance(work_item.get("operation_id"), str)
        or not isinstance(work_item.get("work_item_id"), str)):
        raise SpecBindingError("APPLAB_WORKITEM_IDENTITY_MISMATCH")
    permissions = work_item.get("authority_envelope", {}).get("allowed_capabilities", [])
    if not isinstance(permissions, list) or (not write and NO_READ_EDIT.intersection(permissions)):
        raise SpecBindingError("WORKITEM_UNEXPECTED_CAPABILITIES")
    if (job["mode"] == "propose_diff" and "ALLOW_CODE_EDIT" not in permissions
        or job["mode"] == "prepare_pr" and "CREATE_DRAFT_PR" not in permissions):
        raise SpecBindingError("WORKITEM_WRITE_CAPABILITY_REQUIRED")

    fingerprint = _digest(manifest)
    idem = job.get("idempotency_key")
    if not isinstance(idem, str):
        raise SpecBindingError("JOB_IDEMPOTENCY_REQUIRED")
    binding_id = "fsl_" + _digest({"spec_id": manifest["spec_id"], "job_idempotency_key": idem,
                                  "repository": target["repository"], "source_sha": expected_source_sha})[:32]
    binding = {
        "schema_version": 1, "record_type": "FSL_WORK_ITEM_TRACE_PROJECTION",
        "binding_id": binding_id, "spec_id": manifest["spec_id"],
        "spec_sha256": fingerprint, "job_sha256": job_digest(job),
        "repository": target["repository"], "source_sha": expected_source_sha,
        "work_item_id": work_item["work_item_id"], "operation_id": work_item["operation_id"],
        "acceptance": criteria, "required_checks": sorted(set(required)),
        "delta_lineage": delta_lineage, "previous_state_verified": False,
        "authority": "TRACE_ONLY", "source_verified": False,
        "runtime_verified": False, "side_effects_performed": False,
        "dispatch_performed": False, "certified": False,
    }
    if trusted_prior_binding is not None:
        if not isinstance(trusted_prior_binding, dict) or any(
            trusted_prior_binding.get(key) != value for key, value in binding.items()
        ):
            raise SpecBindingError("REPLAY_IDENTITY_CONFLICT")
        binding["replay_status"] = "IDENTICAL_REPLAY"
    else:
        binding["replay_status"] = "UNPERSISTED_PROPOSAL"
    return binding
