# GBrain recall quality — diagnostic-only v0.1

Factory baseline: App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619 (Master v27, Index v29).

Dependency: PR #26. This branch starts from source-pinned PR #26 HEAD `3a3818d...`; it does not supersede or merge that PR.

`scripts/gbrain_recall_quality.py::evaluate_recall_quality(query, projection)` takes **only** already-admitted `project_recall` output and emits bounded counts and a search-mode hint. It never reads raw memory, stores user text, calls embeddings/API, mutates GBrain, approves a job or certifies truth. Keyword-only degradation is always displayed as such.

Lexical overlap is a cheap debug signal, not semantic relevance or proof that memory is complete, up-to-date or accurate. Multilingual paraphrases can have zero literal overlap even if correct; keyword matches can be false positives. The report intentionally omits query, fact contents, IDs and source metadata to avoid leaking private material into logs.

Tests: `python3 -m unittest discover -s tests -p test_gbrain_recall_quality.py -v`. Real GBrain embedding status, source relevance and persistence across machine restarts remain `NOT_VERIFIED`.

A future host may show `recommended_action=REVIEW_DEGRADED_SEARCH`; it must not auto-enable paid embeddings or modify GBrain configuration without independent authorization. The quality hint cannot be promoted to Factory source authority.
