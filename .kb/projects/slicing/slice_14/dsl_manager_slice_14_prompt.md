Implementa solo la Slice 14 per DSL Manager v1.

Prima leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/projects/slicing/slice_12/dsl_manager_slice_12_report.md`
- `.kb/projects/slicing/slice_13/dsl_manager_slice_13_report.md`
- il codice attuale sotto `src/dsl_mngr`
- i test attuali sotto `tests`

Task:
implementare il minimo incremento verticale per "Parser SQL Code e Log".

Obiettivo:
- estrarre evidenza strutturale deterministica da procedure e trigger SQL;
- estrarre eventi osservati da log testuali line-based;
- salvare i risultati come `source_fragments` idempotenti;
- rendere le evidenze usabili da `candidates validate` tramite `fragment_id`;
- dimostrare, con candidati fixture deterministici nei test, che procedure/trigger/log event `facts` e relazioni `observed_in` possono essere validate e merged senza AI reale.

Scope:
- aggiungi il core parser SQL code minimo, per esempio `dsl_mngr.core.db_code_parser`;
- aggiungi il core parser log minimo, per esempio `dsl_mngr.core.log_parser`;
- aggiungi i worker isolati:
  - `dsl_mngr.workers.parse_db_code`
  - `dsl_mngr.workers.parse_log`
- aggiungi i comandi CLI:
  - `dsl-manager corpus parse-db-code <workspace> --revision REV_000001`
  - `dsl-manager corpus parse-log <workspace> --revision REV_000001`
- aggiungi i profili default creati da `dsl-manager init`:
  - `configs/workers/db_code.default.yaml`
  - `configs/workers/log.default.yaml`
- estendi `runs.RUN_TYPES` con `parse_db_code` e `parse_log`;
- estendi `fragment_registry` per accettare e validare i nuovi worker e fragment type;
- aggiungi fixture minime per SQL code e log;
- aggiungi test deterministici Slice 14.

Comportamento atteso per `parse_db_code`:
- accetta una source revision gia' registrata dal corpus scan;
- valida che il file sorgente corrisponda a `source_revisions.content_hash`;
- invoca il worker tramite `worker_runner.run_worker`;
- produce artifact sotto `fragments/<source_id>/<source_revision_id>/`:
  - `fragments.jsonl`
  - `db_code_report.json`
- persiste i frammenti in `source_fragments` in modo idempotente, riusando `FRAG_*` per sequence su rerun;
- se la source e' `unknown`, la riclassifica come:
  - `source_type = database_code`
  - `source_subtype = trigger`, `procedure` oppure `mixed_sql_code`, in base a cosa viene rilevato
  - `authority_level = runtime_code`
- supporta almeno le fixture:
  - `CREATE TRIGGER TRG_ORDTES_CONF ...`
  - `CREATE PROCEDURE PRC_CALCOLA_SCONTO ...`
- estrae almeno:
  - trigger name;
  - procedure name;
  - trigger timing/event/target table, quando presenti;
  - parameter names della procedura, quando presenti;
  - statement `UPDATE`;
  - writes, per esempio `TRG_ORDTES_CONF writes ORDTES.DATCONF`;
  - reads ragionevoli da `WHERE` e da riferimenti `NEW.<colonna>`, quando rilevabili;
  - calls vuoto o valorizzato solo quando ci sono chiamate esplicite riconosciute.

Fragment type SQL richiesti:
- `sql_trigger`
- `sql_procedure`
- `sql_statement`

Metadata SQL minimi:
- campi comuni gia' richiesti dal registry:
  - `parser`
  - `parser_version`
  - `source_hash`
  - `object_type`
- per `sql_trigger`:
  - `trigger_name`
  - `trigger_timing`
  - `trigger_event`
  - `target_table`
  - `reads`
  - `writes`
  - `calls`
- per `sql_procedure`:
  - `procedure_name`
  - `parameters`
  - `reads`
  - `writes`
  - `calls`
- per `sql_statement`:
  - `parent_object_name`
  - `parent_object_type`
  - `statement_kind`
  - `reads`
  - `writes`
  - `calls`

Comportamento atteso per `parse_log`:
- accetta una source revision gia' registrata dal corpus scan;
- valida che il file sorgente corrisponda a `source_revisions.content_hash`;
- invoca il worker tramite `worker_runner.run_worker`;
- produce artifact sotto `fragments/<source_id>/<source_revision_id>/`:
  - `fragments.jsonl`
  - `log_report.json`
- persiste i frammenti in `source_fragments` in modo idempotente, riusando `FRAG_*` per sequence su rerun;
- se la source e' `unknown`, la riclassifica come:
  - `source_type = log`
  - `source_subtype = batch_log` quando il component e' batch-like, altrimenti `application_log`
  - `authority_level = runtime_observation`
- supporta almeno log line-based nel formato:
  - `YYYY-MM-DD HH:MM:SS LEVEL COMPONENT message`
- produce un `log_event` per ogni riga valida;
- estrae almeno:
  - timestamp;
  - level;
  - component;
  - message;
  - event kind minimo: `start`, `processed`, `warning`, `end`, `unknown`;
  - identifiers/key-value nel messaggio, per esempio `IDORD=1001`, `CODCLI=C000000001`, `processed=2`, `warnings=1`.

Fragment type log richiesti:
- `log_event`

Metadata log minimi:
- campi comuni gia' richiesti dal registry:
  - `parser`
  - `parser_version`
  - `source_hash`
  - `object_type`
- per `log_event`:
  - `timestamp`
  - `level`
  - `component`
  - `event_kind`
  - `message`
  - `observed_identifiers`

Expected CLI output:
- `parse-db-code` deve stampare almeno run, revision, source, procedures, triggers, statements, reads, writes, calls, fragments, fragments hash, fragments JSONL e report;
- `parse-log` deve stampare almeno run, revision, source, events, warnings, components, fragments, fragments hash, fragments JSONL e report;
- gli output path devono essere workspace-relative, con separatori `/`, mai assoluti.

Fixture minime:
- `tests/fixtures/db_code/trigger_ordini.sql`
- `tests/fixtures/db_code/procedura_sconti.sql`
- `tests/fixtures/logs/log_batch_ordini.log`

Usa come contenuto di riferimento le fixture descritte nel design:
- trigger `TRG_ORDTES_CONF`;
- procedura `PRC_CALCOLA_SCONTO`;
- log `BATCH_ORDINI` con start, processed order, warn missing VAT, end.

Test minimi richiesti:
- `test_parse_db_code_trigger`
- `test_parse_log`

I test devono coprire almeno:
- creazione dei profili default via `dsl-manager init`;
- `corpus scan`;
- parsing SQL code via CLI e via `python -m dsl_mngr`;
- parsing log via CLI e via `python -m dsl_mngr`;
- artifact `fragments.jsonl` e report JSON;
- hash canonico dei frammenti stabile;
- persistenza in `source_fragments`;
- classificazione source `unknown -> database_code` e `unknown -> log`;
- rerun idempotente con riuso degli stessi `fragment_id`;
- failure su opzione non supportata con exit code worker `4`, run/worker `failed` e zero frammenti attivi;
- evidence lookup con `fragment_id` tramite `candidates validate`;
- merge tramite `facts merge` di almeno:
  - un `candidate_fact` su un trigger/procedura, per esempio `TRG_ORDTES_CONF` con property `writes = ORDTES.DATCONF`;
  - un `candidate_fact` su un evento log osservato, con `assertion_type = observed`;
  - una `candidate_relation` con `relation_type = observed_in`.

Vincoli:
- non implementare un parser SQL generale;
- non introdurre ORM;
- non aggiungere dipendenze runtime per i parser SQL/log;
- non chiamare provider AI o servizi esterni;
- non implementare AI package handoff, batch orchestration, GEXF, UI, web/API/auth;
- non modificare i contratti pubblici esistenti di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`, salvo fix strettamente necessari e coperti da test;
- i worker parser non devono scrivere direttamente nel database principale;
- i worker parser non devono inserire direttamente `candidate_records`, `facts` o `relations`;
- le `facts` e `relations` della slice devono passare dal flusso esistente `source_fragments -> candidates validate -> facts merge`;
- mantieni gli import assoluti da `dsl_mngr`;
- mantieni output deterministico, newline LF e JSON canonico dove gia' usato dal progetto.

Done when:
- Slice 14 e' implementata nello scope sopra;
- i test Slice 14 esistono e passano;
- la suite completa passa;
- i comandi sono eseguiti con l'interprete configurato in `.codex/config.toml`;
- prima dei test hai eseguito install editable con l'interprete configurato;
- `git diff --check` non segnala errori;
- mostri diff/status e risultati test nel report finale;
- nessuna feature fuori scope e' stata aggiunta.

Prima di coding:
1. leggi i file indicati sopra;
2. dichiara brevemente i file che prevedi di toccare;
3. implementa;
4. esegui install editable e test con l'interprete corretto;
5. esegui una autoverifica finale su scope, test, diff e report;
6. riassumi cosa e' stato aggiunto e cosa e' rimasto fuori scope.

salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_14/dsl_manager_slice_14_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
