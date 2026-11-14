# Factory MCP runtime preflight v0.1 — SAFE SOURCE ONLY

Factory baseline: `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`, Master v27, Index v29. Depends on stacked PR #29 → #28 → #27.

`FactoryRuntimeGate` is a host-injected callable that fits the existing `ReadOnlyFactoryTools.trusted_owner_authorizer` interface. It rejects missing/unverified owner identity, expired or overly long host sessions, improper scopes, source errors and over-budget calls. Per-process revocation and 60-second rate windows are deterministic and tested. It receives NO access token or password itself; `host_verified` is a trusted **upstream assertion**, not OAuth verification performed by this library.

`runtime_exposure_preflight` rejects unsafe public binds and missing host/TLS/provider reports before any host starts a listener. It intentionally never returns `runtime_verified=true`, `connected_to_chatgpt=true` or `certification_granted=true`. Even if all static checks pass, this does not validate issuer/audience/signature, DNS/reverse proxy settings or allow remote deployment.

The only currently verified MCP execution is the in-process official MCP SDK CI on PR #29. There is NO new network endpoint, service, paid API, shared Windows user token or OAuth client.

Before real remote deploy, separately implement and test full OAuth resource server authentication (issuer/JWKS, audience/resource, scopes, per-user tenant binding, expiry, revocation, CSRF/rebinding and denial cases), HTTPS and reverse-proxy config, rate limits distributed across host instances, audit logging without secrets, recovery, health and rollback; then verify ChatGPT consumer connectivity using real signed credentials on the desired provider. Do not share GBrain's public `/mcp` port or tenant without a security review.

Offline tests: `python3 -m unittest discover -s tests -p 'test_factory_mcp_runtime_gate.py' -v`.

Status: **RUNTIME PREFLIGHT SOURCE IMPLEMENTED**, deployment/real auth **NOT VERIFIED**. No write authority.
