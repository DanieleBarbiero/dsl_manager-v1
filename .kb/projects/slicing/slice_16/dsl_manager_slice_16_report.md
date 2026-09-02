# Report Slice 16

Implementata la Slice 16 nello scope richiesto: batch orchestration locale con run padre `batch`, sub-run tracciabili, report deterministico e continuita' sugli errori configurabile.

## Aggiunto

- Core `dsl_mngr.core.batch` per pianificazione ed esecuzione batch di `process-dir`, `chunk-dir`, `package-batch`, `validate-batch` e `merge-batch`.
- Comandi CLI:
  - `dsl-manager batch process-dir <workspace> [--path corpus/active] [--stop-on-error]`
  - `dsl-manager batch chunk-dir <workspace> [--revision REV_000001]... [--profile docling.chunking] [--stop-on-error]`
  - `dsl-manager ai package-batch <workspace> [--revision REV_000001]... [--profile ai_package.default] [--stop-on-error]`
  - `dsl-manager candidates validate-batch <workspace> [--input-dir ai/inbox] [--pattern *.jsonl] [--stop-on-error]`
  - `dsl-manager facts merge-batch <workspace> [--batch CBATCH_000001]... [--stop-on-error]`
- Parent run `batch` con `input.json`, `output.json`, `process_report.json`, `batch_report.json`, log per-run e summary CLI comune.
- Sub-run con `parent_run_id` valorizzato per normalize/chunk/parser/AI package/candidate validation/merge.
- Parametro opzionale `parent_run_id=None` aggiunto alle funzioni di orchestrazione esistenti senza cambiare i comandi singoli.
- Report batch canonico con item ordinati, path relativi al workspace, errori sintetici, `completed/failed/skipped` e supporto `--stop-on-error`.
- Test Slice 16 in `tests/test_slice_16_batch_orchestration.py`, senza Docling nei casi batch principali e senza chiamate AI/rete.

## Diff/status

```text
M  src/dsl_mngr/cli/app.py
M  src/dsl_mngr/cli/commands/ai.py
M  src/dsl_mngr/cli/commands/candidates.py
M  src/dsl_mngr/cli/commands/corpus.py
M  src/dsl_mngr/cli/commands/facts.py
A  src/dsl_mngr/cli/commands/batch.py
A  src/dsl_mngr/core/batch.py
A  tests/test_slice_16_batch_orchestration.py
A  .kb/projects/slicing/slice_16/dsl_manager_slice_16_report.md
```

Diff stat sintetico dei file tracciati gia' esistenti:

```text
src/dsl_mngr/cli/app.py                 | 108 ++++++++++++++++++++++++++++++++
src/dsl_mngr/cli/commands/ai.py         |  33 ++++++++++
src/dsl_mngr/cli/commands/candidates.py |  68 +++++++++++++++-----
src/dsl_mngr/cli/commands/corpus.py     |  12 ++++
src/dsl_mngr/cli/commands/facts.py      |  75 ++++++++++++++++------
```

Nuovi file principali:

```text
src/dsl_mngr/core/batch.py
src/dsl_mngr/cli/commands/batch.py
tests/test_slice_16_batch_orchestration.py
```

## Test

Interprete usato: `.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 16:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_16_batch_orchestration.py
```

Risultato:

```text
4 passed in 11.14s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
66 passed in 249.36s (0:04:09)
```

## Verifiche aggiuntive

- `git diff --check` non segnala errori whitespace; mostra solo warning Git sulla futura normalizzazione LF/CRLF dei file modificati.
- Verificata compatibilita' `python -m dsl_mngr batch process-dir ...` nei test.
- Verificati parent run `batch`, sub-run con `parent_run_id`, `batch_report.json`, `process_report.json`, output CLI comune e blocco `Failed items`.
- Verificato comportamento default continue-on-error e `--stop-on-error`.
- Verificato che `candidates validate-batch` non esegue merge automatico.
- Verificato che `facts merge-batch` non renderizza DSL automaticamente.

## Fuori scope / note

- Nessuna migration aggiunta: la run padre e gli artifact sono sufficienti per l'audit della slice.
- Nessun provider AI, chiamata HTTP, generazione candidati euristica, GEXF, UI, web/API/auth o ORM aggiunto.
- Nessuna modifica al significato pubblico dei comandi singoli di scan, normalize, chunk, parser, AI package, candidate validation, merge, render o diff.
