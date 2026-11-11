# Stato recuperato — agente locale Windows
Data ricostruzione: 11/11/2026. Fonte: chat dell'utente del 10/11/2026. **USER_REPORTED, NON SOURCE_VERIFIED.**

## Ambiente dichiarato
Windows 11 + WSL Ubuntu. Agente Python 3.12.3 nella cartella locale AppFactoryAgent dell'utente (per privacy non si pubblica path Windows completo). Ollama/Qwen2.5-Coder 14B locale, contesto circa 4096. Alcune operazioni erano impostate su PC Windows; un PC spento interrompe worker locali salvo infrastruttura remota.
L'agente GBrain su WSL esiste come infrastruttura separata, non confonderlo con AppFactoryAgent. Esiste un backup cifrato verificato per GBrain, non per il codice di questo runner.

## v0.1 — analisi
- Queue SQLite persistente, record lavori e report; interfaccia CLI `init`, `check`, `add`, `once`, `status`, `run`.
- Issue label `agent:ready`, retry, worker di ascolto.
- Comandi base testati e report locale generato; `repos: nessuno` durante un controllo.
- NO scrittura di codice GitHub, NO patch, PR, merge o esecuzione AI agentica in questo livello.

## v0.2 — evoluzione
- Pianificata capacità lettura file, branch, modifiche, test, correzioni, PR; la presenza di file chiamati v0.2 non dimostra sviluppo end-to-end.
- Non documentare questa fase come funzionante senza test e sorgenti.

## v0.3 — workspace isolato / demo
- Secondo resoconto del 10/11, preparazione workspace e branch isolato, diff con sostituzione circoscritta e protezione governance; NO push/merge.
- `dev-demo` riportato PASS per un esempio minimo di funzione aritmetica, cambiando un return sbagliato; non è prova di funzionamento su una app complessa.
- Validità e SHA del codice v0.3 **NON VERIFICATI** qui.

## v0.4 — monitoraggio issue locale
- L'agente cercava issue con label `agent:dev-local`, clonava workspace separato, conservava diff; non realizzava l'intero ciclo test applicativi/commit/push/merge.
- Problemi riscontrati: CRLF e output Qwen vuoto; `patch_retry.py` applicata per secondo tentativo. Il fix va testato con caso deterministico, non presunto.
- Verifica utente Android: SDK platforms/android-36 e build-tools/36.0.0 esistono, mentre `gradlew.bat` nel target $repo riportava False. Non equivale a compilatore rotto; bisogna accertare root/progetto corretto e wrapper.

## Gap bloccanti prima dell'import
- Identificare e leggere file esistenti, versioni e contratti; non copiare log locali in repo pubblico.
- Verificare licenza e dipendenze del codice che si vuole riutilizzare.
- Distingui stato PR/fix da codice importato/CI/device.
- Segreti e token GitHub restano nel Windows credential store/secret manager, mai committati.

## Come acquisire la sorgente
1. Escludere `.env`, `*.db`, `*.sqlite*`, `results/`, `workspaces/`, `models/`, token, file sensibili e dati personali.
2. Generare inventario dei file e hash SHA-256 in locale.
3. Portare solo sorgente e test su branch dedicato con revisione delle credenziali.
4. Eseguire test sintetici in un ambiente pulito; confrontare gli output dei singoli livelli.
5. Solo dopo aggiornare README, ROADMAP, PROVENANCE con exact commit e prove.
