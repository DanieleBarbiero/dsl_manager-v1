Implementa solo la Slice 12 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/template/template_slice_report.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`
- `.kb/projects/slicing/slice_05/dsl_manager_slice_05_report.md`
- `.kb/projects/slicing/slice_06/dsl_manager_slice_06_report.md`
- `.kb/projects/slicing/slice_07/dsl_manager_slice_07_report.md`
- `.kb/projects/slicing/slice_08/dsl_manager_slice_08_report.md`
- `.kb/projects/slicing/slice_09/dsl_manager_slice_09_report.md`
- `.kb/projects/slicing/slice_10/dsl_manager_slice_10_report.md`
- `.kb/projects/slicing/slice_11/dsl_manager_slice_11_report.md`

Task:
Implementare la minima slice verticale funzionante per parsare DDL SQL e registrare evidenza strutturale deterministica nel registry.

La Slice 12 deve introdurre un parser DDL base, isolato dietro worker, capace di leggere sorgenti `ddl` gia' registrate dal corpus scan, estrarre tabelle, colonne, primary key, foreign key e vincoli minimi, produrre artifact riproducibili e persistere record in `source_fragments`.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs`, `run_worker` e artifact deterministici.
- Slice 5 ha introdotto `chunks`, `source_fragments`, `candidate_batches`, `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto merge deterministico di `candidate_fact` e `candidate_relation`.
- Slice 7 ha introdotto renderer DSL JSON/YAML/Markdown e `dsl_snapshots`.
- Slice 8 ha introdotto `dsl diff` tracciabile.
- Slice 9 ha stabilizzato il golden pipeline test dell'MVP tecnico.
- Slice 10 ha introdotto normalizzazione Docling no-images dietro adapter/worker.
- Slice 11 ha introdotto chunking stabile, `chunks.jsonl`, `chunk_report.json` ed evidence lookup su chunk prodotti.
- `candidate_validation.validate_candidate_payload` supporta gia' `fragment_id`; la Slice 12 deve dimostrare che i frammenti DDL possono essere usati come evidence senza passare da chunk testuali.

Decisione di scope:
- Per questa slice, "`facts` strutturali" significa: oggetti DDL normalizzati prodotti dal parser e rappresentati in artifact/report e in `source_fragments.metadata_json`.
- Non forzare l'inserimento diretto nella tabella `facts`, perche' nello schema attuale `facts.first_candidate_record_id` e' obbligatorio e lega il merge ai candidate records.
- Non creare candidate records sintetici solo per aggirare quel vincolo.
- Se ritieni indispensabile aggiungere una persistenza separata per parser-derived technical `facts`, deve essere una migration append-only piccola e motivata nel report; non modificare il contratto pubblico di `facts merge`, `dsl render` o `dsl diff`.
- Il deliverable primario e accettabile della slice e': parser DDL deterministico + `source_fragments` idempotenti + artifact + test su tables/foreign keys/evidence via `fragment_id`.

Scope:
- aggiungere un core piccolo e testabile per il parsing DDL, per esempio:

```text
src/dsl_mngr/core/ddl_parser.py
```

- aggiungere, se serve, un core piccolo per persistere frammenti in modo idempotente, per esempio:

```text
src/dsl_mngr/core/fragment_registry.py
```

- aggiungere un worker reale:

```text
src/dsl_mngr/workers/parse_ddl.py
```

- integrare un comando CLI nello stile `argparse` esistente:

```powershell
dsl-manager corpus parse-ddl <workspace> --revision REV_000001
```

- mantenere compatibilita' con:

```powershell
python -m dsl_mngr corpus parse-ddl <workspace> --revision REV_000001
```

- aggiungere un profilo default nel workspace inizializzato:

```text
configs/workers/ddl.default.yaml
```

- aggiungere la directory workspace `fragments/`, coerente con il design;
- aggiungere `parse_ddl` ai run type ammessi;
- usare `worker_runner.run_worker` per invocare il worker e registrare `worker_runs`;
- creare run di tipo `parse_ddl`;
- produrre output sotto:

```text
fragments/<source_id>/<source_revision_id>/fragments.jsonl
fragments/<source_id>/<source_revision_id>/ddl_report.json
```

- persistere i frammenti prodotti nella tabella `source_fragments`;
- se la source ha `source_type = "unknown"`, puoi aggiornarla a:
  - `source_type = "ddl"`;
  - `source_subtype = "mixed_ddl"`;
  - `authority_level = "technical_structure"`;
- non sovrascrivere classificazioni gia' esplicite e diverse senza una ragione testata.

Profilo default minimo consigliato:

```yaml
worker:
  name: parse_ddl
  version: 1.0
ddl:
  dialect: generic_sql
  parse_create_table: true
  parse_primary_keys: true
  parse_foreign_keys: true
  parse_unique_constraints: true
  parse_indexes: true
  strict_options_fail_on_unsupported_option: true
  unsupported_statement_policy: warn
  output_fragments_jsonl: true
```

Se il parser YAML minimale non supporta strutture oltre un livello, mantieni questa forma flat a sezioni semplici. Non fare un refactor generale della configurazione.

Parsing minimo richiesto:
- `CREATE TABLE <table> (...)`;
- nomi tabella con eventuale schema, per esempio `dbo.CLIENTI`;
- identificatori non quotati e, se semplice, quotati con `"name"`, `[name]` o `` `name` ``;
- colonne con nome, tipo raw e attributi minimi:
  - `NOT NULL`;
  - `NULL`;
  - `DEFAULT <raw>`;
  - `PRIMARY KEY` inline;
  - `UNIQUE` inline;
- vincoli table-level:
  - `PRIMARY KEY (...)`;
  - `FOREIGN KEY (...) REFERENCES <table> (...)`;
  - `UNIQUE (...)`;
  - `CONSTRAINT <name> ...`;
- `CREATE INDEX` e `CREATE UNIQUE INDEX`, se implementabile in modo piccolo;
- commenti SQL `-- ...` e `/* ... */` da ignorare preservando offsets ragionevoli, oppure da gestire prima del parsing documentando la scelta.

DDL fixture minima da coprire nei test:

```sql
CREATE TABLE ANCLI (
  CODCLI CHAR(10) NOT NULL,
  RAGSOC VARCHAR(80) NOT NULL,
  PIVA CHAR(11),
  PROV CHAR(2),
  PRIMARY KEY (CODCLI)
);

CREATE TABLE ORDTES (
  IDORD INTEGER NOT NULL,
  CODCLI CHAR(10) NOT NULL,
  STATO CHAR(12) NOT NULL,
  DATCONF DATE,
  PRIMARY KEY (IDORD),
  FOREIGN KEY (CODCLI) REFERENCES ANCLI(CODCLI)
);

CREATE TABLE ORDRIG (
  IDORD INTEGER NOT NULL,
  RIGA INTEGER NOT NULL,
  CODART CHAR(20) NOT NULL,
  QTA DECIMAL(9,2) NOT NULL,
  PRIMARY KEY (IDORD, RIGA),
  FOREIGN KEY (IDORD) REFERENCES ORDTES(IDORD)
);
```

Expected behavior:
- il comando verifica che workspace e database siano inizializzati e migrati;
- il comando verifica che `source_revision_id` esista;
- la revision deve appartenere a una `source` esistente;
- il comando legge il file sorgente da `source_revisions.file_path`;
- il path sorgente deve essere relativo al workspace, senza path traversal;
- il contenuto letto deve avere SHA-256 coerente con `source_revisions.content_hash`; se non coincide, fallire con errore leggibile che inviti a rieseguire `corpus scan`;
- il comando carica e valida il profilo `ddl.default` o quello indicato da `--profile`;
- il comando crea una run `parse_ddl`;
- il comando invoca `parse_ddl` via `run_worker`;
- il worker non scrive direttamente nel database principale;
- il worker produce oggetti e frammenti in ordine stabile;
- al successo, il sistema scrive:
  - `fragments.jsonl`;
  - `ddl_report.json`;
- al successo, `worker_runs.status == "completed"`;
- al successo, `runs.status == "completed"`;
- al successo, i frammenti sono persistiti in `source_fragments` con `status = "active"`;
- rieseguire il parsing della stessa revision con stesso input/config non deve creare duplicati attivi;
- rieseguire il parsing della stessa revision deve riusare gli stessi `fragment_id` per le stesse sequence quando possibile;
- eventuali frammenti attivi in eccesso per la stessa revision devono essere marcati `stale`;
- i path salvati in output, report, artifact e database devono essere relativi al workspace e usare `/`;
- i log non devono contenere contenuti lunghi del DDL.

Output CLI minimo al successo:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Tables: 3
Columns: 12
Foreign keys: 2
Fragments: 17
Fragments hash: <sha256>
Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl
Report: fragments/SRC_000001/REV_000001/ddl_report.json
```

Contratto worker:
- il worker deve accettare il contratto gia' usato da `run_worker`:

```powershell
python <worker_path> --input artifacts\runs\RUN_000001\input.json --output artifacts\runs\RUN_000001\output.json
```

- il worker deve produrre `output.json` coerente con `run_worker`, includendo almeno:
  - `run_id`;
  - `worker_name`;
  - `worker_version`;
  - `status`;
  - `exit_code`;
  - `source_id`;
  - `source_revision_id`;
  - `source_hash`;
  - `input_path`;
  - `fragments_jsonl_path`;
  - `ddl_report_path`;
  - `fragment_count`;
  - `fragments_hash`;
  - `table_count`;
  - `column_count`;
  - `foreign_key_count`;
  - `profile`;
  - `dialect`;
  - `ddl_objects`;
  - `fragments`;
- `fragments` puo' contenere record senza `fragment_id` tecnico solo se il core applicativo assegna o riusa gli ID prima di scrivere il `fragments.jsonl` canonico finale;
- non lasciare nel `fragments.jsonl` finale ID provvisori.

Formato `fragments.jsonl` canonico:

Ogni riga deve essere JSON valido e deterministico. Esempio:

```json
{"fragment_id":"FRAG_000001","source_revision_id":"REV_000001","fragment_type":"ddl_table","sequence":1,"path_or_selector":"table:ANCLI","line_start":1,"line_end":7,"char_start":0,"char_end":142,"text":"CREATE TABLE ANCLI (...);","text_hash":"<sha256>","status":"active","metadata":{"parser":"parse_ddl","parser_version":"1.0","dialect":"generic_sql","object_type":"table","table_name":"ANCLI","columns":["CODCLI","RAGSOC","PIVA","PROV"],"primary_key":["CODCLI"],"foreign_keys":[]}}
```

Regole frammenti:
- `sequence` parte da 1 per ogni `source_revision_id`;
- `fragment_id` usa un formato stabile e leggibile, per esempio `FRAG_000001`;
- `fragment_type` deve essere almeno:
  - `ddl_table` per la statement/table;
  - `ddl_column` per colonne;
  - `ddl_constraint` per primary key, foreign key, unique e vincoli table-level;
- `text` deve essere non vuoto;
- `text` deve usare newline `\n`;
- `text_hash` e' SHA-256 del `text` UTF-8;
- `fragments_hash` e' SHA-256 del contenuto canonico di `fragments.jsonl`;
- `metadata_json` nel database deve essere JSON canonico, con chiavi ordinate;
- `metadata_json` deve includere almeno:
  - `parser`;
  - `parser_version`;
  - `dialect`;
  - `source_hash`;
  - `statement_kind`;
  - `object_type`;
  - `table_name`, quando applicabile;
  - `column_name`, quando applicabile;
  - `constraint_name`, quando applicabile;
  - `constraint_kind`, quando applicabile;
  - `columns`, quando applicabile;
  - `references_table`, quando applicabile;
  - `references_columns`, quando applicabile;
  - `nullable`, quando applicabile;
  - `data_type`, quando applicabile;
- `line_start` e `line_end` sono 1-based;
- `char_start` e `char_end` sono offset sul DDL normalizzato con newline `\n`;
- `path_or_selector` deve essere stabile, per esempio:
  - `table:ANCLI`;
  - `table:ANCLI/column:CODCLI`;
  - `table:ORDTES/foreign_key:CODCLI->ANCLI.CODCLI`.

Persistenza DB:
- usare la tabella `source_fragments` gia' esistente;
- non modificare migrazioni gia' applicate;
- se serve una modifica schema, aggiungere una nuova migration append-only e motivarla nel report;
- per questa slice dovrebbe bastare lo schema attuale;
- inserire o aggiornare i campi:
  - `fragment_id`;
  - `source_revision_id`;
  - `fragment_type`;
  - `sequence`;
  - `path_or_selector`;
  - `line_start`;
  - `line_end`;
  - `char_start`;
  - `char_end`;
  - `text`;
  - `text_hash`;
  - `metadata_json`;
  - `status`;
  - `created_at`;
- non cancellare frammenti storici;
- per idempotenza:
  - se esiste gia' un fragment per stessa revision e stessa sequence, riusa il suo `fragment_id`;
  - aggiorna testo/metadati se sono cambiati;
  - marca `active` i fragment prodotti dalla run corrente;
  - marca `stale` eventuali fragment attivi della stessa revision con sequence non piu' prodotta;
  - non creare una nuova serie di fragment attivi identica a ogni rerun.

Evidence lookup:
- `candidate_validation.validate_candidate_payload` verifica che `evidence_text` sia contenuto nel `source_fragments.text` quando il candidato usa `fragment_id`;
- aggiungi un test che dimostri che un candidato fixture puo' essere validato usando `fragment_id` prodotto dal parser DDL;
- il candidato puo' essere un `candidate_relation` con:
  - `source_entity = "ORDTES"`;
  - `relation_type = "references"`;
  - `target_entity = "ANCLI"`;
  - `fragment_id` del foreign key fragment;
  - `chunk_id` assente;
  - `evidence_text` contenuto nel testo del fragment.

Gestione errori:
- se `source_revision_id` non esiste, errore leggibile;
- se la revision non appartiene a una source esistente, errore leggibile;
- se il file sorgente manca, errore leggibile;
- se il file sorgente ha hash diverso da `source_revisions.content_hash`, errore leggibile;
- se il profilo contiene un'opzione non supportata e `strict_options_fail_on_unsupported_option` e' true:
  - il worker deve fallire con exit code `4`;
  - `worker_runs.exit_code` deve essere `4`;
  - `worker_runs.status` deve essere `failed`;
  - `runs.status` deve essere `failed`;
  - `process_report.json` o `log.jsonl` devono includere `unsupported_ddl_option` e la chiave problematica;
  - non devono essere creati frammenti attivi nel database;
- se il DDL e' malformato in modo non recuperabile:
  - fallire con errore leggibile;
  - non applicare mutazioni parziali al database;
  - registrare run/worker failed;
- se ci sono statement non supportati ma `unsupported_statement_policy = "warn"`:
  - completare il parsing delle statement supportate;
  - registrare warning nel report;
  - non trattare come failure.

Artifact:
- `artifacts/runs/<run_id>/input.json` deve includere almeno:
  - `source_id`;
  - `source_revision_id`;
  - `source_hash`;
  - `input_path`;
  - `output_dir`;
  - `profile`;
  - `ddl_options`;
  - `fragment_id_by_sequence`, se usato;
  - `next_fragment_number`, se usato;
- `artifacts/runs/<run_id>/output.json` deve includere almeno il payload del worker/core;
- `artifacts/runs/<run_id>/process_report.json` deve avere:
  - `run_type = "parse_ddl"`;
  - `status = "completed"` al successo;
  - una voce worker `parse_ddl`;
  - `artifact_dir` relativo;
  - `config_hash`;
- `resolved_config.yaml`, `config_hash.txt` e `log.jsonl` devono restare coerenti con Slice 4.

Test minimi richiesti:
- `test_parse_ddl_tables`;
- `test_parse_ddl_foreign_keys`.

Aggiungi preferibilmente anche:
- `test_parse_ddl_fragment_evidence_lookup`;
- `test_parse_ddl_idempotent_rerun`;
- `test_parse_ddl_unsupported_option_fails_without_active_fragments`.

I test devono verificare almeno:
- un workspace temporaneo viene inizializzato con `tmp_path`;
- il database viene inizializzato/migrato;
- `configs/workers/ddl.default.yaml` esiste o il profilo default e' disponibile in modo equivalente;
- una o piu' fixture DDL vengono copiate in `corpus/active`;
- `corpus scan` registra le source/revision;
- `corpus parse-ddl <workspace> --revision REV_000001` completa con exit code 0;
- il comando funziona anche via `python -m dsl_mngr`;
- `fragments/<source_id>/<source_revision_id>/fragments.jsonl` e `ddl_report.json` vengono creati;
- `source_fragments` contiene record `ddl_table`, `ddl_column`, `ddl_constraint`;
- le tabelle `ANCLI`, `ORDTES`, `ORDRIG` sono estratte;
- le colonne e i tipi raw principali sono estratti;
- primary key semplici e composite sono estratte;
- foreign key `ORDTES.CODCLI -> ANCLI.CODCLI` e `ORDRIG.IDORD -> ORDTES.IDORD` sono estratte;
- ogni `text_hash` coincide con SHA-256 del `text`;
- `fragments_hash` resta stabile su rerun con stesso input/config;
- rerun della stessa revision non crea duplicati attivi;
- `runs` contiene run `parse_ddl` completate;
- `worker_runs` contiene worker `parse_ddl` completati;
- `process_report.json` contiene path relativi e nessun `\`;
- evidence lookup con `fragment_id` accetta il candidato fixture;
- nessuna regressione sulle slice 1-11.

Fixture consigliata:
- crea fixture DDL dedicate, per esempio sotto `tests/fixtures/ddl/` o `tests/fixtures/corpus_ddl/`;
- non aggiungere DDL a `tests/fixtures/corpus_initial/` salvo aggiornare consapevolmente i golden test della Slice 9;
- usare file piccoli e locali;
- non usare rete nei test;
- non usare AI reale;
- non dipendere da Docling;
- non introdurre parser SQL esterni;
- evitare assert fragili sull'intero report; verificare invece hash, path, conteggi, oggetti e metadata essenziali.

Constraints:
- non implementare parser XML form;
- non implementare parser SQL code, procedure, trigger o log;
- non implementare AI package handoff;
- non implementare batch orchestration;
- non implementare export GEXF;
- non implementare UI, web/API/auth o integrazioni esterne;
- non aggiungere ORM;
- non aggiungere dipendenze runtime per il parser DDL;
- non modificare il contratto pubblico di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`;
- non salvare path assoluti negli artifact o nel database;
- non fare chiamate di rete durante parsing o test;
- non usare import da `src`;
- usare import assoluti da `dsl_mngr`;
- mantenere separati CLI, worker, core parser, persistence e test;
- mantenere l'implementazione piccola, leggibile e deterministica;
- i test devono usare `tmp_path`.

Done when:
- Slice 12 e' implementata end-to-end nello scope richiesto;
- `corpus parse-ddl` produce artifact DDL stabili;
- `fragments.jsonl` e `ddl_report.json` vengono prodotti;
- la tabella `source_fragments` viene popolata in modo idempotente;
- il parser estrae tabelle, colonne, primary key e foreign key minime;
- evidence lookup funziona con `fragment_id`;
- i test nuovi sono significativi;
- tutta la suite passa;
- non e' stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l'interprete corretto;
5. mostra diff e risultato dei test, indicando l'interprete usato;
6. esegui una breve autoverifica finale contro scope, constraints e done criteria.

Report finale:

```text
salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_12/dsl_manager_slice_12_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
```
