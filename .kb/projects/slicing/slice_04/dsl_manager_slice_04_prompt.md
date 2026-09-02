Implementa solo la Slice 4 per DSL Manager v1.

Prima leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `pyproject.toml`
- i moduli e i test già presenti in `src/dsl_mngr` e `tests`

Contesto:
Le Slice 1-3 hanno già introdotto workspace, config, logging JSONL, SQLite/migrations e corpus scan/source registry.
Lo schema SQLite contiene già `runs` e `worker_runs`; non aggiungere migrazioni salvo necessità reale e compatibile.
Non collegare ancora `corpus scan` al run lifecycle: `source_events.run_id` può restare `NULL`.

Task:
Implementare la minima vertical slice funzionante per "runs lifecycle e worker runner isolato".

Scope:
- aggiungere `runs.py` per creare, completare e fallire run nel database
- aggiungere `worker_runner.py` per eseguire worker isolati tramite subprocess
- creare directory `artifacts/runs/RUN_xxxxxx`
- scrivere per ogni run:
  - `input.json`
  - `output.json`, quando disponibile
  - `process_report.json`
  - `resolved_config.yaml`
  - `config_hash.txt`
  - `log.jsonl`
- registrare e aggiornare righe in `runs` e `worker_runs`
- gestire exit code, durata, stdout/stderr essenziali e failure leggibili
- validare l’output del worker prima di applicare eventuali mutazioni
- applicare eventuali mutazioni DB solo dentro transazione
- fare rollback se l’output è invalido o se l’applicazione delle mutazioni fallisce
- aggiungere CLI minima:
  - `dsl-manager run start [workspace] --type test`
  - `dsl-manager run status [workspace] RUN_000001`
- mantenere compatibile anche `python -m dsl_mngr run ...`
- aggiungere test automatici deterministici

Expected behavior:
- `run start` crea `RUN_000001`, poi ID successivi sequenziali
- la riga `runs` parte con status `running`
- `run_type` accetta almeno `test`, usando i valori del design dove già sensato
- `parent_run_id` è opzionale e validato se presente
- `input_json` e `output_json` sono JSON deterministici, serializzati con chiavi ordinate
- i path salvati nel DB sono relativi al workspace e normalizzati con `/`
- `resolved_config.yaml` deriva dal loader config esistente
- `config_hash.txt` contiene SHA-256 del contenuto di `resolved_config.yaml`
- `log.jsonl` contiene record con `run_id` e, per worker, `worker`
- `run status` stampa run id, type, status, started/finished e artifact directory

Worker runner:
- deve invocare worker Python con l’interprete corrente (`sys.executable`), non con `python` globale
- per i test è accettabile usare piccoli worker fixture sotto `tests/fixtures/workers`
- il worker riceve almeno `--input <input.json>` e `--output <output.json>`
- su exit code `0`, l’output deve essere JSON valido e coerente con `run_id`/`worker_name`
- su exit code non zero, il run e il `worker_run` diventano `failed`
- se l’output è mancante, JSON invalido o incoerente, il run diventa `failed`
- gli artifact restano disponibili per debug anche in caso di errore
- nessuna mutazione applicativa deve essere persistita se il worker fallisce o produce output invalido
- le uniche scritture ammesse in failure sono stato run/`worker_run`, report e log

Constraints:
- non implementare worker reali Docling, chunking, parser DDL/XML/SQL/log
- non implementare AI package, inbox/outbox, candidate import, validation o merge
- non implementare DSL renderer, diff, graph export, batch orchestration o UI
- non modificare lateralmente Slice 1-3
- non usare ORM
- non aggiungere dipendenze runtime
- usare solo import assoluti da `dsl_mngr`
- non importare mai da `src`
- i test devono usare `tmp_path`
- i test non devono dipendere da path assoluti o dallo stato locale

Suggested modules:
- `src/dsl_mngr/core/runs.py`
- `src/dsl_mngr/core/worker_runner.py`
- `src/dsl_mngr/cli/commands/run.py`
- `src/dsl_mngr/cli/app.py`
- `tests/test_slice_04_runs_worker_runner.py`
- eventuali fixture worker minimali in `tests/fixtures/workers/`

Tests:
- `test_run_lifecycle`
- `test_run_start_and_status_cli_smoke`
- `test_worker_success_report`
- `test_worker_failure_does_not_mutate_db`
- `test_worker_invalid_output_marks_run_failed`
- `test_run_artifacts_are_relative_and_deterministic`

Done when:
- la Slice 4 è implementata end-to-end
- `dsl-manager run start` e `dsl-manager run status` funzionano
- il worker runner registra `worker_runs` e produce report
- failure e output invalidi non corrompono lo stato applicativo
- i test pertinenti esistono e sono deterministici
- tutti i test passano con l’interprete configurato in `.codex/config.toml`
- nessuna feature fuori scope è stata aggiunta

Prima di modificare codice:
1. leggi `.codex/config.toml` e ricava `PROJECT_PYTHON`
2. installa il progetto in editable mode con quell’interprete:
   `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
3. dichiara brevemente i file che prevedi di toccare

Poi:
1. implementa la slice
2. aggiungi o aggiorna i test
3. esegui:
   `.\.venv\Scripts\python.exe -m pytest`
4. mostra il diff finale
5. riporta il risultato dei test, indicando l’interprete usato
6. riassumi cosa è stato aggiunto e cosa è rimasto volutamente fuori scope
