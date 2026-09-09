# Report Slice 29

Stato reale: **parziale**.

Il consolidamento documentale richiesto dalla Slice 29 è stato completato senza
modificare il runtime: documenti, esempi CLI, link e nomenclatura sono coerenti
con lo stato osservato. La Slice non può tuttavia essere dichiarata
`completata`, perché il confronto design -> codice/test ha confermato due gap di
dipendenza delle slice precedenti: il budget nodi+archi GEXF non è applicato e
`result_catalog_v1` non è uniforme su OOXML/worker/temporalità/GEXF.

## Aggiunto

- Riscritta l'[analisi tecnica](../../../documenti/documenti%20tecnici/analisi_tecnica_dsl_manager.md)
  sul comportamento realmente consegnato dalle slice 20-28.
- Riscritti i [contratti manifest](../../../documenti/documenti%20tecnici/contratti_manifest_dsl_manager.md)
  per migrazioni v1-v10, review/lineage, effective views, Excel, temporalità,
  DSL e GEXF.
- Riscritto il [manuale utente](../../../documenti/manuali/manuale_utente_dsl_manager.md)
  con tutti i leaf command correnti ed esempi confrontati con `--help`.
- Sostituito il precedente transcript architetturale con un
  [outline input-output](../../../documenti/manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md)
  conciso e coerente.
- Integrate le guide Aurora
  [PowerShell](../../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl-manager-powershell.md)
  e [CMD](../../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl-manager_cmd.md)
  con correzione/reconcile, incomplete e modalità temporali.
- Marcato il [prompt Aurora](../../../projects/corpus%20aurora/prompt_aurora+guida.md)
  come fonte storica; i riferimenti superati a ZIP e guida in root sono
  disambiguati con link agli artifact versionati correnti.
- Aggiunto il [test documentale Slice 29](../../../../tests/test_slice_29_documentation.py)
  per link locali, nomi ordinati, command catalog, opzioni CLI, invarianti e gap.

## Controllo anti-drift e precondizioni

Prima delle modifiche sono stati letti integralmente `AGENTS.md`, design v02,
design v01, template del report, report 01-28, analisi, contratti, manuale e
documentazione/corpus Aurora richiesta. Sono stati ispezionati codice, migrazioni
v7-v10, test, fixture, expected/golden e help CLI.

`git status --short --branch` iniziale mostrava `main...origin/main` e un
worktree già modificato dalle slice 20-28: sorgenti, test, report, risorse GEXF,
fixture Excel/temporali e documenti Aurora erano `M` o `??`. Tali modifiche sono
state trattate come stato preesistente dell'utente, non ripristinate e non
alterate fuori dai documenti Aurora dichiarati.

Classificazione delle precondizioni:

| Precondizione | Evidenza osservata | Stato |
|---|---|---|
| state machine review/merge | v7, `candidate_review.py`, `merge.py`, test Slice 20 | pronta |
| derivazione candidate-first | `candidate_derivation.py`, test Slice 21 | pronta |
| batch checkpoint/retry | `batch_consolidation.py`, test Slice 22 | pronta |
| `.xlsx`/`.xlsm` diretto e sicuro | preflight/worker, test Slice 23 | pronta |
| manifest e regole Excel | v8, workbook core, test Slice 24-25 | pronta |
| temporalità, DSL v2 e GEXF 1.3 | v9-v10, temporal/DSL/GEXF core, test Slice 26-27 | pronta con gap non bloccante per docs |
| corpus Aurora | inventario/checksum/golden, test Slice 28 | pronta |
| budget nodi+archi GEXF | nessuna chiave/guardia in `config.py`/`graph_export.py` | gap non bloccante per docs; proprietario Slice 26 |
| catalogo esiti uniforme | string catalog presente in review/derive/merge/reconcile/batch; envelope diverso o assente altrove | gap non bloccante per docs; proprietari Slice 23/26 e requisito trasversale |

Non è emersa una contraddizione di autorità che richiedesse una nuova decisione
progettuale. I due gap sono stati documentati e non corretti, perché una modifica
runtime sarebbe fuori scope.

## Tracciabilità requisito -> implementazione -> test

| Requisito Slice 29 | Implementazione/file | Test o verifica | Esito |
|---|---|---|---|
| docs consolidate; nessun runtime nuovo | analisi, contratti, manuale, outline e guide | `test_slice_29_documentation.py`; diff su soli documenti/test | completato |
| link/comandi/riferimenti verificati | link relativi e tabella di tutti i leaf command | link resolver; confronto parser; doppio `--help` entry point/modulo | completato |
| state machine e pending non mergeabile | analisi sez. 4; contratti sez. 6-7; manuale sez. 3 | test Slice 20 + ricerca testuale Slice 29 | completato |
| idempotenza/correzione/reconcile/effective views | analisi/contratti/manuale | test Slice 20 e 22; full suite | completato |
| derivazione e batch | analisi sez. 5-6; contratti sez. 8-9 | test Slice 21-22; full suite | completato |
| `.xlsx`/`.xlsm`, sicurezza e manifest | analisi sez. 7-8; contratti sez. 10; manuale sez. 5/12 | test Slice 23-25 e 28 | completato |
| temporal evidence/policy/precision/timezone | analisi sez. 9; contratti sez. 11; manuale sez. 8 | test Slice 26-27 | completato |
| DSL v2/diff e compatibilità schema1/static | analisi sez. 10; contratti sez. 12; manuale sez. 9-10 | test Slice 26-27 + CLI help | completato |
| GEXF 1.3 XSD+semantic offline | analisi sez. 10; contratti sez. 13; manuale sez. 11 | `test_slice_26_gexf_offline.py`, test Slice 27 | implementato; budget GEXF mancante documentato |
| migrazioni v7-v10 | analisi sez. 11; contratti sez. 3 | test migrazione Slice 20, 24, 26, 27 | completato |
| result catalog | analisi sez. 12; contratti sez. 15; manuale sez. 13 | ricerca `catalog_version` e suite | parziale: envelope non uniforme |
| allow-incomplete | analisi sez. 10/14; contratti sez. 12-13; manuale sez. 9 | test Slice 26-27 + help | completato e limitato a DSL2/dynamic |
| riferimenti Aurora superati | nota storica e due guide correnti | test link + `test_slice_28_checksum_inventory_and_references` | completato |

La sola riga assegnata alla Slice 29 nella sezione 17 del design è quindi
verificata: documenti consolidati con controllo testuale automatico, senza nuovo
runtime. Lo stato globale resta parziale per i gap ereditati sopra.

## Matrice documentazione/capacità -> evidenza -> stato

| Documentazione/capacità | Evidenza nel codice | Test/verifica | Stato |
|---|---|---|---|
| foglia confirmed merge-eligible | `candidate_review.py`, `merge._merge_eligibility` | `test_slice_20_pending_not_mergeable` | implementata |
| replay prima della testa, no-op, expected head | `candidate_review.py` | test idempotency/stale head Slice 20 | implementata |
| correzione append-only e reconcile | v7, `candidate_review.py`, `reconciliation.py` | test correction/reconcile Slice 20/27 | implementata |
| effective views | viste SQL v7 | test effective support Slice 20 | implementata |
| regole DDL/XML/code/log/Excel | cataloghi in `candidate_derivation.py` | test matrix Slice 21/25 | implementata |
| batch consolidate/resume | `batch_consolidation.py` | test Slice 22/27 | implementata |
| ingest diretto `.xlsx`/`.xlsm` | `ooxml_preflight.py`, `normalize_docling.py` | test real workbook Slice 23 | implementata |
| manifest formula/cached/macro/link | workbook core/worker | golden/test Slice 24 | implementata |
| budget Excel/temporal | `config.py`, preflight/worker/temporal | boundary test Slice 23/24/27 | implementata |
| budget nodi+archi GEXF | assente da config/export | ricerca codice | mancante |
| raw temporal evidence e policy | v9-v10, `temporal.py`, `temporal_consolidation.py` | test Slice 26/27 | implementata |
| precisione/timezone/multi-spell | temporal core e graph export | test precision/spells Slice 27 | implementata |
| DSL2/diff cross-schema | `dsl_renderer.py`, `dsl_diff.py` | test Slice 26/27 | implementata |
| GEXF 1.3 offline doppio | `gexf_validation.py`, risorse package | test offline/semantic Slice 26 | implementata |
| `result_catalog_v1` uniforme | producer governance completi; OOXML numeric; temporal/GEXF incompleti | ricerca `catalog_version` | parziale |
| Aurora end-to-end | corpus/checksum/expected | test Slice 28 | implementata |

## Migrazioni/schema, API e artifact

Nessuna migrazione, tabella, API o comando è stato aggiunto/modificato dalla
Slice 29. Sono state documentate le migrazioni esistenti v7-v10 e i contratti
pubblici correnti.

Artifact documentati: candidate/review/derive/merge/reconcile report, checkpoint
batch, normalized JSON/Markdown, preflight e workbook manifest/fragments,
package AI, raw temporal evidence/intervalli, snapshot DSL/diff e GEXF/report.

Non sono state aggiunte dipendenze. `pyproject.toml` conserva le modifiche
preesistenti con `docling==2.97.0` e `lxml==6.1.2`.

## Diff/status

File della Slice 29:

```text
M  .kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md
M  .kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md
M  .kb/documenti/manuali/manuale_utente_dsl_manager.md
M  .kb/documenti/manuali/outline dsl manager flow from input to output.md
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl-manager-powershell.md
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl-manager_cmd.md
M  .kb/projects/corpus aurora/prompt_aurora+guida.md
?? tests/test_slice_29_documentation.py
?? .kb/projects/slicing/slice_29/dsl_manager_slice_29_report.md
```

Il `git status --short` finale contiene inoltre tutte le modifiche preesistenti
delle slice 20-28 già presenti al preflight; sono state preservate. Il diff
pertinente è esclusivamente documentale più il test testuale.

Diff stat dei sette file già tracciati, prima dell'aggiunta del report non
tracciato:

```text
7 files changed, 1333 insertions(+), 11430 deletions(-)
```

Il numero elevato di rimozioni deriva soprattutto dalla sostituzione del vecchio
transcript di 7.605 righe con un outline architetturale conciso e dalla rimozione
dei manuali pre-run-2 ormai obsoleti. I file nuovi non compaiono nel normale
`git diff --stat` finché non sono tracciati.

Il `git diff --stat` dell'intero worktree, che include anche le modifiche
preesistenti delle slice 20-28 ma non gli untracked, riporta:

```text
49 files changed, 6271 insertions(+), 11692 deletions(-)
```

## Test

Interprete usato: `.venv\Scripts\python.exe`, Python `3.12.10`.

Install editable eseguita:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
```

Risultato: exit `0`; package `dsl_mngr 0.1.0` installato editable, dipendenze dev
soddisfatte.

Baseline mirata prima delle modifiche:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest 'tests/test_slice_26_cli_contract.py' 'tests/test_slice_28_aurora_e2e.py::test_slice_28_checksum_inventory_and_references'
```

Risultato: `3 passed in 7.79s`, exit `0`.

Test mirato finale:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest 'tests/test_slice_29_documentation.py'
```

Risultati verdi: `4 passed in 1.01s`, poi `4 passed in 1.04s` dopo
l'inclusione del report nel link check; entrambi exit `0`.

Suite completa:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest
```

Prima esecuzione: `174 passed in 343.72s (0:05:43)`, exit `0`.

Esecuzione finale, ripetuta dopo l'ultimo cambiamento al test documentale:
`174 passed in 1090.83s (0:18:10)`, exit `0`. Nessun test skipped, interrotto o
xfailed in entrambe le suite.

### Tentativi falliti/interrotti

Due esecuzioni precedenti dello stesso test Slice 29 sono fallite:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest 'tests/test_slice_29_documentation.py'
```

- primo: `3 passed, 1 failed in 1.26s`, exit `1`; il checker cercava una frase
  oltre un newline Markdown;
- secondo: `3 passed, 1 failed in 1.03s`, exit `1`; lo stesso problema era
  presente nella nota blockquote del prompt storico.

Classificazione: **introdotti dalla Slice 29**, limitati al nuovo test e non al
runtime. Correzione: normalizzazione whitespace o assertion su una frase
stabile. La terza esecuzione e la suite completa confermano il fix.

Il primo script monolitico di confronto help è stato interrotto dal limite di
attesa a 30 secondi dopo i primi leaf command. Comando logico:

```powershell
foreach ($command in $allLeafCommands) {
    & '.\.venv\Scripts\dsl-manager.exe' @command --help
    & '.\.venv\Scripts\python.exe' -m dsl_mngr @command --help
}
```

Classificazione: **limite ambiente**, nessun errore CLI osservato. Verifica
alternativa: lo stesso elenco è stato diviso in tre gruppi e completato con
exit `0` e help equivalenti per tutti i leaf command. Il test Slice 29 confronta
inoltre il catalogo documentato e le opzioni citate direttamente con
`build_parser()`.

## Verifiche aggiuntive

Sono stati verificati, per entry point `dsl-manager` e modulo
`python -m dsl_mngr`, root help e tutti i leaf command documentati:

```text
init; db init;
corpus scan/normalize/chunk/parse-ddl/parse-xml-form/parse-db-code/parse-log;
batch process-dir/chunk-dir/consolidate;
candidates validate/validate-batch/derive;
candidates review list/show/confirm/reject/correct;
ai package/package-batch; ai inbox scan; ai import;
facts merge/merge-batch/reconcile;
dsl render/diff; graph export; run start/status;
log table/csv; ui serve
```

Esito: ogni `--help` exit `0`; output console script e modulo equivalenti.

`git diff --check`:

```text
exit 0; nessun whitespace error
```

Git ha emesso soltanto warning informativi LF -> CRLF per il worktree Windows.

Ricerche sistematiche sui file Slice 29:

- nessun nome path `slice_N`/`dsl_manager_slice_N` non zero-padded;
- nessun marker di mojibake o carattere sostitutivo Unicode;
- nessuna frase positiva che renda pending mergeabile, `.xlsm` una conversione,
  metadata una verità, XSD l'unica validazione o timestamp filesystem evidenza;
- l'unico match `.xlsm ... convertito` è la frase negativa “non viene
  convertito in `.xlsx`”;
- link locali risolti dal test documentale;
- riferimenti ZIP/root nel prompt Aurora confinati sotto una nota esplicita di
  documento storico e collegati agli artifact correnti.

Il diff completo pertinente è stato revisionato: non contiene modifiche sotto
`src/dsl_mngr`, migrazioni, fixture o golden.

## Scostamenti, gap e rischi

### Gap 1 — budget GEXF

Il design v02 dichiara 1.000.000 nodi+archi come default e 5.000.000 come hard
maximum. `DEFAULT_CONFIG`, le validazioni config e `graph_export.py` non
contengono tale limite. Stato documentato: `mancante`; impatto: grafi molto
grandi non ricevono il fail-closed/budget previsto. Owner storico: Slice 26.

### Gap 2 — `result_catalog_v1`

Review, derive, merge, reconcile e batch usano la stringa
`result_catalog_v1`. `ooxml_preflight.py` e il fallback worker usano il numero
`1`; temporalità e `graph_report.json` non contengono l'envelope minimo completo.
Stato documentato: `parziale`; impatto: un consumer non può trattare tutti i
report con un unico contratto senza adattatori. Owner storico: requisiti
trasversali consegnati fra Slice 23 e Slice 26.

Non sono stati trovati test falliti preesistenti. Nessun gap è stato nascosto
modificando test, fixture o golden.

## Fuori scope / note

- Nessuna feature runtime, migrazione, schema o nuova dipendenza.
- Nessun aggiornamento retroattivo di snapshot, graph export o report storici.
- Nessuna correzione runtime dei due gap ereditati.
- Nessuna chiamata di rete o AI reale.
- Nessuna esecuzione macro, ricalcolo formula o dereferenziazione link esterno.
- Design v01/v02 e report precedenti restano fonti storiche/normative e non sono
  stati riscritti.
- Modifiche preesistenti dell'utente preservate.

## Autoverifica finale

- Perimetro Slice 29 rispettato: solo docs e verifica documentale.
- Tutte le capacità richieste sono descritte secondo codice/test/help correnti.
- Compatibilità schema1/static e comportamento allow-incomplete sono espliciti.
- I divieti normativi sono espressi senza ambiguità.
- La riga di tracciabilità della sezione 17 è verificata.
- Suite completa verde e link/comandi verificati.
- Stato `parziale` coerente con i due gap runtime riproducibili.
