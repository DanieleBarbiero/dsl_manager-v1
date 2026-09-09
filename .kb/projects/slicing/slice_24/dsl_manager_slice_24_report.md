# Report Slice 24

Implementata la Slice 24 end-to-end, solo nello scope richiesto. Stato reale: `completata`.

## Aggiunto

- Esteso il preflight OOXML della Slice 23 nello stesso modulo e sullo stesso buffer acquisito/validato; non è stata introdotta una pipeline di sicurezza parallela.
- Aggiunto `workbook_manifest.json` canonico schema `1`, conforme ai campi minimi della sezione 11.3 del design v02: revisione sorgente, workbook, sheet/cell/merge/region, named range scoped, relazioni part+rId, external link, macro e warning.
- Conservate separatamente formula, `cached_value` e `value`; i tipi cella sono `string`, `number`, `bool`, `date`, `error`, `blank`.
- Aggiunto il detector `connected_non_empty_cells/1`, con ordinamento stabile, connessione ortogonale e bridge espliciti da merge/named range.
- Aggiunti frammenti `excel_region` localizzati e canonici, uno per regione, con celle ordinate, formula/cache e locator OOXML.
- Aggiunta la migrazione append-only v8 della sezione 8.2: `workbook_manifests`, `workbook_sheets`, `workbook_regions`, indici e riferimenti a `source_revisions`/`source_fragments`.
- Aggiunta persistenza transazionale con verifica dei file canonici e dei relativi SHA-256, replay idempotente e riuso degli ID registrati.
- Esteso `corpus normalize` per pubblicare e mostrare manifest, JSONL dei frammenti e report workbook; `normalized.md` rimane prodotto secondario e il report dichiara `structural_source=workbook_manifest.json`.
- Aggiunti fixture binari immutabili, catalogo checksum, builder riproducibili, golden manifest e sette test Slice 24.
- Nessuna nuova dipendenza runtime, ORM, servizio esterno o chiamata AI/rete.

## Controllo anti-drift e precondizioni

Stato del gate prima del codice: `pronta`.

- `git status --short --branch` iniziale: branch `main...origin/main` con worktree già modificato dalle Slice 20–23 e dal prompt cumulativo. Tutti i cambiamenti preesistenti non correlati sono stati preservati.
- Design v02, matrice di tracciabilità, design v01 di baseline, template, contratti, analisi tecnica, manuale, report 01–23, codice, schema, test, fixture e golden sono stati confrontati prima della modifica.
- Precondizione Slice 23: `pronta`. `ooxml_preflight.py`, acquisizione singola, controllo hash, limiti ZIP/XML/relazioni, no-network e routing Docling `.xlsx`/`.xlsm` erano presenti e il test baseline completo era verde.
- Gap non bloccante attribuito alla Slice 23: `excel.max_cells` e `excel.max_regions` erano già configurati e validati rispetto agli hard maximum, ma non erano esposti da `ExcelLimits`. È stata applicata la minima estensione compatibile indispensabile alla Slice 24.
- Dipendenze bloccanti: nessuna.
- Nessuna contraddizione irrisolvibile tra fonti normative rilevata.
- È stata consultata ECMA-376 Part 2, quinta edizione dicembre 2021, dalla pubblicazione ufficiale ECMA. SHA-256 del ZIP consultato: `1d489d21e1c83b351678ec56a6a292cf872a73c60a36ac607c1ea9d3f9020c70`; SHA-256 del PDF Part 2 estratto: `18701071fe15f39389761f82512c70d2effbf22bd16dd034f2939797ff5f6147`. I file temporanei non sono stati aggiunti al repository.

## Contratto manifest, artifact e persistenza

Il manifest implementa concretamente le sezioni 11.3 e 8.2 del design v02:

- `source_revision`: `id`, `content_hash`, `extension`, `package_content_type`;
- `workbook`: `part_name`, `date_system`, `calculation_properties`, `macro_presence`;
- `sheets[]`: ordine workbook, nome Unicode, visibility, part/rId, dimensioni, celle, merge e regioni;
- `cells[]`: coordinate/riga/colonna, tipo, valore, formula, cached value e stile;
- `named_ranges[]`: scope workbook/sheet, sheet nullable, nome e formula originale;
- `relationships[]`: source part, rId, tipo, target normalizzato e mode;
- `external_links[]`: source part/rId/target con `disposition=not_dereferenced`;
- `macros`: presenza, part, SHA-256 e `executed=false`;
- `warnings[]`: schema e ordinamento stabile `reason/locator/severity`;
- nessun timestamp operativo, run ID o path assoluto entra nel manifest o nei suoi hash.

Artifact pubblicati per una normalizzazione Excel valida:

```text
normalized/<source_id>/<source_revision_id>/normalized.json
normalized/<source_id>/<source_revision_id>/normalized.md
normalized/<source_id>/<source_revision_id>/source_hash.txt
normalized/<source_id>/<source_revision_id>/docling_report.json
normalized/<source_id>/<source_revision_id>/ooxml_preflight_report.json
normalized/<source_id>/<source_revision_id>/workbook_manifest.json
normalized/<source_id>/<source_revision_id>/workbook_fragments.jsonl
normalized/<source_id>/<source_revision_id>/workbook_report.json
```

Il DB v8 conserva manifest, sheet, regioni, riferimenti ai frammenti e hash; non duplica XML OOXML completo. La persistenza rilegge gli artifact dal workspace, rifiuta path non relativi, controlla canonicalità, hash, cardinalità e coerenza con la revisione registrata.

## Tracciabilità

Righe della sezione 17 assegnate alla Slice 24:

| Requisito | Implementazione/file | Test | Esito |
| --- | --- | --- | --- |
| Due viste Excel | `ooxml_preflight.build_workbook_manifest`: `formula`, `cached_value`, `value` separati nello stesso record cella | `test_slice_24_formula_cached` | passato |
| Struttura workbook | manifest schema 1, detector regioni, fragments, golden e registry DB v8 | `test_slice_24_manifest_golden` | passato |

Copertura operativa aggiuntiva richiesta dal prompt:

| Requisito | Test/evidenza | Esito |
| --- | --- | --- |
| Multi-sheet/multi-region, merge, named range workbook/sheet, visibility e Unicode/order | `test_slice_24_manifest_golden` | passato |
| String/number/bool/date/error/blank | `test_slice_24_manifest_golden` | passato |
| External link senza dereference | `test_slice_24_manifest_golden`, `test_slice_24_deterministic_across_logical_runs_and_no_network` e baseline Slice 23 | passato |
| `.xlsm`, macro part/hash, `executed:false` | `test_slice_24_macro_hash_and_fixture_checksums` e Docling reale Slice 23 | passato |
| Limiti celle/regioni/relazioni/output at/over | `test_slice_24_limits_at_and_over_boundaries` | passato |
| Migrazione v7→v8, DB roundtrip e replay ID stabile | `test_slice_24_v8_is_append_only_from_v7`, `test_slice_24_migration_v8_worker_artifacts_and_db_roundtrip` | passato |
| Manifest/fragments uguali su due run/macchine logiche | `test_slice_24_deterministic_across_logical_runs_and_no_network` | passato |
| Fixture immutabili e checksum | `test_slice_24_macro_hash_and_fixture_checksums` più verifica finale | passato |
| Artifact worker catalogati e fonte strutturale primaria | `test_slice_24_migration_v8_worker_artifacts_and_db_roundtrip` | passato |

## Fixture e hash

I checksum sono stati rilevati alla creazione/baseline e verificati nuovamente dopo implementazione e suite:

| File | SHA-256 iniziale | SHA-256 finale | Esito |
| --- | --- | --- | --- |
| `tests/fixtures/slice_23/real_workbook.xlsx` | `9ed7bda6d838c4142e7e673d5d6faba7e5e93a7e2fd6d83e0fb90b955aac0247` | stesso valore | immutato |
| `tests/fixtures/slice_23/real_macro_workbook.xlsm` | `17f2858e53262098f899180d470a5390c3072ba5415e7d59a3cd9a4b2bd4caf4` | stesso valore | immutato |
| `tests/fixtures/slice_24/structural_workbook.xlsx` | `8691d24f3b6748d76a51731e6dfe362733cc26c2b8ea84769339832346754081` | stesso valore | immutato/riproducibile |
| `tests/fixtures/slice_24/macro_workbook.xlsm` | `17f2858e53262098f899180d470a5390c3072ba5415e7d59a3cd9a4b2bd4caf4` | stesso valore | immutato |

Golden/semantic hash sul fixture strutturale:

```text
workbook_manifest.json  c14fd057300c658528f2a831426fdb7458ba489ad51e9aeb52a7aebda50fecba
workbook_fragments.jsonl 7fd91f5e105d0414fadcab859850574e9ee7ae35164c12b0003b03f5c702a0de
xl/vbaProject.bin       0ced1464b3677e98f5e3a8c5d80135e18dc98dca39299f1a8cfd2a00999fbf9f
```

## Diff/status

File pertinenti modificati o aggiunti dalla Slice 24:

```text
M  src/dsl_mngr/cli/commands/corpus.py
M  src/dsl_mngr/core/migrations.py
M  src/dsl_mngr/core/ooxml_preflight.py
A  src/dsl_mngr/core/workbook_regions.py
A  src/dsl_mngr/core/workbook_registry.py
M  src/dsl_mngr/workers/normalize_docling.py
M  tests/test_slice_20_migration_and_derivation.py
A  tests/test_slice_24_workbook_manifest.py
A  tests/expected/expected_slice_24_workbook_manifest.json
A  tests/fixtures/slice_24/build_slice_24_fixtures.py
A  tests/fixtures/slice_24/build_slice_24_golden.py
A  tests/fixtures/slice_24/checksums.json
A  tests/fixtures/slice_24/structural_workbook.xlsx
A  tests/fixtures/slice_24/macro_workbook.xlsm
A  .kb/projects/slicing/slice_24/dsl_manager_slice_24_report.md
```

La modifica a `tests/test_slice_20_migration_and_derivation.py` limita correttamente il test storico della sola migrazione v7 a `MIGRATIONS[:7]`; la migrazione v8 è verificata separatamente dai test Slice 24. Non modifica il contratto della Slice 20.

`git diff --stat` aggregato del worktree prima del presente report (include le modifiche preesistenti delle Slice 20–23 e non include file untracked):

```text
33 files changed, 2631 insertions(+), 133 deletions(-)
```

Lo stato finale rimane volutamente dirty: oltre ai file Slice 24 sopra elencati, sono ancora presenti tutti i file modificati/untracked osservati all'inizio per Slice 20–23. Nessuno è stato rimosso, resettato o sovrascritto fuori dalle integrazioni necessarie.

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Esito: exit code `0`; `dsl_mngr-0.1.0` editable e dipendenze dev installate. `docling==2.97.0`; `pip check`: `No broken requirements found.`

Baseline mirata eseguita prima delle modifiche:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_23_excel_ingest.py
```

Risultato baseline:

```text
12 passed in 399.00s (0:06:39)
```

Test mirati Slice 24:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_24_workbook_manifest.py
```

Risultato:

```text
7 passed in 3.91s
```

Compatibilità mirata Slice 23/24:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_24_workbook_manifest.py tests\test_slice_23_excel_ingest.py -k "slice_24 or single_byte_sequence or partial_is_distinct_and_atomic"
```

Risultato:

```text
9 passed, 10 deselected in 6.57s
```

Suite senza il file Docling reale Slice 23, usata per isolare eventuali regressioni durante un timeout intermedio:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --ignore=tests\test_slice_23_excel_ingest.py
```

Risultato:

```text
107 passed in 501.44s (0:08:21)
```

Suite completa finale obbligatoria:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Risultato finale:

```text
119 passed in 1059.95s (0:17:39)
```

Nessun test finale fallito, saltato, interrotto o non eseguito.

### Failure intermedi e classificazione

- `tests/test_slice_23_excel_ingest.py tests/test_slice_24_workbook_manifest.py`: `1 failed, 18 passed in 333.17s`; il worker `.xlsx` ha raggiunto esattamente `worker_timeout_seconds=120`, `termination_reason=timeout`, senza traceback né artifact parziale. Classificazione: `limite ambiente`; il `.xlsm` reale e gli altri test sono passati.
- Retry del solo `test_slice_23_real_xlsx_docling`: `1 failed in 125.95s`, stessa causa e classificazione `limite ambiente`. Verifica alternativa immediata: parser/manifest diretto verde; verifica definitiva: la suite completa finale ha poi eseguito con successo entrambi i run `.xlsx` byte-identici.
- Un ulteriore rerun completo, eseguito dopo due rifiniture sperimentali poi rimosse integralmente, ha prodotto `1 failed, 118 passed in 842.91s`: ancora il solo timeout `.xlsx` a 120 s. Classificazione: `limite ambiente`. Il worktree è stato riportato esattamente allo stato della suite completa verde `119 passed`; le rifiniture non fanno parte della consegna.
- Test storico v6→v7 più test DB/24: `1 failed, 15 passed in 9.63s`; atteso `[7]`, osservato `[7,8]` dopo l'append della v8. Classificazione: `introdotto dalla Slice` nel solo assunto del test storico. Correzione: il test Slice 20 ora richiede esplicitamente `MIGRATIONS[:7]`, mentre v7→v8 è coperto dalla Slice 24. Rerun: `8 passed in 4.83s`; suite finale verde.

## Verifiche aggiuntive

- `git diff --check`: exit code `0`; nessun errore whitespace. I warning CRLF già presenti sono attribuibili alla configurazione Git/Windows e non rappresentano errori del diff.
- Verifica finale dopo il ripristino dello stato consegnato: `7 passed in 4.02s` su `tests/test_slice_24_workbook_manifest.py`; compilazione `py_compile` dei moduli Slice 24 con exit code `0`.
- `.\.venv\Scripts\dsl-manager.exe corpus normalize --help`: exit code `0`.
- `.\.venv\Scripts\python.exe -m dsl_mngr corpus normalize --help`: exit code `0`; help identico all'entry point console.
- Entrambi gli entry point su workspace non inizializzato: exit code `2`, messaggio utente su stderr, nessun traceback.
- Nessun nuovo comando pubblico; `corpus normalize` mantiene argomenti e compatibilità e aggiunge solo i path degli artifact workbook nell'output di successo/partial Excel.
- Roundtrip reale osservato dopo il test Docling `.xlsm`: `1` manifest, `1` sheet, `1` regione. Roundtrip strutturale: `1` manifest, `3` sheet, `5` regioni e `5` frammenti; secondo replay con gli stessi ID.
- Manifest/fragments ricostruiti due volte da nuovi buffer logici hanno byte e hash identici.
- External target mai dereferenziato, macro mai eseguita, formule mai calcolate o aggiornate.

## Fuori scope / note

- Nessuna interpretazione di dominio e nessuna produzione/importazione/review di candidati Excel: appartengono alla Slice 25.
- Nessun ricalcolo formule, aggiornamento link, esecuzione macro, rete o fallback alternativo a Docling.
- Nessuna copia dell'XML OOXML completo nel DB; letture XML limitate e streaming usano i budget del preflight Slice 23.
- Nessuna modifica a migrazioni già applicate; v8 è soltanto append-only.
- Nessun aggiornamento esteso di manuale/contratti/analisi: il consolidamento documentale resta assegnato alla Slice 29; il presente report registra il contratto effettivamente consegnato.
