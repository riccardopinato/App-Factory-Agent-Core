# Semantic diff review — protocollo supervisionato v1

**Scope:** dal cambiamento SHA all'ipotesi di aggiornamento documentale. Non auto-inserisce capability, non interpreta CI come dispositivo, non modifica Product Bible/Golden.

## Input minimo
- `repository`, `default_branch`, `before_sha`, `after_sha` (entrambi 40 hex).
- Link a commit/diff o PR GitHub, elenco file cambiati (non solo numero SHA).
- Stato test exact-head (run URL, conclusion, e cosa copre); distinzione fra osservazione sorgente e risultato di un test.
- Provenienza per-evidenza: fonte, data UTC e ambito di autorizzazione.
- Per nuove capability: Product Bible/roadmap del consumer, dedup nel catalogo canonico e licenza del donor. Non dedurre approvazione dall'esistenza del codice.

## Processo decisionale
1. `READ_ONLY`: confrontare i commit GitHub e i path; non aprire PR se nessun diff rilevante.
2. `PROPOSE`: classificare in **governance**, **metadata**, **codice di prodotto**, **test**, **design**, **licenze**; per input non interpretabile → `UNKNOWN`.
3. `SOURCE_CHANGE_REVIEW`: produrre una proposta con `source_sha`, `changed_paths`, `evidence_urls`, `consumer_candidates`, `unknowns`, `requires_human_review=true`, `auto_promote=false` e `auto_merge=false`.
4. `EVIDENCE_CHECK`: se CI, dispositivo o Store non sono stati testati separatamente, registrare `NOT_VERIFIED` per quel livello.
5. `REVIEW`: confrontare i vincoli Product Bible, roadmap e Golden pertinenti; approvazione su caso specifico.
6. `PR`: soltanto i documenti strettamente autorizzati, branch dedicato, CI exact-head, review/merge; non toccare direttamente il Core né il catalogo CAP senza il contratto specifico.
7. `RECONCILE`: eventuale delta sul registro di stato e changelog con URL di PR merged, mai sulla sola base di un webhook.

## Sicurezza
- Limite di notifiche: un candidato per `repo+after_sha+scope`; la deduplicazione è richiesta prima di creare PR.
- Nessuna API LLM a pagamento, niente segreti, nomi di repo privati o codice esterno non licenziato.
- Il modulo `scripts/context_reliability.py::semantic_review` è un helper offline con file path sanitizzati; il risultato è **sempre** una proposta, non una classificazione semantica provata.
- L'agente Windows locale non è stato importato, quindi nessuna orchestrazione continua e nessun reasoning agent live qui.

## Esempio source-backed — NON nuova CAP
- Origine: [App-Factory-Agent-Core PR #12](https://github.com/riccardopinato/App-Factory-Agent-Core/pull/12), merged `32d4d41a3774d465c28056de7dfb83469c631d06`.
- Diff dichiarato: `scripts/context_reliability.py`, `tests/test_context_reliability.py`; CI head pass sulle suite `test_*.py`.
- Interpretazione: helper di recovery e review *infra*, non funzionalità Flutter/Android per utente finale. Possibili consumer futuri: flussi Agent/Finance/Interactive, previo test e deliberazione.
- Stato: `SOURCE_CONFIRMED + CI_VERIFIED (scope helper offline)` in repo origine; `CONSUMER_NOT_INTEGRATED`, `GOLDEN_NOT_PROMOTED` altrove.

## Output e gate
Registrare proposte nell'archivio Idee in una sezione dedicata con provenance e owner, senza aggiornamenti automatici a codice o decisioni. Due runtime indipendenti per `CERTIFIED PROCESS`, per la Golden pertinente.
