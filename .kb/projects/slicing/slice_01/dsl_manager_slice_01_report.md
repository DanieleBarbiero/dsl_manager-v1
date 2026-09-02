Implementata la Slice 1, restando dentro lo scope richiesto.

**Aggiunto**
- CLI `dsl-manager` via entry point in [pyproject.toml](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/pyproject.toml>)
- Compatibilità `python -m dsl_mngr init <workspace>`
- Workspace init in [workspace.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/workspace.py>)
- Loader config minimale con precedenza default `< project.yaml < .env < CLI` in [config.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/config.py>)
- Logging JSONL e renderer table/CSV in [logging_setup.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/logging_setup.py>)
- Comandi:
  - `dsl-manager init [workspace]`
  - `dsl-manager log table [workspace]`
  - `dsl-manager log table [workspace] --format csv --output logs.csv`

**Diff / status**
```text
M  pyproject.toml
M  src/dsl_mngr/__main__.py
M  src/dsl_mngr/main.py
M  tests/test_smoke.py
?? src/dsl_mngr/cli/
?? src/dsl_mngr/core/
?? tests/test_slice_01_workspace_config_logging.py
```

`git diff --stat` sui file tracciati:
```text
pyproject.toml           |  5 ++++-
src/dsl_mngr/__main__.py |  8 ++++----
src/dsl_mngr/main.py     | 13 ++++++++++++-
tests/test_smoke.py      |  2 +-
```

**Test**
Eseguiti con l’interprete richiesto da `.codex/config.toml`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:
```text
6 passed in 1.76s
```

Ho anche reinstallato prima dei test con:
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Nessuna dipendenza runtime aggiunta: YAML e `.env` sono gestiti con parser minimale standard library. Volutamente fuori scope: SQLite, migrazioni, registry, source scan, parser, AI handoff, renderer DSL, diff, web UI/API/auth/integrazioni.