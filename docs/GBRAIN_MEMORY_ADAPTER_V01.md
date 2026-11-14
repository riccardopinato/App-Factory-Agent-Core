# GBrain Memory Adapter v0.1 — Source-only

**Factory baseline:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`, Master v27 / Golden Index v29.

## Implemented
`scripts/gbrain_memory_adapter.py::project_recall` transforms a *previously authorized* GBrain `recall` response into bounded, source-labelled, **context-only** facts. This is not a new GBrain server, MCP endpoint, connection manager or persistent copy of the memory database.

The GBrain connector actually returned a `{"text":"{JSON}\\n[gbrain notice ...]"}` envelope in ChatGPT on 2026-11-14. The adapter uses a JSON decoder that rejects arbitrary trailing content while accepting GBrain's structured degraded-recall notice. It marks `keyword_only_embedding_disabled` as degraded, never as memory absence.

Default admission:
- `visibility=world`, tier in `user_confirmed | operator_curated | tool_observed`, nonexpired and nonsuperseded.
- Excludes `agent_written` unless a trusted caller opts in explicitly. Thus the installed test fact with that tier will not appear by default; this is expected.
- Excludes private/quarantined records, obvious credential-like strings, malformed source IDs and duplicate IDs.
- Limits response bytes, incoming fact count, fact characters and returned count.
- Every fact has `untrusted_context=true` and `verified_by_factory=false`; no user-facing trusted status is minted.

**Authority:** CURRENT / Master / Golden and real repository code always override memory. Source content (including quoted prompts from past conversations) is **data**, never execution instructions. Search absence is never asserted as proven. `source_id` and `trust_tier` are upstream claims; neither is an independent authentication proof.

## Integration contract
The host must invoke the existing connected GBrain `recall` tool after its own authorization and pass the returned envelope to `project_recall`. This module only normalizes the response. It does not embed OpenAI API calls, connect to GBrain URLs, install packages, write back facts or access private memory.

## Tests and remaining gates
`python3 -m unittest discover -s tests -p 'test_gbrain_memory_adapter.py' -v`.

- Offline tests: appended notice, keyword-only search, excluded weak/private/expired/quarantined facts, secrets, deduplication, invalid input, prompt-injection-as-data, no authority escalation.
- Next: integrate into a real host that can call GBrain and verify filtering with real mixed-tier fixtures; measure recall relevance and inspect the embedding setting only with operator permission.
- **Not verified:** semantic embedding quality, operational deployment, memory completeness, future connection uptime, any live read of private data.
