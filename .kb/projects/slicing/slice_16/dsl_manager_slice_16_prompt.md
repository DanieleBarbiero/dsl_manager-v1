Implementa solo la Slice 16 per DSL Manager v1.

Prima leggi e segui:
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
- `.kb/projects/slicing/slice_10/dsl_manager_slice_10_report.md`
- `.kb/projects/slicing/slice_11/dsl_manager_slice_11_report.md`
- `.kb/projects/slicing/slice_12/dsl_manager_slice_12_report.md`
- `.kb/projects/slicing/slice_13/dsl_manager_slice_13_report.md`
- `.kb/projects/slicing/slice_14/dsl_manager_slice_14_report.md`
- `.kb/projects/slicing/slice_15/dsl_manager_slice_15_report.md`
- il codice attuale sotto `src/dsl_mngr`
- i test attuali sotto `tests`

Task:
implementare il minimo incremento verticale per "Batch Orchestration".

Obiettivo:
- processare piu' sorgenti, revisioni, file candidati o batch candidati con un unico comando;
- creare una run padre `batch` e sub-run tracciabili per ogni item processato;
- continuare sugli errori per default, ma supportare `--stop-on-error`;
- produrre un report batch deterministico e leggibile;
- riusare i comandi/core gia' implementati per scan, normalize, chunk, parser, AI package, candidate validation e merge;
- non cambiare il significato pubblico delle slice precedenti.

Contesto attuale:
- Slice 1 ha introdotto workspace, config, logging JSONL e `log table`.
- Slice 2 ha introdotto SQLite, migrazioni, `runs` e `worker_runs`.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `start_run`, `complete_run`, `fail_run`, `run_worker`, artifact run e `parent_run_id`.
- Slice 5 ha introdotto import/validation candidati, `candidate_batches`, `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto merge idempotente di `facts`/`relations`.
- Slice 7 ha introdotto renderer DSL e `dsl_snapshots`.
- Slice 8 ha introdotto `dsl diff`.
- Slice 9 ha stabilizzato un golden test end-to-end senza AI reale.
- Slice 10 ha introdotto `corpus normalize` e worker `normalize_docling`.
- Slice 11 ha introdotto `corpus chunk` e worker `chunk_docling`.
- Slice 12 ha introdotto `corpus parse-ddl` e `source_fragments` DDL.
- Slice 13 ha introdotto `corpus parse-xml-form` e `source_fragments` XML.
- Slice 14 ha introdotto `corpus parse-db-code` e `corpus parse-log`.
- Slice 15 ha introdotto `ai package`, `ai inbox scan`, `ai import`, tabella `ai_packages` e stale detection.
- `runs.RUN_TYPES` contiene gia' `batch`; verifica lo stato reale prima di modificare.
- Le funzioni di orchestrazione esistenti potrebbero non accettare ancora `parent_run_id`; aggiungilo solo dove serve e senza rompere le CLI esistenti.

Decisione di scope:
- La Slice 16 deve orchestrare pezzi esistenti.
- Non deve riscrivere worker, parser, merge, renderer DSL, candidate validation o AI handoff.
- Non deve chiamare comandi CLI tramite subprocess per orchestrare il batch.
- Deve chiamare funzioni Python/core esistenti, o piccoli adapter interni, in modo testabile.
- Deve preferire report e artifact a nuove tabelle. Aggiungi una migration solo se strettamente necessaria.
- La run padre `batch` deve essere la sorgente primaria di audit del batch; le sub-run devono avere `parent_run_id` valorizzato con il run id del batch.

Scope:
- aggiungi un core piccolo e testabile per l'orchestrazione batch, per esempio:

```text
src/dsl_mngr/core/batch.py
```

- aggiungi il comando CLI batch e wiring in `src/dsl_mngr/cli/app.py`, per esempio:

```powershell
dsl-manager batch process-dir <workspace>
dsl-manager batch chunk-dir <workspace>
```

- aggiungi, nei namespace gia' esistenti, i comandi batch minimi:

```powershell
dsl-manager ai package-batch <workspace>
dsl-manager candidates validate-batch <workspace>
dsl-manager facts merge-batch <workspace>
```

- mantieni compatibilita' con:

```powershell
python -m dsl_mngr batch process-dir <workspace>
python -m dsl_mngr batch chunk-dir <workspace>
python -m dsl_mngr ai package-batch <workspace>
python -m dsl_mngr candidates validate-batch <workspace>
python -m dsl_mngr facts merge-batch <workspace>
```

- se serve, aggiungi opzionalmente `parent_run_id` a funzioni esistenti come:
  - `normalize_source_revision`
  - `chunk_source_revision`
  - `parse_ddl_source_revision`
  - `parse_xml_form_source_revision`
  - `parse_db_code_source_revision`
  - `parse_log_source_revision`
  - `build_ai_package`
  - funzioni usate da `candidates validate`
  - funzioni usate da `facts merge`

Mantieni il parametro opzionale e default `None`, cosi' i comandi singoli continuano a produrre run senza parent.

Comportamento atteso per la run padre:
- ogni comando batch crea una run padre con `run_type = "batch"`;
- `input.json` della run padre contiene almeno:
  - `batch_command`;
  - opzioni CLI risolte;
  - `stop_on_error`;
  - path input relativi al workspace;
  - lista item pianificati, se nota all'avvio;
- ogni item che esegue lavoro crea una sub-run con `parent_run_id = <run batch>`;
- item skipped non devono creare sub-run;
- la run padre termina:
  - `completed` se non ci sono item failed;
  - `failed` se almeno un item fallisce, anche se il batch ha continuato sugli item successivi;
- il comando CLI ritorna:
  - `0` se non ci sono item failed;
  - `2` se uno o piu' item falliscono;
- `--stop-on-error` interrompe la coda al primo failure;
- senza `--stop-on-error`, il batch processa tutti gli item possibili e poi segnala l'errore nel riepilogo finale.

Report batch:
- scrivi sempre un report JSON canonico sotto:

```text
artifacts/runs/RUN_000001/batch_report.json
```

- aggiorna anche `artifacts/runs/RUN_000001/process_report.json` con il riepilogo batch.
- il report deve contenere almeno:

```json
{
  "run_id": "RUN_000001",
  "run_type": "batch",
  "batch_command": "process-dir",
  "status": "completed",
  "stop_on_error": false,
  "summary": {
    "total": 3,
    "completed": 2,
    "failed": 0,
    "skipped": 1
  },
  "items": [
    {
      "item_id": "BITEM_000001",
      "kind": "parse_ddl",
      "status": "completed",
      "source_id": "SRC_000001",
      "source_revision_id": "REV_000001",
      "input_path": "corpus/active/schema_ordini.sql",
      "run_id": "RUN_000002",
      "error": null,
      "outputs": {
        "fragments": 6
      }
    }
  ]
}
```

Regole report:
- path sempre relativi al workspace e con `/`;
- ordine item stabile;
- nessun path assoluto;
- nessun contenuto sorgente lungo nei report;
- errori leggibili ma sintetici;
- se una sub-run fallisce, includi `run_id`, `kind`, `source_revision_id` o `input_path`, `status = "failed"` ed `error`.

Comportamento CLI comune:
- ogni comando batch stampa almeno:

```text
Run: RUN_000001
Command: process-dir
Items: 3
Completed: 2
Failed: 0
Skipped: 1
Report: artifacts/runs/RUN_000001/batch_report.json
```

- se ci sono failure, stampa anche un blocco compatto:

```text
Failed items:
- BITEM_000002 parse_xml_form REV_000002: <errore leggibile>
```

Comportamento atteso per `batch process-dir`:
- firma minima:

```powershell
dsl-manager batch process-dir <workspace> [--path corpus/active] [--stop-on-error]
```

- esegue `corpus scan` sulla directory indicata, riusando `scan_corpus`;
- dopo lo scan carica le revisioni correnti attive;
- pianifica item in ordine stabile per `file_path`;
- decide l'azione in modo conservativo:
  - `legacy_document` o estensioni `.md`, `.txt`, `.pdf`, `.docx`, `.pptx`, `.html`:
    1. `normalize`
    2. `chunk`, solo se normalize riesce;
  - `ddl` o SQL che contiene `CREATE TABLE`, `CREATE INDEX` o vincoli DDL:
    - `parse_ddl`;
  - `xml_form` o file `.xml` con root/form compatibile:
    - `parse_xml_form`;
  - `database_code` o SQL che contiene `CREATE TRIGGER`, `CREATE PROCEDURE`, `CREATE FUNCTION` o statement runtime rilevanti:
    - `parse_db_code`;
  - `log` o estensione `.log`:
    - `parse_log`;
  - sorgenti non riconosciute:
    - item `skipped` con reason `unsupported_source_type`;
- per un file SQL misto e' accettabile pianificare sia `parse_ddl` sia `parse_db_code`, purche' l'ordine sia deterministico;
- non generare candidati AI;
- non eseguire `facts merge`, `dsl render`, `dsl diff` o export GEXF;
- non fare chiamate di rete.

Comportamento atteso per `batch chunk-dir`:
- firma minima:

```powershell
dsl-manager batch chunk-dir <workspace> [--revision REV_000001]... [--profile docling.chunking] [--stop-on-error]
```

- se `--revision` e' indicato una o piu' volte, processa solo quelle revisioni;
- se `--revision` non e' indicato, processa tutte le revisioni attive con `normalized_hash` valorizzato;
- verifica che gli artifact normalizzati richiesti esistano, come fa `corpus chunk`;
- crea una sub-run `chunk` per ogni revisione processata;
- item senza input normalizzato valido sono `failed` o `skipped` solo se il motivo e' dichiaratamente non applicabile. Scegli una politica e coprila nei test.

Comportamento atteso per `ai package-batch`:
- firma minima:

```powershell
dsl-manager ai package-batch <workspace> [--revision REV_000001]... [--profile ai_package.default] [--stop-on-error]
```

- se `--revision` e' indicato, considera solo quelle revisioni;
- altrimenti considera tutte le revisioni attive che hanno almeno un chunk attivo o un fragment attivo;
- crea un package AI per ogni revisione, chiamando la logica di Slice 15 con `revision_ids=(REV_x,)`;
- ogni package build e' una sub-run `ai_package` con `parent_run_id` valorizzato;
- revisioni senza evidenze attive sono `skipped` con reason `no_active_evidence`;
- non importa candidati e non esegue merge.

Comportamento atteso per `candidates validate-batch`:
- firma minima:

```powershell
dsl-manager candidates validate-batch <workspace> [--input-dir ai/inbox] [--pattern *.jsonl] [--stop-on-error]
```

- legge file JSONL in ordine stabile nella directory indicata;
- default `--input-dir` = `ai/inbox`;
- default `--pattern` = `*.jsonl`;
- per ogni file crea una sub-run `candidate_validation`;
- riusa `import_candidate_file` e `validate_candidate_payload`;
- non esegue `facts merge`;
- non applica stale detection AI: quella resta responsabilita' di `ai import`. Se decidi di fare stale detection per file `AIPKG_000001_candidates.jsonl`, documentalo nel report e coprilo nei test.

Comportamento atteso per `facts merge-batch`:
- firma minima:

```powershell
dsl-manager facts merge-batch <workspace> [--batch CBATCH_000001]... [--stop-on-error]
```

- se `--batch` e' indicato una o piu' volte, processa solo quei candidate batch;
- se `--batch` non e' indicato, processa tutti i `candidate_batches` con `status = "completed"` in ordine di `batch_id`;
- per ogni batch crea una sub-run `merge`;
- riusa il core merge idempotente esistente;
- e' accettabile che un rerun segnali `facts`/`relations` esistenti, purche' non duplichi dati;
- non renderizza DSL automaticamente.

Failure mode:
- workspace non inizializzato: errore leggibile, exit code `2`, nessuna run parziale se possibile;
- database non inizializzato o migrazioni pendenti: errore leggibile, exit code `2`;
- nessun item trovato: run batch `completed`, report con `total = 0`, exit code `0`;
- item non supportato: `skipped`, non failure;
- errore di un worker/sub-run:
  - item `failed`;
  - report include `run_id` della sub-run, `exit_code` se disponibile e messaggio sintetico;
  - default: continua sugli item successivi;
  - con `--stop-on-error`: ferma la coda;
- failure durante la scrittura del report batch: comando fallisce con messaggio leggibile;
- non lasciare run padre `running` dopo un errore gestito.

Artifact:
- la run padre deve avere i file standard:

```text
artifacts/runs/RUN_xxxxxx/input.json
artifacts/runs/RUN_xxxxxx/output.json
artifacts/runs/RUN_xxxxxx/process_report.json
artifacts/runs/RUN_xxxxxx/resolved_config.yaml
artifacts/runs/RUN_xxxxxx/config_hash.txt
artifacts/runs/RUN_xxxxxx/log.jsonl
artifacts/runs/RUN_xxxxxx/batch_report.json
```

- `output.json` della run padre deve contenere lo stesso summary del batch report o un riferimento chiaro al report;
- le sub-run mantengono i loro artifact standard gia' esistenti;
- i log della run padre devono includere almeno `batch_started`, `batch_item_completed`, `batch_item_failed`, `batch_completed` o `batch_failed`.

Test minimi richiesti:
- `test_batch_report`
- `test_batch_continues_on_error`
- `test_batch_stop_on_error`

I test devono coprire almeno:
- workspace temporaneo con `tmp_path`;
- `dsl-manager init` e `dsl-manager db init`;
- `batch process-dir` su fixture piccole e deterministiche;
- almeno due item processabili con successo, preferibilmente DDL/XML/log per evitare Docling nei test lenti;
- una failure controllata di un item, per esempio XML malformed o profilo/parser non supportato;
- comportamento default: il batch continua dopo il primo errore e tenta gli item successivi;
- comportamento `--stop-on-error`: il batch si ferma al primo errore;
- parent run `batch` creata;
- sub-run con `parent_run_id` uguale al run id batch;
- `batch_report.json` presente e coerente con `process_report.json`;
- summary corretto: total/completed/failed/skipped;
- path relativi e senza `\`;
- output CLI con Run, Command, Items, Completed, Failed, Skipped, Report;
- compatibilita' `python -m dsl_mngr batch process-dir ...`;
- almeno uno smoke test o una sezione nello stesso test per:
  - `batch chunk-dir`;
  - `ai package-batch`;
  - `candidates validate-batch`;
  - `facts merge-batch`;
- nessun merge automatico durante `validate-batch`;
- nessun DSL render automatico durante `merge-batch`;
- nessuna chiamata AI reale o rete.

Fixture e dati test:
- usa fixture gia' esistenti quando possibile:
  - `tests/fixtures/ddl/schema_ordini.sql`
  - `tests/fixtures/xml_forms/form_cliente.xml`
  - `tests/fixtures/xml_forms/form_ordine.xml`
  - `tests/fixtures/db_code/trigger_ordini.sql`
  - `tests/fixtures/db_code/procedura_sconti.sql`
  - `tests/fixtures/logs/log_batch_ordini.log`
  - `tests/fixtures/ai_candidates/AIPKG_MANUALI_001_candidates.jsonl`
- evita Docling nei test Slice 16 se non serve: e' gia' coperto dalla Slice 10 e puo' essere lento;
- se devi testare `chunk-dir`, prepara output normalizzati minimi come fanno i test Slice 11;
- se devi testare `ai package-batch`, prepara chunks/fragments attivi come fa `tests/test_slice_15_ai_package.py`;
- non modificare i golden expected della Slice 9 salvo motivo esplicito e documentato.

Constraints:
- non implementare provider AI;
- non fare chiamate HTTP o integrazioni esterne;
- non generare candidati con euristiche nel core;
- non implementare GEXF, log viewer avanzato, UI, web/API/auth;
- non introdurre ORM;
- non aggiungere dipendenze runtime nuove salvo necessita' forte e motivata;
- non cambiare il contratto pubblico esistente di `corpus normalize`, `corpus chunk`, `corpus parse-*`, `ai package`, `ai import`, `candidates validate`, `facts merge`, `dsl render` o `dsl diff`;
- non fare scrivere ai worker nel database principale;
- non salvare path assoluti nel DB, nei manifest o negli artifact condivisibili;
- non salvare contenuti sorgente lunghi nei log applicativi;
- mantieni import assoluti da `dsl_mngr`;
- mantieni separati CLI, batch core, worker/core esistenti e persistence;
- mantieni implementazione piccola, leggibile e deterministica.

Done when:
- Slice 16 e' implementata nello scope sopra;
- `batch process-dir` crea run padre e sub-run tracciabili;
- `batch chunk-dir` processa piu' revisioni normalizzate;
- `ai package-batch` crea package per revisioni con evidenza attiva;
- `candidates validate-batch` valida piu' file JSONL;
- `facts merge-batch` fonde piu' candidate batch in modo idempotente;
- `--stop-on-error` funziona;
- il report batch e' creato e testato;
- i test Slice 16 esistono e passano;
- la suite completa passa;
- i comandi sono eseguiti con l'interprete configurato in `.codex/config.toml`;
- prima dei test hai eseguito install editable con l'interprete configurato;
- `git diff --check` non segnala errori;
- mostri diff/status e risultati test nel report finale;
- nessuna feature fuori scope e' stata aggiunta.

Prima di coding:
1. leggi i file indicati sopra;
2. dichiara brevemente i file che prevedi di toccare;
3. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
4. implementa;
5. esegui test mirati Slice 16 e poi tutta la suite con l'interprete corretto;
6. esegui `git diff --check`;
7. esegui una autoverifica finale su scope, test, diff, parent/sub-run, report batch e failure mode;
8. riassumi cosa e' stato aggiunto e cosa e' rimasto fuori scope.

salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_16/dsl_manager_slice_16_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
