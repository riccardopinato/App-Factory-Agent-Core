# X10-041 — Diff-aware repository monitor, advisory-only intake

**Factory baseline:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`. **Precondition:** [X10-040 architecture](https://github.com/riccardopinato/Idee-app-Archivi-riferimenti/blob/db8bf17fcab0f10196a67dfb5f827da9c26994bc/19-APP-FACTORY-10X/EVIDENCE_X10-040_CROSS_APP_KNOWLEDGE_ARCHITECTURE_2026-11-12.md).

## Implemented source
[`scripts/diff_capability_monitor.py`](../scripts/diff_capability_monitor.py): pure, bounded, read-only adapter taking an **authenticated source event** with `repository/ref/base_sha/head_sha`, a trusted `verified_head_sha` from control plane and an already calculated bounded `smart_test_plan.git_diff_evidence()` result from **AppLab** (no duplicate git diff implementation).

The trusted caller must attach `base_sha` and `head_sha` provenance **after** independently proving the diff was computed from those exact commits. Event authentication, checkout existence and source identity are NOT inferred from event JSON; external independent trust arguments fail closed unless all explicit flags are true. Reject stale HEAD, missing/invalid SHAs, untrusted/oversized/truncated diffs, duplicate/unsafe/hidden paths, wrong diff identity and missing metrics.

Output `X10_041_DIFF_HINTS` has deterministic SHA256 monitor identity, source commit, changed-path digest and bounded path-only hints (identity, notifications, storage, localization, theme, billing, testing), marked `ADVISORY_ONLY`. **Never copy code hunks/source text, secrets, credentials, personal data or financial data** into the advice. Signals do not create an official CAP, donor, Golden, product roadmap or PR. The same delivered event yields the same candidate key; a different SHA yields a different candidate. No persistent monitor service, scheduler or database created.

[`tests/test_diff_capability_monitor.py`](../tests/test_diff_capability_monitor.py) includes offline positive/negative fixtures for deterministic idempotency, exact-head, tampered/missing trust, source mismatch, unsafe paths, duplicate paths, truncation and non-disclosure. Run via `python3 -m unittest discover -s tests -p 'test_*.py' -v`.

## Explicit next gates
- **X10-042:** join candidate path hints to authoritative CAP registry, SOURCE_INVENTORY, donor SHA/license and consumer/product scope before recommending a cross-app use.
- Real GitHub event delivery requires an authenticated provider/connector, rate-limit/backoff, supported repo allowlist, trusted AppLab diff execution and a recorded successful verified run. **NONE** are implemented here; source+CI does not prove a live monitor or runtime recovery.
- X10-043/044 human semantic review and recommendation cockpit must remain proposal-only. No Golden promotion/merge/release.
