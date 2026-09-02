# Report Slice 11

Implementata la Slice 11 end-to-end nello scope richiesto: chunking stabile dagli output normalizzati della Slice 10, persistenza idempotente in `chunks`, artifact canonici `chunks.jsonl`/`chunk_report.json` ed evidence lookup per `candidates validate`.

## Aggiunto

- Comando CLI `dsl-manager corpus chunk <workspace> --revision REV_000001`, compatibile anche via `python -m dsl_mngr corpus chunk ...`.
- Profilo default `configs/workers/docling.chunking.yaml` generato da `dsl-manager init`.
- Core deterministico `dsl_mngr.core.chunking` con strategia fallback `heading_paragraph`, hash testo, offsets e serializzazione JSONL canonica.
- Persistenza separata `dsl_mngr.core.chunk_registry` con riuso `chunk_id` per sequence, upsert idempotente e marcatura `stale` dei chunk attivi in eccesso.
- Worker isolato `dsl_mngr.workers.chunk_docling`, invocato via `worker_runner.run_worker`, senza accesso al database principale.
- Validazioni su workspace, database migrato, revisione esistente, `normalized_hash`, `normalized.md`, `normalized.json`, `source_hash.txt`, path relativi e hash coerenti.
- Test Slice 11: `test_chunking_stable`, `test_chunk_evidence_lookup` e copertura aggiuntiva unsupported option con worker exit code `4`.

## Diff/status

```text
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/cli/commands/corpus.py
 M src/dsl_mngr/core/config.py
 M src/dsl_mngr/core/workspace.py
?? src/dsl_mngr/core/chunk_registry.py
?? src/dsl_mngr/core/chunking.py
?? src/dsl_mngr/workers/chunk_docling.py
?? tests/test_slice_11_chunking.py
```

Diff stat sui file tracciati gia' presenti:

```text
src/dsl_mngr/cli/app.py             |  25 ++-
src/dsl_mngr/cli/commands/corpus.py | 382 +++++++++++++++++++++++++++++++++++-
src/dsl_mngr/core/config.py         |  14 +-
src/dsl_mngr/core/workspace.py      |  20 ++
4 files changed, 434 insertions(+), 7 deletions(-)
```

Nuovi file principali:

```text
src/dsl_mngr/core/chunk_registry.py
src/dsl_mngr/core/chunking.py
src/dsl_mngr/workers/chunk_docling.py
tests/test_slice_11_chunking.py
```

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita prima degli edit:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 11:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_11_chunking.py
```

Risultato:

```text
3 passed in 5.58s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
48 passed in 122.23s (0:02:02)
```

## Verifiche aggiuntive

- `git diff --check` non segnala errori whitespace; restano solo warning Git sulla futura normalizzazione CRLF dei file modificati.
- Rerun della stessa revision mantiene `chunks_hash` e riusa lo stesso `chunk_id`.
- `candidates validate` accetta gli 8 record fixture perche' gli `evidence_text` sono presenti nei chunk prodotti dal chunker reale.
- Il caso unsupported option fallisce con `worker_runs.exit_code = 4`, `worker_runs.status = failed`, `runs.status = failed` e senza chunk attivi.

## Fuori scope / note

- Non e' stato usato `HybridChunker` come default: per evitare download runtime, tokenizer remoti o flakiness nei test, la slice usa il fallback deterministico `heading_paragraph` su `normalized.md`.
- Nessuna nuova dipendenza runtime, nessun ORM e nessuna migrazione schema aggiunta.
- Non sono stati implementati parser DDL/XML/SQL/log, AI package handoff, batch orchestration, export GEXF, UI, web/API/auth o integrazioni esterne.
