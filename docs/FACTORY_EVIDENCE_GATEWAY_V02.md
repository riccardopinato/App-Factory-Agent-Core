# App Factory read-only evidence Gateway v0.2 (stacked on v0.1)

**Date:** 2026-11-14
**Factory:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619` (Master v27, Index v29)
**Dependency:** PR #27 `feat/factory-readonly-gateway-20261114`. No runtime deployment.

## New source
- `scripts/factory_status_v02.py::FactoryEvidenceGateway` **inherits** v0.1 read-only GitHub HEAD/AppLab operation access; adds a bounded PR evidence reader, batch (<=12), and a read-only operation checkpoint projection. No second queue/scheduler.
- `scripts/factory_github_evidence_reader.py::GitHubEvidenceConnector` adapts an **already connected, authenticated, injected** GitHub fetch action to actual GitHub REST `GET /pulls/{n}` and `GET /actions/runs?head_sha=...&event=pull_request`.
- Strict host-controlled repository allowlists and exact expected PR HEAD; validates PR base repository, both SHA values, CI run source SHA, report timestamps, run statuses and duplicate IDs.
- Returns only minimal normalized, provenance-labelled records. Does not forward PR body, token, job payload, comment text or raw logs. Upstream provider errors are sanitized.
- `ALL_OBSERVED_CHECKS_SUCCESS` means ONLY those **observed PR-triggered workflow runs** succeeded. It does NOT mean branch protection, required third-party checks, review, release, device or runtime success. The result always says `review_verified=false`, `exact_head_gate_verified=false`, and `certification_granted=false`. Missing/truncated runs fail closed.
- `operation_checkpoint` calls the real AppLab `get_operation` path already exercised in the v0.1 pin; never reaches live SQLite or claims recovery verification.

## Validation
- `python3 -m unittest discover -s tests -p 'test_factory_status_v02.py' -v`
- `python3 -m unittest discover -s tests -p 'test_factory_github_evidence_reader.py' -v`
- Existing v0.1 pinned AppLab integration CI inherited from stacked parent; no live queue writes or encrypted asset reads.
- Actual GitHub connector API envelope was compared against `riccardopinato/App-Factory-Agent-Core` PR #27 and PR-triggered workflow-run response; this confirms input shape, not a deployed v0.2 service.

## Roadmap dependencies / deployment gate
The source-only adapter is not an MCP server and not a deployed control plane. It must be bound by a trusted runtime to connected GitHub and pinned AppLab store; provider auth cannot be delegated to PR text or LLM memory. A later MCP surface must have explicit authentication, source isolation, rate limits and operational logging, with no write tools exposed by default.

Stacked PR must be integrated only after #27's required review and exact-head gate; do not self-approve, auto-merge or bypass protected rules. GBrain context is a different trust domain: project it through PR #26 adapter as background context, never as CI or GitHub authority.
