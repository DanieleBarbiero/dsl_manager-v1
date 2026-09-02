Implementa solo la Slice 10 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/template/template_slice_report.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`
- `.kb/projects/slicing/slice_05/dsl_manager_slice_05_report.md`
- `.kb/projects/slicing/slice_06/dsl_manager_slice_06_report.md`
- `.kb/projects/slicing/slice_07/dsl_manager_slice_07_report.md`
- `.kb/projects/slicing/slice_08/dsl_manager_slice_08_report.md`
- `.kb/projects/slicing/slice_09/dsl_manager_slice_09_report.md`

Task:
Implementare la minima slice verticale funzionante per normalizzare documenti tramite Docling dietro adapter/worker, usando il profilo no-images della v1.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs`, `run_worker` e artifact deterministici.
- Slice 5 ha introdotto `chunks`, `source_fragments`, `candidate_batches`, `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto merge deterministico di `candidate_fact` e `candidate_relation`.
- Slice 7 ha introdotto renderer DSL JSON/YAML/Markdown e `dsl_snapshots`.
- Slice 8 ha introdotto `dsl diff` tracciabile.
- Slice 9 ha stabilizzato il golden pipeline test dell'MVP tecnico, usando un helper test-only per seminare `chunks`.
- La Slice 10 deve introdurre normalizzazione documentale reale, ma non deve ancora implementare chunking stabile: quello resta Slice 11.

Note tecniche Docling verificate il 2026-06-03:
- Docling e una dipendenza esterna; PyPI indica `docling` 2.97.0 pubblicata il 2026-06-03 e compatibile con Python `>=3.10,<4.0`.
- In Docling v2, `DocumentConverter.convert(...)` converte un singolo input e il documento si esporta con `result.document.export_to_markdown()` e `result.document.export_to_dict()`.
- Le pipeline options Docling includono opzioni per OCR, immagini di pagina e immagini di figure, tra cui concetti come `do_ocr`, `generate_page_images`, `generate_picture_images` e `force_full_page_ocr`.
- Riferimenti utili:
  - https://pypi.org/project/docling/
  - https://docling-project.github.io/docling/reference/document_converter/
  - https://docling-project.github.io/docling/reference/pipeline_options/
  - https://docling-project.github.io/docling/v2/

Scope:
- aggiungere Docling come dipendenza runtime con pin esplicito compatibile con Python 3.12, preferibilmente:

```toml
docling==2.97.0
```

- se durante l'implementazione risulta necessario usare una versione diversa, motivarlo nel report e mantenere comunque un pin riproducibile;
- aggiungere un adapter piccolo e isolato, per esempio:

```text
src/dsl_mngr/core/docling_adapter.py
```

- aggiungere un worker reale:

```text
src/dsl_mngr/workers/__init__.py
src/dsl_mngr/workers/normalize_docling.py
```

- il worker deve accettare il contratto gia usato da `run_worker`:

```powershell
python <worker_path> --input artifacts\runs\RUN_000001\input.json --output artifacts\runs\RUN_000001\output.json
```

- aggiungere un comando CLI minimo, integrato nello stile `argparse` esistente:

```powershell
dsl-manager corpus normalize <workspace> --revision REV_000001
```

- mantenere compatibilita con:

```powershell
python -m dsl_mngr corpus normalize <workspace> --revision REV_000001
```

- aggiungere, se serve per il test unsupported option, un'opzione piccola:

```powershell
--profile docling.no_images
```

che legge `configs/workers/<profile>.yaml`;
- aggiungere un profilo default no-images nel workspace inizializzato:

```text
configs/workers/docling.no_images.yaml
```

- usare un formato di config coerente con il parser minimale esistente oppure aggiungere un parser worker-profile molto piccolo basato su standard library;
- non introdurre PyYAML o altre dipendenze solo per leggere il profilo;
- scrivere gli output normalizzati sotto:

```text
normalized/<source_id>/<source_revision_id>/normalized.md
normalized/<source_id>/<source_revision_id>/normalized.json
normalized/<source_id>/<source_revision_id>/source_hash.txt
normalized/<source_id>/<source_revision_id>/docling_report.json
```

- aggiornare `source_revisions.normalized_hash` con hash deterministico del Markdown normalizzato;
- creare una run di tipo `normalize`;
- usare `worker_runner.run_worker` per invocare il worker, registrare `worker_runs` e gestire success/failure;
- aggiungere log JSONL applicativo per normalizzazione completata o fallita;
- aggiungere test deterministici per il comportamento richiesto.

Profilo no-images:
- la v1 non usa immagini come contenuto semantico;
- non estrarre immagini come evidenza primaria;
- non generare page images;
- non generare picture images;
- non produrre file immagine negli output standard della slice;
- non abilitare VLM/picture description;
- disabilitare OCR salvo profilo esplicito futuro;
- preservare tabelle in modo ragionevole se Docling le supporta;
- salvare nel report Docling la config risolta e la versione Docling usata.

Profilo default minimo consigliato:

```yaml
worker:
  name: normalize_docling
  version: "1.0"
docling:
  input_formats: "pdf,docx,pptx,html,md,txt"
  output_normalized_markdown: true
  output_normalized_json: true
  images_enabled: false
  image_export_mode: placeholder
  generate_page_images: false
  generate_picture_images: false
  ocr_enabled: false
  force_full_page_ocr: false
  tables_enabled: true
  tables_mode: auto
  strict_options_fail_on_unsupported_option: true
```

Se il parser YAML attuale non supporta questa struttura annidata, puoi:
- usare un profilo flat equivalente, purche sia documentato nel test e nel report;
- oppure estendere il parser in modo minimale e coperto da test.

Non fare un refactor generale della configurazione.

Expected behavior:
- il comando verifica che workspace e database siano inizializzati e migrati;
- il comando verifica che `source_revision_id` esista;
- la revision deve appartenere a una `source` esistente;
- la revision deve puntare a un file dentro il workspace;
- il file deve esistere;
- path assoluti o path traversal fuori workspace devono essere rifiutati con errore leggibile;
- il comando crea una run `normalize`;
- il comando invoca `normalize_docling` via `run_worker`;
- il worker legge il file sorgente e normalizza tramite l'adapter Docling;
- il worker scrive:
  - `normalized.md`;
  - `normalized.json`;
  - `source_hash.txt`;
  - `docling_report.json`;
- il worker produce `output.json` coerente con `run_worker`, includendo almeno:
  - `run_id`;
  - `worker_name`;
  - `worker_version`;
  - `status`;
  - `exit_code`;
  - `source_id`;
  - `source_revision_id`;
  - `input_path`;
  - `normalized_markdown_path`;
  - `normalized_json_path`;
  - `source_hash_path`;
  - `docling_report_path`;
  - `source_hash`;
  - `normalized_hash`;
  - `docling_version`;
  - `profile`;
- al successo, `worker_runs.status == "completed"`;
- al successo, `runs.status == "completed"`;
- al successo, `source_revisions.normalized_hash` viene aggiornato;
- rieseguire la normalizzazione della stessa revision puo creare una nuova run, ma deve produrre lo stesso `normalized_hash` a parita di input e config;
- i path salvati in output, report e database devono essere relativi al workspace e usare `/`;
- i log non devono contenere contenuti lunghi del documento.

Calcolo hash:
- `source_hash.txt` deve contenere l'hash SHA-256 del file sorgente, coerente con `source_revisions.content_hash`;
- `normalized_hash` deve essere SHA-256 del Markdown normalizzato con newline `\n`;
- non includere timestamp o path assoluti nel materiale usato per `normalized_hash`;
- il JSON normalizzato deve essere scritto in forma deterministica per quanto possibile:
  - UTF-8;
  - newline finale;
  - `sort_keys=True` quando si usa `json.dumps`;
  - niente path assoluti.

Gestione unsupported option:
- l'adapter deve tradurre solo opzioni applicative supportate verso le opzioni reali della versione Docling installata;
- se il profilo contiene un'opzione applicativa non supportata e `strict_options_fail_on_unsupported_option` e true:
  - il worker deve fallire prima di produrre output normalizzati;
  - il processo worker deve uscire con exit code `4`;
  - `worker_runs.exit_code` deve essere `4`;
  - `worker_runs.status` deve essere `failed`;
  - `runs.status` deve essere `failed`;
  - `process_report.json` o `log.jsonl` devono includere `unsupported_docling_option` e la chiave problematica;
  - `source_revisions.normalized_hash` non deve cambiare;
  - non deve partire alcun chunking.
- Il comando CLI puo restituire `2` se mantiene la convenzione locale degli errori leggibili, ma il worker deve conservare exit code `4`.

Output CLI minimo al successo:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Normalized hash: <sha256>
Markdown: normalized/SRC_000001/REV_000001/normalized.md
JSON: normalized/SRC_000001/REV_000001/normalized.json
Report: normalized/SRC_000001/REV_000001/docling_report.json
```

Artifact:
- `artifacts/runs/<run_id>/input.json` deve includere almeno:
  - `source_id`;
  - `source_revision_id`;
  - `input_path`;
  - `output_dir`;
  - `profile`;
  - `docling_options` o riferimento alla config risolta;
- `artifacts/runs/<run_id>/output.json` deve includere almeno il payload del worker;
- `artifacts/runs/<run_id>/process_report.json` deve avere:
  - `run_type = "normalize"`;
  - `status = "completed"` al successo;
  - una voce worker `normalize_docling`;
  - `artifact_dir` relativo;
  - `config_hash`;
- `artifacts/runs/<run_id>/resolved_config.yaml`, `config_hash.txt` e `log.jsonl` devono restare coerenti con Slice 4.

Test minimi richiesti:
- `test_docling_normalization_no_images`;
- `test_docling_unsupported_option`.

I test devono verificare almeno:
- un workspace temporaneo viene inizializzato con `tmp_path`;
- `configs/workers/docling.no_images.yaml` esiste o il profilo default e disponibile in modo equivalente;
- un piccolo file Markdown o HTML fixture viene copiato in `corpus/active`;
- `corpus scan` registra `SRC_000001` e `REV_000001`;
- `corpus normalize <workspace> --revision REV_000001` completa con exit code 0;
- `normalized.md`, `normalized.json`, `source_hash.txt` e `docling_report.json` vengono creati;
- `normalized.md` contiene testo leggibile proveniente dalla fixture;
- `normalized.json` e JSON valido;
- non vengono generati file immagine sotto `normalized/` o `artifacts/runs/`;
- `source_revisions.normalized_hash` e valorizzato ed e stabile su riesecuzione con stesso input/config;
- `runs` contiene run `normalize` completata;
- `worker_runs` contiene worker `normalize_docling` completato;
- `process_report.json` contiene path relativi e nessun `\`;
- il comando funziona anche via `python -m dsl_mngr`;
- il test unsupported option crea o usa un profilo con una chiave non supportata;
- il worker fallisce con exit code `4`;
- l'errore riporta `unsupported_docling_option`;
- non vengono creati output normalizzati validi per il caso fallito;
- nessuna regressione sulle slice 1-9.

Fixture consigliata:
- usare Markdown o HTML piccolo e locale, non PDF reali pesanti;
- non usare rete nei test;
- non usare AI reale;
- non dipendere da OCR;
- evitare assert fragili sull'intero JSON Docling se la struttura include campi variabili; verificare invece proprieta stabili, hash, file creati, no-images e testo essenziale.

Constraints:
- non implementare chunking stabile;
- non inserire record in `chunks`;
- non inserire record in `source_fragments`;
- non modificare candidate validation, merge, DSL render o diff;
- non implementare parser DDL/XML/SQL/log;
- non implementare AI package handoff;
- non implementare batch orchestration;
- non implementare GEXF;
- non implementare UI, web/API/auth o integrazioni esterne;
- non aggiungere ORM;
- non importare Docling fuori dall'adapter/worker dedicato;
- non fare chiamate di rete durante normalizzazione o test;
- non salvare path assoluti negli artifact o nel database;
- non generare immagini nella pipeline standard;
- non usare import da `src`;
- usare import assoluti da `dsl_mngr`;
- mantenere separati CLI, adapter/worker, persistence e test;
- mantenere l'implementazione piccola, leggibile e deterministica;
- i test devono usare `tmp_path`.

Done when:
- Slice 10 e implementata end-to-end nello scope richiesto;
- Docling e invocato solo dietro adapter/worker;
- il profilo no-images e rispettato;
- `normalized.md`, `normalized.json`, `source_hash.txt` e `docling_report.json` vengono prodotti;
- `source_revisions.normalized_hash` viene aggiornato in modo deterministico;
- unsupported option fallisce con worker exit code `4`;
- i test nuovi sono significativi;
- tutta la suite passa;
- non e stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l'interprete corretto;
5. mostra diff e risultato dei test, indicando l'interprete usato;
6. esegui una breve autoverifica finale contro scope, constraints e done criteria.

Report finale:

```text
salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_10/dsl_manager_slice_10_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
```
