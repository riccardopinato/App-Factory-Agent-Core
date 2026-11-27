#!/usr/bin/env python3
"""GBrain recall-quality diagnostics (offline, source-only, non-authoritative).

Consumes only admitted `project_recall` output, never raw GBrain memory.
No embeddings, paid models, network calls, writes or factory approvals.
Token-overlap is diagnostic, NOT a truth/confidence/authorization score.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

MAX_QUERY = 160
MAX_FACTS = 32
MAX_FACT_TEXT = 1600
STOPWORDS = frozenset({
    "a", "ad", "al", "alla", "con", "da", "del", "della", "di",
    "e", "ed", "il", "in", "la", "le", "lo", "nel", "per", "su",
    "the", "and", "for", "from", "of", "in", "a", "to", "is",
})


class RecallQualityError(ValueError):
    pass


def _tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return {w for w in re.findall(r"[a-z0-9]{2,}", ascii_text.casefold()) if w not in STOPWORDS}


def evaluate_recall_quality(query: str, projection: dict[str, Any]) -> dict[str, Any]:
    """Inspect relevance only; never claim results are complete or true.

    No fact bodies, queries, credential-bearing metadata or GBrain IDs are
    copied into the output. This makes the derived report shareable, but does
    NOT prove the underlying records contain no secrets.
    """
    if (not isinstance(query, str) or not query.strip()
            or len(query) > MAX_QUERY or not query.isprintable()):
        raise RecallQualityError("INVALID_QUERY")
    if (not isinstance(projection, dict)
            or projection.get("record_type") != "GBRAIN_RECALL_PROJECTION"
            or projection.get("authority") != "CONTEXT_ONLY"
            or projection.get("read_only") is not True
            or projection.get("absence_proven") is not False):
        raise RecallQualityError("UNTRUSTED_RECALL_PROJECTION")
    facts, mode = projection.get("facts"), projection.get("search_mode")
    if not isinstance(facts, list) or len(facts) > MAX_FACTS:
        raise RecallQualityError("INVALID_FACT_SET")
    if mode not in ("KEYWORD_ONLY_DEGRADED", "SOURCE_REPORTED"):
        raise RecallQualityError("UNTRUSTED_SEARCH_MODE")
    query_terms = _tokens(query)
    overlap_count = 0
    for item in facts:
        if (not isinstance(item, dict)
                or item.get("untrusted_context") is not True
                or item.get("verified_by_factory") is not False
                or not isinstance(item.get("text"), str)
                or len(item["text"]) > MAX_FACT_TEXT):
            raise RecallQualityError("UNTRUSTED_FACT")
        if query_terms and query_terms.intersection(_tokens(item["text"])):
            overlap_count += 1
    # A low overlap is not proof of poor semantic relevance; synonyms and
    # cross-language matches may be valid. A high overlap is not evidence.
    return {
        "schema_version": 1,
        "record_type": "GBRAIN_RECALL_QUALITY_HINT",
        "authority": "DIAGNOSTIC_ONLY",
        "read_only": True,
        "search_mode": mode,
        "admitted_fact_count": len(facts),
        "lexical_overlap_count": overlap_count,
        "query_has_indexable_terms": bool(query_terms),
        "semantic_search_verified": False,
        "memory_complete": False,
        "absence_proven": False,
        "relevance_verified": False,
        "fact_truth_verified": False,
        "certification_granted": False,
        "recommended_action": (
            "REVIEW_DEGRADED_SEARCH" if mode == "KEYWORD_ONLY_DEGRADED"
            else "REVIEW_CONTEXT_IF_MATERIAL"
        ),
    }
