Implementata solo la Slice 5.

Aggiunto:
- migration v2 in [migrations.py](</c:/Users/dbarbiero/OneDrive - Engineering Ingegneria Informatica S.p.A/Projects/dsl_manager-v1/src/dsl_mngr/core/migrations.py>) con `chunks`, `source_fragments`, `candidate_batches`, `candidate_records`, `rejected_candidates`;
- core separato:
  - `candidate_validation.py` per schema/evidence validation;
  - `candidate_import.py` per import JSONL e persistence;
- CLI `dsl-manager candidates validate <workspace> --input <path>`;
- compatibilita testata via `python -m dsl_mngr candidates validate ...`;
- fixture JSONL sotto `tests/fixtures/candidates/`;
- test Slice 5 richiesti.

**Diff**
```text
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/core/migrations.py
?? src/dsl_mngr/cli/commands/candidates.py
?? src/dsl_mngr/core/candidate_import.py
?? src/dsl_mngr/core/candidate_validation.py
?? tests/fixtures/candidates/
?? tests/test_slice_05_candidate_validation.py
```

Tracked diff stat:
```text
src/dsl_mngr/cli/app.py         |  22 ++++++++
src/dsl_mngr/core/migrations.py | 118 ++++++++++++++++++++++++++++++++++++++++
2 files changed, 140 insertions(+)
```

**Test**
Interprete usato, come da `.codex/config.toml`:
```powershell
.\.venv\Scripts\python.exe
```

Install editable eseguita:
```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Suite completa:
```text
31 passed in 7.52s
```

Nessuna dipendenza runtime nuova, nessun ORM, nessun merge/render/AI/parser/chunker aggiunto.