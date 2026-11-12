#!/usr/bin/env python3
"""X10-013: bind Agent Core job intent to existing AppLab queue + WorkGraph.

The ONLY durable queue/lease/work-item authority is AppLab. This module never
dispatches a shell, calls GitHub, mints approvals, or marks verification PASS.
External trusted admission MUST bind a job digest to its persisted operation.
"""
from __future__ import annotations

import hashlib
import math
import time
from copy import deepcopy
from typing import Any, Callable

try:
    from scripts.agent_job_gateway import evaluate, job_digest
    from scripts.applab_queue_bridge import AppLabQueueBridge, BridgeError
    from scripts.applab_workspace_gate import propose_in_applab_workspace
except ModuleNotFoundError:
    from agent_job_gateway import evaluate, job_digest
    from applab_queue_bridge import AppLabQueueBridge, BridgeError
    from applab_workspace_gate import propose_in_applab_workspace

OPERABLE = frozenset({"analyze", "run_tests", "propose_diff"})


class OrchestrationError(ValueError):
    pass


class BoundedAppLabOrchestrator:
    """Dependency-injected front end, NOT a second AppLab worker.

    binding_verifier is a trusted control-plane lookup for immutable
    (job_sha256, operation_id, persisted operation) records. Never accept
    a claim or a job field as proof of that mapping.
    """

    def __init__(
        self, bridge: AppLabQueueBridge,
        *, binding_verifier: Callable[[str, str, dict[str, Any]], bool],
        work_item_factory: Callable[..., dict[str, Any]],
    ):
        if not isinstance(bridge, AppLabQueueBridge):
            raise OrchestrationError("REQUIRES_EXISTING_APPLAB_BRIDGE")
        if not callable(binding_verifier) or not callable(work_item_factory):
            raise OrchestrationError("TRUSTED_ADAPTERS_REQUIRED")
        self.bridge = bridge
        self.binding_verifier = binding_verifier
        self.work_item_factory = work_item_factory

    def _bound(self, job: dict[str, Any], operation_id: str) -> dict[str, Any]:
        try:
            op = self.bridge._operation(operation_id, job)
            valid = self.binding_verifier(job_digest(job), operation_id, op)
        except (KeyError, ValueError, TypeError) as exc:
            raise OrchestrationError("TRUSTED_OPERATION_BINDING_REQUIRED") from exc
        if valid is not True:
            raise OrchestrationError("TRUSTED_OPERATION_BINDING_REQUIRED")
        return op

    def _require_live_app_lab_lease(
        self, claim: dict[str, Any], operation_id: str,
        *, now_ts: float, allowed_operation_states: frozenset[str],
    ) -> None:
        """Check actual AppLab SQLite queue entry, never trust a copied claim."""
        if not isinstance(claim, dict):
            raise OrchestrationError("INVALID_LEASE_CLAIM")
        entry_getter = getattr(self.bridge.queue, "_entry", None)
        if not callable(entry_getter):
            raise OrchestrationError("APPLAB_LEASE_INSPECTION_UNAVAILABLE")
        entry = entry_getter(operation_id)
        if entry is None:
            raise OrchestrationError("APPLAB_LEASE_NOT_FOUND")
        try:
            same_lease = (
                entry["operation_id"] == operation_id
                and entry["state"] == "LEASED"
                and entry["leased_by"] == claim["worker_id"]
                and entry["repository"] == claim["repository"]
                and entry["resolved_sha"] == claim["resolved_sha"]
                and type(entry["lease_until"]) in (int, float)
                and type(claim["lease_until"]) in (int, float)
                and float(entry["lease_until"]) == float(claim["lease_until"])
            )
        except (TypeError, KeyError, ValueError):
            same_lease = False
        if not same_lease:
            raise OrchestrationError("APPLAB_LEASE_OWNER_OR_GENERATION_MISMATCH")
        # AppLab's caller-supplied now_ts is not sufficient to prove a
        # *current* lease: a stale or malicious clock can be far in the past.
        # Check trusted process wall clock as well, including prepare_claim.
        real_now = time.time()
        if not (type(now_ts) in (int, float) and math.isfinite(now_ts)
                and 0 <= now_ts < float(entry["lease_until"])
                and real_now < float(entry["lease_until"])):
            raise OrchestrationError("APPLAB_LEASE_EXPIRED")
        persisted_state = self.bridge.store.get_operation(operation_id)["current_state"]
        if persisted_state not in allowed_operation_states:
            raise OrchestrationError("APPLAB_OPERATION_NOT_ACTIVE")

    def stage(
        self, job: dict[str, Any], policy: dict[str, Any], operation_id: str,
        *, now_ts: float, receipt: dict[str, Any] | None = None,
        verifier_key: bytes | None = None,
    ) -> dict[str, Any]:
        """Idempotent enqueue through AppLab's *own* durable store only."""
        if job.get("mode") not in OPERABLE:
            raise OrchestrationError("NO_PR_OR_MERGE_ROUTING")
        self._bound(job, operation_id)
        result = self.bridge.enqueue_admitted(
            job, policy, operation_id, now_ts=now_ts,
            receipt=receipt, verifier_key=verifier_key,
        )
        return {**result, "automatic_dispatch": False,
                "control_plane_authority": "NONE"}

    def prepare_claim(
        self, job: dict[str, Any], policy: dict[str, Any], operation_id: str,
        claim: dict[str, Any], *, now_ts: float,
        receipt: dict[str, Any] | None = None,
        verifier_key: bytes | None = None,
    ) -> dict[str, Any]:
        """Validate a lease handed off by AppLab; no queue.claim_next here.

        The AppLab dispatcher owns fair queue selection and may lease a job
        from another repo. Never claim/release leases on behalf of a caller.
        """
        if job.get("mode") not in OPERABLE:
            raise OrchestrationError("NO_PR_OR_MERGE_ROUTING")
        decision = evaluate(job, policy, receipt=receipt, verifier_key=verifier_key)
        if decision.get("authorized") is not True:
            raise OrchestrationError("JOB_NOT_AUTHORIZED")
        operation = self._bound(job, operation_id)
        if (not isinstance(claim, dict) or claim.get("operation_id") != operation_id
            or claim.get("repository") != job["target"]["repository"]
            or claim.get("resolved_sha") != job["target"]["source_sha"]
            or claim.get("executor") != "GITHUB_ACTIONS"
            or claim.get("dispatch_performed") is not False
            or not isinstance(claim.get("worker_id"), str)
            or not claim["worker_id"]):
            raise OrchestrationError("CROSS_JOB_LEASE_MISMATCH")
        lease_until = claim.get("lease_until")
        if (type(now_ts) not in (int, float) or not math.isfinite(now_ts)
            or type(lease_until) not in (int, float)
            or not math.isfinite(lease_until) or not 0 <= now_ts < lease_until):
            raise OrchestrationError("LEASE_EXPIRED_OR_INVALID")
        self._require_live_app_lab_lease(
            claim, operation_id, now_ts=now_ts,
            allowed_operation_states=frozenset({
                "PLANNING", "READY", "RUNNING", "WAITING_RETRY", "WAITING_EXTERNAL",
            }),
        )
        digest = job_digest(job)
        work_item_id = "wrk_x10_" + hashlib.sha256(
            (operation_id + ":" + digest).encode("utf-8")
        ).hexdigest()[:24]
        work_item = self.work_item_factory(
            operation, work_item_id=work_item_id,
            allow_code_edit=job["mode"] == "propose_diff",
            allow_draft_pr_steward=False,
        )
        if (not isinstance(work_item, dict)
            or work_item.get("record_type") != "APPLAB_WORK_ITEM"
            or work_item.get("work_item_id") != work_item_id
            or work_item.get("operation_id") != operation_id
            or work_item.get("repository") != operation["repository"]
            or work_item.get("resolved_sha") != operation["resolved_sha"]
            or work_item.get("authority") != "ORCHESTRATION_ONLY"):
            raise OrchestrationError("WORKGRAPH_IDENTITY_MISMATCH")
        envelope = work_item.get("authority_envelope")
        if not isinstance(envelope, dict) or not isinstance(envelope.get("allowed_capabilities"), list):
            raise OrchestrationError("WORKGRAPH_MALFORMED_AUTHORITY")
        allowed = envelope["allowed_capabilities"]
        if ("CREATE_DRAFT_PR" in allowed or "UPDATE_DRAFT_PR" in allowed
            or (job["mode"] == "propose_diff") != ("ALLOW_CODE_EDIT" in allowed)):
            raise OrchestrationError("WORKGRAPH_PRIVILEGE_ESCALATION")
        if job["mode"] in {"analyze", "run_tests"} and not all(
            name in allowed for name in ("READ_REPOSITORY", "READ_EVIDENCE")
        ):
            raise OrchestrationError("WORKGRAPH_MISSING_READ_AUTHORITY")
        return {
            "schema_version": 1, "record_type": "X10_BOUNDED_DISPATCH_INTENT",
            "state": "LEASE_VALIDATED_PROPOSAL_ONLY",
            "operation_id": operation_id, "repository": operation["repository"],
            "resolved_sha": operation["resolved_sha"], "job_sha256": digest,
            "work_item": work_item, "mode": job["mode"],
            "worker_id": claim["worker_id"], "lease_until": lease_until,
            "dispatch_performed": False, "runtime_verified": False,
            "auto_merge_performed": False,
        }

    def propose_bounded_patch(
        self, intent: dict[str, Any], job: dict[str, Any], policy: dict[str, Any],
        *, receipt: dict[str, Any], verifier_key: bytes,
        repo_root: Any, patch_path: Any, investigation: dict[str, Any],
        attempt_number: int, bounded_worker: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        """Delegate to X10-012 + AppLab v6.0C. Never close the lease as PASS."""
        if (not isinstance(intent, dict)
            or intent.get("record_type") != "X10_BOUNDED_DISPATCH_INTENT"
            or intent.get("mode") != "propose_diff"
            or intent.get("state") != "LEASE_VALIDATED_PROPOSAL_ONLY"
            or intent.get("job_sha256") != job_digest(job)
            or intent.get("repository") != job["target"]["repository"]
            or intent.get("resolved_sha") != job["target"]["source_sha"]
            or not isinstance(intent.get("work_item"), dict)
            or intent["work_item"].get("operation_id") != intent.get("operation_id")
            or intent["work_item"].get("repository") != job["target"]["repository"]
            or intent["work_item"].get("resolved_sha") != job["target"]["source_sha"]):
            raise OrchestrationError("INVALID_PATCH_INTENT")
        operation = self._bound(job, intent["operation_id"])
        # An intent is caller-carried mutable data. Source/operation binding
        # does not authenticate its WorkItem or authority envelope. Recreate
        # the canonical WorkItem from the trusted pinned AppLab factory and
        # pass THAT copy to the worker, never the mutable caller reference.
        expected_id = "wrk_x10_" + hashlib.sha256(
            (intent["operation_id"] + ":" + job_digest(job)).encode("utf-8")
        ).hexdigest()[:24]
        trusted_work_item = self.work_item_factory(
            operation, work_item_id=expected_id,
            allow_code_edit=True, allow_draft_pr_steward=False,
        )
        if (not isinstance(trusted_work_item, dict)
            or trusted_work_item.get("record_type") != "APPLAB_WORK_ITEM"
            or trusted_work_item.get("work_item_id") != expected_id
            or trusted_work_item.get("operation_id") != intent["operation_id"]
            or trusted_work_item.get("repository") != job["target"]["repository"]
            or trusted_work_item.get("resolved_sha") != job["target"]["source_sha"]
            or trusted_work_item.get("authority") != "ORCHESTRATION_ONLY"
            or intent["work_item"] != trusted_work_item):
            raise OrchestrationError("WORKGRAPH_INTENT_TAMPERED")
        envelope = trusted_work_item.get("authority_envelope")
        allowed = envelope.get("allowed_capabilities") if isinstance(envelope, dict) else None
        if (not isinstance(allowed, list)
            or "ALLOW_CODE_EDIT" not in allowed
            or any(c in allowed for c in (
                "CREATE_DRAFT_PR", "UPDATE_DRAFT_PR",
                "MERGE_PR", "PUBLISH_RELEASE", "DEPLOY_PRODUCTION",
            ))):
            raise OrchestrationError("WORKGRAPH_PRIVILEGE_ESCALATION")
        # Independent local snapshot, no reference to untrusted intent
        # passes through the delegated preflight/worker callback.
        trusted_work_item = deepcopy(trusted_work_item)
        # Real clock; a stale caller-controlled timestamp cannot reauthorize a
        # queued/cancelled operation after a lease has expired or been reassigned.
        self._require_live_app_lab_lease(
            {"operation_id": intent["operation_id"],
             "repository": intent["repository"], "resolved_sha": intent["resolved_sha"],
             "worker_id": intent.get("worker_id"),
             "lease_until": intent.get("lease_until")},
            intent["operation_id"], now_ts=time.time(),
            allowed_operation_states=frozenset({"READY", "RUNNING"}),
        )
        def fenced_worker(*args: Any, **kwargs: Any) -> dict[str, Any]:
            # X10-013: the workspace preflight can run Git subprocesses; a
            # lease can expire or be recovered during that work. Re-check
            # current durable AppLab state at the exact callback boundary.
            self._bound(job, intent["operation_id"])
            self._require_live_app_lab_lease(
                {"operation_id": intent["operation_id"],
                 "repository": intent["repository"],
                 "resolved_sha": intent["resolved_sha"],
                 "worker_id": intent.get("worker_id"),
                 "lease_until": intent.get("lease_until")},
                intent["operation_id"], now_ts=time.time(),
                allowed_operation_states=frozenset({"READY", "RUNNING"}),
            )
            return bounded_worker(*args, **kwargs)

        result = propose_in_applab_workspace(
            job, policy, receipt=receipt, verifier_key=verifier_key,
            repo_root=repo_root, patch_path=patch_path,
            work_item=trusted_work_item, investigation=investigation,
            attempt_number=attempt_number, bounded_worker=fenced_worker,
        )
        return {**result, "operation_id": intent["operation_id"],
                "queue_lease_closed": False, "independent_verification_required": True}

    def recover(self, *, now_ts: float) -> dict[str, Any]:
        """AppLab owns expired lease retry and backoff. No job rerun in Chat."""
        return self.bridge.recover(now_ts=now_ts)
