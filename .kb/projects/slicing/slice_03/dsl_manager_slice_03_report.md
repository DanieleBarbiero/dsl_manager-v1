Implementata la Slice 3 end-to-end.

Aggiunto:
- `dsl-manager corpus scan <workspace>` con `--path` / `--corpus-dir`
- hash SHA-256 sui byte originali dei file
- registry SQLite per `sources`, `source_revisions`, `source_events`
- rilevazione `added`, `modified`, `deleted`, `unchanged`
- path relativi al workspace normalizzati con `/`
- blocco path traversal fuori workspace
- test deterministici con `tmp_path`

Nessuna migration nuova: lo schema Slice 2 aveva già le tabelle necessarie.

**Diff Finale**
```text
 M src/dsl_mngr/cli/app.py
 A src/dsl_mngr/cli/commands/corpus.py
 A src/dsl_mngr/core/hashing.py
 A src/dsl_mngr/core/source_registry.py
 A tests/test_slice_03_corpus_scan_source_registry.py
```

`src/dsl_mngr/cli/app.py` aggiunge il comando `corpus scan`. I nuovi file contengono CLI, hashing, logica core/persistenza e test Slice 3.

**Test**
Eseguiti con l’interprete configurato in `.codex/config.toml`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
21 passed in 10.68s
```

Interprete usato: `.venv\Scripts\python.exe` / Python 3.12.10.