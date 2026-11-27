# Agent efficiency pilot — 18 novembre 2026

**Status:** SOURCE IMPLEMENTED; CI and exact-head verification required; Windows/WSL runtime, actual dependency installation, external API savings and cross-consumer reuse **NOT VERIFIED**.

**Scope:** App-Factory-Agent-Core only. No modification to AppLab, GBrain, App-Factory-Core, the central Capability catalog or application repositories. No new cron or persistent agent loop. No paid LLM or network calls.

## Authority and baseline

- Factory baseline: App-Factory-Core@a8d20ceb71ce9e9e16e6756d257d611fa6f1e0ec (CURRENT.yaml selects Master v27, Golden Index v29, Registry v2).
- Agent source baseline: App-Factory-Agent-Core@f2b4c28cc3a9afa4ef39c6d32fe0a8ef14dac512.
- Product scope: Product Bible; job approval: X10-010; persistence/retry and exactly-scoped lease: AppLab existing queue; existing source adapters: X10-011/012/013.
- Golden governance: AGENT_GOVERNANCE Certified Process, EVENT_DRIVEN_RECONCILIATION Copy-ready Process, PERFORMANCE_REGRESSION_FIXTURES Candidate.
- **No optimizer is an authorization source or proof of a successful test.** Source/CI does not certify a Windows worker or external provider.

## Five execution stages

| Step | Implementation | Current evidence | Remaining work |
|---|---|---|---|
| 1 — Terminal compression | \`plan_rtk_oss\`, fixed read-only command profiles, \`compare_output\` with raw log preservation | Pure policy with negative offline fixtures | Install/test **rtk-oss** on trusted Windows/WSL worker; capture real commands, rc, tokenized outputs and log links; ensure CI logs are retained |
| 2 — Failure budgets | \`build_pybreaker\`, \`guarded_idempotent_call\`; **reuse** X10-011/AppLab queue | Injection-testable BSD-3 adapter | Pin dependency; run isolated fault injection with 429/5xx/timeouts, circuit OPEN/HALF_OPEN and process restart; do not double-retry |
| 3 — Documents | \`convert_local_document\` with allowlisted formats, limits, resolved root and SHA-256 | Fake-converter offline tests | Pin MIT MarkItDown; add process-level wall-time/memory cap and network egress denial; validate structured tables and extracted content against originals |
| 4 — Memory and caching | \`read_scoped_memory\`, \`exact_cache_key\`, bounded \`EphemeralExactCache\` | Scoped provenance, tenant/SHA and TTL tests | Pilot Mem0 as read-only optional adapter against **GBrain canonical store**; evaluate extraction provenance, retention/deletion; only exact/ephemeral cache by default |
| 5 — Routing/compression | \`model_route\` and \`compress_document_candidate\`; both only propose choices | Offline fail-closed cases | Benchmark local vs approved provider; RouteLLM as reference (stale 2024 models), LLMLingua only on non-normative public docs with semantic equivalence checks |

Each stage is a **pilot adapter**, not an end-to-end rollout. The original App Factory Agent roadmap's Windows source intake, independent consumer and real AppLab fault-injection gates remain open.

## External OSS provenance and legal intake

| Project | Source | Checked ref | License / rule |
|---|---|---|---|
| RTK | https://github.com/rtk-ai/rtk | eb710be4719657e8717301caf0eef9a8d8a9e153 | Only \`rtk-oss\` Apache-2.0 initially; full engine and proxy include BUSL-1.1; no global hooks or auto-injected pipelines |
| PyBreaker | https://github.com/danielfm/pybreaker | 2b0b965fcfc7705ca9a776c614ea6cb3ec3fe783 | BSD-3-Clause; circuit breaker, not retry scheduler |
| MarkItDown | https://github.com/microsoft/markitdown | ed178952a6672abdfd35b5f9e76a80b6cefc086e | MIT; local-only basic converter, plugins off; paid Azure/LLM extensions excluded |
| Mem0 | https://github.com/mem0ai/mem0 | fff8a6472512d1bc1a4bccab8c645b65a1df7fe5 | Apache-2.0; candidate, no new sovereign memory database |
| GPTCache | https://github.com/zilliztech/GPTCache | a74ac654473f7bf4109118e8576945161616e17a | MIT; reference for cache only, no new-model adapters promised by upstream |
| RouteLLM | https://github.com/lm-sys/RouteLLM | 0b64fdafe049e596a3f5657c219329f24af24198 | Apache-2.0; last verified default commit 2024-08-10; not a current-model quality guarantee |
| LLMLingua | https://github.com/microsoft/LLMLingua | 01b9e9481d7395e1e83a48df4a062b11f6304325 | MIT; semantic information-loss risk, no policy/code compression |

The seven projects are not vendored, forked, or imported as dependencies in this PR. Actual distribution must verify exact release artifact and license notices again.

## Security and isolation

1. **X10-010 first.** Require a separately trusted job grant for repo/source SHA, tool and paths. Existing worker separately decides if an optimization may run.
2. **Do not trust approval booleans from an issue or LLM.** The adapter booleans are *inner guards* and do not establish actual authority. Runner must bind them to independently verified receipts and time/attempt budgets.
3. **RTK:** fixed argv profile only; never shell-interpolate; edition must be \`rtk-oss\` and its binary signature verified externally. Retain full raw stdout/stderr and exit code privately; when failure or truncation anomaly occurs, use raw log. A byte-count reduction is not proof of saved LLM tokens or quality.
4. **MarkItDown:** running a parser on untrusted Office, PDF or HTML still needs an OS process/container boundary, wall-time/memory cap, file-read restriction and network-denied environment. \`network_isolated=True\` is a caller assertion, not real sandbox enforcement. No plugins, paid Azure or LLM integrations by default; scan outputs before placing them in an LLM context.
5. **PyBreaker:** prevent non-idempotent calls without explicit approval, count attempts in **existing** AppLab queue. Never re-drive terminal operations to obtain a green check. Do not bypass 401/403, auth or scope failures.
6. **Mem0/GBrain:** only tenant/repository/exact-SHA memories with source_url are shown as untrusted candidates. No automatic writes, cross-tenant sharing, or source-of-truth promotion. User content or secrets must not be transmitted to an external service without separate product authorization.
7. **Cache:** only two classes of static, non-sensitive results. Key is bound to tenant, repo, exact source SHA, model, prompt revision and input SHA-256. No semantic similarity cache, no release/security decisions and no writes to GBrain.
8. **RouteLLM/LLMLingua:** routing only chooses a proposal, no provider invocation. No normative Core, Golden, AGENTS, approvals, code or test content goes through lossy compression; public documents may produce reviewable candidate summaries only.

## Benchmark contract

Use a **fixed input corpus** at identical exact source SHA/runner/model configuration. Record:
- \`repo_sha\`, \`job_id\`, \`runner_profile\`, \`tool_version\`, \`model_id\`, \`prompt_revision\`, \`input_sha256\`;
- raw and compressed bytes; tokenizer-specific **actual tokens** before/after, including cache prefixes;
- generation+preprocessing wall time (cold/warm), RAM/CPU and any local GPU utilization;
- actual API billed input/output tokens and EUR where provider bills apply, otherwise \`EUR=N/A\`;
- correctness gate: exit code, failing assertions, missing claims/citations, output truncation, test pass/fail;
- circuit states, retry count, breaker opening/closing, expired AppLab leases and recovery;
- privacy, retention and deletion checks.

Never infer EUR from characters/4 or advertise percentages from synthetic fixtures. **Target is net verified improvement** with no permission/quality regression, not a fixed universal 90%.

## Test plan

\`\`\`shell
python3 -m unittest discover -s tests -p 'test_agent_efficiency.py' -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
\`\`\`

Tests use no network, no secrets, no cloud and no paid providers. For a production pilot, add pinned dependencies in a **separate**, approved worker integration PR after running license/supply-chain review and test on real Windows/WSL. AppLab and GBrain remain unchanged in this PR.

## Promotion boundary

- Current: **Source-only candidate pilot**.
- Copy-ready only after exact-head CI, installed dependency version pinning, real worker measurement and recovery evidence.
- Scoped donor only with a real independently verified agent consumer.
- Golden promotion requires distinct central registry governance, evidence and PR. No promotion is implied here.
