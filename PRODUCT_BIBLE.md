# Product Bible — App Factory Agent Core
Versione design 0.1 — 11/11/2026

## Problema e target
Ridurre lavoro ripetitivo di sviluppo e QA di molte app senza duplicare per ogni prodotto un agente completo. Utente principale: sviluppatore singolo che lavora in Chat, GitHub e su PC Windows, con approccio reuse-first e costi bassi.

## Prodotto autorizzato
Nucleo generico per analizzare task, mantenerne lo stato, usare tool autorizzati, restituire diff/test/PR con prove; plugin specializzati per developer, QA, research e finance. Lo stesso core deve essere estendibile senza portare un broker nel trust boundary di GitHub.

## Principi invarianti
- Solo Chat per decisioni interattive; un worker esterno persistente è un processo separato, non una chat che si riapre da sola.
- Dry-run/analysis è default per qualsiasi tool sconosciuto; azioni non reversibili bloccate finché esplicitamente autorizzate.
- Job idempotente, riprendibile dopo interruzione, con log applicativo sanitizzato e identità commit/percorso esatto.
- State machine trasparente, nessun ghost task, no falsi PASS.
- Input e output come dati non fidati (anche prompt contenuti in issue o README).
- Può preparare PR ma non aggirare review, branch protection, check e firma.

## Non-obiettivi v1
Non costruire un nuovo LLM, non ricreare Codex/AppLab/GBrain, non gestire account broker, non sostituire GitHub Actions, non eseguire auto-merge o update del Master/Golden.

## Percorsi prodotto
A. Audit leggibile -> report con fonti e commit.
B. Fix locale -> workspace isolato -> diff -> test -> proposta di PR.
C. QA -> build/test/quality evidence -> report; device e Play distinti.
D. Research -> OSS/license review -> candidati Donor; promozione mai automatica.
E. Finance consumer -> autorizzazioni e storage separati; read-only.

## Misure di successo
Tasso job finiti e ripresi, retry non dannosi, falsi PASS zero, tempo risparmiato misurato, zero write fuori scope, qualità patch, CI exact-head e risparmio token/costi. Nessun KPI di performance dichiarato in assenza di esperimenti.
