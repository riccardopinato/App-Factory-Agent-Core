# STANDARD comparative pilot — Agent Core Spec Lite delta trace

Source baseline: `117b56b20dff1e63012c314ef32a2aa80fc558ab`. Core baseline when pilot started: `a185c16000608b90c5db639f37903b49b059b10b`. This pilot is a source-only improvement inside existing Agent Core, Product Bible and AppLab trust boundaries.

## Why / behavior and scope
Existing Agent Core adapter checked that every AC was a required check but did not check the inverse: a declared mandatory check could be missing from AC entirely. The existing archived proposed pilot manifest contains exactly this mismatch (SOURCE_TEST declared but no matching AC). Mirror Core's already-implemented `REQUIRED_CHECK_UNMAPPED` semantics and retain new optional `delta` lineage in the read-only WorkItem projection.

Delta: MODIFIED Spec Lite WorkItem admission behavior and projection only. No queue, scheduler, agent execution, privileged mutation, AppLab release certification, Product Bible, or Windows runner.

## AC and regression plan
- AC-001: missing mandatory kind is denied before WorkItem projection (UNIT_TEST).
- AC-002: duplicate mandatory kind is denied (UNIT_TEST).
- AC-003: valid `delta.previous` is carried with `previous_state_verified=False`, without implying historical verification (UNIT_TEST).
- AC-004: missing or self-referential previous SHA is denied (UNIT_TEST).
- AC-005: replay of a changed delta manifest is rejected (UNIT_TEST).
- AC-006: existing 19+ Agent WorkItem bridge regressions stay green on exact-head CI (UNIT_TEST).

The historical fixture is only normalized in test memory; its earlier evidence is not retroactively changed. Changes remain candidate until actual PR merge and postmerge CI are independently reviewed. Runbook remains Core-owned.

## Measurement protocol
Compare baseline and pilot source tests, CI time, changed files, documentation, defects caught and missing E2E Windows proof; tokens/time are NOT_MEASURED unless instrumented. No new Golden or opt-in fleet-wide rollout.
