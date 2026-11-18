#!/usr/bin/env python3
"""Optional, fail-closed AI-efficiency adapters for App Factory Agent Core.

Source-only pilot. These helpers do not authorize an agent job, start a worker,
install tools, call paid APIs, mutate GitHub, or certify runtime savings.
Job authorization and durable operations remain owned by X10-010 and AppLab.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Callable

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm"})
SAFE_CACHE_CATEGORIES = frozenset({"static_document_extract", "static_public_classification"})
PROTECTED_MARKERS = (
    "CURRENT.yaml", "AGENTS.md", "GOLDEN_REGISTRY", "MASTER_CORE",
    "approval receipt", "private key", "secret=", "BEGIN PRIVATE KEY",
)

# These are fixed, read-only examples. The AppLab worker must still enforce its
# own executable and path allowlists, pin the repository and verify exit status.
RTK_OSS_OPERATIONS = {
    "git_status": ("rtk", "git", "status", "--short"),
    "git_diff_stat": ("rtk", "git", "diff", "--stat"),
    "git_log_recent": ("rtk", "git", "log", "--oneline", "-10"),
    "pytest_quiet": ("rtk", "pytest", "-q"),
    "ruff_check": ("rtk", "ruff", "check", "."),
}


class EfficiencyDenied(ValueError):
    """A proposed optimization does not satisfy an authorization boundary."""


def _identity(repository: str, source_sha: str) -> None:
    if not isinstance(repository, str) or REPO.fullmatch(repository) is None:
        raise EfficiencyDenied("INVALID_REPOSITORY")
    if not isinstance(source_sha, str) or SHA40.fullmatch(source_sha) is None:
        raise EfficiencyDenied("INVALID_SOURCE_SHA")


def plan_rtk_oss(operation: str, *, allowed: bool = False, edition: str = "oss") -> dict[str, Any]:
    """Return argv only: never configure global shell hooks or execute commands.

    The OSS edition is required explicitly because the full RTK distribution
    contains additional BUSL-1.1 licensed components.
    """
    if not allowed:
        raise EfficiencyDenied("TRUSTED_TOOL_PERMISSION_REQUIRED")
    if edition != "oss":
        raise EfficiencyDenied("OSS_EDITION_REQUIRED")
    if not isinstance(operation, str) or operation not in RTK_OSS_OPERATIONS:
        raise EfficiencyDenied("OPERATION_NOT_ALLOWLISTED")
    return {"argv": RTK_OSS_OPERATIONS[operation], "executes": False,
            "edition": "rtk-oss", "must_preserve_raw_log": True,
            "must_preserve_exit_code": True}


def compare_output(raw: str, filtered: str, *, raw_exit: int, filtered_exit: int) -> dict[str, Any]:
    """Byte-count only. This NEVER proves LLM token or monetary savings."""
    if not isinstance(raw, str) or not isinstance(filtered, str):
        raise EfficiencyDenied("INVALID_OUTPUT")
    if type(raw_exit) is not int or type(filtered_exit) is not int:
        raise EfficiencyDenied("INVALID_EXIT")
    before, after = len(raw.encode("utf-8")), len(filtered.encode("utf-8"))
    safe = raw_exit == 0 and filtered_exit == 0 and after <= before
    return {"status": "BYTE_REDUCTION_CANDIDATE" if safe else "RAW_REQUIRED",
            "raw_bytes": before, "filtered_bytes": after,
            "bytes_saved": before - after if safe else 0,
            "reduction_percent": round((before - after) * 100 / before, 2) if safe and before else 0.0,
            "token_cost_verified": False, "semantic_equivalence_verified": False,
            "publish_filtered": safe, "retain_full_log": True}


def convert_local_document(
    filepath: str | Path, *, root: str | Path, approved: bool = False,
    network_isolated: bool = False, converter: Any = None,
    max_file_bytes: int = 8 * 1024 * 1024,
    max_output_bytes: int = 4 * 1024 * 1024,
) -> dict[str, Any]:
    """Use MarkItDown only inside an independently isolated, approved worker.

    Environment isolation, parser process timeout and secret-scanning must be
    implemented by the real runner; passing a flag does not create a sandbox.
    """
    if not approved or not network_isolated:
        raise EfficiencyDenied("ISOLATED_APPROVAL_REQUIRED")
    if not isinstance(max_file_bytes, int) or not 1 <= max_file_bytes <= 16 * 1024 * 1024:
        raise EfficiencyDenied("BAD_INPUT_BUDGET")
    if not isinstance(max_output_bytes, int) or not 1 <= max_output_bytes <= 8 * 1024 * 1024:
        raise EfficiencyDenied("BAD_OUTPUT_BUDGET")
    base = Path(root).resolve(strict=True)
    target = Path(filepath).resolve(strict=True)
    if not base.is_dir() or not target.is_file():
        raise EfficiencyDenied("NOT_A_LOCAL_FILE")
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise EfficiencyDenied("PATH_OUTSIDE_ALLOWED_ROOT") from exc
    if target.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise EfficiencyDenied("UNSUPPORTED_FILE_FORMAT")
    if target.stat().st_size > max_file_bytes:
        raise EfficiencyDenied("INPUT_BUDGET_EXCEEDED")
    if converter is None:
        try:
            from markitdown import MarkItDown  # optional MIT dependency
        except ImportError as exc:
            raise EfficiencyDenied("MARKITDOWN_NOT_INSTALLED") from exc
        converter = MarkItDown(enable_plugins=False)
    result = converter.convert(str(target))
    markdown = getattr(result, "text_content", None)
    if not isinstance(markdown, str):
        raise EfficiencyDenied("INVALID_CONVERTER_RESULT")
    if len(markdown.encode("utf-8")) > max_output_bytes:
        raise EfficiencyDenied("OUTPUT_BUDGET_EXCEEDED")
    return {"text": markdown, "source_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "format": target.suffix.lower(), "conversion_verified": False,
            "source_preserved": True}


def build_pybreaker(*, enabled: bool = False, fail_max: int = 3,
                    reset_timeout: int = 60, factory: Callable[..., Any] | None = None) -> Any:
    """Construct PyBreaker; never add retries or spawn a second scheduler."""
    if not enabled:
        raise EfficiencyDenied("CIRCUIT_BREAKER_NOT_APPROVED")
    if type(fail_max) is not int or not 1 <= fail_max <= 10:
        raise EfficiencyDenied("INVALID_FAILURE_THRESHOLD")
    if type(reset_timeout) is not int or not 5 <= reset_timeout <= 900:
        raise EfficiencyDenied("INVALID_RESET_TIMEOUT")
    if factory is None:
        try:
            from pybreaker import CircuitBreaker  # optional BSD-3-Clause dependency
        except ImportError as exc:
            raise EfficiencyDenied("PYBREAKER_NOT_INSTALLED") from exc
        factory = CircuitBreaker
    return factory(fail_max=fail_max, reset_timeout=reset_timeout)


def guarded_idempotent_call(breaker: Any, fn: Callable[..., Any], *args: Any,
                            approved: bool = False, idempotent: bool = False,
                            **kwargs: Any) -> Any:
    """Execution boundary for an already authorized, idempotent external call."""
    if not approved or not idempotent:
        raise EfficiencyDenied("CALL_NOT_APPROVED_OR_NOT_IDEMPOTENT")
    if breaker is None or not callable(getattr(breaker, "call", None)):
        raise EfficiencyDenied("INVALID_BREAKER")
    return breaker.call(fn, *args, **kwargs)


def exact_cache_key(*, tenant: str, repository: str, source_sha: str, task_type: str,
                    model: str, prompt_revision: str, input_sha256: str) -> str:
    """Deterministic, per-tenant, per-source key; never cache raw prompt strings."""
    _identity(repository, source_sha)
    if task_type not in SAFE_CACHE_CATEGORIES:
        raise EfficiencyDenied("TASK_NOT_CACHEABLE")
    if not isinstance(input_sha256, str) or SHA64.fullmatch(input_sha256) is None:
        raise EfficiencyDenied("INVALID_INPUT_HASH")
    parts = (tenant, task_type, model, prompt_revision)
    if not all(isinstance(p, str) and 1 <= len(p) <= 160 for p in parts):
        raise EfficiencyDenied("INVALID_CACHE_IDENTITY")
    payload = {"tenant": tenant, "repository": repository,
               "source_sha": source_sha, "task": task_type, "model": model,
               "prompt_revision": prompt_revision, "input_sha256": input_sha256}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class EphemeralExactCache:
    """Bounded process memory only: NOT a second GBrain or persistent user store."""

    def __init__(self, *, max_entries: int = 64, ttl_seconds: int = 300,
                 clock: Callable[[], float] = time.monotonic):
        if type(max_entries) is not int or not 1 <= max_entries <= 1024:
            raise EfficiencyDenied("INVALID_CACHE_CAPACITY")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise EfficiencyDenied("INVALID_CACHE_TTL")
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self.entries: dict[str, tuple[float, str]] = {}

    def put(self, key: str, value: str) -> None:
        if not isinstance(key, str) or SHA64.fullmatch(key) is None:
            raise EfficiencyDenied("INVALID_CACHE_KEY")
        if not isinstance(value, str) or len(value.encode("utf-8")) > 1024 * 1024:
            raise EfficiencyDenied("INVALID_CACHE_VALUE")
        now = self.clock()
        self.entries = {k: v for k, v in self.entries.items() if v[0] > now}
        if key not in self.entries and len(self.entries) >= self.max_entries:
            oldest = min(self.entries, key=lambda k: self.entries[k][0])
            del self.entries[oldest]
        self.entries[key] = (now + self.ttl_seconds, value)

    def get(self, key: str) -> str | None:
        if not isinstance(key, str) or SHA64.fullmatch(key) is None:
            raise EfficiencyDenied("INVALID_CACHE_KEY")
        hit = self.entries.get(key)
        if hit is None:
            return None
        if hit[0] <= self.clock():
            del self.entries[key]
            return None
        return hit[1]


def read_scoped_memory(client: Any, *, query: str, tenant: str, repository: str,
                       source_sha: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Read-only Mem0-compatible pilot; GBrain remains the knowledge owner.

    Memory responses are untrusted suggestions, NEVER proof of source state.
    Only records with explicit matching tenant, repo, immutable SHA and source
    provenance survive. The adapter does not mutate any memory store.
    """
    _identity(repository, source_sha)
    if not isinstance(query, str) or not 1 <= len(query) <= 1000:
        raise EfficiencyDenied("INVALID_MEMORY_QUERY")
    if not isinstance(tenant, str) or not 1 <= len(tenant) <= 128:
        raise EfficiencyDenied("INVALID_TENANT")
    if type(max_results) is not int or not 1 <= max_results <= 10:
        raise EfficiencyDenied("INVALID_RESULT_LIMIT")
    response = client.search(query=query, user_id=tenant, limit=max_results)
    entries = response.get("results", []) if isinstance(response, dict) else response
    if not isinstance(entries, list):
        raise EfficiencyDenied("INVALID_MEMORY_RESPONSE")
    accepted = []
    for item in entries[:max_results]:
        if not isinstance(item, dict):
            continue
        meta = item.get("metadata")
        if not isinstance(meta, dict):
            continue
        if (meta.get("tenant") != tenant or meta.get("repository") != repository
                or meta.get("source_sha") != source_sha):
            continue
        url = meta.get("source_url")
        if not isinstance(url, str) or not url.startswith(
            "https://github.com/" + repository + "/"
        ):
            continue
        text = item.get("memory")
        if isinstance(text, str) and len(text) <= 4000:
            accepted.append({"memory": text, "source_url": url,
                             "authoritative": False, "write_permitted": False})
    return accepted


def model_route(task_type: str, *, local_available: bool = True,
                remote_approved: bool = False, remote_budget_eur: float = 0.0) -> dict[str, Any]:
    """Routing recommendation only; creates no provider call or paid charge."""
    local = frozenset({"log_summary", "document_summary", "classify_static", "code_draft"})
    critical = frozenset({"security_review", "release_review", "source_certification"})
    if task_type not in local | critical:
        return {"route": "HUMAN_REVIEW", "reason": "UNKNOWN_OR_UNCLASSIFIED"}
    if task_type in critical:
        return {"route": "HUMAN_REVIEW", "reason": "CRITICAL_CANNOT_BE_AUTO_ROUTED"}
    if local_available:
        return {"route": "LOCAL", "reason": "LOCAL_FIRST", "quality_gate_required": True}
    if remote_approved and isinstance(remote_budget_eur, (int, float)) and 0 < remote_budget_eur <= 100:
        return {"route": "REMOTE_APPROVED", "reason": "BOUND_BUDGET",
                "quality_gate_required": True}
    return {"route": "BLOCKED", "reason": "NO_AUTHORIZED_PROVIDER"}


def compress_document_candidate(text: str, *, kind: str, approved: bool,
                                compressor: Callable[[str], str]) -> dict[str, Any]:
    """LLMLingua-compatible experimental candidate, never automatic replacement."""
    if not approved or kind not in {"public_document", "public_research"}:
        raise EfficiencyDenied("COMPRESSION_SCOPE_DENIED")
    if not isinstance(text, str) or not 1 <= len(text) <= 100_000:
        raise EfficiencyDenied("INVALID_DOCUMENT")
    if any(marker.lower() in text.lower() for marker in PROTECTED_MARKERS):
        raise EfficiencyDenied("PROTECTED_TEXT_CANNOT_BE_COMPRESSED")
    result = compressor(text)
    if not isinstance(result, str) or not result or len(result) > len(text):
        raise EfficiencyDenied("COMPRESSION_INVALID")
    return {"candidate": result, "original_chars": len(text),
            "candidate_chars": len(result), "validated_facts": False,
            "may_replace_source": False, "requires_semantic_eval": True}
