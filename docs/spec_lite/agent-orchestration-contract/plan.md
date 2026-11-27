# Plan — bounded AppLab WorkItem regression-only pilot

1. Reuse `scripts/bounded_applab_orchestrator.py`, `scripts/agent_job_gateway.py`, `scripts/applab_queue_bridge.py`, their existing `Store/Queue` fixtures, and `tests/test_bounded_applab_orchestrator.py`.
2. Add four independent tests for read-only WorkItem authority, out-of-scope paths, wrong SHA and unsigned write refusal. No production code change; no second scheduler, worker, ledger or permissions API.
3. Run the existing Agent Core `validate.yml` offline contract suite. Record exact-head SHA and run, no invented live execution.
4. Review the current Product Bible/roadmap and open Agent Core PRs (including #25–35) without changing their ownership.
5. Rollback: revert test/docs-only PR. The trusted permission gateway remains unchanged.
