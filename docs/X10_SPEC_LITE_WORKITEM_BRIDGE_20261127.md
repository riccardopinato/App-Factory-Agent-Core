# Factory Spec Lite Step 4 — WorkItem trace projection (source-only)

**Upstream Master:** App-Factory-Core `8b3d9263ad1a72f3b8a43273550fe43646780d78`, Master v27 / Index v31. **Agent Core source:** `e7903b33f9bd03a969f039d8c20292532a92951c`. **Spec Lite schema:** App-Factory-Core `schemas/factory_spec_lite_v1.schema.json` (owned by Core). **No new scheduler, DB, lease, WorkGraph, test engine or runtime executor**.

`scripts/spec_lite_work_item_adapter.py` projects a feature-scoped FSL `FR-`/`AC-` requirement set into a side-effect-free reference bound to an existing **AppLab validated** `APPLAB_WORK_ITEM`. Input contract:

1. A trusted caller supplies the actual independently resolved target source SHA and Factory SHA; no values are believed from the manifest.
2. AppLab creates/loads the existing WorkItem from its durable operation and validates it using **its** canonical `agent_work_graph_v60a.validate_work_item` and persisted-operation identity. The callback used by the adapter MUST be a trusted injection, not an LLM-supplied predicate.
3. Existing `agent_job_gateway.evaluate` checks mode, repo, path, budget, receipt/HMAC. The specification **cannot grant permissions**.
4. Only work items with matching repo/SHA, `ORCHESTRATION_ONLY` authority and the correct permissions are projected. Any write-mode projection requires independent product-decision verification AND the current Agent Core signed receipt; a manifest's `APPROVED` string is not approval.
5. The adapter returns only `TRACE_ONLY` metadata: feature, immutable job hash, work item/operation IDs and AC→test expectations. No write to the existing WorkItem, AppLab queue or filesystem.
6. Replay is deterministic by `spec_id`, idempotency key and target; an injected trusted prior binding can detect changed job/spec/work item and **fail closed**. No second persistence ledger is created.

**Tests:** `python3 -m unittest discover -s tests -p test_spec_lite_work_item_adapter.py -v` + all existing source tests via `.github/workflows/validate.yml`. Negative vectors include replay/change, out-of-scope paths, path traversal, wrong SHA, missing AC/evidence tests, unvalidated WorkItem, unauthorized capabilities, missing independent product approval, unsigned job. One signed test receipt is synthetic, verifies the existing gateway and does not authorize actual GitHub writes.

**Accept/reject:** SOURCE+CI only. Do not equate test fixtures with a real Windows worker, AppLab durable-queue E2E, physical device, real user-approved write or production certification.
