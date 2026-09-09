# Report Slice 25

Implementata la Slice 25 end-to-end, solo nello scope richiesto. Stato reale: **completata**.

Il percorso verificato e' `workbook -> workbook_manifest/workbook_fragments -> candidate batch -> review comune -> merge`: nessun valore di cella viene materializzato direttamente come autorita'. Le relazioni Excel richiedono sempre una decisione umana; i soli candidati ammessi all'auto-review sono fatti di struttura tecnica esplicita.

## Aggiunto

- catalogo separato e versionato di sei regole Excel `*/1`, senza cambiare l'ordine o il contenuto del catalogo storico delle Slice 20-21;
- derivazione deterministica da `workbook_manifest.json` e dagli `excel_region` attivi, con verifica del path confinato al workspace, canonicalizzazione e hash registrato;
- fatti tecnici per workbook, sheet, region, named range e table; relazioni `references` solo per riferimenti espliciti e risolti a named range, table o region di un altro sheet;
- locator completo `source_revision_id + fragment_id + manifest_id + sheet_name + coordinate + part_name`, oltre al `path_or_selector` dell'evidenza attiva;
- inventario conservativo delle table OOXML dichiarate tramite relationship interna e relativo table part; il manifest v1 aggiunge `tables` solo quando presenti, mantenendo invariati gli artifact storici senza table;
- collegamento del risultato `normalize` Excel del batch `process-dir` alle regole della Slice 25;
- enforcement in `batch consolidate` di `automatic_review_allowed`: le cinque regole di fatto possono essere confermate solo dalla propria policy allowlisted esatta, mentre `excel_explicit_reference/1` resta `pending` anche se la policy e' configurata;
- fixture OOXML deterministica con regioni multiple a contenuto duplicato, named range workbook/sheet con nome duplicato, table, formule con cached value, sheet hidden/veryHidden e link esterno non dereferenziato;
- golden per regola/versione e test verticale `test_slice_25_excel_candidates` con due run logiche e rete vietata.

### Regole e confine semantico

| regola | input strutturale | evidence locator | candidate type | auto-review consentita? | ragione |
|---|---|---|---|---|---|
| `excel_workbook_fact/1` | identita' e metadati tecnici del workbook nel manifest registrato | fragment di ancoraggio, sheet, coordinate e workbook part | `candidate_fact` / `excel_workbook` | si, solo `explicit_excel_workbook_only/1` | il contenitore OOXML e' esplicito; valori e formule non entrano nei campi semantici |
| `excel_sheet_fact/1` | indice, nome, visibility, dimensioni, relationship e part dello sheet | fragment dello stesso sheet, coordinate e worksheet part | `candidate_fact` / `excel_sheet` | si, solo `explicit_excel_sheet_only/1` | la visibility e' un attributo tecnico; `hidden` e `very_hidden` non significano inattivo |
| `excel_region_fact/1` | regione rilevata e relativo `excel_region` attivo | fragment della regione, sheet, range e worksheet part | `candidate_fact` / `excel_region` | si, solo `explicit_excel_region_only/1` | celle, header, label, formule, cached value e valori restano in `technical_attributes.cell_attributes` ed evidenza |
| `excel_named_range_fact/1` | defined name esplicito, scope workbook/sheet e range risolto | fragment sovrapposto, sheet, range e worksheet part | `candidate_fact` / `excel_named_range` | si, solo `explicit_excel_named_range_only/1` | nome, scope e `refers_to` sono dichiarazioni strutturali; nessuna inferenza sul contenuto |
| `excel_table_fact/1` | relationship table interna, table part, display name, ref e colonne dichiarate | fragment sovrapposto, sheet, range e worksheet part | `candidate_fact` / `excel_table` | si, solo `explicit_excel_table_only/1` | la table e' una struttura OOXML esplicita; header/nomi colonna restano attributi |
| `excel_explicit_reference/1` | token formula esplicito risolto a named range scoped, table o region cross-sheet | fragment della formula, sheet, coordinata cella e worksheet part | `candidate_relation` / `references` | **no** | formula e token restano attributi; la relazione tecnica richiede review umana e i riferimenti esterni sono esclusi |

## Controllo anti-drift e dipendenze

Preflight eseguito prima delle modifiche su design v02, baseline v01, template, documenti tecnici, tre documenti sui candidati deterministici, report 01-24, schema/migrazioni, codice, fixture, golden, test e help correnti.

Classificazione iniziale:

- `pronta`: importer e schema candidati della Slice 20, review/lineage comune, regole deterministiche della Slice 21, consolidatore della Slice 22 e manifest/fragments persistiti dalla Slice 24 erano presenti e verificabili;
- `gap non bloccante` di proprieta' Slice 22: l'orchestratore confrontava la policy configurata ma non il flag `automatic_review_allowed`; correzione minima indispensabile applicata in `batch_consolidation.py`, senza modificare `candidate_review.py`;
- `gap non bloccante` di proprieta' Slice 24: manifest e fragments esistevano realmente, ma il manifest non inventariava nome/ref delle table OOXML necessari al fatto e al riferimento esplicito; estensione minima e compatibile applicata in `ooxml_preflight.py`, senza migrazione;
- `bloccata da dipendenza`: nessuna;
- conflitti normativi non risolvibili: nessuno.

Il test baseline delle dipendenze, eseguito prima del codice, ha prodotto `34 passed in 141.40s`. La derivazione legge il manifest registrato come fonte primaria e usa gli `excel_region` attivi come evidence ref; non legge `normalized.md` per ricavare candidati.

File dichiarati prima dell'implementazione: `src/dsl_mngr/core/candidate_derivation.py`, `src/dsl_mngr/core/batch_consolidation.py`, `src/dsl_mngr/core/batch.py`, estensione minima di `src/dsl_mngr/core/ooxml_preflight.py`, nuovo test, fixture/golden e questo report.

## Schema, API, comandi e artifact

- Migrazioni/database: nessuna nuova migrazione e nessuna modifica alla v8 applicata. Le table restano nell'artifact manifest e non introducono una tabella DB parallela.
- Review/merge: `candidate_review.py` e `merge.py` non sono stati modificati dalla Slice 25. Tutti i record entrano tramite `import_candidate_file(..., origin_type="deterministic_derivation")`, acquisiscono lineage e raggiungono facts/relations solo dopo una decisione della review comune.
- CLI pubblica: nessun nuovo comando o argomento. `candidates derive --rule <regola_excel/1>` usa l'opzione generica esistente; `batch consolidate` riconosce automaticamente una normalizzazione Excel completata.
- Artifact: `workbook_manifest.json` puo' contenere la chiave opzionale `tables`; `derived_candidates.jsonl` e `derive_report.json` restano gli artifact comuni per ogni regola/versione; il golden nuovo e' `tests/expected/expected_slice_25_excel_candidates.json`.
- Dipendenze: nessuna dipendenza runtime o dev aggiunta. Il builder di fixture usa `xlsxwriter` nello stesso modo del builder gia' presente per la Slice 24 e non partecipa al runtime/test ordinario.

## Tracciabilita'

| requisito design v02 sezione 17 / prompt | implementazione | test | esito |
|---|---|---|---|
| candidati Excel -> solo struttura esplicita -> candidate schema -> evidence locator completo, pending/auto policy | `EXCEL_DERIVATION_RULE_CATALOG`, loader manifest registrato, producer tecnici e gating review | `test_slice_25_excel_candidates` | passato |
| workbook/sheet/region/named range/table come soli fatti tecnici | cinque regole fact `*/1`; semantic fields limitati a `excel_*` e `object_type` | golden per regola e assert sui semantic values | passato |
| relazioni soltanto da riferimenti espliciti | `excel_explicit_reference/1` risolve table, named range scoped e cross-sheet; esclude external formula/link | reference kinds, scope locale preferito, assenza target esterno | passato |
| locator sheet + coordinate/part ed evidence ref esistente | locator Excel completo e fragment `excel_region` attivo; validator comune invariato | assert locator; caso `FRAG_999999 -> unknown_fragment` | passato |
| regioni multiple/duplicate | fixture con blocchi `A1:B3` ed `E1:F3` aventi stessi tipi/valori ma identita' e coordinate distinte | confronto valori e `candidate_id` distinti | passato |
| named range scoped | `LocalBlock` sia workbook-scoped sia sheet-scoped; formula locale risolta allo scope sheet | assert su entrambi i fatti e sul target della relazione | passato |
| table reference | inventario table OOXML `Orders` e structured reference `Orders[Amount]` | manifest table + fact table + relation table | passato |
| formule/cached | formula e cached value conservati nelle celle/technical attributes | assert `H1` formula/cached e `H7` cached | passato |
| hidden/veryHidden senza semantica inattiva | sheet facts prodotti con visibility tecnica invariata | mapping `Main/Hidden/VeryHidden` | passato |
| external link non semantico | link catalogato `not_dereferenced`; formula esterna esclusa dalle relazioni | rete vietata, manifest external link e nessun source/target esterno | passato |
| candidate ID ripetuto fra batch | identita' semantica stabile, record e lineage distinti per import | seconda derivazione: stessi candidate/payload/report hash, record ID disgiunti | passato |
| ordine invertito e due run | sort key strutturale canonica e derivazione idempotente | input forward/reversed uguale; due derivazioni uguali | passato |
| pending vs auto policy | cinque fact rule allowlisted, reference rule con `automatic_review_allowed=False` | 16 auto-confirmed, 3 pending con `automatic_review_not_allowed` | passato |
| nessuna cella direttamente autoritativa | derive e review non scrivono facts/relations; merge materializza solo decisioni positive | conteggi zero prima di review/merge; 16 facts dopo auto decision; 1 relation dopo review umana | passato |
| golden e no-network | fixture/checksum e golden stabili; socket/URL bloccati | confronto golden, checksum e monkeypatch rete | passato |

Tutte le righe pertinenti della sezione 17 assegnate alla Slice 25 risultano verificate; la sezione contiene la riga `candidati Excel`, coperta dal test nominato richiesto.

## Diff/status

File modificati o aggiunti dalla Slice 25:

```text
M  src/dsl_mngr/core/batch.py
?? src/dsl_mngr/core/batch_consolidation.py (preesistente untracked, esteso)
?? src/dsl_mngr/core/candidate_derivation.py (preesistente untracked, esteso)
?? src/dsl_mngr/core/ooxml_preflight.py (preesistente untracked, esteso)
?? tests/test_slice_25_excel_candidates.py
?? tests/expected/expected_slice_25_excel_candidates.json
?? tests/fixtures/slice_25/build_slice_25_fixtures.py
?? tests/fixtures/slice_25/candidate_workbook.xlsx
?? tests/fixtures/slice_25/checksums.json
?? .kb/projects/slicing/slice_25/dsl_manager_slice_25_report.md
```

`candidate_derivation.py`, `batch_consolidation.py` e `ooxml_preflight.py` erano gia' file untracked introdotti dalle Slice 21/22/24; sono stati estesi senza rimuovere il lavoro esistente. `batch.py` conteneva modifiche preesistenti e la Slice 25 vi aggiunge soltanto `outputs.is_excel`.

Il worktree iniziale era dirty: 33 file tracked modificati e artifact/codice/test untracked delle Slice 20-24, oltre a `.kb/prompt/prompt_slicing_dsl-manager.md`. Sono stati preservati. Per questo il `git diff --stat` globale descrive anche lavoro preesistente e non include i file untracked:

```text
33 files changed, 2632 insertions(+), 133 deletions(-)
```

Stato finale: branch `main...origin/main`, le stesse modifiche preesistenti sono presenti; in aggiunta risultano i file Slice 25 elencati sopra. Nessun file estraneo e' stato modificato dalla Slice 25.

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`, determinato esclusivamente da `PROJECT_PYTHON` in `.codex/config.toml`.

Install editable eseguita:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Risultato: exit code `0`; `dsl_mngr-0.1.0` installato in editable mode. Anche `.\.venv\Scripts\python.exe -m pip check` ha restituito exit code `0` e `No broken requirements found`.

Baseline mirata pre-modifica:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_20_candidate_review.py tests\test_slice_20_migration_and_derivation.py tests\test_slice_21_deterministic_derivation.py tests\test_slice_22_batch_consolidation.py tests\test_slice_24_workbook_manifest.py
```

Risultato:

```text
34 passed in 141.40s
```

Test mirato finale:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_25_excel_candidates.py
```

Risultato:

```text
1 passed in 2.35s
```

Regressione mirata Slice 20-25 eseguita durante l'integrazione:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_20_candidate_review.py tests\test_slice_20_migration_and_derivation.py tests\test_slice_21_deterministic_derivation.py tests\test_slice_22_batch_consolidation.py tests\test_slice_24_workbook_manifest.py tests\test_slice_25_excel_candidates.py
```

Risultato:

```text
35 passed in 159.35s
```

Suite completa finale:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
120 passed in 266.63s (0:04:26)
```

Nessun test fallito o saltato nella suite finale.

Altre esecuzioni verdi svolte durante l'integrazione:

- `.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_21_deterministic_derivation.py tests\test_slice_22_batch_consolidation.py`: `14 passed in 100.88s`;
- `.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_25_excel_candidates.py`: `1 passed in 8.32s`, poi `1 passed in 9.81s` dopo il refactoring dei producer;
- `.\.venv\Scripts\python.exe -m pytest`: `120 passed in 416.29s (0:06:56)` prima della rimozione finale dell'identificativo registry dal segnale hash; la suite completa e' stata quindi rieseguita, producendo il risultato finale sopra.

### Esiti intermedi non verdi

- prima esecuzione Slice 25: exit code `1`, `1 failed in 4.14s`; classificazione `introdotto dalla Slice`: il filtro external trattava ogni `[` come link esterno e scartava anche la structured reference `Orders[Amount]`. Corretto restringendo il riconoscimento esterno a URI/file e riferimenti con estensione spreadsheet; table reference poi verificata;
- seconda esecuzione Slice 25: exit code `1`, `1 failed in 4.00s`; classificazione `bootstrap golden richiesto`, non difetto funzionale: il test ha emesso la proiezione deterministica perche' il nuovo golden non esisteva ancora. Il golden e' stato creato e rieseguito due volte, poi incluso nella suite completa;
- dopo la rimozione intenzionale di `manifest_id` dal segnale hash, `.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_25_excel_candidates.py`: exit code `1`, `1 failed in 2.13s`, e la ripetizione diagnostica con `-vv`: exit code `1`, `1 failed in 3.11s`; classificazione `golden da riallineare a una correzione semantica intenzionale`. Il solo delta era nei candidate ID attesi; payload, ordine e comportamento erano invariati. Golden aggiornato, test mirato e suite completa rieseguiti verdi;
- `.\.venv\Scripts\python.exe -m ruff check src/dsl_mngr/core/candidate_derivation.py src/dsl_mngr/core/ooxml_preflight.py src/dsl_mngr/core/batch_consolidation.py src/dsl_mngr/core/batch.py tests/test_slice_25_excel_candidates.py`: exit code `1`, causa `No module named ruff`, classificazione `limite ambiente/strumento opzionale`. Ruff non e' dichiarato in `.[dev]`, non e' un gate del repository e non e' stata aggiunta una dipendenza fuori scope. Verifiche alternative: `py_compile`, suite completa, `git diff --check` e scan whitespace, tutti verdi.

Nessun test e' stato interrotto o lasciato non eseguito.

## Verifiche aggiuntive (opzionale)

- `dsl-manager candidates derive --help` e `.\.venv\Scripts\python.exe -m dsl_mngr candidates derive --help`: entrambi exit code `0`, stdout equivalente, stderr vuoto, nessun traceback;
- `dsl-manager batch consolidate --help` e `.\.venv\Scripts\python.exe -m dsl_mngr batch consolidate --help`: entrambi exit code `0`, stdout equivalente, stderr vuoto, nessun traceback;
- `.\.venv\Scripts\python.exe -m py_compile` sui quattro moduli core interessati e sul test Slice 25: exit code `0`;
- `git diff --check`: exit code `0`; i soli messaggi sono warning Git sulla futura conversione LF/CRLF di file gia' presenti nel worktree;
- scan di whitespace finale sui file Slice 25: nessuna occorrenza;
- fixture `candidate_workbook.xlsx`: SHA-256 `751848e1c7c91bf7406a35a88d23b62c2b4f6923fcd5fd5db77290e26b6e0498`, verificato dal test;
- revisione del diff pertinente: nessuna migrazione, nessun ORM, nessuna rete/AI, nessun formato spreadsheet oltre `.xlsx/.xlsm`, nessun path assoluto/timestamp/run ID negli hash semantici aggiunti.

## Fuori scope / note (opzionale)

- nessun fatto di dominio e nessuna interpretazione di header, label, formule, cached value o valori di cella;
- nessuna euristica su sheet hidden/veryHidden, layout visuale, stile, colore o formula non risolta;
- nessuna dereferenziazione di external link e nessun accesso di rete;
- nessun nuovo formato spreadsheet, editor workbook, calcolo formule o fallback a librerie alternative;
- nessuna modifica ai contratti di review/merge e nessuna materializzazione diretta dai manifest/fragments;
- gli sheet o gli oggetti senza una regione attiva utilizzabile come evidence ref non generano candidati: e' una scelta conservativa coerente con l'obbligo di evidenza esistente, non un'inferenza sostitutiva;
- le table sono inventariate nell'artifact manifest; una persistenza relazionale dedicata o un ampliamento dello schema DB restano fuori scope.

Autoverifica finale: perimetro, non-obiettivi, invarianti, matrice di tracciabilita', failure mode, compatibilita' legacy, determinismo e Definition of Done risultano soddisfatti. Tutti gli output Excel attraversano candidati e decisioni; nessuna cella diventa direttamente autoritativa.
