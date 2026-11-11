# Roadmap — AGF-2026-001
Stato iniziale 11/11/2026: plan, source locale non importato. Ogni voce `[ ]` è aperta.

## Lane infrastrutturale trasversale — Context Sync 35 repo (11/11/2026)
**Stato:** rollout tecnico `MERGED` su 35/35 repo; PR contract CI verificato. **NON equivale al completamento del runtime AppFactoryAgent Windows o dei maxi-step 1–5 sottostanti.**

- [x] Workflow GitHub Actions con schedule UTC, `workflow_dispatch`, metadata SHA dei repository upstream, snapshot documentale e PR-only; 32 rollout nuovi + 3 workflow originali Agent/Finance/Scene irrobustiti.
- [x] Pin dell'Action `actions/checkout` coerente con Golden corrente; v2 con recovery PR no-op, avvio da default branch e job name specifico.
- [x] **M1 LIVE 2026-11-11:** cinque esecuzioni `event=push` vere su pubblico, privato, `master`, questo workflow originale e repo ruleset; snapshot e bot-owned branches corretti. Nel presente repository [run #43040897071](https://github.com/riccardopinato/App-Factory-Agent-Core/actions/runs/43040897071): `CONTEXT_SNAPSHOT_WRITE_PASS` e `CHECK_PASS`, poi blocco su create PR.
- [x] **M1 E2E parziale:** [btrader Actions run](https://github.com/riccardopinato/btrader/actions/runs/43040885976) ha creato [PR #5](https://github.com/riccardopinato/btrader/pull/5) come `github-actions[bot]`, con rerun idempotente (nessun duplicato). Tutti i push temporanei di collaudo rimossi tramite CI+PR.
- [ ] **P0 BLOCKED:** impostazione repo-specifica `Allow GitHub Actions to create and approve pull requests` mancante in quattro canary, incluso questo repo. Dopo abilitazione admin verificare rerun, creation PR bot e recovery della branch già pubblicata.
- [x] **P0 IDENTITY BUG FIXED / RUNTIME VERIFIED:** originariamente il rerun [#43040897071](https://github.com/riccardopinato/App-Factory-Agent-Core/actions/runs/43040897071) ha fallito con `Committer identity unknown` durante il merge. Configurazione bot spostata prima di `git merge --no-edit` tramite [PR #8](https://github.com/riccardopinato/App-Factory-Agent-Core/pull/8), identico fix CI-validato su Finance e Interactive Scene. [Run reale post-fix #43052705998](https://github.com/riccardopinato/App-Factory-Agent-Core/actions/runs/43052705998): merge riuscito, `CONTEXT_SNAPSHOT_WRITE_PASS`, `CHECK_PASS`, push branch PASS; poi PR create BLOCKED da GitHub Actions repo setting. Trigger QA rimosso nella [PR #10](https://github.com/riccardopinato/App-Factory-Agent-Core/pull/10).
- [x] **Fleet static audited 35/35:** `schedule`, `workflow_dispatch`, write scopes verificati sul default branch; nessun evento schedule/dispatch del workflow contesto osservato nei log. [Rapporto completo](https://github.com/riccardopinato/Idee-app-Archivi-riferimenti/blob/main/18-AGENT-FACTORY/EVIDENCE_M1_35_REPO_SWEEP_AND_RETRY_2026-11-11.md).
- [ ] **P0 NOT_VERIFIED:** veri `workflow_dispatch` e `schedule` ancora non osservati; audit statico sui rimanenti 30 repo NON è test runtime, che resta da eseguire.

- [ ] **P0:** fault injection e test retry/rate-limit/branch divergence/permessi per 35 repo.
- [ ] **P1:** inventario centrale `last_run / last_success / PR / blocked_reason` con source provenance, senza doppie fonti di verità.
- [ ] **P1:** riconciliazione documentale semantica supervisionata con diff/test, separata dall'osservazione SHA.
- [ ] **P2:** attestazione riuso e candidato Donor/Golden solo dopo prove runtime su almeno due consumer indipendenti.

**Roadmap canonica del rollout:** [Hub Idee / Agent Factory — 35 repository](https://github.com/riccardopinato/Idee-app-Archivi-riferimenti/blob/main/18-AGENT-FACTORY/ROADMAP_CONTEXT_AUTOMATION_35_REPOS_2026-11-11.md). Riferimento Factory: `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619` (Master v27, Golden Index v29). Il codice locale Windows v0.1–v0.4 resta `USER_REPORTED` / non importato.

## Maxi-step 1 — Inventory & import controllato (P0)
- [ ] Acquisire cartella AppFactoryAgent Windows in repo/branch privato o archivio protetto, con hash e lista file; escludere .env, SQLite privata, risultati sensibili e credenziali.
- [ ] Identificare versione dei file v0.1/v0.2/v0.3/v0.4 e patch_retry.py; scegliere sorgente canonica invece di concatenare script obsoleti.
- [ ] Eseguire `init/check/add/once/status/run` con fixture sintetiche, registrarne logs sanitizzati, python version e hash.
- [ ] Analizzare v0.4 su issue `agent:dev-local`, differenze CRLF, output LLM vuoto e il ciclo retry; distinguere problemi risolti da restanti.
- [ ] Verificare toolchain Flutter/Gradle/Android SDK con repo che possiede wrapper reale.

**Gate:** commit import e licenza verificati, lint/test offline; nessun token.

## Maxi-step 2 — Contract/safety foundation (P0)
- [ ] Definire runtime mode analysis-only / proposed-write / PR-ready, lifecycle job.
- [ ] SQLite schema versionato, idempotency e checkpoints.
- [ ] Permission gateway per repo/path/tool e secret references.
- [ ] Contratto request/result versionato e fixture negative.

**Gate:** 100% casi permessi negati previsti, no unsanctioned writes.

## Maxi-step 3 — Isolated execution / PR agent (P1)
- [ ] Checkout worktree isolato; parser patch deterministico e restricted edits.
- [ ] Verify diff, run focused tests, fail-closed su nonzero exit, no destructive scripts.
- [ ] Branch/PR con source SHA, no merge default, crash/recovery.
- [ ] Quota CPU/GPU, tempo, token modello, retry cap.

**Gate:** due repo pilota, PR senza bypass e report source-linked.

## Maxi-step 4 — Agent adapters / AppLab (P1)
- [ ] Driver QA, build/report, research/donor, repo watchers.
- [ ] Evidence receipt: test results, CI run, artifact hash, physical NOT_VERIFIED.
- [ ] Separare l'infrastruttura di esecuzione da ChatGPT UX; schedulazione locale/CI.

**Gate:** replay + failure matrix event loss, duplicate, outage, resume, changed SHA.

## Maxi-step 5 — Cross-consumer & Donor (P2)
- [ ] Consumer independente Finance (read-only) o app pilota.
- [ ] Benchmark ripetibilità, consumo e sicurezza; governance Golden.
- [ ] Nuove capability proposte nel catalogo solo dopo dedup/tesi di riuso.
- [ ] Changelog + Provenance ledger + recovery playbook.

**Gate:** un donor scoped con evidence, non Golden automatico.

Nota: aggiunta script di snapshot metadata non completa nessuno dei cinque step di prodotto.
