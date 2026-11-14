# Factory MCP OAuth — JWT resource-server boundary v0.1

**Baseline:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`, Master v27, Index v29.
**Stack:** PR #27 → #28 → #29 → #32 → #33, with independent memory PR #26 → #31.
**Status:** CRYPTOGRAPHIC SOURCE CANDIDATE / NO REMOTE SERVICE / NOT CERTIFIED.
**Scope:** owner-only read-only tools, never AppLab enqueue/merge/release, no new runtime listener.

## What is implemented in this PR

`scripts/factory_mcp_oauth_resource.py` implements a strict issuer-pinned RS256 JWT access-token verifier with a host-injected, request-bound Authorization header source and **host-injected trusted JWKS**. Only `typ=at+jwt`, a single exact `aud` resource, exact `iss`, exact owner `sub`, bound `client_id` / `azp`, exact `scope=factory:read`, integer `exp/iat/nbf` and ≤1-hour original lifetime are admitted. Tokens with wrong algorithm, key use, ID-token type, unknown or duplicate kid, JOSE remote key URLs, bad signatures, wrong client/audience/owner, unexpected scopes, missing timestamps, future/expired claims, malformed Authorization headers or overlong tokens are denied generically. No token, private key or provider exception is returned.

`FactoryJwtOwnerIdentity.read_owner_identity` returns exactly the trusted shape expected by `FactoryRuntimeGate(trusted_identity_provider=...)`; an existing `ReadOnlyFactoryTools` then requires its `authorize` gate **for every tool call**. The verifier has no access to a mutable user tool argument to forge trust, and does not return the incoming bearer token.

`protected_resource_metadata()` defines the RFC 9728 resource metadata payload; `unauthorized_challenge()` defines the related HTTP 401 WWW-Authenticate value. The host must actually serve the metadata at `/.well-known/oauth-protected-resource/mcp` and use the challenge. These are inert helpers, not a deployed route.

**Provider contract is intentionally narrow:** issuer and resource are exact HTTPS URIs; resource ends `/mcp`. This adapter deliberately does not accept opaque tokens, alternative JWT algorithms, ID tokens, multi-audience tokens or other OAuth providers until independently audited.

## Host responsibilities (NOT implemented here)

1. Pick an actual OAuth 2.1 authorization server and validate its discovery metadata (RFC 8414/OpenID discovery); register one approved client and configure its exact issuer, client ID, owner `sub` and canonical resource URI. The issuer must grant a **JWT access token** with the required claims and explicit resource binding (RFC 8707). No credentials or real identities in the public repo.
2. Fetch and cache JWKS only from the pinned issuer's discovered HTTPS `jwks_uri`; enforce SSRF protection, timeouts, maximum response size, certificate verification, bounded cache TTL, rotation and refresh-on-unknown-kid. Never use token-provided `jku`/`x5u`.
3. Read Authorization **only** from the current authenticated ASGI/HTTP request. Fail closed when request context is missing; avoid a process-global token, shared authorization state or any user-controllable MCP tool argument for identity.
4. Serve RFC 9728 protected resource metadata + 401 Bearer challenge and run a TLS-enabled reverse proxy, with loopback-only backend and configured Origin/Host validation. Confirm OAuth handshake with actual ChatGPT client. Support PKCE/authorization-server flow via the external provider, not an invented password flow.
5. Provide revocation / short session cancellation, cross-instance shared rate limiting, sanitized audit logs, keys rotation, restart recovery, provider outages and denial-case checks. Existing `FactoryRuntimeGate` revocation and limits are **per process only**.
6. Verify source-SHA-based GitHub/AppLab read providers, minimum permissions, sensitive field filtering, GBrain memory provenance, deployment rollback and remote connectivity on the real service.
7. Complete formal PR reviews, branch-protection verification and exact-head CI before merge; remote deploy needs separate approval/gates and cannot be certified by this source-level suite.

## Offline verification

`python3 -m pip install 'PyJWT[crypto]==2.10.1'`

`python3 -m unittest discover -s tests -p 'test_factory_mcp_oauth_resource.py' -v`

Also run `test_factory_mcp_runtime_gate.py` for the existing owner gate. Tests create ephemeral RSA 2048-bit keys in memory, produce signed **synthetic** access tokens and run positive and rejection cases. No provider, OAuth account, access token or TCP listener is contacted.

**Evidence boundary:** Offline cryptographic verification can establish correct verification logic against synthetic tokens. It does **not** prove actual OAuth issuer configuration, remote resource metadata delivery, successful client authorization, session revocation, TLS, production runtime or availability. No automated merge or public deploy.


## ASGI request boundary (PR #34 follow-up)

`scripts/factory_mcp_oauth_asgi.py` now adds an inert ASGI wrapper for **one host-mounted** read-only MCP application. The wrapper:
- exposes the protected resource metadata JSON at `/.well-known/oauth-protected-resource/mcp` (GET) and emits RFC 9728 `WWW-Authenticate` on 401;
- rejects Host mismatch, unallowlisted Origin, duplicate Authorization, unsupported methods, unknown paths and tokens invalid under the issuer-pinned verifier **before** calling the downstream MCP app;
- verifies the bearer from the trusted ASGI request header, not from tool arguments, and places only the verified owner identity in a `ContextVar`;
- makes that identity available to the existing `FactoryRuntimeGate` through `host.current_identity`; a request lease becomes inactive when its ASGI call ends, so an inherited task context cannot revive an earlier request;
- starts no socket and has no independent credentials, Job API, AppLab queue or provider configuration.

The host must wire a real vetted MCP SDK ASGI app to the wrapper and must **not** mount an administrative/write API underneath it. The host must control TLS termination and trusted reverse-proxy Host/Origin behavior. Approved browser origins must be configured explicitly: absence of `Origin` is normal for some nonbrowser OAuth clients, but an unknown `Origin` is rejected. OAuth/JWKS verification is synchronous here: provide only a bounded cache lookup in request processing, not network I/O from the event loop. Cache staleness and revocation remain host obligations.

Offline ASGI test:
`python3 -m unittest discover -s tests -p 'test_factory_mcp_oauth_asgi.py' -v`.
It uses fake ASGI requests and synthetic signed tokens, **not** real HTTP/TLS, OAuth authorization, GitHub permissions, AppLab runtime or ChatGPT connectivity.

Remote deployment, actual provider registration, independent adversarial review and all merge/release gates remain **NOT VERIFIED**.
