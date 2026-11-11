# AGENTS — App Factory Agent Core

1. Risolvere una volta la baseline App-Factory-Core/CURRENT.yaml, Master v27 e Golden Index/Registry correnti, poi Golden pertinenti: governance agenti, event-driven reconciliation, provenance, continuous maintenance. Fissare il commit.
2. PRODUCT_BIBLE.md governa lo scope; ROADMAP.md l'ordine; AGENTS.md governa il modo di operare; codice e test provano il comportamento reale.
3. Mantenere `main` protetta; modifiche sostanziali su branch/PR, controlli sull'exact SHA. Non fare force push, bypass, auto-merge o pubblicazioni senza gate.
4. Non dichiarare importati i file locali Windows né simulare output di test; USER_REPORTED resta distinto da CI_VERIFIED/DEVICE_VERIFIED.
5. Ogni job deve avere tenant, autorizzazioni esplicite, idempotency key, limite temporale, ledger dell'azione, input/output verificati e annullamento sicuro.
6. Per ogni write: least privilege, allowlist repo/path, verifica exact-head, approvazione richiesta; merge e release sono azioni più privilegiate dei commit.
7. No secret, token, keystore, .env, prompt contenenti credenziali, dati di portafoglio o log personali nel repository pubblico.
8. No LLM fuori rete o uso di API a pagamento senza autorizzazione esplicita; preferenza modello locale opzionale, con costi e limiti visibili.
9. Riuso: verificare codice, commit, file license e donor gates; non duplicare AppLab, GBrain o la Factory centrale.
10. Aggiornamento metadata automatico SOLO in `docs/AUTO_CONTEXT.*` tramite PR; narrativa e codice richiedono revisione semantica ed evidence.
11. Un cron GitHub Actions non è un servizio persistente Windows; non promettere continuità se il PC è spento.
12. Test minimi per coding agent: idempotenza, crash+resume, errori rete, diff invalidi, shell injection, changed HEAD, privilege refusal, rollback.
