#!/usr/bin/env python3
"""X10 Factory status gateway: no HTTP server, no shell, no queue mutation.

Host supplies a scoped, authenticated GitHub *reader* and canonical AppLab
DurableStoreV54B object. This facade never creates jobs/leases, generates
approvals, calls an LLM or interprets repository text as policy.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Callable, Iterable

REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
OP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
STATE = re.compile(r"^[A-Z][A-Z_0-9]{1,63}$")
MAX_REPOS = 16
MAX_AGE_SECONDS = 900


class StatusGatewayError(ValueError):
    pass


def _stamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise StatusGatewayError("INVALID_SOURCE_TIME")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StatusGatewayError("INVALID_SOURCE_TIME") from exc
    if moment.tzinfo is None:
        raise StatusGatewayError("INVALID_SOURCE_TIME")
    return moment.astimezone(timezone.utc)


class FactoryReadOnlyGateway:
    """Host-provided allowlist and readers are mandatory trust boundaries.

    The host must independently authenticate the end user and the providers.
    No untrusted caller-supplied policy or AppLab job summary is used.
    """

    def __init__(
        self, *,
        allowed_repositories: Iterable[str],
        github_head_reader: Callable[[str], dict[str, Any]],
        applab_store: Any,
    ):
        if not isinstance(allowed_repositories, (tuple, list, frozenset, set)):
            raise StatusGatewayError("INVALID_REPOSITORY_POLICY")
        allowed = frozenset(allowed_repositories)
        if not (1 <= len(allowed) <= 64) or any(
            not isinstance(r, str) or REPO.fullmatch(r) is None for r in allowed
        ):
            raise StatusGatewayError("INVALID_REPOSITORY_POLICY")
        if not callable(github_head_reader) or not callable(getattr(applab_store, "get_operation", None)):
            raise StatusGatewayError("READ_PROVIDERS_MISSING")
        self._allowed = allowed
        self._github_head_reader = github_head_reader
        self._applab_store = applab_store

    def _repository(self, repository: str) -> None:
        if not isinstance(repository, str) or repository not in self._allowed:
            raise StatusGatewayError("REPOSITORY_NOT_AUTHORIZED")

    def repository_status(self, repository: str, *, now: datetime | None = None) -> dict[str, Any]:
        self._repository(repository)
        if now is None:
            now = datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise StatusGatewayError("INVALID_CLOCK")
        now = now.astimezone(timezone.utc)
        record = self._github_head_reader(repository)
        if not isinstance(record, dict) or record.get("authenticated") is not True:
            raise StatusGatewayError("GITHUB_SOURCE_NOT_AUTHENTICATED")
        sha = record.get("head_sha")
        if record.get("repository") != repository or not isinstance(sha, str) or SHA.fullmatch(sha) is None:
            raise StatusGatewayError("GITHUB_REPOSITORY_IDENTITY_MISMATCH")
        observed = _stamp(record.get("observed_at"))
        age = (now - observed).total_seconds()
        if not 0 <= age <= MAX_AGE_SECONDS:
            raise StatusGatewayError("GITHUB_SOURCE_STALE_OR_FUTURE")
        return {
            "schema_version": 1, "record_type": "FACTORY_REPOSITORY_STATUS",
            "repository": repository, "head_sha": sha,
            "observed_at": observed.isoformat(), "evidence": "HOST_AUTHENTICATED_GITHUB_HEAD",
            "read_only": True, "ci_verified": False,
            "runtime_verified": False, "certification_granted": False,
        }

    def repositories_status(self, repositories: list[str], *, now: datetime | None = None) -> dict[str, Any]:
        if not isinstance(repositories, list) or not (1 <= len(repositories) <= MAX_REPOS):
            raise StatusGatewayError("INVALID_REPOSITORY_BATCH")
        if len(repositories) != len(set(map(str, repositories))):
            raise StatusGatewayError("DUPLICATE_REPOSITORY")
        # Pre-admit the complete batch before any provider call.
        for repository in repositories:
            self._repository(repository)
        snapshots = [self.repository_status(repo, now=now) for repo in repositories]
        return {
            "schema_version": 1, "record_type": "FACTORY_REPOSITORY_BATCH",
            "repositories": snapshots, "read_only": True, "runtime_verified": False,
        }

    def operation_status(
        self, operation_id: str, *,
        repository: str, source_sha: str,
    ) -> dict[str, Any]:
        self._repository(repository)
        if not isinstance(source_sha, str) or SHA.fullmatch(source_sha) is None:
            raise StatusGatewayError("INVALID_EXPECTED_SOURCE_SHA")
        if not isinstance(operation_id, str) or ".." in operation_id or OP_ID.fullmatch(operation_id) is None:
            raise StatusGatewayError("INVALID_OPERATION_ID")
        # The canonical AppLab store is the ONLY source of operation state.
        operation = self._applab_store.get_operation(operation_id)
        if not isinstance(operation, dict):
            raise StatusGatewayError("OPERATION_NOT_PERSISTED")
        if (operation.get("operation_id") != operation_id
                or operation.get("repository") != repository
                or operation.get("resolved_sha") != source_sha):
            raise StatusGatewayError("APPLAB_OPERATION_SOURCE_MISMATCH")
        state = operation.get("current_state")
        if not isinstance(state, str) or STATE.fullmatch(state) is None:
            raise StatusGatewayError("APPLAB_OPERATION_STATE_INVALID")
        # Never expose opaque payload_json, credentials, worktree paths or
        # attached user-generated job summaries. Terminal state != QA PASS.
        return {
            "schema_version": 1, "record_type": "FACTORY_APPLAB_OPERATION_STATUS",
            "operation_id": operation_id, "repository": repository,
            "source_sha": source_sha, "applab_state": state,
            "evidence": "CANONICAL_APPLAB_STORE_REPORTED",
            "read_only": True, "runtime_verified": False,
            "ci_verified": False, "certification_granted": False,
            "external_write_performed": False,
        }
