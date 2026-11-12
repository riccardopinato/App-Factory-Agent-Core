#!/usr/bin/env python3
"""App Factory 10x X10-010: side-effect-free job authorization policy.

This is a decision boundary, NOT an executor and NOT a source of real user
approval. The runner must provide a protected policy and an HMAC key obtained
out of band. No external source or LLM is authorized to generate that key.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MODES = frozenset(("analyze", "run_tests", "propose_diff", "prepare_pr"))
READ_MODES = frozenset(("analyze", "run_tests"))
WRITE_MODES = MODES - READ_MODES
PROTECTED = frozenset(("AGENTS.md", "CURRENT.yaml", ".github", "golden",
                      "master", "governance", "contracts", ".env", "secrets"))
SHA256 = re.compile(r"^[a-f0-9]{64}$")
MAX_TIMEOUT = 900
MAX_ATTEMPTS = 2


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def job_digest(job: dict[str, Any]) -> str:
    """Canonical digest only; secret-free and stable across JSON key ordering."""
    return hashlib.sha256(canonical(job)).hexdigest()


def safe_path(value: str) -> bool:
    if not isinstance(value, str) or not value or len(value) > 256:
        return False
    if any(ch in value for ch in ("\\", "\x00", "\r", "\n")) or value.startswith(("/", "~")):
        return False
    if value.startswith("./") or "//" in value or "/./" in value:
        return False
    parts = PurePosixPath(value).parts
    if not parts or any(p in (".", "..", "") for p in parts):
        return False
    return all(p not in PROTECTED and not p.startswith(".") for p in parts)


def _reason(reason: str) -> dict[str, Any]:
    return {"authorized": False, "state": "BLOCKED", "reason": reason,
            "side_effects_performed": False, "runtime_verified": False}


def evaluate(job: dict[str, Any], policy: dict[str, Any],
             *, receipt: dict[str, Any] | None = None,
             verifier_key: bytes | None = None,
             now: datetime | None = None) -> dict[str, Any]:
    """Fail-closed, explicitly scoped policy; never calls AppLab or GitHub.

    HMAC is useful only when the verifier key is injected by a trusted runner
    and never supplied by the untrusted job or included in a repository.
    """
    if not isinstance(job, dict) or not isinstance(policy, dict):
        return _reason("MALFORMED_INPUT")
    if job.get("schema_version") != 1 or job.get("mode") not in MODES:
        return _reason("UNSUPPORTED_JOB")
    target, limits = job.get("target"), job.get("limits")
    if not isinstance(target, dict) or not isinstance(limits, dict):
        return _reason("INVALID_TARGET_OR_LIMITS")
    repo, sha = target.get("repository"), target.get("source_sha")
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        return _reason("INVALID_REPOSITORY")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        return _reason("INVALID_SHA")
    paths = target.get("allowed_paths", [])
    if not isinstance(paths, list) or not paths or len(paths) > 128 or len(paths) != len(set(map(str, paths))):
        return _reason("BAD_PATH_SET")
    if any(not safe_path(p) for p in paths):
        return _reason("UNSAFE_PATH")
    try:
        timeout = limits["timeout_seconds"]
        attempts = limits["max_attempts"]
        if type(timeout) is not int or type(attempts) is not int:
            raise ValueError
        if not (1 <= timeout <= MAX_TIMEOUT and 1 <= attempts <= MAX_ATTEMPTS):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        return _reason("BUDGET_EXCEEDED")
    summary = job.get("request", {}).get("summary", "") if isinstance(job.get("request"), dict) else None
    if not isinstance(summary, str) or len(summary) > 10000:
        return _reason("INVALID_REQUEST")
    if not isinstance(policy.get("repositories"), list) or not isinstance(policy.get("modes"), list):
        return _reason("INVALID_POLICY")
    if repo not in policy["repositories"] or job["mode"] not in policy["modes"]:
        return _reason("NOT_ALLOWLISTED")
    allowed = policy.get("allowed_paths", [])
    if not isinstance(allowed, list) or any(not safe_path(p) for p in allowed):
        return _reason("INVALID_POLICY_PATHS")
    if any(not any(p == scope or p.startswith(scope + "/") for scope in allowed) for p in paths):
        return _reason("PATH_OUT_OF_SCOPE")
    if job["mode"] in WRITE_MODES and not paths:
        return _reason("EMPTY_WRITE_SCOPE")
    # Read-only is only a planning admission; executor still needs source
    # checkout and isolation. This function cannot certify a runnable job.
    if job["mode"] in READ_MODES:
        return {"authorized": True, "state": "ADMITTED_FOR_ISOLATED_READ",
                "mode": job["mode"], "repository": repo, "source_sha": sha,
                "job_sha256": job_digest(job), "side_effects_performed": False,
                "runtime_verified": False}
    if not isinstance(verifier_key, bytes) or len(verifier_key) < 32 or not isinstance(receipt, dict):
        return _reason("TRUSTED_APPROVAL_REQUIRED")
    if receipt.get("schema_version") != 1 or receipt.get("job_sha256") != job_digest(job):
        return _reason("APPROVAL_JOB_MISMATCH")
    if receipt.get("repository") != repo or receipt.get("source_sha") != sha or receipt.get("mode") != job["mode"]:
        return _reason("APPROVAL_SCOPE_MISMATCH")
    if receipt.get("allowed_paths") != paths:
        return _reason("APPROVAL_PATH_MISMATCH")
    if not receipt.get("reviewer") or not receipt.get("review_url", "").startswith("https://github.com/"):
        return _reason("APPROVAL_PROVENANCE_MISSING")
    try:
        expiry = datetime.fromisoformat(receipt["expires_at"].replace("Z", "+00:00"))
        stamp = now or datetime.now(timezone.utc)
        if expiry.tzinfo is None or stamp.tzinfo is None or not stamp < expiry:
            return _reason("APPROVAL_EXPIRED")
        if (expiry - stamp).total_seconds() > 3600:
            return _reason("APPROVAL_TTL_TOO_LONG")
    except (KeyError, ValueError, TypeError):
        return _reason("APPROVAL_TIME_INVALID")
    mac = receipt.get("hmac_sha256")
    if not isinstance(mac, str) or not SHA256.fullmatch(mac):
        return _reason("APPROVAL_SIGNATURE_MISSING")
    signed = {k: v for k, v in receipt.items() if k != "hmac_sha256"}
    expected = hmac.new(verifier_key, canonical(signed), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return _reason("APPROVAL_SIGNATURE_INVALID")
    return {"authorized": True, "state": "ADMITTED_FOR_SCOPED_PROPOSAL",
            "mode": job["mode"], "repository": repo, "source_sha": sha,
            "job_sha256": job_digest(job), "side_effects_performed": False,
            "runtime_verified": False, "requires_runner_checks": [
                "authenticated caller", "exact checkout SHA", "filesystem realpath allowlist",
                "independent review and required CI", "bounded AppLab lease",
            ]}
