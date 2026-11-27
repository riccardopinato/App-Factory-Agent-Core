# Agent Core — existing AppLab orchestration contract (Spec Lite STANDARD pilot)

**ID:** `FSL-20261127-AGENT-ORCH` · **Source:** `f2b4c28cc3a9afa4ef39c6d32fe0a8ef14dac512` · **Factory:** `f8b9f550c544735237f19cdd723bd2df667ceee6`

**FR-001:** The existing source-only AppLab orchestration contract must map read-only jobs and deny untrusted source, scope, and write authority while retaining AppLab as the sole durable scheduler.

- **AC-001:** A read-only AppLab WorkItem preserves resolved SHA, includes no code-edit permission and cannot declare runtime verification, dispatch or merge.
- **AC-002:** An untrusted job that expands allowed paths beyond trusted policy is denied before scheduling or worker execution.
- **AC-003:** A lease claim with a mismatched immutable source SHA is rejected before a WorkItem is issued.
- **AC-004:** A write attempt without an independently signed approval receipt is denied before any queue or workspace effects.

This pilot adds only independent offline unit regression vectors. It does NOT integrate a CLI Spec Kit worker, change security policy, schedule a durable job, issue a real approval receipt, or verify Windows runtime. The manifest is PROPOSED / NOT_VERIFIED until genuine CI receipts. The user authorized a contract pilot, not unattended job execution.
