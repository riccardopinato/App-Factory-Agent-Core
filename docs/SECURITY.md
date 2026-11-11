# Trust boundaries e autorizzazioni

**Threat model iniziale:** issue/README/PR/prompt possono contenere istruzioni ostili; trattarli come input dati, non policy. Code runner e shell sono superfici ad alto rischio.

| Operazione | Default | Gate |
|---|---|---|
| read GitHub public, analysis | consentito nel task | citazione ref e rate limits |
| local fixture tests | consentito in sandbox | no network/secret; resource cap |
| clone repository consentito | ammesso solo repo allowlist | URL e ref pinned |
| modifica file in workspace | proposta soltanto | path allowlist + diff |
| push branch / creazione PR | vietato finché non autorizzato | conferma scope e tests |
| merge PR / deploy / release | vietato per default | exact-head gates + approval |
| Master/Golden mutation | vietato via auto-sync | Factory governance PR |
| broker/order live | fuori scope | mai consentire nel core |

- Secret manager esterno; mai logs di token o path sensibili.
- Privilegi minimi per adapter; ripartire Finance e Development in service accounts/secret scopes distinti.
- No shell injection: args strutturati, allowlist eseguibili, sandbox, filesystem temporaneo.
- Niente git force push né cancellazione di dati non richiesti.
- Data minimization e masking su logs/evidence; audit retention configurabile, non implicito.
- Read-only cron non è agent di sviluppo; un modello che suggerisce comandi non li autorizza.
