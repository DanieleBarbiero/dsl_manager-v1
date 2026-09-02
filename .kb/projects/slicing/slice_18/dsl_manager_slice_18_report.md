# Report Slice 18

Implementata la Slice 18 nello scope richiesto: log viewer statico HTML/CSV, mantenendo compatibile il comando legacy `log table`.

## Aggiunto

- Core `dsl_mngr.core.log_viewer` per risolvere input workspace o JSONL, ordinare i record per timestamp, renderizzare tabella testuale, CSV deterministico e HTML statico.
- Comando `dsl-manager log table <workspace-or-jsonl> --format table|html|csv`, con inferenza HTML quando `--format` non e' indicato e `--output` termina con `.html`.
- Comando esplicito `dsl-manager log csv <workspace-or-jsonl> --output <file.csv>`.
- Lettura log da `logs/app.jsonl` e da `artifacts/runs/<run_id>/log.jsonl`.
- HTML UTF-8 senza asset esterni, con filtro client-side, escaping HTML, stile minimo per `level` e link relativi agli artifact esistenti del `run_id`.
- Creazione automatica delle directory di output.
- Gestione JSONL invalido con errore leggibile e return code non zero.
- Test Slice 18 in `tests/test_slice_18_log_viewer.py`.

## Diff/status

```text
M  src/dsl_mngr/cli/app.py
M  src/dsl_mngr/cli/commands/log.py
A  src/dsl_mngr/core/log_viewer.py
A  tests/test_slice_18_log_viewer.py
A  .kb/projects/slicing/slice_18/dsl_manager_slice_18_report.md
```

Diff stat tracciato prima del report:

```text
src/dsl_mngr/cli/app.py          | 26 +++++++++++++-----
src/dsl_mngr/cli/commands/log.py | 59 ++++++++++++++++++++++++++++++++++------
```

Nuovi file principali:

```text
src/dsl_mngr/core/log_viewer.py
tests/test_slice_18_log_viewer.py
```

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 18:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_18_log_viewer.py
```

Risultato:

```text
2 passed in 1.70s
```

Regression mirata Slice 1 logging:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_01_workspace_config_logging.py
```

Risultato:

```text
5 passed in 1.59s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
70 passed in 197.31s (0:03:17)
```

## Verifiche aggiuntive

- Entry point modulo verificato:

```powershell
.\.venv\Scripts\python.exe -m dsl_mngr --help
```

Risultato: exit code `0`, help CLI mostrato.

- `git diff --check` non segnala errori whitespace; mostra solo warning Git sulla futura normalizzazione CRLF dei file modificati.
- Il timeout storico Docling citato nel report Slice 17 non si e' riprodotto: `tests/test_slice_10_docling_normalization.py` e' passato nella suite completa.

## Controllo anti-drifting

- Nessuna nuova dipendenza runtime, ORM, database server, API web, autenticazione, mini-server o UI locale aggiunta.
- Nessuna migration schema introdotta per la Slice 18.
- Non e' stato modificato il significato pubblico di scan, parser, AI package, batch, merge, render DSL, diff o GEXF.
- La base logging Slice 1 resta compatibile: `log table <workspace>` stampa ancora una tabella testuale e `log table <workspace> --format csv --output <file>` continua a funzionare con il CSV legacy.
- La Slice 19 (`log serve` / UI locale) resta fuori scope.
- Nessuna deviazione nuova rilevata rispetto alla sequenza concordata delle slice 0-18.

## Fuori scope / note

- Non e' stato aggiunto `dsl-manager log serve`.
- Non e' stata introdotta una UI complessa o una pagina servita via rete.
- Il parser di log sorgente della Slice 14 non e' stato modificato.
