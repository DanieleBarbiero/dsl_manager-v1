Implementata la Slice 8 end-to-end.

Ho aggiunto il core diff deterministico in [dsl_diff.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/dsl_diff.py>) e collegato il comando `dsl diff` in [dsl.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/cli/commands/dsl.py>) / [app.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/cli/app.py>). Aggiunti i test Slice 8 in [test_slice_08_dsl_diff.py](<c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/tests/test_slice_08_dsl_diff.py>).

**Diff**
```text
 M src/dsl_mngr/cli/app.py          +27
 M src/dsl_mngr/cli/commands/dsl.py +110
?? src/dsl_mngr/core/dsl_diff.py    932 lines
?? tests/test_slice_08_dsl_diff.py    492 lines
```

**Coperto**
```text
dsl-manager dsl diff <workspace> --from DSL_000001 --to DSL_000002
python -m dsl_mngr dsl diff <workspace> --from DSL_000001 --to DSL_000002
```

Il diff legge solo `dsl_snapshots.content_json` per il contenuto, valida mismatch `metadata.dsl_hash` vs tabella, produce JSON/Markdown sotto `exports/dsl_diff`, crea run `dsl_diff`, aggiorna artifact Slice 4 e fallisce con `missing_traceability` se una change non ha cause.

**Comandi eseguiti**
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests\test_slice_08_dsl_diff.py
# 4 passed

.\.venv\Scripts\python.exe -m pytest
# 41 passed in 19.45s
```

Interprete usato: `.\.venv\Scripts\python.exe` / Python 3.12.10.

`git diff --check` non segnala errori whitespace; solo warning Git sulla futura normalizzazione CRLF dei due file tracciati modificati.