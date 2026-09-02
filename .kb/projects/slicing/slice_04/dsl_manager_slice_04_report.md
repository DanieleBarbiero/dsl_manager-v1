Implementata la Slice 4 end-to-end.

**Diff finale compatto**
```text
M  src/dsl_mngr/cli/app.py                         +34
A  src/dsl_mngr/cli/commands/run.py                59 lines
A  src/dsl_mngr/core/runs.py                       482 lines
A  src/dsl_mngr/core/worker_runner.py              475 lines
A  tests/test_slice_04_runs_worker_runner.py         274 lines
A  tests/fixtures/workers/failure_worker.py        13 lines
A  tests/fixtures/workers/invalid_output_worker.py 23 lines
A  tests/fixtures/workers/success_worker.py        28 lines
```

Aggiunto:
- lifecycle run con `RUN_000001` sequenziale, `running/completed/failed`, parent validation
- artifact per run: `input.json`, `output.json`, `process_report.json`, `resolved_config.yaml`, `config_hash.txt`, `log.jsonl`
- worker runner isolato via `sys.executable`, con `worker_runs`, report, stdout/stderr, exit code e rollback su output invalido o mutazioni fallite
- CLI `dsl-manager run start [workspace] --type test` e `dsl-manager run status [workspace] RUN_000001`
- compatibilità `python -m dsl_mngr run ...`
- test deterministici Slice 4 con fixture worker sotto `tests/fixtures/workers`

**Test**
Eseguiti con l’interprete configurato in `.codex/config.toml`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
27 passed in 6.43s
```

Interprete usato: `.venv\Scripts\python.exe` / Python 3.12.10.

Volutamente fuori scope: nessuna migrazione nuova, nessun worker reale Docling/parser/AI, nessun collegamento tra `corpus scan` e run lifecycle, nessun ORM e nessuna dipendenza runtime aggiunta.