# Report Slice 17

Implementata la Slice 17 nello scope richiesto: export GEXF deterministico da snapshot DSL persistito, senza leggere il registry live e senza rilanciare render, merge, parser, batch o AI handoff.

## Aggiunto

- Core `dsl_mngr.core.graph_export` con validazione snapshot, build grafo diretto, writer GEXF basato su `xml.etree.ElementTree`, report JSON canonico e hash stabile.
- Comando CLI `dsl-manager graph export <workspace> --snapshot DSL_000001`, compatibile anche con `python -m dsl_mngr graph export ...`.
- Orphan handling:
  - default non strict: nodo placeholder `status = "orphaned"`, warning nel report e run completata;
  - `--strict-orphans`: errore leggibile, run `gexf_export` fallita e nessun nuovo record `graph_exports` completato.
- Migration append-only v6 `graph_exports` con `GEXF_000001`, path relativi al workspace, conteggi, hash e stato.
- Profilo workspace `configs/workers/gexf.default.yaml` generato da `dsl-manager init`.
- Artifact run aggiornati: `input.json`, `output.json`, `process_report.json`; log applicativo `gexf_export_completed` / `gexf_export_failed`.
- Test deterministici `tests/test_slice_17_graph_export.py` con GEXF parseable via standard library, record DB, artifact, hash stabile su doppio export, compatibilita' `python -m dsl_mngr`, warning orphan e strict failure.

## Diff/status

```text
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/core/migrations.py
 M src/dsl_mngr/core/workspace.py
?? src/dsl_mngr/cli/commands/graph.py
?? src/dsl_mngr/core/graph_export.py
?? tests/test_slice_17_graph_export.py
```

Diff stat tracciato:

```text
src/dsl_mngr/cli/app.py         | 33 +++++++++++++++++++++++++++++++++
src/dsl_mngr/core/migrations.py | 36 ++++++++++++++++++++++++++++++++++++
src/dsl_mngr/core/workspace.py  | 17 +++++++++++++++++
3 files changed, 86 insertions(+)
```

Nuovi file principali:

```text
src/dsl_mngr/core/graph_export.py
src/dsl_mngr/cli/commands/graph.py
tests/test_slice_17_graph_export.py
.kb/projects/slicing/slice_17/dsl_manager_slice_17_report.md
```

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita prima degli edit:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 17:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_17_graph_export.py
```

Risultato:

```text
2 passed in 59.65s
```

Suite completa tentata:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato del secondo run completo:

```text
1 failed, 67 passed in 1232.35s (0:20:32)
```

Il fallimento e' nel test storico `tests/test_slice_10_docling_normalization.py::test_docling_normalization_no_images`: il secondo subprocess `python -m dsl_mngr corpus normalize ...` ha superato il timeout interno di 180 secondi. La Slice 17 era gia' passata in quel run. Un rerun mirato dello stesso test Slice 10 e' rimasto appeso fino al timeout esterno; i processi Python orfani generati dal timeout sono stati terminati.

Regression eseguita escludendo solo quel caso Docling bloccante:

```powershell
.\.venv\Scripts\python.exe -m pytest -k "not test_docling_normalization_no_images"
```

Risultato:

```text
67 passed, 1 deselected in 784.13s (0:13:04)
```

## Verifiche aggiuntive

- `git diff --check` non segnala errori whitespace; restano solo warning Git sulla futura normalizzazione LF/CRLF di file tracciati.
- Il GEXF usa `defaultedgetype = "directed"` ed e' parseable con `xml.etree.ElementTree`.
- I path salvati in `graph_exports`, report e artifact sono relativi al workspace e usano `/`.
- Il `graph_hash` resta stabile su due export dello stesso snapshot con le stesse opzioni.
- La policy scelta per doppio export dello stesso snapshot e' sovrascrivere i file derivati `exports/graph/DSL_000001.gexf` e `exports/graph/DSL_000001.graph_report.json`; l'audit storico resta in `graph_exports` e negli artifact separati di ogni run.
- I nodi sorgente sono creati da `traceability.facts` e `traceability.relations`; le relazioni portano `source_ids` come attributo e le fonti sono collegate con archi `derives_from` verso entita'/fact derivati.

## Fuori scope / note

- Nessuna dipendenza runtime nuova, nessun NetworkX e nessun ORM.
- Nessun render DSL automatico durante `graph export`.
- Nessun merge, diff, parser, batch, log viewer, UI, web/API/auth, provider AI, chiamata HTTP o integrazione esterna.
- I conflitti aperti sono rappresentati in modo minimale come nodi `conflict` e archi `conflicts_with` verso i fact coinvolti quando presenti nello snapshot.
