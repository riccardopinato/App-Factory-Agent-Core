# Context Sync — candidate riuso e gate Golden (11/11/2026)

**Classification:** `PROCESS_CANDIDATE / NOT_CERTIFIED`. Non registrato nel Golden Registry; nessuna nuova CAP creata.
**Factory baseline:** `c5adc147046beb7024629466d10eeb799c3c2619` · Master v27 · Golden Index v29.

## Componenti effettivamente esistenti
- `scripts/sync_context.py`: snapshot GitHub per l'Agent Core; legge sorgenti pubbliche versionate; stdout e file JSON/Markdown. CI e run post-fix osservati, ma PR creation impedita dall'admin setting di questo repo.
- `scripts/context_reliability.py`: helper stdlib, puro (nessuna API/secret, nessuna chiamata GitHub), test offline per retry bounded, access denial, branch conflict, SHA, snapshot idempotente, redazione private, candidate semantic-review e receipt guard. [PR #12](https://github.com/riccardopinato/App-Factory-Agent-Core/pull/12), merge `32d4d41a3774d465c28056de7dfb83469c631d06`.
- Workflow metadata-only `app-factory-context.yml` installato su 32 repo + workflow originario `context-snapshot.yml` in 3. Non sono consumers integrati dell'helper puro (ancora nessun import in quei workflow).
- [btrader PR bot #5](https://github.com/riccardopinato/btrader/pull/5) ed [E2E Actions run](https://github.com/riccardopinato/btrader/actions/runs/43040885976): un consumer *del pattern di snapshot* ha ottenuto PR bot realmente creata e riconciliata senza duplicati. L'evento di prova è `push`, non `schedule`.

## Evidenza e limiti

| Gate | Osservazione | Stato |
|---|---|---|
| Repository installati | 35/35 workflow in default branch | STATIC_CONFIG_VERIFIED |
| File aggiornati | Sono due file JSON/MD di metadata | SOURCE + CANARY VERIFIED |
| Snapshot reali | 5 veri `push` canary, alcuni privati | PUSH_RUNTIME_VERIFIED_SCOPED |
| PR bot | btrader #5, creata da github-actions[bot] | PR_FLOW_VERIFIED_ONE_REPO |
| Retry e dedup | btrader rerun e aggiornamento SHA, una sola PR | VERIFIED_ONE_REPO |
| Identity merge | Agent Core run #43052705998 PASS fino alla PR | VERIFIED_SCOPED |
| Cron reale | Nessun evento `schedule` contesto osservato | NOT_VERIFIED |
| Manual run | Nessun `workflow_dispatch` contesto osservato | NOT_VERIFIED |
| Admin PR permission | 4 canary bloccati, inclusi Agent e World-Days | BLOCKED |
| Consumer 2 indipendente completo | Nessuno col flusso cron→PR→recovery verificato | NOT_VERIFIED |
| Reuse helper puro in altre app | Nessun import, soltanto candidate | NOT_INTEGRATED |
| Golden promotion | Nessuna proposta al Core per promozione | NOT_ELIGIBLE |

## Decisioni successive
- Prima completare M1: abilitazione per-repo della permission GitHub PR, run `schedule`/dispatch vero, PR bot su due repo indipendenti senza bypass.
- Per un **CERTIFIED DONOR** scoped: provenance codice e tests del componente e primo consumer dimostrati; non certificare il solo scaffolding come runtime agent.
- Per **CERTIFIED PROCESS / Golden**: almeno due progetti indipendenti con recovery e PR verified, source SHA esatti, limiti temporali, test negativi e compatibilità; review tramite App-Factory-Core, PR separata e Golden admission gate. Non utilizzare `COPY-READY` come sinonimo di `CERTIFIED`.
- Nessun riuso automatico in Finance, Notes, Anna o app Android. Ogni Product Bible/roadmap e license gate rimane autoritativo.
- Recupero/rollback: [playbook](CONTEXT_SYNC_RECOVERY_PLAYBOOK.md); proposals: [protocollo semantico](SEMANTIC_REVIEW_PROTOCOL.md).
