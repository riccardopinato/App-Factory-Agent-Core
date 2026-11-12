#!/usr/bin/env python3
"""X10-041: read-only diff event -> bounded reusable-capability hints.

Accepts already authenticated webhook/CI event and AppLab's existing
smart_test_plan.git_diff_evidence() result. It never fetches from GitHub,
runs arbitrary git commands, persists user data or registers/promotes a CAP.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

try:
    from scripts.agent_job_gateway import safe_path
except ModuleNotFoundError:
    from agent_job_gateway import safe_path

SHA40 = re.compile(r"^[a-f0-9]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ALLOWED = frozenset({"A", "M", "D", "R", "C", "T"})
EXTENSIONS = frozenset((".dart", ".kt", ".java", ".swift", ".py", ".js", ".ts", ".tsx",
                       ".json", ".yaml", ".yml", ".kts", ".gradle", ".xml", ".sql"))
KEYWORDS = (
    ("identity", ("login", "auth", "oauth", "profile", "account", "credential")),
    ("notifications", ("notification", "alarm", "push", "reminder")),
    ("storage", ("database", "backup", "restore", "persist", "sqlite", "migration")),
    ("localization", ("locale", "l10n", "i18n", "translation", "intl")),
    ("design_tokens", ("theme", "design_system", "token", "color_scheme")),
    ("billing", ("billing", "payment", "purchases", "admob", "revenuecat")),
    ("testing", ("test", "quality", "benchmark", "regression", "ci")),
)
MAX_CHANGED = 200
MAX_HINTS = 30


class MonitorError(ValueError):
    pass


def _require(value: bool, message: str) -> None:
    if not value:
        raise MonitorError(message)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=True).encode("ascii")).hexdigest()


def analyze(event: dict[str, Any], diff: dict[str, Any], *,
            verified_head_sha: str, diff_provider: str = "APPLAB_SMART_TEST_PLAN_V1",
            trust: dict[str, Any]) -> dict[str, Any]:
    """Candidate hints depend on pinned SHA, not prose or untrusted event fields.

    Caller MUST independently authenticate delivery, resolve actual GitHub
    head, ensure diff generated from this exact base/head and ensure replay.
    'verified_head_sha' and 'trust' are trusted arguments from its control plane.
    """
    _require(isinstance(event, dict) and isinstance(diff, dict)
             and isinstance(trust, dict), "INVALID_INPUT")
    repo = event.get("repository")
    base_sha, head_sha = event.get("base_sha"), event.get("head_sha")
    ref = event.get("ref")
    _require(isinstance(repo, str) and REPO.fullmatch(repo) is not None
             and isinstance(ref, str) and (ref.startswith("refs/heads/") or
                                           ref.startswith("refs/tags/"))
             and len(ref) <= 256, "EVENT_SOURCE_INVALID")
    _require(all(isinstance(x, str) and SHA40.fullmatch(x) for x in
                 (base_sha, head_sha, verified_head_sha))
             and base_sha != head_sha and head_sha == verified_head_sha,
             "EVENT_SHA_NOT_PINNED")
    _require(trust.get("authenticated") is True
             and trust.get("exact_head_resolved") is True
             and trust.get("diff_provenance_verified") is True
             and trust.get("no_unauthorized_repo_scope") is True,
             "TRUST_PROOF_REQUIRED")
    _require(diff_provider == "APPLAB_SMART_TEST_PLAN_V1", "DIFF_PROVIDER_UNSUPPORTED")
    _require(diff.get("trusted") is True and diff.get("status") == "ok"
             and diff.get("too_large") is False and diff.get("semantic_diff_truncated") is not True,
             "DIFF_UNTRUSTED_OR_TRUNCATED")
    _require(diff.get("base_sha") == base_sha and diff.get("head_sha") == head_sha,
             "DIFF_IDENTITY_MISMATCH")
    rows = diff.get("files")
    _require(isinstance(rows, list) and 0 < len(rows) <= MAX_CHANGED,
             "DIFF_INVALID_SIZE")
    if "file_count" in diff:
        _require(type(diff["file_count"]) is int and diff["file_count"] == len(rows),
                 "DIFF_FILE_COUNT_DRIFT")
    paths_seen = set()
    targets = []
    for row in rows:
        _require(isinstance(row, dict), "DIFF_ROW_INVALID")
        path, status = row.get("path"), row.get("status")
        _require(isinstance(path, str) and safe_path(path) and isinstance(status, str)
                 and status in ALLOWED, "UNSAFE_CHANGED_PATH")
        _require(path not in paths_seen, "DUPLICATE_CHANGED_PATH")
        paths_seen.add(path)
        previous = row.get("previous_path", "")
        if previous:
            _require(isinstance(previous, str) and safe_path(previous),
                     "UNSAFE_RENAME_PATH")
        additions, deletions = row.get("additions"), row.get("deletions")
        _require(type(additions) is int and type(deletions) is int
                 and 0 <= additions <= 20000 and 0 <= deletions <= 20000,
                 "INVALID_DIFF_METRICS")
        # Never serialize source hunks, code text, secrets or user payload.
        # We only take bounded path signals; rename predecessor also matters.
        for source_path in (path, previous):
            if (not source_path or
                ("." + source_path.rsplit(".", 1)[-1].lower()) not in EXTENSIONS):
                continue
            normalized = source_path.lower().replace("-", "_")
            signals = sorted({kind for kind, keywords in KEYWORDS
                              if any(token in normalized for token in keywords)})
            if not signals:
                continue
            # Filenames may themselves contain access tokens or personal
            # identifiers. Do not copy even trusted path metadata into reports.
            targets.append({"path_sha256": _digest(["path", source_path]),
                            "signals": signals})
    targets.sort(key=lambda x: x["path_sha256"])
    _require(len(targets) <= MAX_HINTS, "DIFF_HINT_CAP_EXCEEDED")
    report = {
        "schema_version": 1, "record_type": "X10_041_DIFF_HINTS",
        "authority": "ADVISORY_ONLY", "repository": repo,
        "source_ref_sha256": _digest(["ref", ref]),
        "base_sha": base_sha, "head_sha": head_sha,
        "monitor_key": _digest([repo.casefold(), ref, base_sha, head_sha]),
        "signals": targets, "changed_file_count": len(rows),
        "changed_files_sha256": _digest(sorted(paths_seen)),
        "requires_cap_registry_match": True, "requires_license_review": True,
        "source_code_copied": False, "automated_pr_created": False,
        "golden_promotion_performed": False, "runtime_verified": False,
    }
    return report
