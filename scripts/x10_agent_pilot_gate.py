#!/usr/bin/env python3
"""X10-046/047: fail-closed acceptance of two real agent-assisted PR pilots.

Reuses the existing Agent Core gateway, AppLab draft PR steward, trusted QA and
the CODEX exact-head review. Does not run the Windows worker or create any PR.
"""
from __future__ import annotations
import hashlib
import json
import re
from typing import Any, Callable

try:
    from scripts.agent_job_gateway import safe_path
except ModuleNotFoundError:
    from agent_job_gateway import safe_path

SHA = re.compile(r"[a-f0-9]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
OP = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
ALLOWED = frozenset(("X10-046", "X10-047"))

class PilotEvidenceError(ValueError):
    pass

def _require(ok: bool, code: str) -> None:
    if not ok:
        raise PilotEvidenceError(code)

def assess(records: list[dict[str, Any]], *,
           trusted_evidence_resolver: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """Only observed exact-run data can be reviewed; never self-certifies the agent."""
    _require(isinstance(records, list) and 1 <= len(records) <= 2,
             "PILOT_LENGTH_INVALID")
    _require(callable(trusted_evidence_resolver), "INDEPENDENT_RESOLVER_REQUIRED")
    seen_repos = set()
    output = []
    for index, row in enumerate(records):
        expected_task = "X10-046" if index == 0 else "X10-047"
        _require(isinstance(row, dict) and set(row) == {
            "task_id", "repository", "base_sha", "pr_head_sha",
            "operation_id", "worker_run_url", "qa_run_url", "pr_url",
            "changed_files", "changed_line_count", "attempt_count",
            "risk", "draft_pr_only", "agent_patch_applied",
            "independent_qa_state", "codex_review_state", "human_acceptance",
            "merge_performed", "release_performed",
        }, "PILOT_RECEIPT_SCHEMA_INVALID")
        name, source, head = row["repository"], row["base_sha"], row["pr_head_sha"]
        _require(row["task_id"] == expected_task
                 and isinstance(name, str) and REPO.fullmatch(name) is not None
                 and isinstance(source, str) and SHA.fullmatch(source) is not None
                 and isinstance(head, str) and SHA.fullmatch(head) is not None and source != head,
                 "PILOT_IDENTITY_OR_ORDER_INVALID")
        lowered = name.casefold()
        _require(lowered not in seen_repos, "PILOT_REPOSITORY_MUST_DIFFER")
        seen_repos.add(lowered)
        _require(isinstance(row["operation_id"], str)
                 and OP.fullmatch(row["operation_id"]) is not None
                 and row["risk"] == "LOW"
                 and type(row["attempt_count"]) is int and 1 <= row["attempt_count"] <= 2
                 and type(row["changed_line_count"]) is int
                 and 1 <= row["changed_line_count"] <= 250,
                 "PILOT_SCOPE_OR_ATTEMPT_BUDGET_INVALID")
        files = row["changed_files"]
        _require(isinstance(files, list) and 1 <= len(files) <= 5
                 and len(set(files)) == len(files)
                 and all(isinstance(p, str) and 1 <= len(p) <= 240
                         and safe_path(p)
                         and not p.endswith((".key", ".env"))
                         for p in files), "PILOT_PATHS_NOT_SAFE")
        _require(row["pr_url"].startswith(f"https://github.com/{name}/pull/")
                 and re.fullmatch(r"[1-9][0-9]*", row["pr_url"].rsplit("/", 1)[-1]) is not None
                 and isinstance(row["worker_run_url"], str)
                 and row["worker_run_url"].startswith("https://")
                 and isinstance(row["qa_run_url"], str)
                 and row["qa_run_url"].startswith("https://github.com/")
                 and "/actions/runs/" in row["qa_run_url"],
                 "PILOT_RUN_URLS_INVALID")
        _require(row["draft_pr_only"] is True
                 and row["agent_patch_applied"] is True
                 and row["merge_performed"] is False
                 and row["release_performed"] is False
                 and row["independent_qa_state"] == "PASS"
                 and row["codex_review_state"] == "NO_FINDINGS",
                 "PILOT_WORKER_OR_QA_NOT_VERIFIED")
        verified = trusted_evidence_resolver(row)
        _require(isinstance(verified, dict)
                 and verified.get("verified") is True
                 and verified.get("task_id") == expected_task
                 and verified.get("repository") == name
                 and verified.get("base_sha") == source
                 and verified.get("pr_head_sha") == head
                 and verified.get("operation_id") == row["operation_id"]
                 and verified.get("worker_run_url") == row["worker_run_url"]
                 and verified.get("qa_run_url") == row["qa_run_url"]
                 and verified.get("pr_url") == row["pr_url"]
                 and verified.get("independent_review_verified") is True,
                 "PILOT_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED")
        if index > 0:
            _require(records[0]["human_acceptance"] is True,
                     "PILOT_A_HUMAN_GATE_NOT_ACCEPTED")
        output.append({
            "task_id": expected_task, "repository": name,
            "source_sha": source, "pr_head_sha": head,
            "pr_url": row["pr_url"], "agent_worker_reported": True,
            "owner_acceptance_reported": row["human_acceptance"] is True,
            "code_quality_source_only": True,
        })
    return {
        "schema_version": 1, "record_type": "X10_TWO_REPO_AGENT_PILOT_ASSESSMENT",
        "authority": "REPORT_ONLY",
        "state": "INDEPENDENT_PILOT_EVIDENCE_FOR_OWNER_REVIEW",
        "pilots": output,
        "two_repos_distinct": len(seen_repos) == 2,
        "real_windows_worker_verified_by_this_module": False,
        "human_acceptance_minted": False,
        "merge_authorized": False, "release_authorized": False,
        "note": "The host must authenticate independent receipts and apply each human gate; "
                "this module neither runs the agent nor verifies physical device.",
    }
