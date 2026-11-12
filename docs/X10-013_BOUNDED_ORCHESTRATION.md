# X10-013 — Bounded AppLab orchestration adapter

**Factory baseline:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`; Agent Core after X10-011 PR #16 (`ac9ab9e9`) and X10-012 PR #17 (`05897470`).

## Source implemented
[`BoundedAppLabOrchestrator`](../scripts/bounded_applab_orchestrator.py) composes the X10-010 admission gateway, X10-011 facade to AppLab's `SQLiteShadowStore`/`DurablePerRepoQueue`, X10-012 bounded workspace guard, and an injected pinned AppLab `adapt_operation_to_work_item` factory. The already persisted AppLab operation is its unit of idempotency; there is no second scheduler, database or patcher.

- `stage()`: require an independently trusted **job digest → persisted AppLab operation ID** binding provided by the control plane; verify exact repository/commit and gateway allowlist, then delegate enqueue/replay to AppLab.
- `prepare_claim()`: inspect **only** a lease issued by the existing AppLab queue (never steal/claim another repo's queued job). Check worker ID, source SHA, expiration, operation ID; create a deterministic WorkItem and refuse draft-PR capabilities. This returns a **dispatch intent**, not proof a worker ran.
- `propose_bounded_patch()`: for explicitly authorized `propose_diff`, delegate to X10-012, which calls an *injected real pinned AppLab v6.0C worker* and returns `INDEPENDENT_APPLAB_VERIFICATION`; no queue completion or certification.
- `recover()`: delegate lease expiration and bounded backoff to the **same** AppLab queue. `prepare_pr` and all merge/release routes remain disabled; actual PR steward is downstream gated work.

[`tests/test_bounded_applab_orchestrator.py`](../tests/test_bounded_applab_orchestrator.py) exercises two independent replay cases (duplicate event & lease after crash), deterministic WorkItem identities, cross-job/expired lease refusal, unbound job, denied write without external approval, forbidden PR and unauthorized authority envelope. CI runs `python3 -m unittest discover -s tests -p 'test_*.py' -v`.

## Evidence boundary
These are offline Python tests using a fake AppLab `Store`, `Queue`, WorkGraph factory and synthetic job approval data. The test suite proves adapter logic **only**. It does **not** prove a production trust mapping exists, a Windows agent or real AppLab v6 worker has been imported/executed, AppLab SQL recovery after a process crash, shell/network isolation, actual consumer tests, an immutable build artifact, independent code review of generated diffs, automated PR merge, Play release or 10x productivity.

**Next gate X10-014/015:** trusted control-plane registration, pinned local AppLab checkout/import, authenticated webhook/event delivery, bounded real execution with exact HEAD, real replay/timeout/rollback and independently verified CI/evidence before terminal lease completion. No self-issued approvals or silent escalation.
