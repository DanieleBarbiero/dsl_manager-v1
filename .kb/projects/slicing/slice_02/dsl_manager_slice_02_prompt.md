Implementa solo la Slice 2 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`

Task:
Implementare la minima vertical slice funzionante per "inizializzare lo schema SQLite minimo e gestire migrazioni idempotenti".

Scope:
- creare un layer SQLite minimale usando solo `sqlite3` della standard library
- aggiungere un modulo `database.py` per:
  - risolvere il path del database dal workspace e dalla config esistente
  - aprire connessioni SQLite
  - applicare `PRAGMA foreign_keys = ON`
  - applicare WAL quando `database.wal` / `MDW_ENABLE_WAL` è true
- aggiungere un modulo `migrations.py` per:
  - creare `schema_migrations`
  - definire migrazioni ordinate e versionate
  - applicare solo le migrazioni mancanti
  - registrare versione, nome, checksum e timestamp di applicazione
  - essere rieseguibile senza duplicare o corrompere stato
- creare lo schema SQLite minimo con queste tabelle:
  - `schema_migrations`
  - `sources`
  - `source_revisions`
  - `source_events`
  - `runs`
  - `worker_runs`
- aggiungere un comando CLI verificabile:
  - `dsl-manager db init [workspace]`
  - compatibile anche con `python -m dsl_mngr db init [workspace]`
- usare il config loader già esistente dalla Slice 1
- scrivere un record JSONL in `logs/app.jsonl` quando il database viene inizializzato o migrato
- aggiungere test automatici per il comportamento implementato

Expected behavior:
- dato un workspace già creato con `dsl-manager init`, `dsl-manager db init <workspace>` crea il file SQLite configurato
- il path del database viene letto da:
  - default interni
  - `configs/project.yaml`
  - `.env`
  - eventuali opzioni CLI già supportate
- il default è `workspace.sqlite` dentro il workspace
- il comando applica tutte le migrazioni mancanti in ordine
- rieseguire il comando non applica di nuovo migrazioni già registrate
- `schema_migrations` contiene una riga per ogni migrazione applicata
- `PRAGMA foreign_keys` risulta attivo sulle connessioni create dal layer applicativo
- se WAL è abilitato in config, il database usa `journal_mode = wal`
- se il workspace non è inizializzato, il comando fallisce con un errore leggibile che invita a eseguire prima `dsl-manager init`
- l’output CLI indica in modo leggibile database path e numero di migrazioni applicate/skippate

Schema minimo atteso:
- `sources` contiene almeno:
  - `source_id`
  - `logical_name`
  - `source_type`
  - `source_subtype`
  - `authority_level`
  - `first_seen_at`
  - `last_seen_at`
  - `current_revision_id`
  - `status`
  - `created_at`
  - `updated_at`
- `source_revisions` contiene almeno:
  - `source_revision_id`
  - `source_id`
  - `revision_number`
  - `content_hash`
  - `normalized_hash`
  - `file_path`
  - `file_size`
  - `detected_at`
  - `status`
  - `created_at`
- `source_events` contiene almeno:
  - `source_event_id`
  - `source_id`
  - `source_revision_id`
  - `event_type`
  - `event_timestamp`
  - `details_json`
  - `run_id`
- `runs` contiene almeno:
  - `run_id`
  - `run_type`
  - `status`
  - `started_at`
  - `finished_at`
  - `parent_run_id`
  - `input_json`
  - `output_json`
  - `created_at`
  - `updated_at`
- `worker_runs` contiene almeno:
  - `worker_run_id`
  - `run_id`
  - `worker_name`
  - `worker_version`
  - `status`
  - `input_path`
  - `output_path`
  - `report_path`
  - `log_path`
  - `exit_code`
  - `duration_ms`
  - `started_at`
  - `finished_at`

Constraints:
- non implementare corpus scan, source registry applicativo, candidate import, merge, renderer DSL o diff
- non implementare Docling, parser DDL/XML/SQL/log o handoff AI
- non implementare worker runner completo: `runs` e `worker_runs` sono solo schema in questa slice
- non inserire dati applicativi reali oltre alle righe di `schema_migrations`
- non aggiungere ORM
- non aggiungere dipendenze runtime
- mantenere la CLI coerente con lo stile `argparse` già presente
- mantenere separati CLI, database e migrations
- usare import assoluti dal package `dsl_mngr`
- non importare mai da `src`
- mantenere l’implementazione piccola, leggibile e deterministica
- i test devono usare `tmp_path`
- i test non devono dipendere da path assoluti o dallo stato della macchina locale

Suggested modules:
- `src/dsl_mngr/core/database.py`
- `src/dsl_mngr/core/migrations.py`
- `src/dsl_mngr/cli/commands/db.py`
- `src/dsl_mngr/cli/app.py`
- `tests/test_slice_02_database_migrations.py`

Questi nomi sono suggeriti: adatta la struttura se il repository esistente richiede una soluzione più semplice, ma mantieni chiari i confini tra CLI, database e migrations.

Tests:
- `test_database_init`
- `test_migrations_idempotent`
- `test_wal_config`
- `test_foreign_keys_enabled`
- `test_db_init_cli_smoke`
- un test che verifica la presenza delle tabelle minime richieste
- un test che verifica che il comando fallisca in modo leggibile se il workspace non è inizializzato

Done when:
- `dsl-manager db init <workspace>` crea e migra il database SQLite
- `python -m dsl_mngr db init <workspace>` funziona
- le tabelle minime esistono
- `schema_migrations` registra le migrazioni applicate
- rieseguire la migrazione è idempotente
- foreign keys e WAL configurabile sono verificati dai test
- viene scritto un log JSONL applicativo coerente con la Slice 1
- i test pertinenti esistono
- `python -m pytest` passa con l’interprete corretto indicato da `AGENTS.md`
- nessuna feature fuori scope della v1 è stata aggiunta

Prima di modificare codice:
1. ispeziona `.codex/config.toml`, se presente, e usa `PROJECT_PYTHON` come unico interprete Python valido in ambiente VS Code Windows
2. installa il progetto con l’interprete corretto:
   `python -m pip install -e ".[dev]"`
   riscrivendo il comando secondo `AGENTS.md`
3. dichiara brevemente i file che prevedi di toccare

Poi:
1. implementa la slice
2. aggiungi o aggiorna i test
3. esegui i test con l’interprete corretto
4. mostra il diff
5. riporta il risultato dei test, indicando quale interprete è stato usato
6. riassumi cosa è stato aggiunto e cosa è rimasto volutamente fuori scope
