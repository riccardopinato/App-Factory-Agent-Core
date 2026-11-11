# Decision log
## ADR-001 — One core, many agents — 11/11/2026
Decision: condividere orchestrator, checkpoint e tool gates. Separare domain adapters (Developer, QA, Research, Finance); non ricreare queue e sicurezza per app.
## ADR-002 — Preserve original Windows source
Decision: non riscrivere l'agente a memoria. Acquisire file v0.1–v0.4, patch_retry.py e test prima di decidere stack.
## ADR-003 — No autonomous GitHub merge by default
Decision: PR e check exact-head prima di merge; source SHA pin e approval per write.
## ADR-004 — Context snapshot != knowledge rewrite
Decision: cron riconcilia commit pubblici soltanto, non aggiorna decisioni qualitative senza audit.
## ADR-005 — Local first, cost conscious
Decision: Qwen/Ollama è opzionale; nessuna dipendenza cloud AI a pagamento per bootstrap.
