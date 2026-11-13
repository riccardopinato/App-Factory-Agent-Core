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

## Addendum — Autopilot v0.5.1 / v0.6.0, 13/11/2026

**SOURCE_INSPECTED_IN_CONVERSATION / NOT_CANONICALLY_IMPORTED:** il pacchetto originale v0.6.0 e i suoi test sono disponibili come allegati di conversazione. Il ZIP ha SHA-256 `c5af037f9a00f340f26a6d020a0b9cb842928b298e5b48d377bb46407f8f7da2`; 28 test Python locali sul pacchetto hanno superato la suite, ma non sono test Windows indipendenti né attestazioni AppLab. Vedi [dossier X10-008/015](X10-008_015_WINDOWS_AUTOPILOT_RECONCILIATION_2026-11-13.md) per manifest per-file, provenance, compatibilità e restrizioni.

**USER_REPORTED_WINDOWS:** output PowerShell v0.6.0 `1 attivita`, issue #6 `ci_pass`, PR #7, `repair=0`. Su GitHub PR #7 esiste e ha CI PASS all'exact-head `92530c4a8d41c2834655275d667fab7824e60598`; una correzione di indentazione finale è stata applicata separatamente tramite ChatGPT, non dal worker locale.

**NO PROMOTION:** X10-008 resta bloccato dall'import privato e secret/provenance review; X10-015 resta pianificato per controllo runtime con due repo, process crash/restart/replay, approvazione X10-010 e AppLab queue/pr steward. La nuova utility [x10_windows_autopilot_receipt.py](../scripts/x10_windows_autopilot_receipt.py) produce solo evidence minimale in sola lettura e NON connette o sostituisce la coda.
