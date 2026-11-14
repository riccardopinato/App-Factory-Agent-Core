#!/usr/bin/env python3
"""X10 Gateway v0.2: bounded, read-only PR/CI and AppLab checkpoint evidence.

Not an HTTP/MCP server; real providers and access control must be injected by
an authenticated host. All upstream data is untrusted until host authentication
and expected repository/SHA are checked. No job launch, approval or merge.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Callable

try:
    from scripts.factory_readonly_gateway import (
        FactoryReadOnlyGateway, StatusGatewayError, SHA, _stamp, MAX_AGE_SECONDS
    )
except ModuleNotFoundError:
    from factory_readonly_gateway import (
        FactoryReadOnlyGateway, StatusGatewayError, SHA, _stamp, MAX_AGE_SECONDS
    )

RUN_STATUS = frozenset({
    "queued", "in_progress", "completed", "waiting", "requested", "pending"
})
RUN_CONCLUSION = frozenset({
    "success", "failure", "cancelled", "timed_out", "skipped",
    "neutral", "action_required", "stale", "startup_failure"
})
RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:/-]{0,119}$")
MAX_RUNS = 32
MAX_BATCH = 12


class EvidenceGatewayError(StatusGatewayError):
    pass


class FactoryEvidenceGateway(FactoryReadOnlyGateway):
    """Augments the existing Gateway without creating a second state authority."""

    def __init__(self, *, allowed_repositories,
                 github_head_reader, applab_store,
                 trusted_pr_reader: Callable[[str, int], dict[str, Any]],
                 trusted_ci_reader: Callable[[str, str], dict[str, Any]]):
        super().__init__(
            allowed_repositories=allowed_repositories,
            github_head_reader=github_head_reader, applab_store=applab_store,
        )
        if not callable(trusted_pr_reader) or not callable(trusted_ci_reader):
            raise EvidenceGatewayError("TRUSTED_EVIDENCE_READERS_REQUIRED")
        self._pr = trusted_pr_reader
        self._ci = trusted_ci_reader

    def pull_request_evidence(self, repository: str, pr_number: int, *,
                              expected_head_sha: str | None = None,
                              now: datetime | None = None) -> dict[str, Any]:
        self._repository(repository)
        if type(pr_number) is not int or not 1 <= pr_number <= 100000000:
            raise EvidenceGatewayError("INVALID_PR_NUMBER")
        if expected_head_sha is not None and (
            not isinstance(expected_head_sha, str) or SHA.fullmatch(expected_head_sha) is None
        ):
            raise EvidenceGatewayError("INVALID_EXPECTED_HEAD")
        if now is not None and (
            not isinstance(now, datetime) or now.tzinfo is None
        ):
            raise EvidenceGatewayError("INVALID_CLOCK")
        # Provider exceptions must never disclose credentials or paths.
        try:
            pr = self._pr(repository, pr_number)
        except Exception:
            raise EvidenceGatewayError("PR_PROVIDER_UNAVAILABLE") from None
        if not isinstance(pr, dict) or pr.get("authenticated") is not True:
            raise EvidenceGatewayError("PR_SOURCE_NOT_AUTHENTICATED")
        sha, base = pr.get("head_sha"), pr.get("base_sha")
        if (pr.get("repository") != repository
                or type(pr.get("number")) is not int or pr["number"] != pr_number
                or not isinstance(sha, str) or SHA.fullmatch(sha) is None
                or not isinstance(base, str) or SHA.fullmatch(base) is None):
            raise EvidenceGatewayError("PR_SOURCE_IDENTITY_MISMATCH")
        if expected_head_sha is not None and sha != expected_head_sha:
            raise EvidenceGatewayError("PR_HEAD_CHANGED")
        if pr.get("state") not in ("open", "closed") or type(pr.get("draft")) is not bool:
            raise EvidenceGatewayError("PR_STATE_INVALID")
        observed = _stamp(pr.get("observed_at"))
        try:
            ci = self._ci(repository, sha)
        except Exception:
            raise EvidenceGatewayError("CI_PROVIDER_UNAVAILABLE") from None
        if not isinstance(ci, dict) or ci.get("authenticated") is not True:
            raise EvidenceGatewayError("CI_SOURCE_NOT_AUTHENTICATED")
        if ci.get("repository") != repository or ci.get("head_sha") != sha:
            raise EvidenceGatewayError("CI_SOURCE_IDENTITY_MISMATCH")
        observed_ci = _stamp(ci.get("observed_at"))
        effective_now = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
        for stamp in (observed, observed_ci):
            age = (effective_now - stamp).total_seconds()
            if not 0 <= age <= MAX_AGE_SECONDS:
                raise EvidenceGatewayError("EVIDENCE_STALE_OR_FUTURE")
        runs = ci.get("runs")
        if not isinstance(runs, list) or len(runs) > MAX_RUNS:
            raise EvidenceGatewayError("RUNS_INVALID_OR_TOO_MANY")
        seen = set()
        checks = []
        for run in runs:
            if not isinstance(run, dict):
                raise EvidenceGatewayError("CI_RUN_MALFORMED")
            name, rid = run.get("name"), run.get("run_id")
            status, conclusion = run.get("status"), run.get("conclusion")
            if (not isinstance(name, str) or RUN_NAME.fullmatch(name) is None
                    or type(rid) is not int or rid <= 0 or rid in seen
                    or status not in RUN_STATUS or
                    (conclusion is not None and conclusion not in RUN_CONCLUSION)
                    or (status != "completed" and conclusion is not None)):
                raise EvidenceGatewayError("CI_RUN_MALFORMED")
            seen.add(rid)
            checks.append({
                "name": name, "run_id": rid, "status": status,
                "conclusion": conclusion if status == "completed" else None,
            })
        failures = any(r["status"] == "completed" and r["conclusion"] != "success" for r in checks)
        incomplete = any(r["status"] != "completed" for r in checks)
        if not checks:
            ci_state = "NO_CHECKS_OBSERVED"
        elif failures:
            ci_state = "NON_SUCCESS_REPORTED"
        elif incomplete:
            ci_state = "CHECKS_PENDING"
        else:
            ci_state = "ALL_OBSERVED_CHECKS_SUCCESS"
        blockers = []
        if pr["draft"]:
            blockers.append("DRAFT_PR")
        if ci_state != "ALL_OBSERVED_CHECKS_SUCCESS":
            blockers.append(ci_state)
        # Review, branch protection and any external QA were NOT checked.
        blockers.append("REVIEW_AND_BRANCH_GATES_NOT_VERIFIED")
        return {
            "schema_version": 1, "record_type": "FACTORY_PR_CI_EVIDENCE",
            "repository": repository, "pr_number": pr_number,
            "head_sha": sha, "base_sha": base, "pr_state": pr["state"],
            "draft": pr["draft"], "ci_state": ci_state, "checks": checks,
            "observed_at": effective_now.isoformat(), "blockers": blockers,
            "evidence": "HOST_AUTHENTICATED_GITHUB_REPORT",
            "read_only": True, "review_verified": False,
            "exact_head_gate_verified": False, "runtime_verified": False,
            "physical_device_verified": False, "release_granted": False,
            "certification_granted": False, "external_write_performed": False,
        }

    def pull_request_batch(self, requests: list[dict[str, Any]], *,
                           now: datetime | None = None) -> dict[str, Any]:
        if not isinstance(requests, list) or not 1 <= len(requests) <= MAX_BATCH:
            raise EvidenceGatewayError("INVALID_PR_BATCH")
        unique = set()
        # Validate complete scope before any external provider call.
        for req in requests:
            if not isinstance(req, dict) or set(req) != {"repository", "number", "expected_head_sha"}:
                raise EvidenceGatewayError("INVALID_PR_BATCH_ITEM")
            self._repository(req["repository"])
            number, sha = req["number"], req["expected_head_sha"]
            if type(number) is not int or number <= 0 or not isinstance(sha, str) or SHA.fullmatch(sha) is None:
                raise EvidenceGatewayError("INVALID_PR_BATCH_ITEM")
            key = (req["repository"], number)
            if key in unique:
                raise EvidenceGatewayError("DUPLICATE_PR")
            unique.add(key)
        records = [self.pull_request_evidence(
            r["repository"], r["number"], expected_head_sha=r["expected_head_sha"], now=now
        ) for r in requests]
        return {
            "schema_version": 1, "record_type": "FACTORY_PR_CI_BATCH",
            "items": records, "read_only": True, "certification_granted": False,
        }

    def operation_checkpoint(self, operation_id: str, *, repository: str,
                             source_sha: str) -> dict[str, Any]:
        # Canonical AppLab store remains authoritative; never list SQLite rows.
        op = self.operation_status(operation_id, repository=repository, source_sha=source_sha)
        return {
            **op, "record_type": "FACTORY_OPERATION_CHECKPOINT",
            "recovery_verified": False, "evidence_status": "STATE_ONLY",
            "next_action_authorized": False,
        }
