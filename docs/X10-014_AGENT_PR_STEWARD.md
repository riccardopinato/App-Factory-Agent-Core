# X10-014 — Agent Core → AppLab Draft PR Steward adapter

Factory baseline: App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619 · Master 27 · Golden Index 29.

## Reuse-first design

No new scheduler, PR engine, GitHub client or patch materializer. The adapter in scripts/agent_pr_steward_adapter.py delegates to the existing AppLab v6.0E draft_pr_steward_v60e.execute_remote, rather than bypassing its branch/patch/source preflight. The installed AppLab runtime and trusted credential transport MUST be injected by the runner; untrusted issue text or LLM output cannot supply a trusted operation or approval.

Boundaries:
- A job with prepare_pr requires signed, short-lived, exact-digest authorization from X10-010, with target repo/commit/paths and approval receipt.
- A trusted persisted AppLab operation binds job digest, original source SHA, WorkItem, independently prepared bounded patch result, root WorkItem and retry number.
- Separate CREATE_DRAFT_PR / UPDATE_DRAFT_PR capabilities are required; SELF_MERGE, WRITE_MAIN, RELEASE and self-approval are rejected.
- Patch content/hash/changed-file scope are rechecked before calling the *pinned* AppLab steward. AppLab itself performs actual git worktree/materialization/remote branch/idempotence checks.
- Result must be a source-bound draft PR record; no merge, release or consumer certification.
- assess_exact_head_evidence is READ ONLY and rejects skipped/failed/missing/duplicate checks, mismatched PR source/head or stale review; it never invokes merge.

## Validation

Offline tests/test_agent_pr_steward_adapter.py covers successful proposal, missing/forged authorization, escalation, patch tampering, retry budget, stale PR source and exact-head check/review gates. Tests use a fake AppLab transport, not real remote credentials.

**SOURCE+PYTHON_CI only until exact-head required CI, independent Codex review and gated merge.** Full AppLab/Windows worker, authenticated live PR creation, real fault recovery, human authorizations and consumer device runtime remain NOT_VERIFIED. X10-015 retains the Windows source/hardware HUMAN_GATE. No actual merge authority is granted by X10-014.
