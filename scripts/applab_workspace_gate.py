#!/usr/bin/env python3
"""X10-012: fail-closed entry/exit guard for AppLab's bounded worktree worker.

Reuses AppLab v6.0C apply_bounded_patch. No second patch engine, worktree
lifecycle, queue, git push, merge, release or self-issued approval.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.agent_job_gateway import evaluate, safe_path
except ModuleNotFoundError:
    from agent_job_gateway import evaluate, safe_path

SHA = re.compile(r"^[0-9a-f]{40}$")


class WorkspaceGateError(ValueError):
    pass


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=15, check=False,
    )
    if result.returncode:
        raise WorkspaceGateError("LOCAL_GIT_PREFLIGHT_FAILED")
    return result.stdout.strip()


def _preflight(repo_root: Path, patch_path: Path, expected_sha: str) -> None:
    if not isinstance(repo_root, Path) or repo_root.is_symlink() or not repo_root.is_dir():
        raise WorkspaceGateError("INVALID_REPO_ROOT")
    if not isinstance(patch_path, Path) or patch_path.is_symlink() or not patch_path.is_file():
        raise WorkspaceGateError("INVALID_PATCH_PATH")
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise WorkspaceGateError("INVALID_EXPECTED_SHA")
    resolved = repo_root.resolve(strict=True)
    if Path(_git(resolved, "rev-parse", "--show-toplevel")).resolve() != resolved:
        raise WorkspaceGateError("NOT_EXACT_GIT_ROOT")
    if _git(resolved, "rev-parse", "HEAD") != expected_sha:
        raise WorkspaceGateError("SOURCE_HEAD_CHANGED")
    if _git(resolved, "status", "--porcelain", "--untracked-files=no"):
        raise WorkspaceGateError("SOURCE_CHECKOUT_DIRTY")
    # Patch must be a bounded artifact outside the source tree. AppLab then
    # performs its own patch preflight and private worktree/rollback.
    target = patch_path.resolve(strict=True)
    if resolved == target or resolved in target.parents:
        raise WorkspaceGateError("PATCH_INSIDE_SOURCE_TREE")
    if target.stat().st_size > 512_000:
        raise WorkspaceGateError("PATCH_TOO_LARGE")
    target.read_text(encoding="utf-8", errors="strict")


def propose_in_applab_workspace(
    job: dict[str, Any], policy: dict[str, Any], *,
    receipt: dict[str, Any] | None, verifier_key: bytes | None,
    repo_root: Path, patch_path: Path, work_item: dict[str, Any],
    investigation: dict[str, Any], attempt_number: int,
    bounded_worker: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Invokes installed AppLab worker only after exact-SHA approval checks.

    Injection is for the real pinned AppLab implementation. A test stub can
    assert boundaries; it cannot certify that AppLab ran in a real checkout.
    """
    decision = evaluate(job, policy, receipt=receipt, verifier_key=verifier_key)
    if not decision.get("authorized") or decision.get("state") != "ADMITTED_FOR_SCOPED_PROPOSAL":
        raise WorkspaceGateError("TRUSTED_SCOPED_APPROVAL_REQUIRED")
    if job.get("mode") != "propose_diff":
        raise WorkspaceGateError("WRONG_ACTION")
    if type(attempt_number) is not int or not 1 <= attempt_number <= 2:
        raise WorkspaceGateError("ATTEMPT_BUDGET_EXCEEDED")
    target = job["target"]
    source_sha = target["source_sha"]
    _preflight(repo_root, patch_path, source_sha)
    if not isinstance(work_item, dict) or not isinstance(investigation, dict):
        raise WorkspaceGateError("INVALID_WORK_GRAPH")
    if (work_item.get("repository") != target["repository"]
            or work_item.get("resolved_sha") != source_sha
            or investigation.get("repository") != target["repository"]
            or investigation.get("resolved_sha") != source_sha):
        raise WorkspaceGateError("WORK_GRAPH_IDENTITY_MISMATCH")
    capabilities = work_item.get("authority_envelope", {}).get("allowed_capabilities", [])
    if not isinstance(capabilities, list) or "ALLOW_CODE_EDIT" not in capabilities:
        raise WorkspaceGateError("WORK_GRAPH_CODE_EDIT_DENIED")
    result = bounded_worker(
        repo_root, patch_path, work_item, investigation,
        attempt_number=attempt_number,
    )
    if not isinstance(result, dict) or result.get("record_type") != "BOUNDED_FIX_RESULT_V60C":
        raise WorkspaceGateError("UNTRUSTED_WORKER_RESULT")
    if (result.get("schema_version") != 1
            or result.get("authority") != "BRANCH_WORKSPACE_ONLY"
            or result.get("repository") != target["repository"]
            or result.get("resolved_sha") != source_sha
            or result.get("work_item_id") != work_item.get("work_item_id")
            or result.get("attempt_number") != attempt_number
            or result.get("remote_write_performed") is not False
            or result.get("verification_authority") != "UNCHANGED"
            or result.get("merge_performed") is True
            or result.get("release_performed") is True
            or result.get("state") not in {"NO_CHANGE", "READY_FOR_VERIFICATION"}):
        raise WorkspaceGateError("WORKER_RESULT_AUTHORITY_MISMATCH")
    if result["state"] == "READY_FOR_VERIFICATION":
        paths = result.get("changed_files")
        lines = result.get("changed_lines")
        scopes = target["allowed_paths"]
        if (result.get("mutation_scope") != "EPHEMERAL_LOCAL_WORKTREE_ONLY"
                or not isinstance(paths, list) or len(paths) > 5
                or not paths or len(set(paths)) != len(paths)
                or type(lines) is not int or not 0 <= lines <= 250
                or any(not safe_path(path) or not any(
                    path == scope or path.startswith(scope + "/") for scope in scopes)
                    for path in paths)):
            raise WorkspaceGateError("WORKSPACE_CHANGE_OUT_OF_SCOPE")
    # AppLab's worker removes its temporary worktree and branch in finally.
    # The source checkout must be unchanged even if the callback returned.
    _preflight(repo_root, patch_path, source_sha)
    return {"state": result["state"], "source_sha": source_sha,
            "changed_files": result.get("changed_files", []),
            "next_gate": "INDEPENDENT_APPLAB_VERIFICATION",
            "runtime_verified": False, "merge_performed": False,
            "remote_write_performed": False}
