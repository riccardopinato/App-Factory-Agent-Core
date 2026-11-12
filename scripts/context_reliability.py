#!/usr/bin/env python3
"""Pure, offline policy decisions for the App Factory metadata-only snapshot.

These functions DO NOT run workflows, mutate GitHub or award any evidence level.
Callers must perform GitHub operations using scoped credentials and normal PR gates.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

SHA = re.compile(r"^[a-f0-9]{40}$")
SAFE_EVENTS = frozenset(("schedule", "workflow_dispatch", "push"))
PROTECTED_PREFIXES = ("golden/", "master/", "v27/", "12-CAPABILITY-E-IMPLEMENTAZIONI/")
FORBIDDEN_EVIDENCE = frozenset(("CI_VERIFIED", "DEVICE_VERIFIED", "RELEASE", "CERTIFIED_GOLDEN", "CERTIFIED_DONOR"))
MAX_RETRIES = 3


def is_sha(value: str) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def retry_policy(status: int | None, attempt: int, retry_after: int | None = None) -> dict[str, Any]:
    """Bounded transient failure policy; caller chooses whether to sleep."""
    if not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    if status in (401, 403, 404, 422):
        return {"retry": False, "delay_seconds": 0, "reason": "TERMINAL_AUTH_OR_REQUEST"}
    if status == 429 or (isinstance(status, int) and 500 <= status <= 599):
        if attempt >= MAX_RETRIES:
            return {"retry": False, "delay_seconds": 0, "reason": "RETRY_BUDGET_EXHAUSTED"}
        delay = min(120, max(1, retry_after)) if isinstance(retry_after, int) else min(60, 2 ** attempt)
        return {"retry": True, "delay_seconds": delay, "reason": "TRANSIENT"}
    return {"retry": False, "delay_seconds": 0, "reason": "NOT_RETRYABLE"}


def reconcile(*, source_sha: str, base_sha: str, branch_exists: bool,
              snapshot_changed: bool, open_pr: bool, can_push: bool,
              can_create_pr: bool, branch_conflict: bool = False,
              read_ok: bool = True, event: str = "schedule") -> dict[str, Any]:
    """Plan one bounded reconciliation; NEVER claim PR creation without a receipt.

    A branch may have been pushed before PR create failed. A later run can recover
    and request PR creation without changing the snapshot (idempotent).
    """
    if not (is_sha(source_sha) and is_sha(base_sha)):
        return {"state": "BLOCKED_BAD_SHA", "action": "NONE", "verified": False}
    if event not in SAFE_EVENTS:
        return {"state": "BLOCKED_UNSUPPORTED_EVENT", "action": "NONE", "verified": False}
    if not read_ok:
        return {"state": "BLOCKED_SOURCE_READ", "action": "NONE", "verified": False}
    if branch_conflict:
        return {"state": "BLOCKED_BRANCH_CONFLICT", "action": "NONE", "verified": False}
    if not can_push and (snapshot_changed or (branch_exists and source_sha != base_sha)):
        return {"state": "BLOCKED_PUSH_PERMISSION", "action": "NONE", "verified": False}
    if not snapshot_changed and not branch_exists:
        return {"state": "NO_OP", "action": "NONE", "verified": False}
    if open_pr:
        if not snapshot_changed and source_sha == base_sha:
            return {"state": "PR_EXISTS_UNCHANGED", "action": "NONE", "verified": False}
        return {"state": "PR_UPDATE_PENDING", "action": "UPDATE_BOT_BRANCH", "verified": False}
    if not can_create_pr:
        return {"state": "BLOCKED_PR_PERMISSION", "action": "PRESERVE_BOT_BRANCH", "verified": False}
    if not branch_exists or snapshot_changed or source_sha != base_sha:
        return {"state": "PR_CREATION_PENDING", "action": "CREATE_BOT_PR", "verified": False}
    return {"state": "NO_OP", "action": "NONE", "verified": False}


def semantic_review(source_sha: str, changed_paths: Iterable[str],
                    evidence_refs: Iterable[str] = ()) -> dict[str, Any]:
    """Propose a review task. An SHA change alone cannot mint approval or PASS."""
    if not is_sha(source_sha):
        raise ValueError("invalid source SHA")
    paths = sorted(set(changed_paths))
    if not all(isinstance(p, str) and p and not p.startswith("/") and ".." not in p.split("/") for p in paths):
        raise ValueError("invalid relative path")
    refs = sorted(set(evidence_refs))
    if not all(isinstance(v, str) and v.startswith("https://github.com/") for v in refs):
        raise ValueError("evidence refs must be canonical GitHub URLs")
    protected = sorted(p for p in paths if p.startswith(PROTECTED_PREFIXES))
    return {
        "schema": 1, "source_sha": source_sha, "paths_changed": paths,
        "evidence_refs": refs, "protected_paths": protected,
        "state": "SEMANTIC_REVIEW_PENDING" if paths else "NO_CHANGE",
        "requires_human_review": bool(paths),
        "inferred_evidence": None, "auto_merge": False, "auto_promote": False,
        "proposal_only": True,
    }


def safe_public_status(*, repository: str | None, visibility: str,
                       workflow_state: str, source_url: str | None) -> dict[str, str | None]:
    """Never publish private repository identities or internal URLs."""
    if visibility not in ("public", "private"):
        raise ValueError("invalid visibility")
    if visibility == "private":
        return {"repository": None, "visibility": "private", "workflow_state": workflow_state,
                "source_url": None}
    if not isinstance(repository, str) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("invalid public repository")
    if source_url and not source_url.startswith("https://github.com/" + repository + "/"):
        raise ValueError("source URL does not match repository")
    return {"repository": repository, "visibility": visibility,
            "workflow_state": workflow_state, "source_url": source_url}


def validate_receipt(payload: dict[str, Any]) -> bool:
    """True only for independently observed action receipt at exact commit/run."""
    if not isinstance(payload, dict):
        return False
    if not is_sha(payload.get("commit_sha")) or payload.get("event") not in SAFE_EVENTS:
        return False
    if payload.get("result") != "success" or payload.get("run_url") is None:
        return False
    if not str(payload["run_url"]).startswith("https://github.com/"):
        return False
    if payload.get("evidence_level") in FORBIDDEN_EVIDENCE:
        return False
    return True
