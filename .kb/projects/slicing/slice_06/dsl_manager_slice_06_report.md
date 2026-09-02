Implementata la Slice 6 end-to-end.

Ho aggiunto:
- migration v3 in [migrations.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/migrations.py>) con `facts`, `fact_evidence`, `relations`, `relation_evidence`, `conflicts`;
- core deterministico/transazionale in [merge.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/merge.py>);
- comando CLI `facts merge` in [facts.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/cli/commands/facts.py>) e wiring in [app.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/cli/app.py>);
- test Slice 6 in [test_slice_06_fact_merge.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/tests/test_slice_06_fact_merge.py>).

Diff/status:
```text
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/core/migrations.py
?? src/dsl_mngr/cli/commands/facts.py
?? src/dsl_mngr/core/merge.py
?? tests/test_slice_06_fact_merge.py
```

Diff stat tracciato:
```text
src/dsl_mngr/cli/app.py         |  19 ++++++
src/dsl_mngr/core/migrations.py | 130 ++++++++++++++++++++++++++++++++++++++++
```

Nuovi file:
```text
src/dsl_mngr/core/merge.py                 | 778 insertions
src/dsl_mngr/cli/commands/facts.py         | 150 insertions
tests/test_slice_06_fact_merge.py            | 475 insertions
```

Comandi eseguiti con l’interprete richiesto da `.codex/config.toml`:
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

Risultato finale:
```text
34 passed in 6.26s
```

Inclusa verifica `python -m dsl_mngr facts merge ...` nei test, più idempotenza su facts/evidence, relations/evidence e conflicts.