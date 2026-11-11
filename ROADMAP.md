# Roadmap — AGF-2026-001
Stato iniziale 11/11/2026: plan, source locale non importato. Ogni voce `[ ]` è aperta.

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
