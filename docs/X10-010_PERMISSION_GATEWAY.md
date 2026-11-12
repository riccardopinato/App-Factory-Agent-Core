# X10-010 — Job contract e permission gateway (scoped, offline)

**Data:** 12/11/2026. **Factory:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`, Master v27 / Golden Index v29.  
**Dependency:** [X10-009 AppLab adapter selection, PR #216](https://github.com/riccardopinato/AppLab/pull/216), merged `9bbb424929fe8916e84e2b0a9da384961c26f1e1`.

## Implementato realmente in questo repository
- [`scripts/agent_job_gateway.py`](../scripts/agent_job_gateway.py): funzione pura `evaluate(job, policy, *, receipt=None, verifier_key=None, now=None)` che restituisce decisione e codice di blocco. **Zero** network, shell, GitHub writes, filesystem edits, run agentico, billing o PR create.
- Riusa il contratto preesistente [`contracts/job.schema.json`](../contracts/job.schema.json) e le sue modalità: `analyze`, `run_tests`, `propose_diff`, `prepare_pr`. Allowlists di repository/modalità/path provengono **solo** da policy *trusted* della control plane: un input di issue o README non è fonte di permesso.
- Fail-closed per repo/source SHA non conformi, budget oltre 900 s o 2 tentativi, path traversal/hidden/protected, no scope, policy malformata o modalità non dichiarata.
- `analyze` e `run_tests` ammettono **solo pianificazione per un ambiente isolato**; nessun test realmente lanciato.
- Scritture `propose_diff` e `prepare_pr` bloccate in assenza di una ricevuta d'approvazione firmata **HMAC-SHA256** dalla control plane che lega `job_digest`, source SHA, repo, modalità, path, reviewer e expiry. Il segreto di verifica viene iniettato **fuori dal repository**, mai incluso in job/PR/log. Max TTL 1 ora. La ricevuta non sostituisce branch protection, check o review PR indipendenti.
- Anche una decisione `ADMITTED_FOR_SCOPED_PROPOSAL` **non modifica file** e lascia al runner reale l'obbligo di verificare mittente autenticato, source SHA checkout, symlink/realpath, lease AppLab e gate CI/review.

## Contratto di sicurezza: ciò che NON è stato implementato
- Non è il coding-agent Windows e non può avviare AppLab, generare patch, creare branch/PR o continuare quando il PC è spento.
- La firma HMAC prova soltanto che qualcuno ha la chiave affidabile; la **convalida dell'identità e dell'autorizzazione del reviewer** deve appartenere a una control plane esterna da sviluppare/testare. Non accettare receipt auto-firmate dal modello/agente.
- Gli input devono essere normalizzati dal vero runner; questa funzione non può verificare symlink su checkout perché non accede al filesystem.
- `run_tests` richiede isolamento, permessi runner e una policy dei comandi prima del primo uso reale.
- I limiti di AppLab `controlled_event_v54g.max_active_global=1` nel pilota non sono cambiati; il parallelismo **senza tetto artificiale** della *coda di programma* non altera tali limiti runtime di sicurezza.
- Nessuna promozione v6.2 oltre SELF_CANARY, nessuna certificazione di Device/Store/Golden.

## Verifiche e acceptance
`python3 -m unittest discover -s tests -p 'test_agent_job_gateway.py' -v` esercita modalità lette da schema, allowlist, scope/path, hash e expiry, firma manomessa, limite tentativi, budget/timeout e nessun effetto collaterale.
`python3 -m unittest discover -s tests -p 'test_*.py' -v` copre anche i test esistenti. L'esito di CI su PR head è la **prova di X10-010 nello scope POLICY_GATEWAY_OFFLINE**, non il completamento di X10-011/012/013 né un job runtime.

## Successori
- `X10-011`: adapter a queue/lease persistente **riusando AppLab**, non creando un secondo schema source of truth.
- `X10-012`: filesystem/worktree isolato con verifica realpath e source SHA in spazio effimero, bounded patch AppLab.
- `X10-013`: integrazione reale solo dopo entrambi, con fixture recovery e due repo pilota.
