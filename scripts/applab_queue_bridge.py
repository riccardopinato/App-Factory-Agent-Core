#!/usr/bin/env python3
"""X10-011: scoped bridge to AppLab's EXISTING durable store and queue.

No second database, executor, scheduler, or permission authority. An admitted
job references an operation already persisted by trusted AppLab event admission.
An HMAC approval is still required for write-mode job proposals.
"""
from __future__ import annotations

import math
from typing import Any

try:
    from scripts.agent_job_gateway import evaluate
except ModuleNotFoundError:
    from agent_job_gateway import evaluate


class BridgeError(ValueError):
    pass


def _clock(now_ts: float) -> float:
    if type(now_ts) not in (int, float) or not math.isfinite(now_ts) or now_ts < 0:
        raise BridgeError("INVALID_CLOCK")
    return float(now_ts)


class AppLabQueueBridge:
    """Non-owning facade: store/queue MUST be AppLab v5.4B/v5.4E instances.

    The real backend owns its SQLite journal, operation transitions, leases,
    backpressure and retry budget. Fake implementations are for offline tests
    only. No runtime capability is granted by constructing this bridge.
    """

    def __init__(self, store: Any, queue: Any):
        if store is None or queue is None or getattr(queue, "store", None) is not store:
            raise BridgeError("APPLAB_STORE_QUEUE_MISMATCH")
        self.store = store
        self.queue = queue

    def _operation(self, operation_id: str, job: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 256:
            raise BridgeError("INVALID_OPERATION_ID")
        operation = self.store.get_operation(operation_id)
        if not isinstance(operation, dict):
            raise BridgeError("OPERATION_NOT_PERSISTED")
        target = job["target"]
        if (operation.get("operation_id") != operation_id
                or operation.get("repository") != target["repository"]
                or operation.get("resolved_sha") != target["source_sha"]):
            raise BridgeError("SOURCE_IDENTITY_MISMATCH")
        # Exact caller/job-to-operation idempotency binding must be established
        # by trusted event admission. Do not infer it from a free-text summary.
        return operation

    def enqueue_admitted(
        self, job: dict[str, Any], policy: dict[str, Any], operation_id: str,
        *, now_ts: float, receipt: dict[str, Any] | None = None,
        verifier_key: bytes | None = None, ancestor_shas: set[str] | None = None,
        ancestry_proven: bool = False,
    ) -> dict[str, Any]:
        clock = _clock(now_ts)
        decision = evaluate(job, policy, receipt=receipt, verifier_key=verifier_key)
        if not decision["authorized"]:
            return {"state": "BLOCKED", "reason": decision["reason"],
                    "dispatch_performed": False, "runtime_verified": False}
        if decision.get("runtime_verified") is not False:
            raise BridgeError("UNEXPECTED_GATEWAY_AUTHORITY")
        self._operation(operation_id, job)
        if ancestor_shas and not ancestry_proven:
            raise BridgeError("UNTRUSTED_ANCESTRY")
        result = self.queue.enqueue(
            operation_id, now_ts=clock, max_retries=min(job["limits"]["max_attempts"] - 1, 1),
            ancestor_shas=ancestor_shas, ancestry_proven=ancestry_proven,
        )
        if not isinstance(result, dict) or result.get("operation_id") != operation_id:
            raise BridgeError("QUEUE_RESULT_IDENTITY_MISMATCH")
        if result.get("status") not in {"INSERTED", "REPLAY"}:
            raise BridgeError("UNKNOWN_QUEUE_RESULT")
        return {"state": result["state"], "status": result["status"],
                "operation_id": operation_id, "dispatch_performed": False,
                "runtime_verified": False}

    def checkpoint(self, operation_id: str, job: dict[str, Any]) -> dict[str, Any]:
        self._operation(operation_id, job)
        current = self.store.get_operation(operation_id)["current_state"]
        rebuilt = self.store.rebuild_operation_state(operation_id)
        if current != rebuilt:
            raise BridgeError("TRANSITION_LEDGER_DRIFT")
        return {"operation_id": operation_id, "durable_state": current,
                "replay_verified": True, "dispatch_performed": False}

    def recover(self, *, now_ts: float) -> dict[str, Any]:
        """Existing AppLab lease recovery only; never dispatch or declare PASS."""
        recovered = self.queue.recover_expired_leases(now_ts=_clock(now_ts))
        if not isinstance(recovered, list):
            raise BridgeError("RECOVERY_RESULT_INVALID")
        if any(not isinstance(item, dict) or not item.get("operation_id")
               or type(item.get("retry")) is not bool for item in recovered):
            raise BridgeError("RECOVERY_RESULT_INVALID")
        return {"recovered": recovered, "dispatch_performed": False,
                "runtime_verified": False}
