#!/usr/bin/env python3
"""Read GitHub PR and CI through an existing authenticated, injected connector.

No GitHub PAT, HTTP request library, mutable global client, or GitHub writes.
The injected provider must guarantee real user authentication and access
control. Not a complete required-checks/branch-protection verifier.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Callable

try:
    from scripts.factory_readonly_gateway import REPO, SHA
except ModuleNotFoundError:
    from factory_readonly_gateway import REPO, SHA

MAX_BYTES = 256 * 1024
MAX_RUNS = 32


class GitHubEvidenceReaderError(ValueError):
    pass


def _decode(envelope: Any) -> dict[str, Any]:
    if not isinstance(envelope, dict) or not isinstance(envelope.get("result"), dict):
        raise GitHubEvidenceReaderError("PROVIDER_ENVELOPE_INVALID")
    raw = envelope["result"].get("content")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_BYTES:
        raise GitHubEvidenceReaderError("PROVIDER_CONTENT_INVALID")
    try:
        data = json.loads(raw)
    except ValueError:
        raise GitHubEvidenceReaderError("PROVIDER_JSON_INVALID") from None
    if not isinstance(data, dict):
        raise GitHubEvidenceReaderError("PROVIDER_JSON_INVALID")
    return data


class GitHubEvidenceConnector:
    def __init__(self, *, trusted_fetch: Callable[[str], dict[str, Any]],
                 allowed_repositories, now: Callable[[], datetime] | None = None):
        if not callable(trusted_fetch) or not isinstance(allowed_repositories, (set, list, tuple, frozenset)):
            raise GitHubEvidenceReaderError("TRUSTED_CONNECTOR_REQUIRED")
        allowed = frozenset(allowed_repositories)
        if not allowed or len(allowed) > 64 or any(
            not isinstance(r, str) or REPO.fullmatch(r) is None for r in allowed
        ):
            raise GitHubEvidenceReaderError("INVALID_REPOSITORY_POLICY")
        if now is not None and not callable(now):
            raise GitHubEvidenceReaderError("INVALID_CLOCK_PROVIDER")
        self._fetch = trusted_fetch
        self._allowed = allowed
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _repo(self, repository: str) -> None:
        if not isinstance(repository, str) or repository not in self._allowed:
            raise GitHubEvidenceReaderError("REPOSITORY_NOT_AUTHORIZED")

    def _clock(self) -> str:
        stamp = self._now()
        if not isinstance(stamp, datetime) or stamp.tzinfo is None:
            raise GitHubEvidenceReaderError("CLOCK_NOT_TRUSTED")
        return stamp.astimezone(timezone.utc).isoformat()

    def _fetch_json(self, url: str) -> dict[str, Any]:
        try:
            return _decode(self._fetch(url))
        except GitHubEvidenceReaderError:
            raise
        except Exception:
            raise GitHubEvidenceReaderError("PROVIDER_UNAVAILABLE") from None

    def read_pr(self, repository: str, pr_number: int) -> dict[str, Any]:
        self._repo(repository)
        if type(pr_number) is not int or not 1 <= pr_number <= 100000000:
            raise GitHubEvidenceReaderError("INVALID_PR_NUMBER")
        data = self._fetch_json(
            f"https://api.github.com/repos/{repository}/pulls/{pr_number}"
        )
        head, base = data.get("head"), data.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise GitHubEvidenceReaderError("PR_RESPONSE_MALFORMED")
        base_repo = base.get("repo")
        if (data.get("number") != pr_number or type(data.get("number")) is not int
                or not isinstance(base_repo, dict)
                or base_repo.get("full_name") != repository):
            raise GitHubEvidenceReaderError("PR_REPOSITORY_MISMATCH")
        hsha, bsha = head.get("sha"), base.get("sha")
        if (not isinstance(hsha, str) or SHA.fullmatch(hsha) is None
                or not isinstance(bsha, str) or SHA.fullmatch(bsha) is None):
            raise GitHubEvidenceReaderError("PR_SHA_INVALID")
        if data.get("state") not in ("open", "closed") or type(data.get("draft")) is not bool:
            raise GitHubEvidenceReaderError("PR_STATE_INVALID")
        return {
            "authenticated": True,  # trusted host-provided GitHub connector only
            "repository": repository, "number": pr_number,
            "head_sha": hsha, "base_sha": bsha,
            "state": data["state"], "draft": data["draft"],
            "observed_at": self._clock(),
        }

    def read_ci(self, repository: str, head_sha: str) -> dict[str, Any]:
        self._repo(repository)
        if not isinstance(head_sha, str) or SHA.fullmatch(head_sha) is None:
            raise GitHubEvidenceReaderError("INVALID_HEAD_SHA")
        # This view is explicitly PR-triggered workflow runs only; not GitHub's
        # complete required-check set, external statuses or branch protection.
        data = self._fetch_json(
            f"https://api.github.com/repos/{repository}/actions/runs"
            f"?head_sha={head_sha}&event=pull_request&per_page={MAX_RUNS}"
        )
        rows, total = data.get("workflow_runs"), data.get("total_count")
        if not isinstance(rows, list) or type(total) is not int or total < 0 or total > MAX_RUNS or len(rows) > MAX_RUNS:
            raise GitHubEvidenceReaderError("CI_INCOMPLETE_OR_UNBOUNDED")
        runs = []
        for row in rows:
            if not isinstance(row, dict) or row.get("head_sha") != head_sha:
                raise GitHubEvidenceReaderError("CI_SHA_MISMATCH")
            runs.append({
                "name": row.get("name"), "run_id": row.get("id"),
                "status": row.get("status"), "conclusion": row.get("conclusion"),
            })
        return {
            "authenticated": True, "repository": repository,
            "head_sha": head_sha, "observed_at": self._clock(),
            "coverage": "PR_WORKFLOW_RUNS_ONLY_NOT_REQUIRED_CHECKS",
            "runs": runs,
        }
