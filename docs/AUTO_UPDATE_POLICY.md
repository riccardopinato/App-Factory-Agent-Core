# Aggiornamento automatico — due livelli

## Livello A — live GitHub metadata (implementato nel workflow)
- Github Actions schedule giornaliera UTC 05:17 e run manuale.
- `scripts/sync_context.py --write` legge i repository dichiarati in `automation/SOURCES.json`, verificando commit/branch/data.
- Scrive **solo** `docs/AUTO_CONTEXT.json` e `docs/AUTO_CONTEXT.md` se l'upstream cambia. Lo SHA locale del repo non entra nel feed (evita loop).
- Crea/aggiorna branch `automation/context-snapshot` e apre PR per revisione.
- Non acquisisce task locali Windows, dati di portafoglio o file privati; non cambia codice, roadmap, scope, stato dei test, Golden.
- Senza credenziali aggiuntive possono essere letti solo repository pubblici. Il token Actions dispone dei permessi di scrittura del solo repository di destinazione.
- GitHub Settings > Actions > General: abilitare **Allow GitHub Actions to create and approve pull requests** se non già attivo; la protezione di main continua ad applicarsi.
- Le schedule GitHub possono essere ritardate o disattivate da GitHub per inattività; controllare Actions/PR. Non è monitoraggio realtime.

## Livello B — riconciliazione semantica (revisione)
- Leggere diff di source e test, codice con commit esatto, Product Bible e README; classificare delta: SOURCE_CONFIRMED, CI_VERIFIED, DEVICE_VERIFIED, RELEASE o NOT_VERIFIED.
- Aggiornare dossier e decisioni soltanto con evidenza. I workflow non possono inventare valutazioni qualitative.
- Ogni promozione Donor/Golden avviene nel Core seguendo Gate dedicati, NON per semplice cambiamento SHA.
- Se la sync fallisce, l'ultimo snapshot resta visibile con il proprio commit; un run fallito NON prova che non vi siano cambiamenti.
- Le eventuali automazioni ChatGPT devono lavorare SOLO in Chat, con repo esistenti e gate PR; la loro attivazione è separata da questi file.

## Controllo locale
`python3 scripts/sync_context.py --check` non richiede Internet.
`python3 -m unittest discover -s tests -p 'test_*.py' -v`.
`python3 scripts/sync_context.py --write` richiede GitHub API raggiungibile e produce solo lo snapshot.
