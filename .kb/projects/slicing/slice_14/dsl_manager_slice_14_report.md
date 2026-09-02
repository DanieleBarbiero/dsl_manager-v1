# Report Slice 14

Implementata la Slice 14 end-to-end nello scope richiesto: parser SQL code e parser log deterministici dietro worker isolati, artifact `fragments.jsonl`/report, persistenza idempotente in `source_fragments`, evidence lookup via `fragment_id` e merge tramite candidati fixture senza AI reale.

## Aggiunto

- Core `dsl_mngr.core.db_code_parser` per `CREATE TRIGGER`, `CREATE PROCEDURE`, statement `UPDATE`, reads/writes/calls minimi e parametri procedura.
- Core `dsl_mngr.core.log_parser` per log line-based `YYYY-MM-DD HH:MM:SS LEVEL COMPONENT message`, eventi osservati e key-value nel messaggio.
- Worker isolati `dsl_mngr.workers.parse_db_code` e `dsl_mngr.workers.parse_log`, invocati via `worker_runner.run_worker` e senza scritture dirette nel database principale.
- Comandi CLI `dsl-manager corpus parse-db-code <workspace> --revision REV_000001` e `dsl-manager corpus parse-log <workspace> --revision REV_000001`, compatibili anche via `python -m dsl_mngr`.
- Profili default generati da `dsl-manager init`: `configs/workers/db_code.default.yaml` e `configs/workers/log.default.yaml`.
- Run type `parse_db_code` e `parse_log`.
- Estensione di `fragment_registry` per `sql_trigger`, `sql_procedure`, `sql_statement`, `log_event`, validazione metadata, report `db_code_report.json`/`log_report.json` e riclassificazione `unknown -> database_code/log`.
- Fixture minime:
  - `tests/fixtures/db_code/trigger_ordini.sql`
  - `tests/fixtures/db_code/procedura_sconti.sql`
  - `tests/fixtures/logs/log_batch_ordini.log`
- Test `test_parse_db_code_trigger` e `test_parse_log` per artifact, hash canonico, persistenza, idempotenza, failure worker exit code `4`, validate con `fragment_id` e merge di fact/relation osservate.

## Diff/status

```text
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/cli/commands/corpus.py
 M src/dsl_mngr/core/fragment_registry.py
 M src/dsl_mngr/core/runs.py
 M src/dsl_mngr/core/workspace.py
?? src/dsl_mngr/core/db_code_parser.py
?? src/dsl_mngr/core/log_parser.py
?? src/dsl_mngr/workers/parse_db_code.py
?? src/dsl_mngr/workers/parse_log.py
?? tests/fixtures/db_code/
?? tests/fixtures/logs/
?? tests/test_slice_14_parse_db_code_log.py
```

Diff stat sui file tracciati gia' presenti:

```text
src/dsl_mngr/cli/app.py                |  40 +++
src/dsl_mngr/cli/commands/corpus.py    | 640 ++++++++++++++++++++++++++++++++-
src/dsl_mngr/core/fragment_registry.py | 298 ++++++++++++++-
src/dsl_mngr/core/runs.py              |   2 +
src/dsl_mngr/core/workspace.py         |  30 ++
5 files changed, 1005 insertions(+), 5 deletions(-)
```

Nuovi file principali:

```text
src/dsl_mngr/core/db_code_parser.py
src/dsl_mngr/core/log_parser.py
src/dsl_mngr/workers/parse_db_code.py
src/dsl_mngr/workers/parse_log.py
tests/test_slice_14_parse_db_code_log.py
```

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita prima degli edit:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 14:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_14_parse_db_code_log.py
```

Risultato:

```text
2 passed in 6.62s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
59 passed in 143.97s (0:02:23)
```

## Verifiche aggiuntive

- `git diff --check` non segnala errori whitespace; restano solo warning Git sulla futura normalizzazione CRLF dei file modificati.
- Gli output path CLI e report sono workspace-relative e usano separatori `/`.
- `fragments_hash` coincide con SHA-256 del contenuto canonico di `fragments.jsonl` e resta stabile su rerun.
- Rerun della stessa revision riusa gli stessi `fragment_id` e non crea duplicati attivi.
- Il failure su opzione non supportata usa exit code worker `4`, run/worker `failed` e zero frammenti attivi.
- `candidates validate` accetta evidenza da `fragment_id` per SQL code e log.
- `facts merge` inserisce:
  - fact `TRG_ORDTES_CONF` con `writes = ORDTES.DATCONF`;
  - fact osservata da evento log `BATCH_ORDINI`;
  - relation osservata `observed_in`.

## Fuori scope / note

- Nessun parser SQL generale: il parser copre solo il minimo verticale per procedure/trigger e `UPDATE` richiesto dalle fixture.
- Nessuna dipendenza runtime nuova, nessun ORM e nessuna chiamata AI o servizio esterno.
- I worker parser non scrivono nel database principale e non inseriscono `candidate_records`, `facts` o `relations`.
- Non sono stati implementati AI package handoff, batch orchestration, GEXF, UI, web/API/auth o integrazioni esterne.
