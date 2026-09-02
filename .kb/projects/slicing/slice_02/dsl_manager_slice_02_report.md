Implementata solo la Slice 2.

**Diff**
```text
M  src/dsl_mngr/cli/app.py                         +12
A  src/dsl_mngr/cli/commands/db.py                 +51
A  src/dsl_mngr/core/database.py                   +101
A  src/dsl_mngr/core/migrations.py                 +257
A  tests/test_slice_02_database_migrations.py        +150
```

Aggiunto:
- layer SQLite minimale con `sqlite3`, `PRAGMA foreign_keys = ON`, WAL configurabile e path DB risolto da config Slice 1
- migrazioni versionate/idempotenti con `schema_migrations(version, name, checksum, applied_at)`
- schema minimo: `sources`, `source_revisions`, `source_events`, `runs`, `worker_runs`
- comando `dsl-manager db init [workspace]` e compatibilità `python -m dsl_mngr db init [workspace]`
- log JSONL su `logs/app.jsonl`
- errore leggibile se il workspace non è stato inizializzato

**Test**
Ho usato l’interprete richiesto da `.codex/config.toml`:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
14 passed in 6.57s
```

Verificato anche l’entry point:

```powershell
.\.venv\Scripts\dsl-manager.exe db init <workspace>
```

Output verificato: database path, `Migrations applied: 1`, `Migrations skipped: 0`.

Volutamente fuori scope: corpus scan, registry applicativo, import candidati, merge, renderer DSL, diff, Docling/parser/AI handoff e worker runner completo. Nessuna dipendenza runtime o ORM aggiunta.