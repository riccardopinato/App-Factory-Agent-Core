# Pre-merge integration candidate — App Factory MCP/GBrain/AppLab

**Factory baseline:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`, Master v27 / Golden Index v29.
**Not merged, deployed, consumer-verified or certified.**
**Dependency:** PR #32 → #29 → #28 → #27, GBrain PR #31 → #26. Agent Windows PR #30 is independent and remains unimported.

This test branch reuses the **actual source modules** from Agent Core's stacked Gateway/MCP/runtime branch, a pinned source checkout of GBrain adapter + quality `App-Factory-Agent-Core@11e9c8ed834838ebe49a7c68693daa84ccffdfd7`, and AppLab `@0b45e4a474fe958a141430a6447c50ccf6d114b2` with a temporary SQLiteShadowStore. No competing queue.

GitHub and GBrain inputs are **synthetic** but follow their real API envelope shape. The in-process MCP client exercises all four source tools (repo HEAD, PR/CI report, persisted AppLab operation checkpoint and projected GBrain context), deliberately keeping review/certification false, excluding credential-bearing memory and refusing a fifth read after the owner-bound rate cap.

The same test calls the **real** pinned GBrain quality diagnostic and validates that keyword-only recall is not treated as verified semantic search or data completeness.

CI `.github/workflows/factory-full-readonly-pinned.yml` installs official `mcp==2.3.0` and runs only this hermetic acceptance test. This can prove cross-module source compatibility, NOT real authentication to ChatGPT, real GBrain OAuth, Windows agent execution, production network exposure, real reviewer approval or final release.

No PR from this stack should merge to main before its exact-head CI, blocking review policies and independent source safety gates are met. Do not merge the integration harness as a replacement for the underlying PR approvals.
