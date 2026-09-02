# Report Slice 15

Implementata la Slice 15 nello scope richiesto: handoff AI black-box con package deterministico in `ai/outbox`, scan/import da `ai/inbox`, stale detection prima dell'import e riuso della pipeline esistente di candidate validation/persistence.

## Aggiunto

- Comandi CLI `dsl-manager ai package <workspace>`, `dsl-manager ai inbox scan <workspace>` e `dsl-manager ai import <workspace> --package AIPKG_000001`, compatibili anche via `python -m dsl_mngr`.
- Profilo default `configs/workers/ai_package.default.yaml` generato da `dsl-manager init`.
- Migration v5 append-only con tabella `ai_packages` e status `waiting_for_ai_candidates`, `stale`, `imported`.
- Core `dsl_mngr.core.ai_package` per raccolta evidenze attive dal registry, schema/template JSONL, validazione outbox, persistenza package e stale detection.
- Core `dsl_mngr.core.ai_inbox` per scan inbox e import candidati con stale gate.
- Worker isolato `dsl_mngr.workers.build_ai_package`, senza accesso al database principale e senza provider AI.
- Package outbox con i sei file richiesti: `instructions.md`, `content.md`, `source_manifest.json`, `candidate_schema.json`, `output_template.jsonl`, `package_manifest.json`.
- Test deterministici `test_build_ai_package`, `test_ai_package_stale`, `test_import_batch`.

## Diff/status

```text
 M desktop.ini
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/core/migrations.py
 M src/dsl_mngr/core/workspace.py
?? src/dsl_mngr/cli/commands/ai.py
?? src/dsl_mngr/core/ai_inbox.py
?? src/dsl_mngr/core/ai_package.py
?? src/dsl_mngr/workers/build_ai_package.py
?? tests/test_slice_15_ai_package.py
```

Nota: `desktop.ini` risultava gia' modificato prima della Slice 15 ed e' rimasto fuori dal perimetro.

Diff stat sintetico:

```text
src/dsl_mngr/cli/app.py                 +68
src/dsl_mngr/core/migrations.py         +36
src/dsl_mngr/core/workspace.py          +17
src/dsl_mngr/cli/commands/ai.py         304 lines
src/dsl_mngr/core/ai_package.py         1156 lines
src/dsl_mngr/core/ai_inbox.py           275 lines
src/dsl_mngr/workers/build_ai_package.py 228 lines
tests/test_slice_15_ai_package.py        497 lines
```

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 15:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_15_ai_package.py
```

Risultato:

```text
3 passed in 13.95s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato finale:

```text
62 passed in 177.96s (0:02:57)
```

La prima esecuzione della suite completa e' stata interrotta dal timeout del comando dopo circa 304s senza un risultato pytest finale; e' stata rilanciata con timeout piu' ampio ed e' passata.

## Verifiche aggiuntive

- `git diff --check` non segnala errori whitespace; mostra solo warning Git sulla futura normalizzazione CRLF di file tracciati.
- `ai package` crea `AIPKG_000001` e il rerun crea `AIPKG_000002`, senza sovrascrivere audit storici.
- `package_manifest.json` e `source_manifest.json` usano path relativi al workspace con `/`.
- `candidate_schema.json` resta coerente con `candidate_validation` e non introduce validazione runtime via `jsonschema`.
- `output_template.jsonl` e' JSONL leggibile e i record template sono validabili contro le evidenze fixture.
- Il worker fallisce con exit code `4` su opzione non supportata e non crea record `ai_packages`.
- Stale detection blocca `ai import` di default senza creare `candidate_batches`, aggiorna il package a `stale` e consente import solo con `--allow-stale`.
- `ai import` crea `candidate_batches`, `candidate_records` e `rejected_candidates` tramite `import_candidate_file`; non esegue `facts merge`.

## Fuori scope / note

- Nessun provider AI, chiamata HTTP, euristica di generazione candidati o integrazione esterna e' stata aggiunta.
- Nessun ORM e nessuna dipendenza runtime nuova.
- Nessuna modifica al significato pubblico di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`.
- `package_hash` e' calcolato sui file payload del package elencati in `package_manifest.files`; il manifest stesso e' escluso dal calcolo per evitare self-reference.
