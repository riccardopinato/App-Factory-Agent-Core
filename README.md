# App Factory Agent Core

**ID:** AGF-2026-001 · **Stato:** BOOTSTRAP DOCUMENTALE + monitoraggio metadata proposto in PR · **Data:** 11/11/2026.

Questo repository definisce il nucleo comune di agenti della App Factory: job durevoli, tool adapters, autorizzazioni, diagnostica, checkpoint, audit e riuso. **Non contiene ancora i file originali dell'agente locale Windows**, né un motore AI di produzione. Lo script `scripts/sync_context.py` è un utility funzionante da verificare in CI, NON un task runner/coding-agent.

## Inizia qui
- [Product Bible](PRODUCT_BIBLE.md) — cosa deve fare; limiti.
- [Stato vero dell'agente Windows](docs/LOCAL_AGENT_STATUS.md) — v0.1-v0.4, prove e blocchi.
- [Architecture](docs/ARCHITECTURE.md) — job queue, adapter, approval gateway e osservabilità.
- [Roadmap a cinque maxi-step](ROADMAP.md) — piano con acceptance gates.
- [Contratto job](contracts/job.schema.json) — design di interscambio, non API implementata.
- [Sicurezza](docs/SECURITY.md) · [Provenienza](docs/PROVENANCE.md) · [Evidence](evidence/README.md).
- [Aggiornamenti automatici](docs/AUTO_UPDATE_POLICY.md) · [snapshot](docs/AUTO_CONTEXT.md).

## Provenienza e autorità
Factory: [CURRENT.yaml](https://github.com/riccardopinato/App-Factory-Core/blob/main/CURRENT.yaml) seleziona Master v27 e Golden Index v29 (baseline letta 11/11/2026: `ee72dbb1b0de2cd71bc4aac42c350853c6915159`). Questa repository NON sostituisce il Master.
Ideas: [Dossier AGF/FIN/INT — PR #90](https://github.com/riccardopinato/Idee-app-Archivi-riferimenti/pull/90); stato PR da verificare separatamente. [AppLab](https://github.com/riccardopinato/AppLab) è harness QA esistente, non va copiato qui.
Consumers proposti: Developer Agent, QA Agent, Research/Donor Agent, Finance Agent (separato e senza credenziali cross-domain).

## Stato preciso
- **VERIFICATO su GitHub:** questo repository esiste e contiene file di bootstrap; source of truth del suo codice è solo il suo HEAD.
- **RIPORTATO dall'utente, non importato:** agente Windows locale con queue SQLite, Qwen2.5-Coder 14B e comandi CLI; dettaglio in LOCAL_AGENT_STATUS.
- **PROPOSTO:** worker multi-repo affidabile, tool adapters, test reali, PR, build, recovery e uso in Finance.
- **ESCLUSO:** esecuzione di trading live, merge non autorizzato, rilancio autonomo di ChatGPT senza runner, accesso incontrollato ai file/secret.

## Affidabilità e riuso (11/11/2026)
- [Helper offline di reconciliation](scripts/context_reliability.py), con test negativi in [tests/test_context_reliability.py](tests/test_context_reliability.py), CI verde [PR #12](https://github.com/riccardopinato/App-Factory-Agent-Core/pull/12).
- [Recovery/rollback playbook](docs/CONTEXT_SYNC_RECOVERY_PLAYBOOK.md), [protocollo review semantica](docs/SEMANTIC_REVIEW_PROTOCOL.md) e [candidate admission](docs/CONTEXT_SYNC_REUSE_ADMISSION.md). Nessun Golden promosso.
- [Dashboard fonte flotta](https://github.com/riccardopinato/Idee-app-Archivi-riferimenti/blob/main/16-APP-FACTORY-SITE/data/context_fleet.json): 35 slot, stati separati; deploy del Site non verificato.
- Limiti: 4 permessi PR admin ancora bloccanti; nessuna esecuzione `schedule`/`workflow_dispatch` del contesto osservata; nessun codice Windows locale importato.

## Job permission gateway — X10-010
- [Decision helper fail-closed](scripts/agent_job_gateway.py) e [fixture di sicurezza](tests/test_agent_job_gateway.py) per validare job, repo/source SHA, allowed paths, budget e approvazione scoped. [Contratto e limiti](docs/X10-010_PERMISSION_GATEWAY.md).
- Funzionalità **solo offline/policy**: nessuna chiamata ad AppLab, nessun permesso reale al runner, nessun source Windows importato e nessuna PR creata autonomamente.

## Automazione
Un cron GitHub Actions controlla gli SHA di Core/Ideas/AppLab, aggiorna SOLO il file snapshot in una PR. Non può accedere al PC Windows spento né completare il coding agent. Per i requisiti di autorizzazione e limitazioni: [AUTO_UPDATE_POLICY](docs/AUTO_UPDATE_POLICY.md).

## Matrice sorgente/evidenza
| Cosa | Livello | Fonte |
|---|---|---|
| AppFactoryAgent locale v0.1–0.4 | USER_REPORTED | Conversazione 10/11/2026 |
| GitHub Actions updater di metadata | SOURCE_ADDED, CI_PENDING | `scripts/sync_context.py` |
| Agent orchestrator reale | NOT_IMPORTED | Local workstation only |
| Coding automatico e PR agentiche | ROADMAP | Non dimostrati |
| Persistenza tramite GBrain | Sistema esterno esistente | Nessuna integrazione AGF comprovata |

**Nessun PASS automatico**: PR/CI, prodotto testato, hardware e release hanno evidenze differenti.

## X10-011 — AppLab durable queue bridge (source-only)
- [Adapter `applab_queue_bridge.py`](scripts/applab_queue_bridge.py): autorizza job via X10-010, risolve un'operazione **già persistita** da AppLab, conferma repository/SHA e delega enqueue idempotente, checkpoint riproducibile e recupero lease alla coda AppLab v5.4E; nessun secondo SQLite, scheduler o worker.
- [8 fixture offline](tests/test_applab_queue_bridge.py): replay, source mismatch, write senza receipt, ancestry non provata, ledger drift, expired lease recovery, timestamp errato, scope negato. Comando: `python3 -m unittest discover -s tests -p 'test_applab_queue_bridge.py' -v`.
- **Limite:** test con backend finto, nessuna esecuzione AppLab reale, claim/complete/PR o Windows import. L'operation-id è creato dall'admission canonica, non dalla descrizione non fidata del job; l'adapter non certifica binding dell'idempotency key al delivery. X10-012 e X10-013 restano gate distinti.

## X10-012 — workspace guard (source/CI)
- [Guardia source SHA/scoped worktree](scripts/applab_workspace_gate.py) e [test di regressione](tests/test_applab_workspace_gate.py) davanti al `bounded_fix_worker_v60c` già esistente in AppLab; HMAC, HEAD immutabile, no patch dentro il checkout, max file/linee e verifica che nessuna operazione remote/merge/release sia eseguita.
- [Confini e rollback](docs/X10-012_ISOLATED_WORKSPACE_GATE.md): il rollback del worktree temporaneo è delegato ad AppLab, non è implementato un secondo patcher. Runtime Windows/consumer, shell isolation e PR restano da integrare in X10-013/014/015.

## X10-041 — diff-aware monitoring candidate intake (source+CI)
- [Diff adapter](scripts/diff_capability_monitor.py), [negative tests](tests/test_diff_capability_monitor.py) and [trust boundary](docs/X10-041_DIFF_AWARE_MONITOR.md). Requires authenticated exact GitHub source SHA and AppLab-pinned diff evidence; emits deterministic path-only hints without code, storage, CAP promotion, PR or release. No live webhook/GitHub polling configured.

## X10-013 — AppLab bounded orchestration adapter (source-only)
- [Orchestrator source](scripts/bounded_applab_orchestrator.py), [tests](tests/test_bounded_applab_orchestrator.py), [review boundary](docs/X10-013_BOUNDED_ORCHESTRATION.md). Pins jobs to an already persisted AppLab operation, validates a live queue lease before dispatch intent and at callback boundary after workspace preflight, and delegates recovery to AppLab's own durable queue. No second scheduler, self-issued permissions, automatic PR or release.
- **SOURCE+CI only after exact-head verification.** Synthetic leases, no connected Windows worker, no real AppLab deployment/process-crash verification, no consumer/test artifact certification. Integrates alongside X10-041 without replacing its diff monitor.
