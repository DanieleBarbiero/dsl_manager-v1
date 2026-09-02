# Report Slice 19

Implementata la Slice 19 nello scope richiesto: UI locale opzionale read-only sopra registry, run, log, rejected candidates, conflitti, snapshot e diff gia' prodotti, senza spostare logica applicativa nella UI.

## Aggiunto

- Comando CLI `dsl-manager ui serve <workspace>` con default `127.0.0.1:8765`, supporto `--host`, `--port` e stampa dell'URL con porta effettiva quando si usa `--port 0`.
- Core `dsl_mngr.core.local_ui` basato solo su standard library: `ThreadingHTTPServer`, `BaseHTTPRequestHandler`, routing testabile tramite `resolve_local_ui_request`, rendering HTML inline e query SQLite read-only.
- Viste HTML UTF-8:
  - `/` dashboard workspace;
  - `/runs` e `/runs/<run_id>`;
  - `/logs` e `/logs?run_id=RUN_000001`;
  - `/rejected-candidates`;
  - `/conflicts`;
  - `/snapshots`;
  - `/diff` e `/diff?from=DSL_000001&to=DSL_000002`.
- Protezioni read-only: nessuna API mutativa, metodi diversi da `GET`/`HEAD` con `405`, route sconosciute con `404`, apertura database in modalita' read-only, path controllati sotto workspace e nessun file serving arbitrario.
- Escaping HTML sistematico per contenuti da database, log, JSON e path.
- Test deterministici in `tests/test_slice_19_local_ui.py`, inclusi smoke route, escaping, fingerprint DB prima/dopo, 404/405, errore CLI leggibile e smoke `python -m dsl_mngr ui serve ... --port 0` senza lasciare server appesi.

## Diff/status

```text
 M src/dsl_mngr/cli/app.py
?? src/dsl_mngr/cli/commands/ui.py
?? src/dsl_mngr/core/local_ui.py
?? tests/test_slice_19_local_ui.py
?? .kb/projects/slicing/slice_19/dsl_manager_slice_19_report.md
```

Diff stat tracciato:

```text
src/dsl_mngr/cli/app.py | 24 ++++++++++++++++++++++++
```

Nuovi file principali:

```text
src/dsl_mngr/core/local_ui.py          868 lines
src/dsl_mngr/cli/commands/ui.py        24 lines
tests/test_slice_19_local_ui.py        678 lines
```

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita prima degli edit:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 19:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_19_local_ui.py
```

Risultato:

```text
3 passed in 21.31s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
73 passed in 559.30s (0:09:19)
```

## Verifiche aggiuntive

- `git diff --check` non segnala errori whitespace; resta solo il warning Git sulla futura normalizzazione CRLF di `src/dsl_mngr/cli/app.py`.
- Il test subprocess verifica `python -m dsl_mngr ui serve <workspace> --host 127.0.0.1 --port 0`, legge l'URL stampato, apre `/` e termina il processo.
- La route `/diff?from=...&to=...` legge solo artifact esistenti in `exports/dsl_diff`; se il JSON non esiste mostra un messaggio che invita a eseguire `dsl-manager dsl diff`, senza generare nulla.

## Controllo anti-drifting

- Le slice 1-18 risultano allineate al design v2: registry-first, worker isolati, run/artifact, validation/merge/render/diff/export/log viewer separati e test deterministici.
- La Slice 19 resta v1.1 opzionale e minimale: nessun framework web, template engine, ORM, migration, dipendenza runtime, login/auth, API mutativa, provider AI o servizio esterno.
- La UI non rilancia parser, merge, render DSL, diff, graph export, batch o AI handoff; consulta solo database, log e artifact esistenti.
- Il comando `log table` e `log csv` resta compatibile: non e' stata modificata la Slice 18.

## Fuori scope / note

- Non e' stata implementata una web app enterprise, una UI multiutente o una ricerca full-text/vector.
- Non viene servito alcun asset esterno o file arbitrario fuori dal workspace.
- Non sono state aggiunte nuove migrazioni perche' le tabelle esistenti sono sufficienti per le viste richieste.
