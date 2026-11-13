# X10-008 / X10-015 — Windows Autopilot v0.6 source and evidence reconciliation

**Date:** 2026-11-13. **Factory baseline:** App-Factory-Core@`ee72dbb1b0de2cd71bc4aac42c350853c6915159`, Master v27 / Golden Index v29.
**Agent Core baseline:** `7616459c91311f7ce0b5d3ca8b0d97a9363b7a52`.
**Authority:** Product Bible, Agent Core AGENTS, X10-010..014 and existing AppLab adapters. This PR is REPORT / RECONCILIATION ONLY: no Windows service deployment, no GitHub main writes, no PR merge and no queue promotion.

## X10-008 — source recovered, private canonical import pending

Conversation attachments include original local Windows versions v0.1–v0.4.2 and Autopilot v0.5/v0.5.1/v0.6.0. The exact **v0.6.0 ZIP** SHA-256 is
`c5af037f9a00f340f26a6d020a0b9cb842928b298e5b48d377bb46407f8f7da2`.
Its allowlisted, inspected files and file identities:

| File | Size | SHA-256 |
|---|---:|---|
| `app_factory_autopilot.py` | 58,338 B | `035421b5dd8e05ebfd7b2d1297b941782a21601d31fe6bc945854e68bb2988a2` |
| `test_autopilot.py` | 24,934 B | `e0221f3465d7603945f8330108b6f1a608cc9aad6bf6001c8a75a7b814497b80` |
| `upgrade_autopilot_v060.ps1` | 4,892 B | `a41f20e3ef79d51f62d8ff1a239b84fc27d556b8c5bb7b41b49acfb2e3e28b28` |
| `README.md` | 3,806 B | `99104e6c0402de4a92c6c53ae86a077b8d562bcae08b60f066b29e1b86fbf81c` |

The ZIP was inspected and the 28 packaged Python tests passed in an isolated Python runner on 2026-11-13. A limited regular-expression search found no obvious embedded GitHub/OpenAI token or private-key marker **in these four files only**. This is not a comprehensive secret, license or supply-chain audit. The installed Windows worker may have a later hotfix and must be inventoried separately. **Never add live `autopilot.json`, SQLite, workspaces, logs, .env, secrets or model cache to this public repository.**

X10-008 remains **BLOCKED / PRIVATE_IMPORT_PENDING**: no dedicated private canonical source repository or approved review of original Windows files is yet present, nor does this documentation turn conversation uploads into a GitHub source import. The local `scripts/x10_windows_autopilot_receipt.py` companion creates a reviewable manifest / *opt-in* archive of the two required installed Python files (plus the optional updater when present). Publish to a dedicated private repo only after owner review, complete secret scanning, licensing/provenance check and exact SHA verification. No public source upload was performed.

## X10-015 — bounded real-world evidence, not full E2E certification

Authenticated GitHub observation of 180FlipCharge:
- Issue [#6](https://github.com/riccardopinato/180FlipCharge/issues/6) authorized local agent task by issue label; [draft PR #7](https://github.com/riccardopinato/180FlipCharge/pull/7) is open on `agent/autopilot-6`.
- PR current HEAD `92530c4a8d41c2834655275d667fab7824e60598` (five added KDoc lines; final indentation correction was applied from ChatGPT, **not by the Windows agent**).
- [CI run 42935192666](https://github.com/riccardopinato/180FlipCharge/actions/runs/42935192666) completed with success at that exact HEAD.
- User-provided Windows CLI screenshot/text on 2026-11-13: v0.6.0 reports one activity `ci_pass`, PR 7, `repair=0`. This is **USER_REPORTED**, not an independently authenticated Windows worker trace.
- Canary issue [#19](https://github.com/riccardopinato/180FlipCharge/issues/19) exists, but no corresponding agent PR was observed at this checkpoint.

This demonstrates a limited **single-repo PR/CI pilot**, not X10-015's required two-repo, crash/restart/replay and AppLab-trusted operation/lease E2E evidence. The output of the optional read-only GitHub receipt script is not an authenticated control-plane signature.

### Reuse map — do not create a third orchestration system

| Local v0.6 function | Canonical owner | Integration direction |
|---|---|---|
| Ollama / Qwen local model execution | Windows executor | Keep local adapter; do not export tokens/models |
| SQLite `autopilot-state/queue.sqlite3` | Temporary local history | Preserve read-only during staged migration; **AppLab owns future canonical queue**, no dual writers |
| Issue parsing / authorization | X10-010 job gateway | Require trusted external approval receipt, exact repo/path/SHA; label+author alone insufficient |
| Worktree and restricted patch | X10-012 + AppLab bounded worker | Adapt local proposal output, don't replace independently verified worktree engine |
| Retry/lease/recovery | X10-011/013 + AppLab store | Reconcile key/state and operation ID; only one scheduler and durable write authority after migration |
| PR draft and CI exact-head | X10-014 + AppLab PR steward | Adapter receipt, independent CI/review; never self-approve or auto-merge |
| Research, QA and evidence | X10-016 + AppLab router | Invoke existing adapters, no duplicate QA service |
| Dashboard | AppLab Operations Studio | Read-only compatibility view during transition, no remote Windows control |

**Real source adapter (no dispatch):** [`scripts/x10_windows_job_adapter.py`](../scripts/x10_windows_job_adapter.py) projects a SQLite row with **original pinned base SHA** into the existing [`X10-010 gateway`](../scripts/agent_job_gateway.py) job design; `evaluate_legacy_candidate` calls the canonical gateway and cannot mint an approval. A local `agent:dev-pr` label or owned GitHub PR does **not** satisfy a signed control-plane receipt. It does not enqueue in AppLab, create a PR, or run Qwen. Negative tests assert stable replay identity, denied write without signed approval, protected path refusal and missing source rejection.

**Migration gate:** take private source inventory and preserve database backup; run a shadow, read-only migration comparison; verify job-by-job idempotency (including #6 and #19), permissions, cancellation and restart. Stop old scheduler *before* enabling the AppLab-backed writer; never delete local SQLite until deterministic replay and backup/restore pass. No bridge in this PR starts either scheduler.

### Concrete acceptance to unblock X10-008 / X10-015

1. **X10-008:** owner-reviewed private repository containing only sanitized worker source + independent scan/manifest, pinned SHA and PR; license and exact package lineage checked.
2. **X10-015 / pilot A:** trusted Windows worker run receipt bound to a real AppLab operation and X10-010 signed authorization, exact source, PR, independent CI and review, plus verified stop/crash→resume without duplicate PR or write.
3. **X10-015 / pilot B:** second independently authorized repo with its own matching worker/CI/receipt; no extrapolation from first pilot.
4. **Only then:** update canonical `PROGRAM_QUEUE.json` with appropriate evidence, review and exact-main gate. X10-046/047 have separate human acceptance; no implicit promotion.

## Owner-machine collection (read-only by default)

Once the script is available on the reviewed branch:
```powershell
cd "$HOME\AppFactoryAgent"
python .\x10_windows_autopilot_receipt.py --root . --github-read-only --out .\autopilot-state\x10_receipt.json
```

The `--export-private` option writes a ZIP containing only a strict source allowlist; it **never uploads**. The receipt omits prompt bodies, logs, local user paths and SQLite contents. A GitHub workflow marked green by this helper is **observational only**: it never sets an exact-head required-CI PASS, which remains delegated to the existing X10-014 AppLab steward and independently reviewed check policy. The optional PowerShell updater may be absent from the installed root and is not required for private source export. Review both files offline before transfer. Do not post ZIP or unsanitized logs to public GitHub.

**Current verdict:** X10-008 = SOURCE_RECOVERED_LOCAL, CANONICAL_IMPORT_BLOCKED. X10-015 = SINGLE_REPO_GITHUB_CI_OBSERVED, TWO_REPO_WINDOWS_E2E_NOT_VERIFIED. No merge or automatic action authorized.
