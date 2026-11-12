#!/usr/bin/env python3
"""X10-014: admission adapter for the ALREADY existing AppLab v6.0E draft PR steward.

No new PR engine, scheduler, GitHub API client, merge, release or self approval.
The caller must inject a trusted persisted-operation lookup and the PINNED AppLab
execute_remote implementation. Fixture tests are not live AppLab/Windows evidence.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.agent_job_gateway import evaluate, job_digest, safe_path
except ModuleNotFoundError:
    from agent_job_gateway import evaluate, job_digest, safe_path

SHA = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
OP_ID = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")
STATES = frozenset({"DRAFT_PR_CREATED", "DRAFT_PR_UPDATED"})
FORBIDDEN = frozenset({
    "SELF_APPROVE", "SELF_MERGE", "RELEASE", "WRITE_MAIN", "WRITE_FACTORY_CORE",
    "READ_SECRETS", "EDIT_WORKFLOW", "EDIT_BRANCH_PROTECTION", "WEAKEN_TESTS",
})


class AgentPRGateError(ValueError):
    """A failed gate; no execution permitted."""


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise AgentPRGateError(reason)


def propose_draft_pr(
    job: dict[str, Any], policy: dict[str, Any], *,
    receipt: dict[str, Any] | None, verifier_key: bytes | None,
    operation_id: str,
    trusted_operation_loader: Callable[[str, str], dict[str, Any]],
    pinned_applab_execute_remote: Callable[..., dict[str, Any]],
    repo_root: Path, patch_path: Path,
    chain_attempt_number: int, target_base_branch: str,
    title: str, body: str,
) -> dict[str, Any]:
    """Authorized PR-only delegation, with idempotence/retry owned by AppLab.

    Trusted loader must attest a persisted operation bound to the exact job
    digest, not forward an untrusted WorkItem from an event/LLM. A separate
    credentialed runner performs any real GitHub write via AppLab v6.0E.
    """
    _require(isinstance(job, dict) and job.get("mode") == "prepare_pr", "WRONG_MODE")
    decision = evaluate(job, policy, receipt=receipt, verifier_key=verifier_key)
    _require(decision.get("authorized") is True
             and decision.get("state") == "ADMITTED_FOR_SCOPED_PROPOSAL",
             "TRUSTED_PR_APPROVAL_REQUIRED")
    _require(isinstance(operation_id, str) and OP_ID.fullmatch(operation_id) is not None,
             "INVALID_OPERATION_ID")
    _require(type(chain_attempt_number) is int and chain_attempt_number in (1, 2),
             "RETRY_BUDGET_EXCEEDED")
    _require(target_base_branch == "main", "BASE_BRANCH_NOT_ALLOWED")
    _require(isinstance(title, str) and 5 <= len(title) <= 160
             and isinstance(body, str) and 1 <= len(body) <= 10000,
             "INVALID_PR_METADATA")
    _require(isinstance(repo_root, Path) and isinstance(patch_path, Path)
             and patch_path.is_file() and not patch_path.is_symlink()
             and patch_path.stat().st_size <= 512000, "INVALID_PATCH")
    digest = job_digest(job)
    bound = trusted_operation_loader(operation_id, digest)
    _require(isinstance(bound, dict)
             and bound.get("operation_id") == operation_id
             and bound.get("job_sha256") == digest, "UNBOUND_OPERATION")
    target = job["target"]
    _require(bound.get("repository") == target["repository"]
             and bound.get("source_sha") == target["source_sha"],
             "PERSISTED_SOURCE_MISMATCH")
    work = bound.get("work_item")
    repair = bound.get("repair_result")
    _require(isinstance(work, dict) and isinstance(repair, dict),
             "MISSING_TRUSTED_WORK_GRAPH")
    wid = work.get("work_item_id")
    _require(isinstance(wid, str) and bool(wid)
             and work.get("repository") == target["repository"]
             and work.get("resolved_sha") == target["source_sha"],
             "WORK_GRAPH_IDENTITY_MISMATCH")
    caps = work.get("authority_envelope", {}).get("allowed_capabilities")
    need = "CREATE_DRAFT_PR" if chain_attempt_number == 1 else "UPDATE_DRAFT_PR"
    _require(isinstance(caps, list) and len(set(map(str, caps))) == len(caps)
             and need in caps and not (set(caps) & FORBIDDEN),
             "DRAFT_PR_CAPABILITY_DENIED")
    _require(repair.get("record_type") == "BOUNDED_FIX_RESULT_V60C"
             and repair.get("state") == "READY_FOR_VERIFICATION"
             and repair.get("repository") == target["repository"]
             and repair.get("resolved_sha") == target["source_sha"]
             and repair.get("work_item_id") == wid
             and type(repair.get("attempt_number")) is int
             and repair["attempt_number"] == chain_attempt_number,
             "REPAIR_RESULT_MISMATCH")
    patch_digest = repair.get("result_patch_sha256")
    _require(isinstance(patch_digest, str) and SHA256.fullmatch(patch_digest) is not None
             and hashlib.sha256(patch_path.read_bytes()).hexdigest() == patch_digest,
             "PATCH_PROVENANCE_MISMATCH")
    paths = repair.get("changed_files")
    _require(isinstance(paths, list) and 0 < len(paths) <= 5
             and all(isinstance(p, str) and safe_path(p)
                     and any(p == root or p.startswith(root + "/")
                             for root in target["allowed_paths"]) for p in paths),
             "PATCH_OUT_OF_SCOPE")
    root_id, root_sha = bound.get("root_work_item_id"), bound.get("root_source_sha")
    _require(isinstance(root_id, str) and bool(root_id)
             and isinstance(root_sha, str) and SHA.fullmatch(root_sha) is not None,
             "ROOT_IDENTITY_INVALID")

    result = pinned_applab_execute_remote(
        repo_root, work, repair, patch_path,
        chain_attempt_number=chain_attempt_number,
        root_work_item_id=root_id, root_resolved_sha=root_sha,
        target_base_branch=target_base_branch, title=title, body=body,
    )
    # A transport that writes a branch but returns a malformed receipt is NOT
    # certified. Durable recovery and PR identity must be reconciled in AppLab.
    _require(isinstance(result, dict) and result.get("schema_version") == 1
             and result.get("record_type") == "DRAFT_PR_MATERIALIZATION_V60E"
             and result.get("authority") == "DRAFT_BRANCH_AND_PR_ONLY"
             and result.get("state") in STATES
             and result.get("repository") == target["repository"]
             and result.get("work_item_id") == wid
             and result.get("parent_sha") == target["source_sha"]
             and result.get("result_patch_sha256") == patch_digest
             and result.get("chain_attempt_number") == chain_attempt_number
             and result.get("target_base_branch") == "main"
             and result.get("merge_performed") is False
             and result.get("release_performed") is False
             and result.get("self_approval_performed") is False
             and isinstance(result.get("repaired_source_sha"), str)
             and SHA.fullmatch(result["repaired_source_sha"]) is not None
             and result.get("remote_branch_sha") == result["repaired_source_sha"]
             and isinstance(result.get("repair_branch"), str)
             and result["repair_branch"].startswith("applab/repair/")
             and isinstance(result.get("pr_url"), str)
             and result["pr_url"].startswith("https://github.com/"),
             "UNTRUSTED_APPLAB_PR_RESULT")
    return {
        "state": "DRAFT_PR_RECORDED_NOT_APPROVED",
        "repository": target["repository"], "source_sha": target["source_sha"],
        "pr_head_sha": result["repaired_source_sha"],
        "pr_url": result["pr_url"], "repair_branch": result["repair_branch"],
        "next_gate": "INDEPENDENT_EXACT_HEAD_CI_AND_REVIEW",
        "merge_authorized": False, "release_authorized": False,
        "consumer_runtime_verified": False,
    }


def assess_exact_head_evidence(*, materialized: dict[str, Any],
                               pr: dict[str, Any],
                               check_runs: list[dict[str, Any]],
                               required_contexts: tuple[str, ...],
                               review: dict[str, Any]) -> dict[str, Any]:
    """Read-only evidence classifier. It NEVER executes or approves a merge.

    Inputs must be fetched by a trusted independent verifier from GitHub.
    Missing, duplicate, skipped or failed required contexts are blockers.
    """
    def pending(reason: str) -> dict[str, Any]:
        return {"state": "PENDING_INDEPENDENT_GATE", "reason": reason,
                "merge_performed": False, "certified": False}

    if not isinstance(materialized, dict) or not isinstance(pr, dict):
        return pending("MALFORMED_INPUT")
    head = materialized.get("pr_head_sha")
    if not isinstance(head, str) or not SHA.fullmatch(head):
        return pending("INVALID_HEAD")
    if (pr.get("head_sha") != head
            or pr.get("state") != "open" or pr.get("draft") is not True
            or pr.get("repository") != materialized.get("repository")
            or pr.get("head_branch") != materialized.get("repair_branch")
            or pr.get("base_branch") != "main"):
        return pending("PR_HEAD_OR_SCOPE_CHANGED")
    if (not isinstance(required_contexts, tuple) or not required_contexts
            or len(set(required_contexts)) != len(required_contexts)
            or any(not isinstance(c, str) or not c for c in required_contexts)):
        return pending("REQUIRED_CHECK_POLICY_INVALID")
    if not isinstance(check_runs, list):
        return pending("CHECKS_UNAVAILABLE")
    for name in required_contexts:
        matching = [x for x in check_runs if isinstance(x, dict)
                    and x.get("name") == name and x.get("head_sha") == head]
        if len(matching) != 1 or matching[0].get("status") != "completed" \
                or matching[0].get("conclusion") != "success":
            return pending("EXACT_HEAD_CHECK_MISSING_OR_NONPASS:" + name)
    if (not isinstance(review, dict)
            or review.get("commit_sha") != head
            or review.get("status") != "completed"
            or review.get("has_any_findings") is not False
            or review.get("has_unresolved_findings") is not False
            or review.get("independent") is not True):
        return pending("INDEPENDENT_REVIEW_NOT_CLEAR")
    return {"state": "SOURCE_CI_REVIEW_EVIDENCE_PRESENT",
            "pr_head_sha": head, "merge_performed": False,
            "certified": False, "next_gate": "REPOSITORY_MERGE_RULES"}
