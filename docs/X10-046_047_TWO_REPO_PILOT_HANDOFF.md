# X10-046 + X10-047 — Two real agent feature pilot handoff (HUMAN_GATE)

Factory baseline Core@c5adc147046beb7024629466d10eeb799c3c2619 (Master27/Index29).

**Status: NOT RUN / PLAN+OFFLINE CONTRACT ONLY.** The separate and already implemented AppLab/Agent Core adapters remain the execution authorities:
- `agent_job_gateway.py` issues no self-approval; human-authorized job with exact source/path limits;
- AppLab bounded workgraph/worktree/fix and `agent_pr_steward_adapter.py` prepare a *draft PR*, not auto-merge;
- QA test router and GitHub CI bind exact PR-head SHA; Codex is independently reviewed;
- `scripts/x10_agent_pilot_gate.py` validates a separately obtained genuine worker PR/QA receipt and demands acceptance of pilot A before pilot B.

**Suggested, not yet executed target sequence:** A = AppLab self-canary, test-only noncritical feature (the pre-existing self-canary allowlist permits AppLab itself); B = World-Days, separate consumer, requires explicit approved target and isolated trusted worker. Do not enable B by broadening AppLab SELF_CANARY silently. Target SHA, operation ID, actual worker transcript, CI, review and rollback must be independently pinned at execution time; a GitHub PR manually created by ChatGPT is NOT an agent-produced PR.

**External blocker:** Windows AppFactoryAgent v0.1–v0.4 verified source import X10-008 remains BLOCKED and live X10-015 end-to-end worker test is NOT_VERIFIED. A fixture contract test does not prove the agent running. No finance access, paid model, Store, release, autonomous merge, secrets or branch protection change. For each pilot: 1–5 changed safe files, ≤250 lines, at most two attempts, independent QA, owner signoff before progress; pilot B only after accepted A.

**Final completion requirements:** actual agent execution on selected repo, exact persisted job and trusted work item, real draft PR with CI, Codex clean review, failure/recovery trace, human acceptance and cross-repo comparison. No pilot promotion in central queue from this source PR alone.
