# Context Sync — recovery, rollback e sicurezza (v1)

Baseline Factory: `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`, Master v27 / Golden Index v29.
Ambito: aggiornamenti **solo metadata documentali**. Non è un runner Windows, non modifica codice applicativo né dati utente, non certifica release.

## Stati e priorità
- `CONTRACT_CI_VERIFIED`: workflow/versione controllati; non implica run.
- `BLOCKED_PR_PERMISSION`: branch dati pubblicato, `gh pr create` rifiutato; niente PR fittizia.
- `PR_FLOW_VERIFIED`: PR effettivamente aperta da `github-actions[bot]`, non equivale a cron.
- `SCHEDULE_VERIFIED`: soltanto run osservato con `event=schedule` e conclusione verificata.
- `BLOCKED_BRANCH_CONFLICT`: base avanzata e merge del branch bot non pulito; non forzare.
- `SEMANTIC_REVIEW_PENDING`: diff da interpretare, nessun PASS/Donor/Golden automatico.

## Diagnostica operativa
1. Identificare repository, default branch reale (`main` o `master`), workflow (32 v2 o 3 originali), run URL, evento e commit esatto.
2. Leggere `jobs` e log; distinguere API read, generazione file, push branch, `gh pr create`, CI PR e review.
3. Se `GraphQL: GitHub Actions is not permitted to create or approve pull requests`, il workflow ha raggiunto lo step PR e **fallisce intenzionalmente**. L'owner abilita `Settings > Actions > General > Workflow permissions > Allow GitHub Actions to create and approve pull requests` (per quel repo), senza modificare altri permessi. Poi avvia `workflow_dispatch` o rerun dei job falliti; confermare un'unica PR bot. Non creare PAT sovraprivilegiati come workaround.
4. Se `Committer identity unknown` sul `git merge --no-edit`, verificare il posizionamento di `git config user.name/email` **prima** del merge. Fix originale Agent/Finance/Scene: PR #8/#4/#4. Run Agent Core #43052705998 dimostra merge PASS post-fix.
5. Se API 401/403/404 o permesso scaduto: STOP, nessun retry infinito. Se 429/5xx: retry limitato con `Retry-After` bounded e registrazione del tentativo; non dichiarare recovery riuscito senza nuovo log.
6. Se branch bot divergente/conflict: nessun force push, eliminazione branch o riscrittura manuale di prove. Preparare PR separata con source SHA e diff del conflitto, review umana.
7. Se snapshot inalterato: verificare confronto con default branch e PR preesistente; un branch bot già pubblicato senza PR deve essere recuperato, non abbandonato o duplicato.
8. Se `schedule` non parte: verificare eventi Actions, default branch e policy GitHub; un run `push`/PR non è prova di cron. GitHub può ritardare/saltare i job. Nuovo run cron reale è il gate.

## Contenimento e rollback
- **Per-repo stop:** da GitHub Actions disabilitare lo specifico workflow dopo aver registrato run URL e HEAD; non toccare gli altri workflow di build, prodotto o release.
- **Global stop:** non esiste un interruttore globale installato; per sospensione flotta preparare PR indipendenti/review per rimuovere solo il trigger `schedule` da ciascuno. Non dichiarare kill-switch operativo.
- **Rollback template:** revert mediante PR del commit di sola metadata `.github/workflows/app-factory-context.yml` o `context-snapshot.yml`; eseguire test di contratto e exact-head CI prima del merge. Mai forzare branch o cancellare prove pregresse.
- **Recovery bot branch:** conservare `automation/app-factory-context` o `automation/context-snapshot`; l'ultimo commit e la PR restano evidenze verificabili. Solo dopo confronto con base decidere merge/cleanup attraverso gate regolari.
- **Collisioni:** `concurrency cancel-in-progress: false`, branche bot dedicate, no merge autonomi, nessuna scrittura sul default branch.
- **Segreti:** utilizzare solo `github.token` con scope minimo; non inserire token, portafogli personali, identità repo privati o payload sensibili nei log pubblici.
- **Quote:** per 35 repo la frequenza giornaliera configurata è al massimo una richiesta cron per repo (salvo retry/manuali). Minuti Actions, API quota e costi reali non sono ancora misurati; non pubblicare costi fittizi.

## Reconciliation offline (codice già integrato)
`scripts/context_reliability.py` offre funzioni pure e testabili `retry_policy`, `reconcile`, `semantic_review`, `safe_public_status` e `validate_receipt`. Si tratta di un **decision helper**, non di un agente in esecuzione. Non sostituisce i controlli già presenti nei workflow esistenti.

## Gate di chiusura
- PASS offline: test negativi/percorso previsto nella CI Agent Core.
- OPEN: API failure e branch conflict testati su runner con fixture/real run; recupero dopo cambio impostazioni admin; vero schedule e workflow_dispatch.
- OPEN: certificazione Donor/Golden, che richiede evidence indipendente e decisione separata.
