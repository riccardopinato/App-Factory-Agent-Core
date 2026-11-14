# GBrain MCP ↔ ChatGPT ↔ App Factory: recovery and reuse gate

**2026-11-14 — READ-ONLY AUDIT + OPT-IN WINDOWS HELPER. NOT DEPLOYED/CERTIFIED.**
Factory baseline: `riccardopinato/App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619` (Master v27, Index v29).

## Observed, not assumed
- Windows 11 / WSL Ubuntu ran GBrain MCP `gbrain-serve.service` with local PGLite health 200 on `127.0.0.1:3131` (reported v0.60.554.0).
- CLI exists under `$HOME/.bun/bin/gbrain`; default noninteractive Bash PATH omitted Bun. Working diagnostic: `export PATH="$HOME/.bun/bin:$PATH"; gbrain mcp expose --status --json`.
- Tailscale Funnel served a public HTTPS hostname; initial local connection refused + Funnel 502 became local/tailnet 200 repeatedly after WSL warmed. Operator observed valid /health JSON over phone mobile network while WSL was held open. This is one observed remote path, **not uptime certification**.
- ChatGPT's connected GBrain memory tools still produced generic internal errors. **Auth cause not established.**
- `gbrain backup check` was requested by GBrain because all knowledge-asset recovery was not verified; earlier partial backup rehearsal is not full-coverage validation.

## Operational hardening: WSL availability

Microsoft documents that systemd services do not keep a WSL distro running by themselves.
`scripts/windows_gbrain_keepalive.ps1` supports three explicit modes, default **Status**:

```powershell
pwsh -NoProfile -File .\scripts\windows_gbrain_keepalive.ps1 -Mode Status
pwsh -NoProfile -File .\scripts\windows_gbrain_keepalive.ps1 -Mode Install
pwsh -NoProfile -File .\scripts\windows_gbrain_keepalive.ps1 -Mode Status
# Explicit rollback:
pwsh -NoProfile -File .\scripts\windows_gbrain_keepalive.ps1 -Mode Remove
```

Install creates only `AppFactory-GBrain-WSL-KeepAlive` for the interactive Windows user, with `wsl -d Ubuntu --exec /usr/bin/sleep infinity`. No GBrain service restarts, token changes, database access, Tailscale configuration changes, or touching the paused AppFactoryAutopilot task. Existing same-name task is never overwritten. The `Status` check can wake Ubuntu briefly and uses bounded retries.

**Limits:** source-only Windows script, not yet physically tested; keepalive only when a Windows user is signed in, and never prevents PC sleep/offline periods. No promise of 24/7 service. Power consumption persists while active. Do not run Install without owner review.

## Diagnose ChatGPT connection without touching OAuth secrets

1. Keep WSL awake; check local `/health` and from a separate public network. Do not infer public availability from WSL's tailnet DNS resolution.
2. Open GBrain's owner dashboard locally at `http://localhost:3131/admin` and view **Request Log**; do not share the owner bootstrap credential, cookie, OAuth token, or private memory contents.
3. Trigger a nonmutating GBrain memory tool in ChatGPT and check server Request Log:
   - No inbound request: inspect ChatGPT connector, remote reachability, and registration.
   - Inbound rejected: inspect sanitized HTTP reason. Correct resource URL must match `https://<funnel-domain>/mcp` and grant scope/source. Reauthorize through the ChatGPT UI **only if evidence indicates stale/invalid authorization**.
4. Preserve `127.0.0.1` binding behind Funnel. Never change bind to `0.0.0.0` just to fix auth.
5. Separately run `gbrain backup check` on WSL for knowledge assets prior to changing GBrain persistence.

## Future App Factory gateway: authority contract (NOT IMPLEMENTED)

- ChatGPT Project: reasoning, active session and user context, no perpetual chat wakeup by arbitrary external process.
- App-Factory-Core: authoritative Factory rules.
- GBrain: memory adapter, not an executor, queue writer or shell interface.
- Agent Core: policy-scoped validation (X10-010 gateway, signed receipts).
- AppLab: the sole durable queue, lease/recovery and QA authority.
- Windows Autopilot: bounded local executor, remains paused until an independently authorized pilot.
- GitHub: current authenticated communication bridge; fallback if custom write-capable MCP is unavailable to the user's plan.

A prospective **read-only** status gateway can expose only filtered state, bounded receipt, and health (no arbitrary shell/file routes, no SQLite secrets or raw logs). Deployment and ChatGPT connector capability require distinct security review and real tests. Avoid a second MCP scheduler or competing AppLab queue. No new paid AI/API use.

## Evidence gates to close next
- Keepalive task installed and verified on actual Windows device, including idle, process crash and next login.
- External health steady while signed in, and OAuth discovery verified on public path.
- Actual read-only ChatGPT GBrain tool success OR sanitized Request Log root cause.
- GBrain backup coverage verified.
- Separate gateway implementation/CI/review; this document alone certifies nothing.

References:
- Microsoft WSL systemd: https://learn.microsoft.com/windows/wsl/systemd/
- GBrain ChatGPT troubleshooting: https://github.com/garrytan/gbrain/blob/master/docs/mcp/CHATGPT.md
- GBrain remote MCP: https://github.com/garrytan/gbrain/blob/master/docs/guides/remote-mcp.md
- Core Goldens: `golden/governance/GOLDEN_AGENT_GOVERNANCE_v1.txt`, `GOLDEN_EVENT_DRIVEN_RECONCILIATION_v1.txt`.

## Operational checkpoint 2026-11-14 — user-provided Windows receipt + actual ChatGPT read

**Operator-reported Windows execution (not independently observed on the machine):**
```text
KEEPALIVE_TASK=NOT_INSTALLED name=AppFactory-GBrain-WSL-KeepAlive
GBRAIN_LOCAL=OK version=0.60.554.0 engine=pglite
KEEPALIVE_TASK=INSTALLED_AND_STARTED name=AppFactory-GBrain-WSL-KeepAlive
GBRAIN_LOCAL=OK version=0.60.554.0 engine=pglite
KEEPALIVE_TASK=Running name=AppFactory-GBrain-WSL-KeepAlive
KEEPALIVE_LAST_RESULT=267009
GBRAIN_LOCAL=OK version=0.60.554.0 engine=pglite
```
Task Scheduler result 267009 / 0x41301 = SCHED_S_TASK_RUNNING (success/running status), not a failed task. The downloaded/install-tested local script has NOT been byte-for-byte reconciled against the PR source; treat Windows result as USER_REPORTED, not DEVICE_VERIFIED for this repository's exact script SHA. No evidence of logoff/reboot/sleep persistence yet.

**Authenticated connector evidence (tool-observed in ChatGPT, same conversation):** successful **read-only** `mcp__GBrain__recall` of prior App Factory memory fact, repeated success, and `context_pack` success. This establishes connector access for those two read surfaces now; it does not verify every MCP method or future uptime. Earlier generic internal errors resolved without documented OAuth credential changes. Recall reported `keyword_only_embedding_disabled` degradation; semantic search optimization is a separate follow-up.

**Next acceptance:** compare installed file hash to source in branch, test at next Windows sign-in, record availability of public `/health` and repeat ChatGPT read after a cold boot; inspect recall embeddings only if semantic retrieval is needed. Retain PR in draft until review/Windows canary and full CI exact SHA.
