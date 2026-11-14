# App Factory MCP read-only tool adapter — source v0.1

**Factory baseline:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619` Master v27 / Golden Index v29.
**Stacked dependencies:** Gateway PR #27 -> evidence Gateway PR #28 -> this adapter.
**State:** SOURCE + TEST. This PR does **not** create a ChatGPT-registered remote connector.

## Protocol choice (reviewed 2026-11-14)
- Use **official** `modelcontextprotocol/python-sdk` **v2.3.0**, pinned for CI; this supports the 2026-07-28 stateless protocol and legacy clients. Do not hand-roll JSON-RPC, OAuth or session handling.
- `scripts/factory_mcp_readonly.py::build_mcp_server` creates an `MCPServer` object with three default tools (four when a trusted GBrain memory projection is explicitly bound); it deliberately does **not** call `mcp.run()` or open a port.
- An authenticated, trusted host must instantiate `ReadOnlyFactoryTools` with `FactoryEvidenceGateway` and `trusted_owner_authorizer` (injected, never a model tool argument). The host must validate user identity and GitHub/AppLab access before constructing the object; the callback must authorize every invocation.
- No `stdio` executable or `streamable-http` port is configured by this source. A future real host can choose a transport only with authentication, authorization, TLS, rate limits, protections against DNS rebinding and secrets/log leakage. OS-user-only stdio would not satisfy remote ChatGPT authentication.
- Tool list: `factory_repository_status(repository)`, `factory_pr_evidence(repository, pr_number, expected_head_sha)`, `factory_operation_checkpoint(repository, operation_id, source_sha)`.
- The tool set has **no arbitrary command, write, enqueue, GitHub merge, memory mutation or paid LLM**. Inputs are checked inside inherited Gateway allowlists. GBrain is deliberately not an executor; its recall projection PR #26 is a different trust domain and is only optionally composed through `scripts/factory_mcp_memory_context.py` using owner-bound, injected GBrain recall + pinned PR #26 projection; raw GBrain responses are not exposed.

## Verification
Normal CI runs stdlib offline tests. Dedicated workflow `.github/workflows/factory-mcp-sdk.yml` pins Python 3.12 and `mcp==2.3.0`, launches a real in-process `Client(MCPServer)` and exercises the default three tools, optional memory context tool, real pinned GBrain projector and owner denial without a network server, credentials or PC access.

**Never mislabel this**: an in-process MCP SDK test is proof that a tool interface registers and responds, **not** that ChatGPT can connect or that an external identity was authenticated. Remote integration requires a genuine host/deploy and consumer-verified API permission. Keep code integration in PR and don't connect it to the existing GBrain public Funnel without a security review and isolation.

References:
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/changelog.mdx
- https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0
- https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/index.md
- https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/client/index.md

## Optional GBrain memory context, source-only
- `FactoryMemoryContext` is constructed only by a trusted host with the same `ReadOnlyFactoryTools` owner authorization gate, its existing authenticated GBrain recall provider, and the exact source-pinned `project_recall` from PR #26. No direct GBrain network code is imported here.
- When and only when bound to `build_mcp_server(service, memory_context=...)`, a fourth tool `factory_memory_context(query)` appears. A default server advertises only the three GitHub/AppLab read tools.
- Only public/world, source-labelled, context-only facts are returned, and never CI status, approval, secret data, job authorization or instruction precedence. It cannot prove absence when keyword-only recall is degraded.
- CI checks out `App-Factory-Agent-Core@3a3818d47da0a8b55ca12b82043893e095eba9d1` to test the actual PR #26 projector with synthetic records. No personal GBrain memory or credentials are read.
