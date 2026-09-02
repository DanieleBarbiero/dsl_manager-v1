# Report Slice 13

Implementata la Slice 13 end-to-end nello scope richiesto: parser XML form deterministico dietro worker, artifact `fragments.jsonl`/`xml_form_report.json`, persistenza idempotente in `source_fragments` ed evidence lookup tramite `fragment_id`.

## Aggiunto

- Core `dsl_mngr.core.xml_form_parser` basato su standard library `xml.etree.ElementTree`, con parsing di form, field, required fields, button, action kind, riferimenti table/column e relazioni tecniche `form edits table`.
- Worker isolato `dsl_mngr.workers.parse_xml_form`, invocabile con il contratto `python <worker_path> --input ... --output ...`, senza scritture dirette sul database principale.
- Comando CLI `dsl-manager corpus parse-xml-form <workspace> --revision REV_000001`, compatibile anche via `python -m dsl_mngr corpus parse-xml-form ...`.
- Profilo default `configs/workers/xml_form.default.yaml` generato da `dsl-manager init`.
- Run type `parse_xml_form` e integrazione con `worker_runner.run_worker`, artifact Slice 4 e log applicativo.
- Estensione minimale di `fragment_registry` per `xml_form`, `xml_field`, `xml_button`, mantenendo compatibile `parse_ddl`.
- Persistenza idempotente in `source_fragments`, riuso `FRAG_*` per sequence, stale degli extra e riclassificazione `unknown -> xml_form/form/technical_structure`.
- Fixture XML dedicate sotto `tests/fixtures/xml_forms/`.
- Test `test_parse_xml_form`, `test_form_edits_table_relation`, `test_parse_xml_form_idempotent_rerun`, `test_parse_xml_form_unsupported_option_fails_without_active_fragments`.

## Diff/status

```text
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/cli/commands/corpus.py
 M src/dsl_mngr/core/fragment_registry.py
 M src/dsl_mngr/core/runs.py
 M src/dsl_mngr/core/workspace.py
?? src/dsl_mngr/core/xml_form_parser.py
?? src/dsl_mngr/workers/parse_xml_form.py
?? tests/fixtures/xml_forms/
?? tests/test_slice_13_parse_xml_form.py
```

Nota: durante il task risultano modificati anche `.gitignore` e `desktop.ini`, ma non fanno parte della Slice 13 e non sono stati usati per l'implementazione.

Diff stat sui file tracciati della slice:

```text
src/dsl_mngr/cli/app.py                |  20 ++
src/dsl_mngr/cli/commands/corpus.py    | 326 ++++++++++++++++++++++++++++++++-
src/dsl_mngr/core/fragment_registry.py | 201 ++++++++++++++++++--
src/dsl_mngr/core/runs.py              |   1 +
src/dsl_mngr/core/workspace.py         |  20 ++
5 files changed, 548 insertions(+), 20 deletions(-)
```

Nuovi file principali:

```text
src/dsl_mngr/core/xml_form_parser.py
src/dsl_mngr/workers/parse_xml_form.py
tests/fixtures/xml_forms/form_cliente.xml
tests/fixtures/xml_forms/form_ordine.xml
tests/test_slice_13_parse_xml_form.py
```

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita prima degli edit:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Test mirati Slice 13:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_13_parse_xml_form.py
```

Risultato:

```text
4 passed in 6.54s
```

Regression mirata Slice 12:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_12_parse_ddl.py
```

Risultato:

```text
5 passed in 7.20s
```

Suite completa:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
57 passed in 143.00s (0:02:22)
```

## Verifiche aggiuntive

- `git diff --check` non segnala errori whitespace; restano solo warning Git sulla futura normalizzazione CRLF dei file modificati.
- `fragments_hash` coincide con SHA-256 del contenuto canonico di `fragments.jsonl` e resta stabile su rerun.
- Rerun della stessa revision riusa gli stessi `fragment_id` e non crea duplicati attivi.
- `source_fragments` contiene `xml_form`, `xml_field` e `xml_button` con `metadata_json` canonico.
- Evidence lookup con `fragment_id` accetta un candidato `candidate_relation` senza `chunk_id`.
- `facts merge` inserisce la relazione `FRM_CLIENTE -[edits]-> ANCLI` a partire dal candidato validato.
- Il failure su opzione non supportata usa exit code worker `4`, run/worker `failed` e non crea frammenti attivi.

## Fuori scope / note

- Nessuna migration schema aggiunta: lo schema Slice 5 e' sufficiente.
- Nessun inserimento diretto in `facts`, `relations` o `candidate_records` da parte del parser.
- Non sono stati modificati i contratti pubblici di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`.
- Nessuna dipendenza runtime nuova, nessun ORM, nessuna chiamata di rete.
- Non sono stati implementati parser SQL code/procedure/trigger, parser log, AI handoff, batch orchestration, GEXF, UI, web/API/auth o integrazioni esterne.
