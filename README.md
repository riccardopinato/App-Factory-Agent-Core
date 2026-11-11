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
