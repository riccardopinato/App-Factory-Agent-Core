# Agent Core orchestration pilot — process comparison

**Existing:** X10-013 documented bounded AppLab bridge, 17+ offline tests and mock queue, no real worker execution; source contract `contracts/job.schema.json` explicitly calls itself DESIGN ONLY. Existing guardrails already reject unauthorised PR/merges.

**Spec Lite:** one FR and four explicitly mapped ACs, 4 additional regression tests in existing offline suite, fixed target/Factory SHAs and proposed ownership. No new scheduler or app runtime code. Test actual outcomes through existing `validate.yml`.

**Cost evidence:** measure added test/docs lines and source CI job duration. Real Windows worker runtime throughput, cost/token savings, E2E replay and user-device tests remain NOT_MEASURED/NOT_VERIFIED. This pilot verifies only fixture semantics, not an actual AppLab work execution.
