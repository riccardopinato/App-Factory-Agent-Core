#!/usr/bin/env python3
"""Optional GBrain memory context tool. GBrain is NEVER job/CI authority.

This module is a composition seam only. Owner-approved runtime must supply a
trusted GBrain recall reader and the SHA-pinned PR #26 projection function.
It never calls GBrain URLs or stores, uploads or mutates memory.
"""
from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any

try:
    from scripts.factory_mcp_readonly import ReadOnlyFactoryTools, FactoryMcpAccessError
except ModuleNotFoundError:
    from factory_mcp_readonly import ReadOnlyFactoryTools, FactoryMcpAccessError

SOURCE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
MAX_FACTS = 8
MAX_QUERY_CHARS = 160


class MemoryBridgeError(ValueError):
    pass


class FactoryMemoryContext:
    def __init__(self, *, owner_bound_service: ReadOnlyFactoryTools,
                 trusted_gbrain_recall: Callable[..., dict[str, Any]],
                 pinned_projection: Callable[..., dict[str, Any]]):
        if (not isinstance(owner_bound_service, ReadOnlyFactoryTools)
                or not callable(trusted_gbrain_recall) or not callable(pinned_projection)):
            raise MemoryBridgeError("TRUSTED_GBRAIN_PROVIDERS_REQUIRED")
        self._owner = owner_bound_service
        self._recall = trusted_gbrain_recall
        self._project = pinned_projection

    def recall_context(self, query: str) -> dict[str, Any]:
        self._owner._gate()
        if (not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_QUERY_CHARS
                or any(ord(ch) < 32 for ch in query)):
            raise MemoryBridgeError("INVALID_MEMORY_QUERY")
        try:
            raw = self._recall(query=query, budget_tokens=1000)
            result = self._project(raw, max_facts=MAX_FACTS)
        except Exception:
            raise MemoryBridgeError("GBRAIN_READ_UNAVAILABLE") from None
        if (not isinstance(result, dict)
                or result.get("record_type") != "GBRAIN_RECALL_PROJECTION"
                or result.get("authority") != "CONTEXT_ONLY"
                or result.get("read_only") is not True
                or result.get("absence_proven") is not False
                or result.get("search_mode") not in ("KEYWORD_ONLY_DEGRADED", "SOURCE_REPORTED")):
            raise MemoryBridgeError("MEMORY_PROJECTION_UNTRUSTED")
        facts = result.get("facts")
        if not isinstance(facts, list) or len(facts) > MAX_FACTS:
            raise MemoryBridgeError("MEMORY_PROJECTION_UNTRUSTED")
        safe = []
        for fact in facts:
            if (not isinstance(fact, dict)
                    or fact.get("untrusted_context") is not True
                    or fact.get("verified_by_factory") is not False
                    or fact.get("visibility") != "world"
                    or not isinstance(fact.get("text"), str)
                    or len(fact["text"]) > 1600
                    or not isinstance(fact.get("source_id"), str)
                    or SOURCE_ID.fullmatch(fact["source_id"]) is None
                    or not isinstance(fact.get("fact_id"), str)
                    or SOURCE_ID.fullmatch(fact["fact_id"]) is None):
                raise MemoryBridgeError("MEMORY_PROJECTION_UNTRUSTED")
            safe.append({
                "text": fact["text"], "source_id": fact["source_id"],
                "fact_id": fact["fact_id"], "untrusted_context": True,
                "verified_by_factory": False,
            })
        return {
            "schema_version": 1, "record_type": "FACTORY_MEMORY_CONTEXT",
            "authority": "CONTEXT_ONLY", "read_only": True,
            "search_mode": result["search_mode"], "absence_proven": False,
            "facts": safe, "external_write_performed": False,
            "job_authorized": False, "certification_granted": False,
        }
