# Report Slice 23

Implementata la Slice 23 end-to-end nello scope richiesto. Stato reale: **completata**. `.xlsx` e `.xlsm` seguono il percorso trasparente autorizzato; Docling 2.97.0 ha convertito entrambi i fixture reali come stream e il test reale `.xlsm` non ha richiesto fallback, rinomina, pre-conversione o downgrade.

## Aggiunto

- Acquisizione Excel a singola apertura in un buffer byte limitato, SHA-256 confrontato con `source_revisions.content_hash` prima del parsing e due cursori indipendenti sugli stessi byte immutabili.
- Preflight OPC/OOXML in memoria senza estrazione su disco: firma e directory ZIP, nomi sicuri, collisioni esatte/case-fold, content type, parti minime, XML well-formed senza DTD/entity, relazioni e target, limiti dichiarati ed effettivi in streaming.
- Routing `.xlsx`/`.xlsm` nel batch e profilo Docling predefinito. `.xlsm` richiede il content type macro-enabled e viene inoltrato con nome originale `.xlsm` e `InputFormat.XLSX`.
- Worker isolato con timeout, limite dell'output del processo e dell'output derivato, limite memoria e kill. Nell'ambiente Windows verificato il report dichiara `memory_limit_mode=monitored`; non viene presentato come limite hard. Il ramo POSIX usa `RLIMIT_AS` e dichiara `hard`.
- Pubblicazione degli artifact dopo staging completo, con sostituzione atomica per file; output del worker e report di rifiuto sono anch'essi pubblicati via file temporaneo e `os.replace`.
- Stati/reason catalogati: `source_revision_changed`, `ooxml_security_violation`, `ooxml_budget_exceeded`, `ooxml_external_target_invalid`, `normalization_operational_failure` e `normalization_partial`.
- Artifact Excel `normalized.md`, `normalized.json`, `source_hash.txt`, `docling_report.json` e `ooxml_preflight_report.json`.
- Fixture reali deterministiche:
  - `tests/fixtures/slice_23/real_workbook.xlsx`, SHA-256 `9ed7bda6d838c4142e7e673d5d6faba7e5e93a7e2fd6d83e0fb90b955aac0247`, 5.394 byte;
  - `tests/fixtures/slice_23/real_macro_workbook.xlsm`, SHA-256 `17f2858e53262098f899180d470a5390c3072ba5415e7d59a3cd9a4b2bd4caf4`, 10.033 byte;
  - il progetto VBA incorporato nel fixture `.xlsm` proviene dall'esempio ufficiale XlsxWriter e ha SHA-256 `0ced1464b3677e98f5e3a8c5d80135e18dc98dca39299f1a8cfd2a00999fbf9f`.
- Dodici test Slice 23, inclusi attacchi parametrizzati, limiti at/over, no-network reale, failure CLI catalogati, determinismo e regressioni dei formati legacy.

## Controllo anti-drift e precondizioni

Sono stati letti integralmente `AGENTS.md`, design v02, design v01 come baseline, template del report, analisi tecnica, contratti manifest, manuale utente e tutti i report Slice 01–22. Sono stati inoltre ispezionati `src/dsl_mngr`, test, fixture, expected, schema/migrazioni, help CLI e dipendenze installate.

Esito del gate:

| Voce | Stato iniziale | Evidenza/esito |
|---|---|---|
| Slice 10–11, normalizzazione/chunking Docling | pronta | Test baseline pertinenti eseguiti; regressioni finali verdi. |
| Slice 22, consolidamento batch | pronta con flake ambientale osservato | Il test del checkpoint ha avuto una volta `WinError 5`, poi è passato isolatamente e in tutte le suite complete. Nessuna modifica Slice 23 al checkpoint. |
| Schema e migrazioni | pronta | `source_revisions.content_hash` e `normalized_hash` già disponibili; nessuna migrazione Slice 23 prevista o aggiunta. |
| Routing Excel | gap non bloccante | Mancavano `.xlsx`/`.xlsm`; aggiunti senza cambiare i route legacy. |
| Singola sequenza byte | gap non bloccante | Il worker legacy riapriva il path per l'hash; il ramo Excel ora apre una volta e non usa più il path dopo l'acquisizione. |
| Preflight e isolamento risorse | gap non bloccante | Aggiunti validatore e limiti; Windows verificato in modalità monitored+kill. |
| Supporto diretto `.xlsm` Docling 2.97.0 | precondizione da provare | Prova reale riuscita con `conversion_status=success`; nessun blocco della Slice. |

Il worktree era già dirty prima della Slice 23 per modifiche e file non tracciati delle Slice 20–22, oltre al prompt di slicing. In particolare erano già modificati moduli CLI/core/test e già presenti i report e i nuovi moduli/test delle Slice 20–22. Tali cambi sono stati preservati. Le sole sovrapposizioni di file sono `core/config.py` e `core/batch.py`, estesi localmente senza rimuovere le modifiche preesistenti.

## Tracciabilità Slice 23

| Requisito design §17 / prompt | Implementazione | Test/evidenza | Esito |
|---|---|---|---|
| Byte singoli | `acquire_source_once`, `AcquiredSource.cursors`, ramo Excel del worker | `test_slice_23_single_byte_sequence` | Pass: una apertura, hash registry/preflight/Docling identici; mismatch exit 4. |
| `.xlsm` diretto | content type macro-enabled, `DocumentStream(name=*.xlsm)`, allowed/format option `InputFormat.XLSX` | `test_slice_23_real_xlsm_docling` | Pass reale Docling 2.97.0, status `success`. |
| Preflight sicuro | `core/ooxml_preflight.py` | `test_slice_23_ooxml_attacks` e test limiti/streaming/target | Pass: traversal, assoluti, drive, percent-evasion, duplicati, case-fold, DTD/entity, relazioni, parti mancanti e central directory. |
| Due viste Excel, responsabilità condivisa Slice 24 | una conversione Docling produce `normalized.json` e `normalized.md` | `test_slice_23_real_xlsx_docling` | Pass; due run producono gli stessi byte per output normalizzati e report preflight semantico. Manifest/regione rimandati alla Slice 24. |
| Estensione ↔ content type | `_select_workbook` | `test_slice_23_extension_content_type_must_match` | Pass per entrambi gli scambi `.xlsx`/`.xlsm`. |
| ZIP bomb/entry/streaming limits | budget central directory e conteggio decompressione effettiva | `test_slice_23_limits_at_boundary_and_over`, `test_slice_23_streaming_limit_uses_actual_bytes` | Pass at/over per file, entry, totale, ratio, XML, fogli, relazioni e output. |
| External link e no-network | validazione URI; nessuna dereferenziazione nel preflight o backend | `test_slice_23_real_external_link_is_never_dereferenced` | Pass con target HTTPS irraggiungibile e primitive di rete interdette. |
| Timeout/output/memory | runner limitato con kill e report risorse | `test_slice_23_worker_timeout_output_and_memory_modes` | Pass: tre termination mode distinti; Windows `monitored`. |
| Partial distinto | `partial_success` → status `partial`, reason `normalization_partial`, exit 6 | `test_slice_23_partial_is_distinct_and_atomic` | Pass anche attraverso il runner con exit 6 accettato e non degradato. |
| Compatibilità legacy/routing | alias e profilo estesi; route precedenti invariati | `test_slice_23_configuration_and_legacy_routes` più suite Slice 01–22 | Pass. |

Nessuna riga pertinente della matrice Slice 23 è rimasta non verificata.

## Contratti, API, schema e artifact

- Comando pubblico: sintassi invariata `dsl-manager corpus normalize <workspace> --revision <REV> [--profile ...]`; ora accetta revisioni `.xlsx`/`.xlsm` registrate.
- Exit code Excel: 0 completato, 3 rifiuto security/budget/target, 4 revisione cambiata, 5 failure operativo/risorse, 6 partial. Gli errori attesi non mostrano traceback.
- Persistenza: nessuna migrazione e nessuna modifica dello schema. `normalized_hash` viene aggiornato soltanto dopo output validato; i rifiuti security sono report-only e il mismatch non applica mutazioni.
- Artifact: path relativi al workspace con `/`; nessun path assoluto entra negli output semantici. Il report preflight registra hash, content type, contatori, limiti, assenza di esecuzione macro/rete/dereferenziazione e modalità memoria.
- Non sono state aggiunte dipendenze runtime. `pyproject.toml` conserva `docling==2.97.0`.

## Fonti ufficiali verificate

- Docling v2.97.0, formati supportati: <https://github.com/docling-project/docling/blob/v2.97.0/docs/usage/supported_formats.md>.
- Docling v2.97.0, mapping estensioni e `DocumentStream`: <https://github.com/docling-project/docling/blob/v2.97.0/docling/datamodel/base_models.py> e <https://github.com/docling-project/docling/blob/v2.97.0/docling/datamodel/document.py>.
- Docling v2.97.0, backend Excel su stream e `data_only=True`: <https://github.com/docling-project/docling/blob/v2.97.0/docling/backend/msexcel_backend.py>.
- Docling v2.97.0, `DocumentConverter`/`ExcelFormatOption`: <https://github.com/docling-project/docling/blob/v2.97.0/docling/document_converter.py>.
- ECMA-376, 5th edition, Part 2 — Open Packaging Conventions: <https://ecma-international.org/publications-and-standards/standards/ecma-376/>.
- Fixture VBA ufficiale XlsxWriter: <https://github.com/jmcnamara/XlsxWriter/blob/main/examples/vbaProject.bin>.

## Diff/status

File Slice 23 aggiunti:

```text
.kb/projects/slicing/slice_23/dsl_manager_slice_23_report.md
src/dsl_mngr/core/ooxml_preflight.py
tests/fixtures/slice_23/checksums.json
tests/fixtures/slice_23/real_macro_workbook.xlsm
tests/fixtures/slice_23/real_workbook.xlsx
tests/test_slice_23_excel_ingest.py
```

File Slice 23 modificati:

```text
src/dsl_mngr/cli/commands/corpus.py
src/dsl_mngr/core/batch.py                  # sovrapposto a cambi preesistenti Slice 22
src/dsl_mngr/core/config.py                 # sovrapposto a cambi preesistenti Slice 20
src/dsl_mngr/core/docling_adapter.py
src/dsl_mngr/core/worker_runner.py
src/dsl_mngr/core/workspace.py
src/dsl_mngr/workers/normalize_docling.py
```

Lo `git diff --stat` del worktree prima del presente report, che include anche le modifiche preesistenti Slice 20–22 e non include i file untracked, era:

```text
33 files changed, 2355 insertions(+), 131 deletions(-)
```

Lo stato Git finale resta intenzionalmente dirty: oltre ai file Slice 23 sopra elencati contiene tutte le modifiche preesistenti osservate al gate. Nessun file preesistente è stato ripristinato, cancellato o escluso.

## Test

Interprete usato: `.\.venv\Scripts\python.exe` / Python `3.12.10`.

Docling realmente importato/eseguito: `2.97.0` tramite `importlib.metadata.version("docling")`.

Install editable eseguita senza upgrade richiesti:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Risultato: exit 0; `docling==2.97.0` già soddisfatto, progetto reinstallato editable.

Baseline mirata prima delle modifiche:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_04_runs_worker_runner.py tests/test_slice_10_docling_normalization.py tests/test_slice_16_batch_orchestration.py tests/test_slice_22_batch_consolidation.py
```

Risultato iniziale: exit 1, `1 failed, 20 passed in 225.28s`. Fallimento: `test_slice_22_policy_absent_version_mismatch_and_zero_candidates`, `WinError 5` su `batch_checkpoint.tmp` → `batch_checkpoint.json`. Classificazione: **preesistente / flake ambiente Windows**. Verifica alternativa immediata:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_22_batch_consolidation.py::test_slice_22_policy_absent_version_mismatch_and_zero_candidates
```

Risultato: exit 0, `1 passed in 5.99s`; il test è poi passato in tutte le suite complete.

Test rapidi Slice 23 durante lo sviluppo:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_23_excel_ingest.py -k "not real_xlsx_docling and not real_xlsm_docling"
```

Primo risultato: exit 1, `1 failed, 8 passed, 2 deselected in 7.28s`. Il test memoria usava una soglia di 5 MB, superiore al working set osservato del piccolo processo fixture, e terminava per timeout. Classificazione: **test Slice 23 in sviluppo**, non difetto runtime. Soglia resa deterministica a 1 MB; rerun exit 0, `9 passed, 2 deselected in 1.67s`.

Dopo l'hardening finale, `-k "not real"` ha prodotto exit 0, `9 passed, 3 deselected in 11.53s`; il test attacchi isolato ha prodotto exit 0, `1 passed in 1.24s`.

Gate reali Docling:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_23_excel_ingest.py::test_slice_23_real_xlsx_docling tests/test_slice_23_excel_ingest.py::test_slice_23_real_xlsm_docling
```

Risultato: exit 0, `2 passed in 141.10s`. `.xlsm`: `docling_version=2.97.0`, `conversion_status=success`, contenuto atteso presente.

No-network reale con external relationship:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_23_excel_ingest.py::test_slice_23_real_external_link_is_never_dereferenced
```

Risultato: exit 0, `1 passed in 27.31s`.

Suite mirata completa definitiva, dopo l'hardening del catalogo e dei nomi/parti XML:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_23_excel_ingest.py
```

Risultato: exit 0, `12 passed in 389.04s`. Una precedente esecuzione completa mirata, prima dell'ultimo hardening, aveva prodotto `12 passed in 107.21s`.

Regressioni mirate ulteriori:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_04_runs_worker_runner.py
```

Risultato: exit 0, `6 passed in 3.49s`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_01_workspace_config_logging.py tests/test_slice_10_docling_normalization.py::test_docling_unsupported_option tests/test_slice_16_batch_orchestration.py -k "not end_to_end"
```

Risultato: exit 0, `10 passed in 13.83s`.

Verifica partial dopo l'estensione finale del test:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_slice_23_excel_ingest.py::test_slice_23_partial_is_distinct_and_atomic
```

Risultato: exit 0, `1 passed in 1.37s`.

Suite completa definitiva, eseguita dopo l'ultima modifica di codice:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
112 passed in 675.86s (0:11:15)
```

Non risultano test finali falliti, saltati, interrotti o non eseguibili. Ulteriori suite complete intermedie, tutte verdi, hanno prodotto `112 passed in 266.52s`, `112 passed in 256.36s` e `112 passed in 322.42s`; l'ultima riga sopra è l'esecuzione autorevole successiva a ogni modifica di codice.

## Verifiche aggiuntive

- `.\.venv\Scripts\dsl-manager.exe corpus normalize --help`: exit 0.
- `.\.venv\Scripts\python.exe -m dsl_mngr corpus normalize --help`: exit 0; help identico all'entry point.
- Probe reale su revisione `.xlsx` mutata tramite entrambi gli entry point: exit 4 per entrambi, solo messaggio `Error: ... exit_code=4`, nessun traceback.
- Prova diretta in un solo processo dei due stream reali: `.xlsx 2.97.0 success`, `.xlsm 2.97.0 success`; entrambi contenevano il testo atteso.
- `git diff --check`: exit 0; sole notice Git CRLF del worktree Windows, nessun errore whitespace.
- Revisione del diff pertinente completata; nessuna migrazione, dipendenza, golden o feature Slice 24 introdotta.

Durante un probe manuale iniziale il riconoscimento dell'estensione del dotfile `_rels/.rels` era errato e produceva exit 1; classificazione: **difetto introdotto durante lo sviluppo**, corretto prima dei test formali e coperto dalla suite finale. Un primo comando diagnostico usava inoltre `docling.__version__`, attributo non esposto dal package, e terminava con exit 1; la versione è stata poi verificata con `importlib.metadata`, senza impatto sul prodotto.

## Fuori scope / note

- Non sono stati implementati manifest Excel completo, regioni/candidati, vista raw dei fogli o semantica formula/cached value della Slice 24.
- Nessun ricalcolo, esecuzione macro, attivazione link/query, conversione LibreOffice, normalizzatore openpyxl sostitutivo, rinomina o downgrade.
- `openpyxl` è usato internamente dal backend Excel ufficiale Docling 2.97.0 con `data_only=True`; l'applicazione non lo invoca come normalizzatore alternativo.
- Nessun servizio esterno, ORM, chiamata AI o accesso rete è stato aggiunto.
- I warning CRLF di Git derivano dalla configurazione del worktree Windows e non sono errori di `git diff --check`.
