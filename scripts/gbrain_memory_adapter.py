#!/usr/bin/env python3
"""X10 GBrain recall projection: local, fail-closed, source-labelled, read-only.

This adapter accepts the JSON response of an already-authorized GBrain read.
It does not connect to GBrain, create memory, mutate any database or issue jobs.
Memory is untrusted context, never a Factory policy or execution approval.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

DEFAULT_TIERS = frozenset({"user_confirmed", "operator_curated", "tool_observed"})
KNOWN_TIERS = DEFAULT_TIERS | {"agent_written", "unknown", "external_untrusted"}
SENSITIVE = re.compile(
    r"-----BEGIN (?:(?:RSA|EC|OPENSSH|ENCRYPTED) )?PRIVATE KEY-----"
    r"|\b(?:github_pat_[A-Za-z0-9_]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|sk-(?:proj-)?[A-Za-z0-9_-]{16,})",
    re.IGNORECASE,
)
MAX_BYTES = 256 * 1024
MAX_INPUT_FACTS = 128
MAX_FACT_CHARS = 1600


class GBrainMemoryError(ValueError):
    """Invalid/untrusted GBrain read envelope."""


def _timestamp(raw: str) -> datetime:
    if not isinstance(raw, str):
        raise GBrainMemoryError("INVALID_TIMESTAMP")
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GBrainMemoryError("INVALID_TIMESTAMP") from exc
    if result.tzinfo is None:
        raise GBrainMemoryError("NAIVE_TIMESTAMP")
    return result.astimezone(timezone.utc)


def project_recall(
    response: dict[str, Any],
    *,
    now: datetime | None = None,
    max_facts: int = 12,
    allowed_tiers: frozenset[str] = DEFAULT_TIERS,
) -> dict[str, Any]:
    """Normalize GBrain recall into bounded context; do not elevate evidence.

    GBrain may append an out-of-band '[gbrain notice ...]' after its JSON.
    The notice is not parsed as instructions. Keyword-only degradation means
    an empty result can NEVER be interpreted as absence of remembered data.
    """
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        raise GBrainMemoryError("INVALID_ENVELOPE")
    if type(max_facts) is not int or not 1 <= max_facts <= 32:
        raise GBrainMemoryError("INVALID_LIMIT")
    if not isinstance(allowed_tiers, frozenset) or not allowed_tiers or not allowed_tiers <= KNOWN_TIERS:
        raise GBrainMemoryError("INVALID_TRUST_POLICY")
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise GBrainMemoryError("INVALID_CLOCK")
    now = now.astimezone(timezone.utc)

    text = response["text"]
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise GBrainMemoryError("RESPONSE_TOO_LARGE")
    try:
        payload, end = json.JSONDecoder().raw_decode(text.lstrip())
    except (ValueError, TypeError) as exc:
        raise GBrainMemoryError("INVALID_JSON") from exc
    suffix = text.lstrip()[end:].strip()
    if suffix and not suffix.startswith("[gbrain notice "):
        raise GBrainMemoryError("UNRECOGNIZED_TRAILER")
    if not isinstance(payload, dict) or type(payload.get("protocol_version")) is not int or payload["protocol_version"] != 1:
        raise GBrainMemoryError("UNSUPPORTED_PROTOCOL")
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list) or len(raw_facts) > MAX_INPUT_FACTS:
        raise GBrainMemoryError("UNBOUNDED_FACTS")
    degraded = bool(payload.get("search_degraded")) or suffix.startswith("[gbrain notice degraded_recall")
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_facts:
        if not isinstance(item, dict):
            raise GBrainMemoryError("INVALID_FACT")
        tier, visibility = item.get("trust_tier"), item.get("visibility")
        if not isinstance(tier, str) or tier not in allowed_tiers or visibility != "world":
            continue
        if item.get("expired_at") is not None or item.get("superseded_by") is not None or item.get("quarantined") is True:
            continue
        expiry = item.get("valid_until")
        if expiry is not None and _timestamp(expiry) <= now:
            continue
        fact, source, fid = item.get("fact"), item.get("source_id"), item.get("fact_id", item.get("id"))
        if not isinstance(fact, str) or not fact.strip() or len(fact) > MAX_FACT_CHARS:
            continue
        if not isinstance(source, str) or not (1 <= len(source) <= 128) or not re.fullmatch(r"[A-Za-z0-9_.:-]+", source):
            continue
        if not isinstance(fid, (str, int)) or isinstance(fid, bool) or not (1 <= len(str(fid)) <= 128):
            continue
        if SENSITIVE.search(fact):
            continue
        key = (source, str(fid))
        if key in seen:
            continue
        seen.add(key)
        kept.append({
            "text": fact, "source_id": source, "fact_id": str(fid),
            "trust_tier": tier, "visibility": "world",
            "untrusted_context": True, "verified_by_factory": False,
        })
        if len(kept) >= max_facts:
            break
    return {
        "schema_version": 1, "record_type": "GBRAIN_RECALL_PROJECTION",
        "authority": "CONTEXT_ONLY", "read_only": True,
        "search_mode": "KEYWORD_ONLY_DEGRADED" if degraded else "SOURCE_REPORTED",
        "absence_proven": False, "source_facts_count": len(raw_facts),
        "facts": kept,
        "state": "FACTS_FOR_REVIEW" if kept else "NO_ADMITTED_CONTEXT",
    }
