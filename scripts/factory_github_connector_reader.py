#!/usr/bin/env python3
"""Bridge existing authenticated GitHub connector's branch GET to Factory gateway.

Host must supply a trusted `fetch(url)` function bound to the user's GitHub
connection. No separate token, HTTP stack, credentials or GitHub writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Callable
from urllib.parse import quote

REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_JSON_BYTES = 64 * 1024


class GitHubConnectorReaderError(ValueError):
    pass


class GitHubConnectorHeadReader:
    """Read-only callable usable as FactoryReadOnlyGateway.github_head_reader.

    The injected provider must authenticate/authorize the user *before* this
    class is constructed. Its output is not cryptographically authenticated by
    this class. Fail closed if the content or source identity differs.
    """

    def __init__(self, *,
                 trusted_fetch: Callable[[str], Any],
                 branches: dict[str, str],
                 now: Callable[[], datetime] | None = None):
        if not callable(trusted_fetch) or not isinstance(branches, dict) or not (1 <= len(branches) <= 64):
            raise GitHubConnectorReaderError("MISSING_TRUSTED_PROVIDER")
        for repo, branch in branches.items():
            if (not isinstance(repo, str) or REPO.fullmatch(repo) is None
                    or not isinstance(branch, str) or BRANCH.fullmatch(branch) is None
                    or branch.startswith("-") or "//" in branch
                    or any(part in ("", ".", "..") for part in branch.split("/"))):
                raise GitHubConnectorReaderError("INVALID_PINNED_REPOSITORY_REF")
        if now is not None and not callable(now):
            raise GitHubConnectorReaderError("INVALID_CLOCK_PROVIDER")
        self._fetch = trusted_fetch
        self._branches = dict(branches)
        self._now = now or (lambda: datetime.now(timezone.utc))

    def __call__(self, repository: str) -> dict[str, Any]:
        if not isinstance(repository, str) or repository not in self._branches:
            raise GitHubConnectorReaderError("REPOSITORY_NOT_AUTHORIZED")
        branch = self._branches[repository]
        url = f"https://api.github.com/repos/{repository}/branches/{quote(branch, safe='')}"
        try:
            envelope = self._fetch(url)
        except Exception as exc:
            raise GitHubConnectorReaderError("GITHUB_PROVIDER_UNAVAILABLE") from exc
        # tools.mcp__GitHub__fetch returns {result: {content: JSON string}}.
        if (not isinstance(envelope, dict)
                or not isinstance(envelope.get("result"), dict)
                or not isinstance(envelope["result"].get("content"), str)):
            raise GitHubConnectorReaderError("GITHUB_PROVIDER_RESPONSE_INVALID")
        raw = envelope["result"]["content"]
        if len(raw.encode("utf-8")) > MAX_JSON_BYTES:
            raise GitHubConnectorReaderError("GITHUB_RESPONSE_TOO_LARGE")
        try:
            obj = json.loads(raw)
        except ValueError as exc:
            raise GitHubConnectorReaderError("GITHUB_JSON_INVALID") from exc
        if not isinstance(obj, dict) or obj.get("name") != branch:
            raise GitHubConnectorReaderError("GITHUB_REF_MISMATCH")
        commit = obj.get("commit")
        sha = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(sha, str) or SHA.fullmatch(sha) is None:
            raise GitHubConnectorReaderError("GITHUB_SHA_INVALID")
        observed = self._now()
        if not isinstance(observed, datetime) or observed.tzinfo is None:
            raise GitHubConnectorReaderError("INVALID_CLOCK")
        return {
            "authenticated": True,  # Host-injected trusted connector assertion
            "repository": repository, "head_sha": sha,
            "observed_at": observed.astimezone(timezone.utc).isoformat(),
        }
