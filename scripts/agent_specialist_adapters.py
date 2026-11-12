#!/usr/bin/env python3
"""X10-016: read-only research intake and AppLab QA delegation, not a new agent.

Never fetches GitHub, executes shell/AI, connects financial providers or
materializes PRs. Only the host's existing authorized AppLab adapter can run.
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

SHA = re.compile(r"[a-f0-9]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
LICENSE = re.compile(r"[A-Za-z0-9_.+()-]{1,64}\Z")
KIND = frozenset(("code", "documentation", "reference"))
FORBIDDEN = frozenset(("broker", "trading", "portfolio", "finance_live", "market_orders"))
MAX_CANDIDATES = 12


class SpecialistAdapterError(ValueError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise SpecialistAdapterError(code)


def _admit(job: dict[str, Any], policy: dict[str, Any], mode: str) -> dict[str, Any]:
    _require(isinstance(job, dict) and job.get("mode") == mode,
             "SPECIALIST_JOB_MODE_INVALID")
    decision = evaluate(job, policy)
    _require(decision.get("authorized") is True
             and decision.get("state") == "ADMITTED_FOR_ISOLATED_READ",
             "READ_POLICY_DENIED")
    _require(isinstance(job.get("target"), dict)
             and isinstance(job["target"].get("repository"), str)
             and isinstance(job["target"].get("source_sha"), str),
             "SOURCE_IDENTITY_MISSING")
    return decision


def research_intake(job: dict[str, Any], policy: dict[str, Any], *,
                    research_input: dict[str, Any],
                    trusted_source_resolver: Callable[[str, str], dict[str, Any]]) -> dict[str, Any]:
    """Normalize bounded metadata about OSS donors; never grant Golden admission.

    trusted_source_resolver is an authenticated host-injected source metadata
    lookup. A fixture resolver in tests does not prove any actual OSS license.
    """
    decision = _admit(job, policy, "analyze")
    _require(isinstance(research_input, dict) and
             research_input.get("schema_version") == 1
             and research_input.get("intent") == "OSS_DONOR_RESEARCH"
             and set(research_input).issubset({"schema_version", "intent", "candidates"}),
             "RESEARCH_SCOPE_INVALID")
    _require(callable(trusted_source_resolver), "TRUSTED_SOURCE_RESOLVER_REQUIRED")
    candidates = research_input.get("candidates")
    _require(isinstance(candidates, list) and 1 <= len(candidates) <= MAX_CANDIDATES,
             "CANDIDATE_BOUNDS_EXCEEDED")
    normalized = []
    seen = set()
    for item in candidates:
        _require(isinstance(item, dict)
                 and set(item) == {"repository", "source_sha", "path", "kind"},
                 "RESEARCH_CANDIDATE_SCHEMA_INVALID")
        repo, sha, path, kind = (item[x] for x in ("repository", "source_sha", "path", "kind"))
        _require(isinstance(repo, str) and REPO.fullmatch(repo) is not None
                 and isinstance(sha, str) and SHA.fullmatch(sha) is not None
                 and isinstance(path, str) and safe_path(path)
                 and kind in KIND and not any(token in path.casefold().split("/")
                                            for token in FORBIDDEN),
                 "SOURCE_OR_PATH_INVALID")
        key = (repo.casefold(), sha, path)
        _require(key not in seen, "DUPLICATE_RESEARCH_CANDIDATE")
        seen.add(key)
        resolved = trusted_source_resolver(repo, sha)
        _require(isinstance(resolved, dict)
                 and resolved.get("repository") == repo
                 and resolved.get("source_sha") == sha
                 and resolved.get("authenticated") is True
                 and resolved.get("exact_source") is True
                 and isinstance(resolved.get("license_spdx"), str)
                 and LICENSE.fullmatch(resolved["license_spdx"]) is not None,
                 "RESEARCH_SOURCE_NOT_VERIFIED")
        # A declared SPDX from the resolver is not independent license review.
        normalized.append({
            "repository": repo, "source_sha": sha, "path": path, "kind": kind,
            "declared_license_spdx": resolved["license_spdx"],
            "license_review": "REQUIRED",
            "source_url": f"https://github.com/{repo}/blob/{sha}/{path}",
            "donor_admission": "NOT_GRANTED",
        })
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema_version": 1, "record_type": "X10_SPECIALIST_RESEARCH_INTAKE",
        "authority": "REPORT_ONLY", "state": "CANDIDATES_REQUIRE_REVIEW",
        "repository": decision["repository"], "source_sha": decision["source_sha"],
        "job_sha256": job_digest(job), "candidates_sha256": digest,
        "candidates": normalized, "research_execution_verified": False,
        "license_verified": False, "golden_promoted": False, "external_write_performed": False,
    }


def delegate_qa(job: dict[str, Any], policy: dict[str, Any], *,
                route: dict[str, Any],
                pinned_applab_delegate: Callable[..., dict[str, Any]],
                authorized_runner: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    """Call *existing* AppLab QA router in read-only mode.

    The returned wrapper is source-bound but never attests runtime. A real
    runner's independent evidence verifier must validate the upstream output.
    """
    decision = _admit(job, policy, "run_tests")
    _require(isinstance(route, dict) and route.get("schema_version") == 1
             and route.get("record_type") == "APP_FACTORY_X10_QA_ROUTE"
             and route.get("authority") == "ROUTE_ONLY"
             and route.get("state") == "PENDING_TRUSTED_EXECUTOR"
             and route.get("repository") == decision["repository"]
             and route.get("source_sha") == decision["source_sha"]
             and route.get("test_executed") is False
             and route.get("certification_granted") is False
             and route.get("store_release_granted") is False,
             "QA_ROUTE_UNTRUSTED_OR_STALE")
    _require(callable(pinned_applab_delegate) and callable(authorized_runner),
             "APPLAB_DELEGATE_NOT_CONNECTED")
    # The injected canonical adapter owns the test plan and expected gate set.
    receipt = pinned_applab_delegate(route, runner=authorized_runner)
    _require(isinstance(receipt, dict)
             and receipt.get("schema_version") == 1
             and receipt.get("record_type") == "APP_FACTORY_X10_QA_RECEIPT"
             and receipt.get("repository") == decision["repository"]
             and receipt.get("source_sha") == decision["source_sha"]
             and receipt.get("analysis_mode") == route.get("effective_mode")
             and receipt.get("independent_provenance_verified") is False
             and receipt.get("certification_granted") is False
             and receipt.get("store_release_granted") is False
             and isinstance(receipt.get("gate_results"), dict)
             and receipt.get("state") in ("RUNNER_REPORTED_ONLY", "BLOCKED_OR_FAIL_REPORTED"),
             "QA_DELEGATE_RECEIPT_INVALID")
    return {
        "schema_version": 1, "record_type": "X10_SPECIALIST_QA_REVIEW_RECEIPT",
        "authority": "REPORT_ONLY",
        "state": "AWAITING_INDEPENDENT_EVIDENCE",
        "repository": decision["repository"], "source_sha": decision["source_sha"],
        "job_sha256": job_digest(job),
        "analysis_mode": route["effective_mode"],
        "upstream_state": receipt["state"],
        "reported_gate_results": dict(receipt["gate_results"]),
        "run_url": receipt.get("run_url", ""),
        "independent_provenance_verified": False,
        "runtime_verified": False, "physical_device_verified": False,
        "certification_granted": False, "store_release_granted": False,
        "external_write_performed": False,
    }
