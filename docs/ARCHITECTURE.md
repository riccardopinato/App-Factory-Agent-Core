# Architettura di riferimento — DESIGN ONLY

```text
Event (GitHub issue / CLI / schedule)
 -> Authentication + untrusted-input filter
 -> Authorization policy (repo/path/tool/phase)
 -> Durable job ledger (SQLite first, versioned)
 -> idempotency + lease + checkpoint + queue
 -> Orchestrator
     |-- read-only analysis adapter
     |-- local model adapter (optional; bounded)
     |-- isolated workspace adapter
     |-- build/test QA adapter
     |-- proposed PR adapter (requires approval)
 -> evidence receipt & status report
 -> reconciliation watcher (lost event/retry/expired lease)
```

## Stati e transizioni
DRAFT -> VALIDATED -> QUEUED -> LEASED -> RUNNING -> WAITING_APPROVAL -> SUCCEEDED/FAILED/CANCELLED/BLOCKED.
Un terminal state non deve tornare RUNNING in modo opaco; retry è una nuova attempt con jobId stabile, attemptId crescente.
In `WAITING_APPROVAL`, la decisione approvata è associata a diff hash + source SHA + tool scope + expiry. Un cambiamento di input o SHA invalida l'approvazione.

## Deployment
- Windows/WSL worker locale con service/restart controllato; niente promesse 24/7 a PC spento.
- Per operation GitHub, usare Actions o runner esterno solo se necessario; token ristretto e secrets.
- Modello Qwen/Ollama locale come adapter, non parte obbligatoria dell'orchestratore; fallback deterministico se output non valido.
- GBrain è un possibile knowledge adapter da autorizzare e testare, non una dipendenza hard.

## Recovery
Duplicate delivery: idempotency key; EVENT_LOSS: reconciliation scan; EXECUTOR_OUTAGE: durable pending; INTERRUPTED_OPERATION: resume checkpoint; COORDINATOR_RESTART: lease recovery; EXPIRED_LEASE: recover; SUPERSEDING_SHA: block/re-plan.
Fonte processo: GOLDEN_EVENT_DRIVEN_RECONCILIATION_v1 (Core, COPY-READY PROCESS).

## Dev tools
SDK 36 verificato presente nella postazione non certifica build Gradle. Validare gradlew.bat, JDK, Gradle, Flutter e root target per repo; l'assenza di wrapper non va risolta copiando un wrapper arbitrario.
