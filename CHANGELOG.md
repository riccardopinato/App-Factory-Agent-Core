# Changelog
## 2026-11-11 — Context-sync roadmap M2–M5: evidence-gated implementation
- [PR #12](https://github.com/riccardopinato/App-Factory-Agent-Core/pull/12) merged `32d4d41a3774d465c28056de7dfb83469c631d06`: pure offline retry/reconciliation/privacy/semantic-review helpers with green tests; no production runner integration.
- Added recovery playbook, semantic-diff review protocol and reuse admission candidate; no Golden, donor or CAP auto promotion.
- [Ideas #97](https://github.com/riccardopinato/Idee-app-Archivi-riferimenti/pull/97) merged with privacy-safe 35-repo registry and Site source view. No Site deploy or automatic data refresh claimed.
- Open: four repo admin PR permissions, actual schedule/dispatch, integration/fault injection, second independent consumer, real cost/quote measurement.

## 2026-11-11 — Reconciliation identity corrected and proved on real Actions run
- [PR #8](https://github.com/riccardopinato/App-Factory-Agent-Core/pull/8): bot `git config` moved before merge, CI green.
- [run #43052705998](https://github.com/riccardopinato/App-Factory-Agent-Core/actions/runs/43052705998): merge of bot branch with advanced main succeeded, snapshot write/check PASS, branch push PASS. Only `createPullRequest` denied by repository Actions setting. [Cleanup #10](https://github.com/riccardopinato/App-Factory-Agent-Core/pull/10) removed temporary scoped push trigger.
- [Fleet audit](https://github.com/riccardopinato/Idee-app-Archivi-riferimenti/blob/main/18-AGENT-FACTORY/EVIDENCE_M1_35_REPO_SWEEP_AND_RETRY_2026-11-11.md): all 35 workflow sources inspected, no schedule/dispatch event for context workflow yet, original Finance/Scene fixed by CI but runtime not tested.
- Windows coding-agent source and production functionality unchanged; no Golden certificate or autonomous scheduling success claimed.

## 2026-11-11 — Context snapshot E2E canary: PASS partial, admin blocker
- Live [run 43040897071](https://github.com/riccardopinato/App-Factory-Agent-Core/actions/runs/43040897071) completed HTTP upstream read, `CONTEXT_SNAPSHOT_WRITE_PASS`, `CONTEXT_SNAPSHOT_CHECK_PASS`, committed and pushed `automation/context-snapshot`, but failed `gh pr create` due GitHub Actions permission.
- Comparison: `btrader` bot [PR #5](https://github.com/riccardopinato/btrader/pull/5) was successfully created by github-actions[bot] and rerun without duplication. 5 canary jobs/branch snapshots proved, 4 PR permissions blocked.
- Canary `on.push` removed from workflow after tests; cron/dispatch not run. See [central evidence report](https://github.com/riccardopinato/Idee-app-Archivi-riferimenti/blob/main/18-AGENT-FACTORY/EVIDENCE_M1_CONTEXT_SYNC_CANARY_2026-11-11.md).
- No local Windows agent import/verification or source code changes.

## 2026-11-11 — 35-repo context-sync rollout (infrastructure lane)
- GitHub Actions workflow metadata-only merged in the default branch of all 35 owner repositories; original Agent/Finance/Scene context-snapshot workflows hardened.
- Real schedule/dispatch, bot-authored snapshot PR and permission recovery remain NOT_VERIFIED; PR CI checks do not certify scheduled runtime.
- Added infrastructure lane to `ROADMAP.md` and linked the cross-repo hub; five product-agent maxi-steps remain open until local Windows source is imported and tested.
- Factory reference resolved at `c5adc147046beb7024629466d10eeb799c3c2619`, Master v27 / Golden Index v29. No paid model calls, code-agent runtime, secrets, trading or deployment.

## 2026-11-11 — Bootstrap documentale
- Created canonical Product Bible, technical architecture, ADR, local Windows agent fact sheet v0.1–v0.4, roadmap, trust boundaries, provenance and job schema.
- Added stdlib-only GitHub context snapshot + workflow PR-only and deterministic offline checks; CI on PR pending.
- No local Windows runner sources, no model binaries, no credentials, no claim of coding agent runtime.
