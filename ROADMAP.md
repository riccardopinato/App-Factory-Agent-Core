# Roadmap — AGF-2026-001
Stato iniziale 11/11/2026: plan, source locale non importato. Ogni voce `[ ]` è aperta.

## Lane infrastrutturale trasversale — Context Sync 35 repo (11/11/2026)
**Stato:** rollout tecnico `MERGED` su 35/35 repo; PR contract CI verificato. **NON equivale al completamento del runtime AppFactoryAgent Windows o dei maxi-step 1–5 sottostanti.**

- [x] Workflow GitHub Actions con schedule UTC, `workflow_dispatch`, metadata SHA dei repository upstream, snapshot documentale e PR-only; 32 rollout nuovi + 3 workflow originali Agent/Finance/Scene irrobustiti.
- [x] Pin dell'Action `actions/checkout` coerente con Golden corrente; v2 con recovery PR no-op, avvio da default branch e job name specifico.
- [ ] **P0 NEXT:** test reale `workflow_dispatch`/primo `schedule`, PR automatica e recovery del token su canary pubblico, privato, `master` e regole rigide.
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
