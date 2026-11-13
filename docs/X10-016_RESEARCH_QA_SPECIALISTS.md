# X10-016 — Research/QA specialist adapter (SOURCE+CI candidate)
Factory baseline App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619, Master 27 / Golden Index 29.

Implements two **thin read-only** facades around existing Agent Core gateway and AppLab QA router.

* Research metadata intake requires a policy-admitted analyze job, immutable repository commit, bounded safe source path, injected authenticated source resolver and SPDX declaration; only a donor *candidate*. A declared license is **not independently reviewed**, no file contents included and no Golden admission or autonomous research fetching.
* QA receipt delegates to the pinned existing AppLab X10-028 `qa_test_router_x10.delegate`, which is supplied by the trusted host. Gate plan/source identity must match the Agent job. Even a PASS-labelled runner fixture is `AWAITING_INDEPENDENT_EVIDENCE`, with runtime, physical, Store and certification all FALSE.
* Does not import the original Windows agent, invoke any broker/Finance API, use remote LLM, create PR, merge or deploy. No perpetual execution or trusted live AppLab runner claim.
* Tests cover read policy, stale SHA, duplicate/path traversal, license provenance, forgery, and delegate permission rejection.

Promote X10-016 only after the repo exact-head CI and independent review; never conflate source-level adapter tests with working local Windows worker.