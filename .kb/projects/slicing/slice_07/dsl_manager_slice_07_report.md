Implementata la Slice 7 end-to-end.

Ho aggiunto:
- migration v4 `dsl_snapshots` in [migrations.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/migrations.py>)
- renderer deterministico JSON/YAML/Markdown in [dsl_renderer.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/dsl_renderer.py>)
- comando `dsl-manager dsl render <workspace>` in [dsl.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/cli/commands/dsl.py>)
- wiring CLI in [app.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/cli/app.py>)
- test Slice 7 in [test_slice_07_dsl_render.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/tests/test_slice_07_dsl_render.py>)

Diff/status:
```text
 M src/dsl_mngr/cli/app.py                 +17
 M src/dsl_mngr/core/migrations.py         +33
 A src/dsl_mngr/cli/commands/dsl.py        146 lines
 A src/dsl_mngr/core/dsl_renderer.py       806 lines
 A tests/test_slice_07_dsl_render.py         405 lines
```

Install editable eseguita con l’interprete richiesto da `.codex/config.toml`:
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test eseguiti con lo stesso interprete:
```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_07_dsl_render.py
# 3 passed

.\.venv\Scripts\python.exe -m pytest
# 37 passed in 24.62s
```

Ho anche verificato `git diff --check`: nessun errore whitespace, solo warning Git sulla futura normalizzazione CRLF dei due file tracciati modificati.