# Report Slice 12

Implementata la Slice 12 end-to-end nello scope richiesto: parser DDL deterministico dietro worker, artifact `fragments.jsonl`/`ddl_report.json`, persistenza idempotente in `source_fragments` ed evidence lookup tramite `fragment_id`.

## Aggiunto

- Comando CLI `dsl-manager corpus parse-ddl <workspace> --revision REV_000001`, compatibile anche via `python -m dsl_mngr corpus parse-ddl ...`.
- Profilo default `configs/workers/ddl.default.yaml` generato da `dsl-manager init` e directory workspace `fragments/`.
- Core `dsl_mngr.core.ddl_parser` per `CREATE TABLE`, colonne, primary key, foreign key, unique e `CREATE INDEX` minimale, con commenti SQL ignorati preservando offset.
- Core `dsl_mngr.core.fragment_registry` per riuso `FRAG_*` per sequence, upsert idempotente, stale degli extra e JSON metadata canonico.
- Worker isolato `dsl_mngr.workers.parse_ddl`, invocato via `worker_runner.run_worker`, senza scritture dirette sul database principale.
- Run type `parse_ddl`, artifact Slice 4 coerenti, classificazione `unknown -> ddl/mixed_ddl/technical_structure` solo quando la source era sconosciuta.
- Fixture DDL dedicata sotto `tests/fixtures/ddl/` e test Slice 12 per tabelle, foreign key, evidence lookup, rerun idempotente e opzione non supportata.

## Diff/status

```text
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/cli/commands/corpus.py
 M src/dsl_mngr/core/runs.py
 M src/dsl_mngr/core/workspace.py
?? src/dsl_mngr/core/ddl_parser.py
?? src/dsl_mngr/core/fragment_registry.py
?? src/dsl_mngr/workers/parse_ddl.py
?? tests/fixtures/ddl/
?? tests/test_slice_12_parse_ddl.py
```

Diff stat sui file tracciati gia' presenti:

```text
src/dsl_mngr/cli/app.py             |  20 +++
src/dsl_mngr/cli/commands/corpus.py | 344 +++++++++++++++++++++++++++++++++++-
src/dsl_mngr/core/runs.py           |   1 +
src/dsl_mngr/core/workspace.py      |  20 +++
4 files changed, 384 insertions(+), 1 deletion(-)
```

Nuovi file principali:

```text
src/dsl_mngr/core/ddl_parser.py
src/dsl_mngr/core/fragment_registry.py
src/dsl_mngr/workers/parse_ddl.py
tests/fixtures/ddl/schema_ordini.sql
tests/test_slice_12_parse_ddl.py
```

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita prima degli edit:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 12:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_12_parse_ddl.py
```

Risultato:

```text
5 passed in 5.13s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
53 passed in 130.59s (0:02:10)
```

## Verifiche aggiuntive

- `git diff --check` non segnala errori whitespace; restano solo warning Git sulla futura normalizzazione CRLF dei file modificati.
- `fragments_hash` coincide con SHA-256 del contenuto canonico di `fragments.jsonl` e resta stabile su rerun.
- Rerun della stessa revision riusa gli stessi `fragment_id` e non crea duplicati attivi.
- `source_fragments` contiene `ddl_table`, `ddl_column` e `ddl_constraint` con `metadata_json` canonico.
- Evidence lookup con `fragment_id` accetta un candidato `candidate_relation` senza `chunk_id`.
- Il failure su opzione non supportata usa exit code worker `4`, run/worker `failed` e non crea frammenti attivi.

## Fuori scope / note

- Nessuna migration schema aggiunta: lo schema Slice 5 e' sufficiente.
- Nessun inserimento diretto in `facts` e nessun candidate record sintetico.
- Non sono stati modificati i contratti pubblici di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`.
- Nessun parser XML form, SQL code/procedure/trigger, log, AI handoff, batch orchestration, GEXF, UI, web/API/auth, ORM o integrazione esterna.
