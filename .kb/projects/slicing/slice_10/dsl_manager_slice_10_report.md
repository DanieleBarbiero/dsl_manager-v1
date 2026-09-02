# Report Slice 10

Implementata la Slice 10 end-to-end nello scope richiesto: normalizzazione documentale tramite Docling dietro adapter/worker, con profilo v1 no-images e senza introdurre chunking stabile.

## Aggiunto

- Dipendenza runtime riproducibile `docling==2.97.0`, compatibile con Python `>=3.12,<3.13`.
- Profilo default `configs/workers/docling.no_images.yaml` generato da `dsl-manager init`.
- Loader profilo worker minimale basato sul parser YAML standard library gia' presente, senza PyYAML.
- Adapter isolato `dsl_mngr.core.docling_adapter` con whitelist di opzioni applicative Docling, traduzione no-images e fallimento `unsupported_docling_option`.
- Worker subprocess `dsl_mngr.workers.normalize_docling`, invocato via `worker_runner.run_worker`.
- Comando CLI `dsl-manager corpus normalize <workspace> --revision REV_000001`, compatibile anche via `python -m dsl_mngr corpus normalize ...`.
- Output normalizzati sotto `normalized/<source_id>/<source_revision_id>/`: `normalized.md`, `normalized.json`, `source_hash.txt`, `docling_report.json`.
- Aggiornamento transazionale di `source_revisions.normalized_hash` solo dopo worker completato e output validato.
- Run `normalize`, `worker_runs` `normalize_docling`, artifact Slice 4 coerenti e log applicativo di completamento/fallimento.
- Test deterministici `test_docling_normalization_no_images` e `test_docling_unsupported_option`.

## Diff/status

```text
 M pyproject.toml
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/cli/commands/corpus.py
 M src/dsl_mngr/core/config.py
 M src/dsl_mngr/core/worker_runner.py
 M src/dsl_mngr/core/workspace.py
?? .kb/projects/slicing/slice_10/dsl_manager_slice_10_report.md
?? src/dsl_mngr/core/docling_adapter.py
?? src/dsl_mngr/workers/
?? tests/test_slice_10_docling_normalization.py
```

Nota: `.kb/` e' ignorata da `.gitignore`; il report e' stato salvato in `.kb/projects/slicing/slice_10/dsl_manager_slice_10_report.md` ma non compare nello status Git standard.

Diff stat sui file tracciati gia' presenti:

```text
pyproject.toml                      |   6 +-
src/dsl_mngr/cli/app.py             |  21 ++-
src/dsl_mngr/cli/commands/corpus.py | 299 +++++++++++++++++++++++++++++++++++-
src/dsl_mngr/core/config.py         |  33 ++++
src/dsl_mngr/core/worker_runner.py  |   4 +-
src/dsl_mngr/core/workspace.py      |  22 +++
6 files changed, 380 insertions(+), 5 deletions(-)
```

Nuovi file principali:

```text
src/dsl_mngr/core/docling_adapter.py
src/dsl_mngr/workers/__init__.py
src/dsl_mngr/workers/normalize_docling.py
tests/test_slice_10_docling_normalization.py
```

## Test

Interprete usato: `.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 10:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_10_docling_normalization.py
```

Risultato:

```text
2 passed in 176.27s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
45 passed in 81.05s
```

## Verifiche aggiuntive

- `test_docling_normalization_no_images` verifica profilo default, `corpus scan`, `corpus normalize`, output Markdown/JSON/report/hash, no file immagine sotto `normalized/` e `artifacts/runs/`, hash stabile su riesecuzione e compatibilita' `python -m dsl_mngr`.
- `test_docling_unsupported_option` verifica profilo con chiave non supportata, worker exit code `4`, run/worker falliti, report con `unsupported_docling_option` e nessuna mutazione di `source_revisions.normalized_hash`.
- `git diff --check` non segnala errori whitespace; sono presenti solo warning Git sulla futura normalizzazione CRLF dei file modificati.

## Fuori scope / note

- Non e' stato implementato chunking stabile.
- Non sono stati inseriti record in `chunks` o `source_fragments`.
- Non sono stati modificati candidate validation, merge, renderer DSL o diff.
- Non sono stati aggiunti parser DDL/XML/SQL/log, AI handoff, batch orchestration, GEXF, UI, web/API/auth, ORM o integrazioni esterne.
- Docling viene importato e invocato solo dietro adapter/worker dedicati; la pipeline standard non genera immagini, non abilita OCR e non abilita VLM/picture description.
