# Bugfix 01 — preflight temporale OOXML dei documenti DOCX

## Metadati

| Campo | Valore |
|---|---|
| ID | `BUGFIX_01` |
| Titolo | Preflight Excel applicato erroneamente ai documenti DOCX durante la derivazione temporale |
| Stato | `verificato` |
| Severità | Alta: blocco completo di `batch consolidate`, senza corruzione dati osservata |
| Data di rilevazione | 2026-09-09 |
| Data di correzione | 2026-09-09 |
| Release interessata | `1.1.0` |
| Release corretta | `1.1.0` nel working tree; nessun bump di versione eseguito |
| Baseline | branch `main`, commit `a644ebb` |
| Componente | `dsl_mngr.core.ooxml_preflight`, `dsl_mngr.core.temporal` |
| Scenario | Corpus Aurora; workspace `.workspaces/laboratorio_aurora`; run `RUN_000001` |
| Autore della correzione | Codex, su richiesta dell'utente |

## 1. Sintesi esecutiva

Il comando `batch consolidate` sul corpus Aurora completava la fase `parse` ma
falliva in `derive` con `Excel preflight requires an .xlsx or .xlsm name.`. La
pipeline classificava correttamente DOCX, PPTX, XLSX e XLSM come package OOXML,
ma l'estrattore temporale passava tutti questi formati al preflight strutturale
specifico per workbook Excel.

La correzione introduce un preflight per metadata Office OOXML: XLSX/XLSM
continuano a usare il validatore Excel esistente, mentre DOCX/PPTX ricevono una
validazione OPC coerente con il loro content type prima della lettura di core
properties, app properties e timestamp ZIP. È stato aggiunto un test di
regressione sulla fase `derive` con il DOCX reale del corpus Aurora.

## 2. Impatto e perimetro

| Dimensione | Valutazione |
|---|---|
| Utenti o workflow coinvolti | Workflow che eseguono `batch consolidate` su corpus contenenti `.docx`; `.pptx` era esposto alla stessa incompatibilità |
| Input interessati | Package Office OOXML `.docx` e `.pptx` durante l'estrazione temporale |
| Fasi interessate | `derive`, dopo il completamento della normalizzazione e dei parser |
| Dati e persistenza | La run osservata riportava `mutations: false`; `review`, `merge` e `reconcile` sono stati saltati dopo il fallimento |
| Sicurezza | Nessun bypass introdotto; il nuovo percorso valida il package prima di leggerne i metadata |
| Compatibilità | Nessuna modifica a CLI, database, schema, manifest workbook o formato degli artefatti |

Il preflight e la costruzione dei manifest Excel non erano difettosi: l'errore
era la loro applicazione a un tipo di documento diverso. PDF, HTML e formati di
testo non attraversano questo ramo e non sono interessati.

## 3. Rilevazione ed evidenze

### 3.1 Sintomo

```text
Error: Excel preflight requires an .xlsx or .xlsm name.
```

### 3.2 Evidenze verificabili

| Evidenza | Percorso o riferimento | Osservazione |
|---|---|---|
| Report della run | `../../../.workspaces/laboratorio_aurora/artifacts/runs/RUN_000001/batch_report.json` | `parse` completato con 27 item; `derive` fallito con reason `ooxml_security_violation` |
| Output della run | `../../../.workspaces/laboratorio_aurora/artifacts/runs/RUN_000001/output.json` | XLSX e XLSM risultano normalizzati prima del fallimento |
| Log della run | `../../../.workspaces/laboratorio_aurora/artifacts/runs/RUN_000001/log.jsonl` | registra il messaggio di errore della run parent |
| Codice precedente | `../../../src/dsl_mngr/core/temporal_consolidation.py` | `_OOXML_SUFFIXES` include `.docx`, `.pptx`, `.xlsx`, `.xlsm` |
| Guard precedente | `../../../src/dsl_mngr/core/ooxml_preflight.py` | `preflight_ooxml` accetta intenzionalmente solo `.xlsx` e `.xlsm` |

Il file che riproduce per primo il problema nell'ordinamento della run è
`documenti/nuovi_utili/manuale_ufficio_crediti_2024.docx`, revisione
`REV_000005`. La conclusione deriva dall'ordine delle revisioni e dalla guardia
sull'estensione; il report parent precedente non registrava l'ID dell'item
temporale che aveva sollevato l'eccezione.

## 4. Riproduzione

### 4.1 Prerequisiti

- release `1.1.0` prima della correzione;
- Python 3.12 e progetto installato in editable mode;
- workspace con database inizializzato e almeno una revisione DOCX registrata;
- per lo scenario originale, le 18 fonti attive del corpus Aurora.

### 4.2 Procedura minima

Scenario completo descritto dalla guida Aurora:

```bat
"%PY%" -m dsl_mngr corpus scan "%WS%"
"%PY%" -m dsl_mngr batch consolidate "%WS%"
```

La regressione automatizzata usa direttamente `_derive_phase` con la revisione
del DOCX Aurora, evitando che la verifica dipenda dai tempi di Docling.

### 4.3 Risultato atteso

La fase `derive` deve validare il package DOCX, persistere le evidenze temporali
grezze disponibili e proseguire verso le fasi successive.

### 4.4 Risultato effettivo prima della correzione

Il preflight Excel rifiutava il nome `.docx`; `derive` falliva con exit code 3 e
le fasi `review`, `merge` e `reconcile` venivano saltate.

## 5. Analisi della causa radice

### 5.1 Catena di chiamate o eventi

```text
batch consolidate
  -> _derive_phase
  -> _derive_temporal_candidates
  -> extract_temporal_evidence
  -> extract_ooxml_temporal_evidence
  -> preflight_ooxml (specifico Excel)
  -> rifiuto dell'estensione .docx
```

### 5.2 Causa tecnica

`extract_temporal_evidence` riconosceva quattro estensioni Office OOXML. Per
ognuna richiamava `extract_ooxml_temporal_evidence`, che usava
`preflight_ooxml`. Quest'ultimo è un validatore di workbook: oltre ai controlli
OPC comuni, richiede un content type Excel e una struttura workbook/sheet.

Il contratto dell'estrattore temporale e quello del preflight chiamato non
coincidevano quindi per DOCX/PPTX. Il messaggio non indicava un file Excel
malformato: segnalava che un DOCX valido era stato inviato al validatore errato.

### 5.3 Fattori contribuenti

- Il nome generico `preflight_ooxml` nascondeva il suo perimetro effettivo,
  limitato ai workbook Excel.
- I metadata temporali OOXML sono indipendenti dalla struttura specifica del
  documento, ma condividevano direttamente il preflight della Slice 23.
- Il report di errore della fase `derive` non includeva la revisione corrente,
  rendendo meno immediata l'identificazione del DOCX responsabile.

### 5.4 Perché i test non lo rilevavano

I test temporali della Slice 26 usavano un workbook `.xlsx`. Il workflow E2E
della Slice 28 orchestrava esplicitamente normalizzazione e derivazioni
selezionate, senza eseguire `batch consolidate` sull'intero albero Aurora. Il
test di retry batch usava soltanto sorgenti SQL. Mancava quindi un test della
fase `derive` con una revisione DOCX reale.

Il test negativo `workbook_malformed_controllato.xlsx` non copriva questo caso:
il suo nome `.xlsx` supera la guardia sull'estensione e verifica un package
malformato intenzionale.

## 6. Risoluzione

### 6.1 Decisione

È stato aggiunto `preflight_ooxml_metadata`, un punto di ingresso coerente con
i formati ammessi dall'estrattore temporale. Per XLSX/XLSM delega al preflight
Excel esistente. Per DOCX/PPTX verifica il package OPC e il content type del
documento senza richiedere strutture workbook.

Questa soluzione conserva l'estrazione dei metadata temporali dai documenti
Office e non riduce il perimetro funzionale previsto dal design.

### 6.2 Alternative considerate

| Alternativa | Esito | Motivazione |
|---|---|---|
| Rimuovere DOCX/PPTX da `_OOXML_SUFFIXES` | Scartata | Evita il crash ma elimina intenzionalmente evidenze core/app/ZIP già previste per OOXML |
| Accettare DOCX/PPTX nel preflight Excel | Scartata | Il validatore continuerebbe a richiedere workbook e sheet non presenti nei documenti Word/PowerPoint |
| Preflight metadata OOXML distinto con delega Excel | Adottata | Allinea il contratto ai formati, riusa i controlli esistenti e mantiene la validazione specifica Excel |

### 6.3 Modifiche implementate

| File o componente | Modifica | Contratto preservato o aggiornato |
|---|---|---|
| `src/dsl_mngr/core/ooxml_preflight.py` | Content type DOCX/PPTX e nuovo `preflight_ooxml_metadata` | Controlli Excel invariati; metadata Office ammessi solo dopo validazione OPC |
| `src/dsl_mngr/core/temporal.py` | L'estrattore temporale usa il nuovo entry point | Stessi record temporali e stessa persistenza append-only |
| `tests/test_slice_28_aurora_e2e.py` | Test di regressione sulla fase `derive` con `manuale_ufficio_crediti_2024.docx` e test negativo extension/content type | Verifica no-network, completamento, core properties, timestamp ZIP e rifiuto dei package rinominati |

Il nuovo percorso DOCX/PPTX verifica: firma e directory centrale ZIP; nomi
interni e collisioni; cifratura; budget di entry, decompressione, rapporto di
compressione, XML e relazioni; `[Content_Types].xml`; content type coerente con
l'estensione; XML ben formato senza DTD/entity; target interni esistenti;
relazione `officeDocument` unica e coerente. Non estrae file sul filesystem e
non dereferenzia target esterni.

## 7. Verifica

Interprete usato: `.venv\Scripts\python.exe`, Python `3.12.10`.

Installazione editable eseguita con successo:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

| Livello | Comando o test | Esito | Evidenza |
|---|---|---|---|
| Regressione + negativo Excel | `pytest -q tests\test_slice_28_aurora_e2e.py -k "batch_derive_accepts_docx_temporal_metadata or malformed_partial_budget_and_no_network"` | Passato | `2 passed, 3 deselected in 2.99s` |
| Scenario Aurora | `pytest -q tests\test_slice_28_aurora_e2e.py` | Passato | `6 passed in 40.37s` |
| Slice coinvolte | Slice 23, 24, 26, 27 e 28 | Passato salvo lock transitorio Docling | `32 passed, 1 failed in 355.22s`; il solo failure è passato al rerun |
| Rerun Docling | `test_slice_23_real_xlsx_docling` | Passato | `1 passed in 101.95s` |
| Suite completa prima del follow-up documentale | `.\.venv\Scripts\python.exe -m pytest` | Bug runtime verificato; tre failure documentali distinti | `176 passed, 3 failed in 339.79s` su 179 test raccolti |
| Suite completa finale | `.\.venv\Scripts\python.exe -m pytest` | Passato dopo `BUGFIX_02` | `179 passed in 330.96s` |
| Diff | `git diff --check` sui file di codice/test | Passato | Nessun errore; soli warning informativi LF/CRLF del working tree Windows |

I tre failure osservati prima del follow-up erano non correlati al runtime:
ognuno cercava `.kb/documenti/manuali/outline dsl manager flow from input to
output.md`, rinominato nel commit `a644ebb` senza aggiornare test e link
canonici. Il problema è stato corretto e documentato separatamente in
`BUGFIX_02`; la suite completa finale è verde.

In una precedente esecuzione, `test_slice_23_real_xlsx_docling` aveva inoltre
incontrato `WinError 32` eliminando `.worker_stdout.tmp`, ancora aperto da un
processo Windows. Lo stesso test è passato sia al rerun isolato sia nella suite
completa finale; l'episodio è quindi registrato come lock transitorio.

Tutti i test della Slice 28, incluso il nuovo test DOCX, sono passati durante la
suite completa.

## 8. Sicurezza, dati e compatibilità

- **Sicurezza:** nessuna estensione viene accettata senza allowlist e content
  type coerente. Restano vietati DTD/entity, path pericolosi, package cifrati e
  target esterni attivi; nessuna rete viene usata.
- **Dati:** nessuna migrazione. La persistenza delle evidenze temporali resta
  append-only e idempotente. La run originale non ha raggiunto merge/reconcile.
- **Compatibilità:** CLI, schema SQLite, report, manifest Excel e hash
  preesistenti non cambiano. XLSX/XLSM continuano a usare lo stesso validatore.
- **Prestazioni:** DOCX/PPTX vengono letti dal buffer acquisito e validati una
  volta prima dell'estrazione; il costo è lineare nel package e soggetto ai
  limiti configurati.

## 9. Recupero operativo

Dopo aver installato il codice corretto nello stesso ambiente, la run Aurora
fallita può essere ripresa come indicato dalla guida:

```bat
"%PY%" -m dsl_mngr batch consolidate "%WS%" --resume RUN_000001
```

La fase `parse`, già completata, deve essere riusata tramite checkpoint; la fase
`derive` viene ritentata. Candidati ed evidenze usano contratti idempotenti, ma
prima del resume è opportuno conservare gli artefatti della run fallita per
audit. Il resume della workspace reale non è stato eseguito durante la
correzione, per non mutare dati operativi senza una richiesta esplicita.

## 10. Tracciabilità

| Tipo | Riferimento |
|---|---|
| Design | `../../documenti di design/run 2/design_document_v_02.md`, sezione 12 |
| Guida scenario | `../../projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl_manager_cmd_v_02.md` |
| Codice | `../../../src/dsl_mngr/core/ooxml_preflight.py`; `../../../src/dsl_mngr/core/temporal.py` |
| Test | `../../../tests/test_slice_28_aurora_e2e.py::test_slice_28_batch_derive_accepts_docx_temporal_metadata` |
| Report runtime | `../../../.workspaces/laboratorio_aurora/artifacts/runs/RUN_000001/batch_report.json` |
| Template | `../../template/template_bugfix_report.md` |
| Commit/PR | Non ancora disponibile; modifiche nel working tree |
| Riepilogo progetto | `../project_summary.md` |

## 11. Rischi residui e follow-up

- Non è presente nel repository una fixture PPTX; il codice gestisce il suo
  content type, ma la copertura di regressione binaria è attualmente DOCX.
- Il report di fallimento batch potrebbe essere arricchito in futuro con
  `source_revision_id` e `file_path` della sorgente temporale corrente.
- Il lock transitorio Windows del worker Docling è un'osservazione distinta e
  non è stato modificato in questo bugfix.

## 12. Rollback

Il rollback consiste nel rimuovere il nuovo entry point, ripristinare la chiamata
a `preflight_ooxml` in `temporal.py` e rimuovere il test. Tale rollback
reintroduce il blocco per DOCX/PPTX e non richiede rollback di database o
artefatti persistenti.

## 13. Nota di rilascio proposta

> Corretto il consolidamento dei corpus contenenti documenti DOCX/PPTX: i
> metadata temporali Office vengono ora validati ed elaborati senza applicare
> erroneamente i requisiti strutturali dei workbook Excel.

## 14. Checklist di chiusura

- [x] Causa radice identificata e supportata da evidenze.
- [x] Riproduzione minima documentata.
- [x] Correzione limitata al perimetro necessario.
- [x] Test di regressione aggiunto e passato.
- [x] Suite pertinente eseguita.
- [x] Suite completa eseguita; failure non correlati documentati.
- [x] Sicurezza, dati, compatibilità e rollback valutati.
- [x] Recupero delle run già fallite documentato.
- [x] Riepilogo del progetto aggiornato.
- [x] Diff controllato e modifiche estranee preservate.

## 15. Fonti esterne, se utilizzate

| Fonte | Data di consultazione | Punto supportato |
|---|---|---|
| Nessuna | 2026-09-09 | Il codice, i test, il design e gli artefatti locali erano sufficienti e più autorevoli per questa correzione |
