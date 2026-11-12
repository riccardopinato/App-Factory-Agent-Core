# X10-012 — Isolated workspace and exact source SHA boundary

**Factory baseline:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`; X10-010 authorization and X10-011 AppLab queue adapter already source/CI integrated.

## Implementation
- [`scripts/applab_workspace_gate.py`](../scripts/applab_workspace_gate.py): verifies scoped HMAC authorization, job mode, max 2 attempts, clean exact-SHA original Git checkout, external bounded patch file, WorkItem+Investigation source identity and `ALLOW_CODE_EDIT`. It invokes an **injected, already installed AppLab v6.0C** `apply_bounded_patch` function. It does not import, vendor or duplicate AppLab's patch engine.
- The actual AppLab v6.0C worker creates a temporary Git worktree, uses bounded git apply, checks changed paths and test weakening, and removes the worktree/temporary branch in `finally`; source: [bounded_fix_worker_v60c.py](https://github.com/riccardopinato/AppLab/blob/7d07e0fae2cc709d09ce5512efb160b9d4b4faa7/scripts/bounded_fix_worker_v60c.py).
- Adapter checks returned source/work item/attempt identity, the `BRANCH_WORKSPACE_ONLY` authority, max 5 changed files / 250 lines, explicit `EPHEMERAL_LOCAL_WORKTREE_ONLY` scope, no remote write, release or merge. A successful proposal **always** requires subsequent independent AppLab verification; no code execution/test PASS or PR is minted here.
- [`tests/test_applab_workspace_gate.py`](../tests/test_applab_workspace_gate.py): local ephemeral Git fixture with negative cases for no approval, moved HEAD, dirty source, patch inside repo, out-of-scope secret, fake remote write, missing edit capability and excess attempts.

**Not done:** installation/invocation of AppLab code in the Windows Agent, any real patch applied to consumer repo, end-to-end rollback/fault injection after Windows crash, CI exact consumer/worker trust, PR publication. These belong to X10-013/014/015 after trusted runtime and control-plane integration. Fixture callback does not certify actual rollback behavior.

**Rollback policy:** AppLab v6.0C owns rollback/cleanup of the isolated temporary worktree and ephemeral branch. This facade intentionally never runs a second `git reset --hard` or `git clean -fd` against a user checkout and never force-pushes.
