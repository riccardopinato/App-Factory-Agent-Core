# X10-007 — Ricognizione sorgenti AppFactoryAgent Windows e preparazione import

**Data:** 12/11/2026 · **Factory baseline:** `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619`.  
**Repo Agent Core source controllato:** [main@78dc19318b5905fd83b52b8840e082c5fec51b45](https://github.com/riccardopinato/App-Factory-Agent-Core/commit/78dc19318b5905fd83b52b8840e082c5fec51b45).

## Risultato effettivo della ricognizione
- I file root del repository GitHub sono AGENTS, Product Bible, roadmap, docs, contracts, scripts, tests. Nell'inventario GitHub `scripts/` sono presenti solo `sync_context.py` e `context_reliability.py`. I file dell'**agente originale Windows** non risultano acquisiti nel repository.
- [LOCAL_AGENT_STATUS.md](LOCAL_AGENT_STATUS.md) è un resoconto `USER_REPORTED`: v0.1 queue SQLite e CLI `init/check/add/once/status/run`; v0.3 workspace isolato sperimentale; v0.4 issue `agent:dev-local`, problemi CRLF/Qwen output e `patch_retry.py`. **Nessuna prova a questa data di funzionamento end-to-end su PC o di codice importato.**
- Product Bible autorizza solo un agente controllato con job bounded e PR per review; lo scheduler AppLab v5/v6 esistente è il primo candidato di riuso. GBrain è un'altra infrastruttura, non parte automaticamente dell'agent.
- L'accesso GitHub non dà accesso ai file o ai processi del PC Windows; inventare un import da un README sarebbe una falsa evidence.

## Preflight offline ora implementato (source, non import)
- `python3 scripts/windows_source_preflight.py --root "C:\path\to\AppFactoryAgent"` **solo sul PC dell'owner**, con un path scelto manualmente. Stampa un manifesto JSON di file e SHA256.
- Nessuna rete, nessun upload, nessun file modificato, nessun contenuto sorgente nei log. Directory `models/results/workspaces/logs/backups/venv`, file nascosti, SQLite, .env e nomi sensibili sono esclusi. File >5MiB o non testuali sono esclusi.
- I nomi restanti e gli hash **possono essere sensibili**: esaminare il manifesto localmente; **non pubblicarlo automaticamente in issue/PR**. Uno script basato su nomi non equivale a secret scanning.
- `python3 -m unittest discover -s tests -p 'test_windows_source_preflight.py' -v` esercita fixture sintetiche, symlink, excluse sensibili e limiti; non legge il PC.
- Non si richiede né si archivia `ghp_*`, token, credenziali Ollama, `.env`, `*.sqlite`, `*.db`, keystore o logs personali.

## Gate del successivo X10-008 (HUMAN_GATE)
1. Il proprietario fornisce **solo** sorgenti e test non sensibili, preferibilmente tramite repository/branch privato, con controllo credenziali e licenze. Nessun codice importato in questa PR.
2. Confrontare versioni v0.1–v0.4 e `patch_retry.py`; identificare entrypoint di queue, worker, worktree, model adapter e test, non concatenare patch incompatibili.
3. Eseguire `init/check/add/once/status/run` con fixture sintetiche su Windows e/o WSL; registrare Python, git SHA, output sanitizzato, hash degli artifact. Testare errore LLM vuoto, CRLF, retry, source SHA changed, deny permissions.
4. Verificare toolchain Flutter/Gradle su un repo con wrapper reale, non assumere `gradlew.bat` nella root arbitraria.
5. Solo allora predisporre PR di import su scope approvato, test CI e aggiornamento Product Bible/roadmap.

**Gate X10-007:** inventory statico concluso e script/test offline introdotti; **X10-008 resta in attesa del codice locale e consenso specifico**. Non è un agent autonomo funzionante.
