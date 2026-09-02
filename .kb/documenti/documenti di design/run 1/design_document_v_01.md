# DSL Manager - documento di design v1.0

**Data:** 2026-05-25  
**Formato:** design document operativo, implementabile per slice verticali  
**Codifica consigliata:** UTF-8 senza BOM  
**Repository di riferimento:** `dsl_manager-v1`  
**Package Python:** `dsl_mngr`  
**Python:** `>=3.12,<3.13`

---

## 1. Sintesi

DSL Manager è un'applicazione locale per ricostruire in modo verificabile la conoscenza semantica di un sistema legacy.

L'applicazione non deve essere un generatore automatico di DSL. Deve essere un sistema di controllo, validazione, audit e rendering intorno a fonti eterogenee:

```text
documenti legacy
DDL
XML di form e schermate
procedure
trigger
log
note manuali
candidati prodotti da AI esterna
```

La regola principale resta:

```text
L'AI produce candidati.
L'applicazione produce stato, validazione, merge, DSL, export e audit.
```

Il DSL non è la memoria primaria. Il DSL è una vista generata a partire dal registry interno:

```text
fonti originali
  -> revisioni
  -> normalizzazioni
  -> chunk o frammenti strutturali
  -> pacchetti per AI esterna
  -> candidati importati
  -> validazione
  -> fatti, relazioni, mapping, conflitti, domande
  -> snapshot DSL
  -> export Markdown / YAML / JSON / GEXF
```

Questa versione rende il disegno più implementabile:

```text
- allinea la struttura al package reale `dsl_mngr`;
- separa MVP, v1 applicativa e sviluppi successivi;
- tratta l'AI non deterministica come scatola nera;
- introduce contratti più espliciti per ID, hash, database, worker e snapshot;
- aggiunge una scomposizione in slice verticali adatte a sviluppo assistito da AI;
- conserva i requisiti della prima stesura, salvo le parti AI/M365 lasciate volutamente non dettagliate.
```

### 1.1 Rinomine consolidate nella v1

La v1 usa nomi più generici rispetto alla stesura preliminare, che citava direttamente Copilot. La modifica è intenzionale: il core deve conoscere solo il contratto di handoff, non lo strumento specifico.

```text
modernize                         -> dsl-manager
copilot/                          -> ai/
copilot/outbox                    -> ai/outbox
copilot/inbox                     -> ai/inbox
CP_000001                         -> AIPKG_000001
copilot_packages                  -> ai_packages
COPILOT_PACKAGE_READY             -> AI_PACKAGE_READY
WAITING_FOR_COPILOT_CANDIDATES    -> WAITING_FOR_AI_CANDIDATES
copilot_candidates fixture         -> ai_candidates fixture
```

---

## 2. Principio Guida

Ogni informazione esposta nel DSL deve poter rispondere a queste domande:

```text
Da quale fonte arriva?
Da quale revisione?
Da quale chunk o frammento strutturale?
È esplicita, inferita, osservata, ambigua o confermata da un umano?
È ancora supportata da fonti attive?
Contraddice qualcosa?
È stata validata?
Quale run l'ha prodotta?
Quale snapshot DSL ne è influenzato?
```

Se il sistema non può rispondere, l'informazione non deve entrare nel registry come fatto attivo.

---

## 3. Obiettivi

### 3.1 Obiettivi MVP

L'MVP deve dimostrare il flusso end-to-end senza dipendere da Docling, da Copilot o da sistemi esterni:

```text
1. creare un workspace locale;
2. inizializzare un database SQLite;
3. registrare fonti e revisioni;
4. rilevare file aggiunti, modificati e cancellati;
5. produrre log JSONL;
6. importare candidati fixture JSONL;
7. validare candidati contro schema e registry;
8. fondere candidati validi in facts/relations/mappings;
9. renderizzare uno snapshot DSL YAML/JSON/Markdown;
10. confrontare due snapshot;
11. eseguire test deterministici con pytest e `tmp_path`.
```

### 3.2 Obiettivi v1 applicativa

La v1 completa aggiunge:

```text
1. normalizzazione documentale con Docling no-images;
2. chunking stabile;
3. parser DDL base;
4. parser XML form base;
5. parser SQL code base per procedure e trigger;
6. parser log base;
7. generazione pacchetti per AI esterna;
8. pausa esplicita in attesa dei candidati;
9. import batch dei candidati;
10. validazione evidence-or-reject;
11. merge idempotente;
12. export GEXF;
13. visualizzatore log HTML/CSV;
14. comandi batch;
15. golden tests su corpus finto.
```

### 3.3 Obiettivi v1.1 e successivi

Le evoluzioni successive possono includere:

```text
- UI locale minima;
- review human-in-the-loop;
- browser di candidati rifiutati;
- browser di conflitti;
- ricerca full-text locale;
- vector search locale;
- profili multipli di normalizzazione;
- integrazioni enterprise se autorizzate;
- UI nativa.
```

---

## 4. Non Obiettivi

La v1 non deve:

```text
1. chiamare direttamente un provider AI da codice core;
2. dipendere dalla memoria persistente di un assistente AI;
3. permettere all'AI di aggiornare database, registry, DSL o snapshot;
4. fondere dati senza spiegazione;
5. cancellare definitivamente fonti, revisioni, fatti o decisioni;
6. usare immagini estratte dai documenti nella pipeline standard;
7. implementare una UI complessa;
8. usare un database server;
9. usare un ORM salvo motivazione forte;
10. pretendere determinismo da componenti AI;
11. usare output reali di AI nei test automatici;
12. supportare concorrenza multiutente;
13. supportare deploy web aziendale;
14. implementare autenticazione;
15. integrare direttamente sistemi aziendali esterni.
```

---

## 5. Principi di Design

### 5.1 Registry First

Il registry è la memoria primaria.

Contiene almeno:

```text
sources
source_revisions
source_events
chunks
source_fragments
ai_packages
candidate_batches
candidate_records
rejected_candidates
facts
relations
mappings
conflicts
questions
review_decisions
dsl_snapshots
graph_exports
runs
worker_runs
logs
```

Il DSL è sempre generato dal registry.

### 5.2 Append-Only by Default

I record storici non vengono cancellati o modificati silenziosamente.

Quando qualcosa cambia:

```text
- si crea una nuova revisione;
- i record vecchi vengono marcati stale, superseded, unsupported o conflicted;
- il renderer decide cosa mostrare nello snapshot corrente;
- lo storico resta interrogabile.
```

### 5.3 Evidence-or-Reject

Un candidato entra nel registry solo se ha evidenza verificabile.

Per candidati testuali:

```text
source_revision_id deve esistere;
chunk_id deve esistere;
chunk_id deve appartenere alla source_revision_id indicata;
evidence_text deve essere presente nel chunk;
start_char/end_char, se presenti, devono essere coerenti o correggibili;
assertion_type deve essere esplicito, inferito, osservato o ambiguo.
```

Per DDL, XML, SQL code e log l'evidenza può essere:

```text
- frammento sorgente;
- range di righe;
- nodo XML;
- oggetto strutturale normalizzato;
- evento log normalizzato.
```

### 5.4 AI as Candidate Generator

L'AI non aggiorna mai:

```text
- database;
- registry;
- DSL;
- snapshot;
- export;
- decisioni di review.
```

L'AI può solo restituire candidati:

```text
candidate_fact
candidate_relation
candidate_mapping
candidate_conflict
candidate_question
```

### 5.5 Pipeline Sospendibile

La pipeline deve potersi fermare e riprendere.

Stati principali:

```text
SOURCE_REGISTERED
SOURCE_NORMALIZED
SOURCE_CHUNKED
AI_PACKAGE_READY
WAITING_FOR_AI_CANDIDATES
CANDIDATES_IMPORTED
CANDIDATES_VALIDATED
FACTS_MERGED
DSL_RENDERED
EXPORTS_GENERATED
FAILED
```

`WAITING_FOR_AI_CANDIDATES` è uno stato normale, non un errore.

### 5.6 Worker Isolati

Ogni worker specialistico è un processo Python autonomo:

```text
- riceve input espliciti;
- produce output espliciti;
- produce report;
- produce log;
- non scrive direttamente nel database principale;
- può fallire senza corrompere lo stato globale.
```

L'orchestratore valida l'output del worker e applica le mutazioni in transazione.

### 5.7 Configurazione Riproducibile

Ogni run deve salvare:

```text
resolved_config.yaml
config_hash.txt
input.json
output.json
process_report.json
log.jsonl
```

Precedenza:

```text
default interni
  < configs/project.yaml
  < configs/workers/<worker>.yaml
  < .env
  < opzioni CLI
```

### 5.8 Test Deterministici

I test automatici non devono dipendere da output AI reali.

La variabilità AI viene assorbita tramite:

```text
fixtures/candidate JSONL
schema validation
merge deterministico
golden output
review umana esplicita
```

---

## 6. Convenzioni di Progetto

### 6.0 Vista ad Alto Livello

```text
              Corpus locale
     docs / ddl / xml / sql / log / note
                    |
                    v
              Orchestrator
 scan / register / state / transactions / logs
                    |
                    v
          Worker Python isolati
 normalize / parse / chunk / package / render
                    |
                    v
       Artefatti normalizzati e chunk
 normalized / chunks / fragments / reports
                    |
                    v
              AI handoff
             outbox / inbox
                    |
                    v
          Import + validation + merge
                    |
                    v
            Registry SQLite locale
 facts / relations / mappings / conflicts / questions
                    |
                    v
       DSL snapshots / GEXF / diff / log viewer
```

### 6.1 Layout Repository

Il repository usa il layout `src/`:

```text
dsl_manager-v1/
  pyproject.toml
  src/
    dsl_mngr/
      __init__.py
      __main__.py
      main.py
      cli/
      core/
      workers/
  schemas/
  configs/
  tests/
```

`src` non è un package Python e non deve essere importato.

Import ammessi:

```python
from dsl_mngr.core.registry import Registry
from dsl_mngr.main import main
```

Import vietati:

```python
from src.dsl_mngr.main import main
import main
```

### 6.2 Nome Comando

Il package Python è `dsl_mngr`.

Il comando CLI pubblico consigliato è:

```text
dsl-manager
```

Per compatibilità con la prima stesura, `modernize` può essere mantenuto come alias opzionale. Gli esempi del documento usano `dsl-manager`; dove si trovano esempi legacy con `modernize`, considerarli equivalenti.

### 6.3 Moduli Principali

```text
src/dsl_mngr/
  core/
    database.py
    migrations.py
    ids.py
    hashing.py
    config.py
    logging_setup.py
    registry.py
    source_registry.py
    runs.py
    worker_runner.py
    schemas.py
    validation.py
    merge.py
    dsl_renderer.py
    dsl_diff.py
    graph_export.py
    log_viewer.py

  cli/
    app.py
    commands/
      init.py
      corpus.py
      source.py
      run.py
      batch.py
      ai.py
      candidates.py
      facts.py
      dsl.py
      graph.py
      log.py
      test.py

  workers/
    detect_source.py
    normalize_docling.py
    chunk_docling.py
    parse_ddl.py
    parse_xml_form.py
    parse_log.py
    parse_db_code.py
    build_ai_package.py
    import_candidates.py
    validate_candidates.py
    merge_facts.py
    render_dsl.py
    diff_dsl.py
    export_gexf.py
    render_log_table.py
```

### 6.4 Directory di Supporto

```text
schemas/
  source.schema.json
  source_revision.schema.json
  chunk.schema.json
  candidate_fact.schema.json
  candidate_relation.schema.json
  candidate_mapping.schema.json
  candidate_conflict.schema.json
  candidate_question.schema.json
  fact.schema.json
  relation.schema.json
  mapping.schema.json
  conflict.schema.json
  dsl.schema.json

configs/
  project.yaml
  workers/
    docling.no_images.yaml
    docling.chunking.yaml
    ddl.default.yaml
    xml_form.default.yaml
    log.default.yaml
    ai_package.default.yaml
    merge.default.yaml
    dsl_renderer.default.yaml
    gexf.default.yaml

manifests/
  pipeline_manifest.yaml
  worker_manifest.yaml
```

---

## 7. Workspace Locale

### 7.1 Struttura Directory

```text
workspace/
  .env
  configs/
    project.yaml
    workers/
      docling.no_images.yaml
      merge.default.yaml

  corpus/
    incoming/
    active/
    deleted/
    ignored/

  normalized/
    SRC_000001/
      REV_000001/
        normalized.md
        normalized.json
        source_hash.txt
        normalize_report.json

  chunks/
    SRC_000001/
      REV_000001/
        chunks.jsonl
        chunk_report.json

  fragments/
    SRC_000001/
      REV_000001/
        fragments.jsonl
        fragment_report.json

  ai/
    outbox/
      AIPKG_000001/
        instructions.md
        content.md
        source_manifest.json
        candidate_schema.json
        output_template.jsonl
        package_manifest.json
    inbox/
      AIPKG_000001_candidates.jsonl
    imported/

  artifacts/
    runs/
      RUN_000001/
        input.json
        output.json
        process_report.json
        resolved_config.yaml
        config_hash.txt
        log.jsonl

  exports/
    dsl/
    dsl_diff/
    graph/
    logs/

  logs/
    app.jsonl

  workspace.sqlite
```

### 7.2 Regole sui Percorsi

Nel database si salvano percorsi relativi al workspace, non percorsi assoluti, salvo log diagnostici espliciti.

Regole:

```text
- normalizzare separatori a `/` nel database;
- accettare input CLI Windows e POSIX;
- impedire path traversal fuori dal workspace;
- non salvare contenuti sorgente lunghi nei log.
```

---

## 8. Configurazione

### 8.1 `.env`

```env
MDW_WORKSPACE_DIR=.
MDW_DB_PATH=workspace.sqlite
MDW_LOG_LEVEL=INFO
MDW_DEFAULT_DOC_PROFILE=docling.no_images
MDW_AI_OUTBOX=./ai/outbox
MDW_AI_INBOX=./ai/inbox
MDW_ENABLE_WAL=true
```

### 8.2 `configs/project.yaml`

```yaml
project:
  name: dsl-manager
  default_language: it
  timezone: Europe/Rome

database:
  path: workspace.sqlite
  wal: true
  foreign_keys: true

logging:
  app_log_path: logs/app.jsonl
  per_run_logs: true
  jsonl: true

corpus:
  active_dir: corpus/active
  incoming_dir: corpus/incoming
  deleted_dir: corpus/deleted
  ignored_dir: corpus/ignored

ai_handoff:
  outbox_dir: ai/outbox
  inbox_dir: ai/inbox
  package_format: markdown_plus_json
```

### 8.3 Configurazione Risolta

Ogni worker riceve configurazione già risolta dall'orchestratore.

La configurazione risolta deve essere salvata in:

```text
artifacts/runs/RUN_xxxxxx/resolved_config.yaml
artifacts/runs/RUN_xxxxxx/config_hash.txt
```

---

## 9. Identificativi, Hash e Determinismo

### 9.1 ID Umani e ID Canonici

Gli ID leggibili sono comodi per debug:

```text
SRC_000001
REV_000001
CHK_000001
RUN_000001
FACT_000001
```

Gli ID derivati da contenuto sono utili per idempotenza:

```text
fact_key_hash
relation_key_hash
mapping_key_hash
registry_hash
dsl_hash
```

La v1 può usare ID sequenziali per record primari e hash canonici per deduplica.

### 9.2 Hash Contenuto

Per file sorgente:

```text
sha256(bytes originali)
```

Per JSON/YAML strutturato:

```text
serializzazione canonica con chiavi ordinate
UTF-8
newline finale normalizzato
sha256(serializzazione)
```

Per testo normalizzato:

```text
normalizzare newline a `\n`
preservare contenuto significativo
sha256(testo UTF-8)
```

### 9.3 Orologio e Timezone

Timestamp:

```text
ISO 8601 con offset
timezone di progetto, default Europe/Rome
```

Nei test è ammesso iniettare un clock deterministico.

---

## 10. Tipi di Fonte

### 10.1 Tipi Principali

```text
legacy_document
ddl
xml_form
database_code
log
manual_note
unknown
```

### 10.2 Sottotipi

```text
legacy_document:
  functional_manual
  technical_manual
  user_manual
  release_note
  unknown_document

ddl:
  table
  index
  constraint
  view
  mixed_ddl

xml_form:
  form
  screen
  widget_tree
  unknown_xml

database_code:
  procedure
  trigger
  function
  batch_sql
  mixed_sql_code

log:
  application_log
  batch_log
  error_log
  audit_log
```

### 10.3 Livelli di Autorità

```text
functional_documentation
technical_structure
runtime_code
runtime_observation
human_review
ai_inference
unknown
```

Il livello serve a distinguere:

```text
- cosa il sistema dovrebbe fare;
- cosa esiste nel database;
- cosa fa il codice;
- cosa è stato osservato;
- cosa l'AI ha inferito;
- cosa un umano ha confermato.
```

---

## 11. Database

### 11.1 Scelta

SQLite locale.

Se configurato:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
```

Nota operativa: se WAL è attivo, backup e copia del database devono usare procedure coerenti con WAL, non una semplice copia parziale del solo file `.sqlite`.

### 11.2 Tabelle Minime

```text
schema_migrations
sources
source_revisions
source_events
chunks
source_fragments
ai_packages
candidate_batches
candidate_records
rejected_candidates
facts
relations
mappings
conflicts
questions
review_decisions
dsl_snapshots
graph_exports
runs
worker_runs
```

### 11.3 `sources`

```text
source_id
logical_name
source_type
source_subtype
authority_level
first_seen_at
last_seen_at
current_revision_id
status
created_at
updated_at
```

Status:

```text
active
deleted_from_corpus
ignored
unknown
```

### 11.4 `source_revisions`

```text
source_revision_id
source_id
revision_number
content_hash
normalized_hash
file_path
file_size
detected_at
status
created_at
```

Status:

```text
active
superseded
deleted
invalid
```

### 11.5 `source_events`

```text
source_event_id
source_id
source_revision_id
event_type
event_timestamp
details_json
run_id
```

Eventi:

```text
source_added
source_modified
source_deleted
source_restored
source_ignored
source_reclassified
```

### 11.6 `source_fragments`

`source_fragments` rappresenta evidenza strutturale per sorgenti non chunked o semi-strutturate: DDL, XML, procedure, trigger e log.

```text
fragment_id
source_revision_id
fragment_type
sequence
path_or_selector
line_start
line_end
char_start
char_end
text
text_hash
metadata_json
status
created_at
```

`fragment_type`:

```text
ddl_table
ddl_column
ddl_constraint
xml_form
xml_field
xml_button
sql_procedure
sql_trigger
sql_statement
log_event
log_summary
unknown
```

Status:

```text
active
stale
superseded
invalid
```

Regole:

```text
- `source_revision_id` è obbligatorio;
- `sequence` è stabile a parità di input e parser version;
- `path_or_selector` contiene XPath, nome oggetto SQL, range logico o selettore equivalente;
- `line_start`/`line_end` sono preferiti per SQL e log;
- `char_start`/`char_end` sono preferiti per testo normalizzato;
- `text_hash` è sha256 del testo normalizzato del frammento;
- `metadata_json` contiene attributi strutturati, non testo lungo duplicato.
```

### 11.7 `questions`

`questions` conserva domande aperte prodotte da candidati AI, parser deterministici o review umana.

```text
question_id
source_revision_id
chunk_id
fragment_id
question_type
subject
question_text
status
candidate_record_id
review_decision_id
created_at
updated_at
```

Status:

```text
open
answered
dismissed
converted_to_review_decision
stale
```

Regole:

```text
- una domanda non modifica il DSL se non come `open_question`;
- una domanda può diventare review_decision;
- se la fonte di supporto diventa stale, anche la domanda diventa stale salvo conferma umana.
```

### 11.8 `runs`

```text
run_id
run_type
status
started_at
finished_at
parent_run_id
input_json
output_json
created_at
updated_at
```

`run_type`:

```text
scan
register
normalize
chunk
ai_package
candidate_import
candidate_validation
merge
dsl_render
dsl_diff
gexf_export
batch
log_table
test
```

### 11.9 `worker_runs`

```text
worker_run_id
run_id
worker_name
worker_version
status
input_path
output_path
report_path
log_path
exit_code
duration_ms
started_at
finished_at
```

### 11.10 Log nel Registry

I log applicativi sono file JSONL, non una tabella obbligatoria della v1.

Se in futuro servirà interrogazione SQL sui log, si potrà aggiungere una tabella derivata o una vista importabile senza cambiare il formato primario dei log.

---

## 12. Registro Corpus

### 12.1 Scansione

Comando:

```cmd
dsl-manager corpus scan corpus\active
```

Il comando deve:

```text
- calcolare hash dei file;
- confrontare con sources/source_revisions;
- individuare nuovi file;
- individuare file modificati;
- individuare file non più presenti;
- creare source_events;
- non processare automaticamente salvo flag esplicito.
```

Flag:

```cmd
dsl-manager corpus scan corpus\active --process-new --process-modified
```

### 12.2 File Modificati

Quando un file cambia:

```text
- viene creata nuova source_revision;
- la vecchia revision diventa superseded;
- i chunk della vecchia revision diventano stale se non riconfermati;
- i package AI precedenti diventano stale;
- i fact derivati solo dalla vecchia revision diventano possibly_stale;
- gli snapshot DSL precedenti restano immutati;
- una nuova pipeline può essere lanciata sulla nuova revision.
```

### 12.3 File Cancellati

Quando un file sparisce dal corpus:

```text
- source.status = deleted_from_corpus;
- current_revision resta memorizzata;
- i fact supportati solo da quella fonte diventano unsupported_by_active_sources;
- i fact supportati anche da altre fonti restano active;
- viene creato un source_event source_deleted.
```

---

## 13. Pipeline

### 13.1 Pipeline Standard

```text
01_scan_corpus
02_register_or_update_source
03_detect_source_type
04_normalize_source
05_parse_or_chunk_source
06_build_ai_package
07_pause_waiting_for_candidates
08_import_candidates
09_validate_candidates
10_merge_facts
11_render_dsl
12_export_graph_optional
13_render_log_table_optional
```

### 13.2 Documenti Legacy

```text
source file
  -> normalize_docling
  -> chunk_docling
  -> build_ai_package
  -> WAITING_FOR_AI_CANDIDATES
  -> import_candidates
  -> validate_candidates
  -> merge
  -> render DSL
```

### 13.3 DDL

```text
source sql
  -> parse_ddl
  -> structural facts diretti
  -> eventuale build_ai_package per mapping semantici
  -> validate
  -> merge
```

Estrazione deterministica minima:

```text
- tabelle;
- colonne;
- tipi;
- primary key;
- foreign key;
- indici;
- vincoli.
```

### 13.4 XML Form

```text
source xml
  -> parse_xml_form
  -> facts strutturali diretti
  -> eventuale build_ai_package per mapping semantici
  -> validate
  -> merge
```

### 13.5 Procedure e Trigger

```text
source sql code
  -> parse_db_code
  -> read/write/call/eventi diretti se rilevabili
  -> eventuale build_ai_package per interpretazione comportamentale
  -> validate
  -> merge
```

### 13.6 Log

```text
source log
  -> parse_log
  -> eventi osservati
  -> eventuale build_ai_package per pattern
  -> validate
  -> merge
```

---

## 14. Worker Isolati

### 14.1 Contratto Comune

Ogni worker accetta input JSON e produce output JSON/JSONL.

Esempio:

```cmd
python -m dsl_mngr.workers.parse_ddl --input artifacts\runs\RUN_000042\input.json --output artifacts\runs\RUN_000042\output.json
```

L'orchestratore deve invocare il worker con l'interprete Python corretto dell'ambiente corrente.

### 14.2 Input Comune

```json
{
  "run_id": "RUN_000042",
  "worker_name": "parse_ddl",
  "worker_version": "1.0",
  "workspace_dir": ".",
  "source_id": "SRC_000017",
  "source_revision_id": "REV_000003",
  "input_path": "corpus/active/ddl_clienti.sql",
  "output_dir": "artifacts/runs/RUN_000042",
  "config": {
    "profile": "ddl.default",
    "resolved_config_path": "artifacts/runs/RUN_000042/resolved_config.yaml"
  }
}
```

### 14.3 Output Comune

```json
{
  "run_id": "RUN_000042",
  "worker_name": "parse_ddl",
  "worker_version": "1.0",
  "status": "success",
  "exit_code": 0,
  "started_at": "2026-05-25T10:00:00+02:00",
  "finished_at": "2026-05-25T10:00:02+02:00",
  "duration_ms": 2000,
  "outputs": [
    {
      "type": "parsed_objects",
      "path": "artifacts/runs/RUN_000042/parsed_objects.jsonl",
      "record_count": 12
    }
  ],
  "errors": []
}
```

### 14.4 Exit Code

```text
0 = success
1 = validation_error
2 = parsing_error
3 = unsupported_input
4 = configuration_error
5 = external_tool_error
9 = unexpected_error
```

### 14.5 Mutazioni Database

Regola:

```text
I worker non scrivono direttamente sul database principale.
```

Flusso:

```text
worker produce output
  -> orchestrator valida output
  -> orchestrator apre transazione SQLite
  -> orchestrator applica mutazioni
  -> orchestrator logga commit/rollback
```

---

## 15. Docling nella v1

### 15.1 Posizione Architetturale

Docling è usato solo dietro adapter/worker:

```text
workers/normalize_docling.py
workers/chunk_docling.py
```

La logica applicativa non deve importare Docling direttamente fuori da questi adapter.

### 15.2 Profilo No-Images

La v1 non usa immagini come contenuto semantico:

```text
- non estrarre immagini come evidenza primaria;
- non inviare immagini al processo AI;
- non generare page images o picture images nella pipeline standard;
- disabilitare OCR salvo profilo esplicito futuro;
- preservare placeholder o riferimenti solo se utili per audit.
```

Config applicativa:

```yaml
worker:
  name: normalize_docling
  version: "1.0"

docling:
  input_formats:
    - pdf
    - docx
    - pptx
    - html
    - md
    - txt

  output:
    normalized_markdown: true
    normalized_json: true

  images:
    enabled: false
    image_export_mode: placeholder
    generate_page_images: false
    generate_picture_images: false

  ocr:
    enabled: false
    force_full_page_ocr: false

  tables:
    enabled: true
    mode: auto

  strict_options:
    fail_on_unsupported_option: true
```

L'adapter traduce la configurazione applicativa nelle opzioni reali della versione Docling installata.

### 15.3 Chunking

```yaml
worker:
  name: chunk_docling
  version: "1.0"

chunking:
  strategy: docling_hybrid
  max_tokens: 512
  merge_peers: true
  repeat_table_header: true
  include_headings: true
  include_page_numbers: true
  include_source_offsets: true
  min_chars: 200
  max_chars_hard_limit: 4000
  fallback_strategy: heading_then_paragraph
```

Ogni chunk normalizzato deve avere formato stabile:

```json
{
  "record_type": "chunk",
  "chunk_id": "CHK_000001",
  "source_id": "SRC_000001",
  "source_revision_id": "REV_000001",
  "chunker": "docling_adapter",
  "chunker_version": "1.0",
  "chunking_strategy": "docling_hybrid",
  "sequence": 1,
  "text": "contenuto del chunk",
  "normalized_text_hash": "sha256:...",
  "start_char": 0,
  "end_char": 1200,
  "page_start": 1,
  "page_end": 1,
  "metadata": {
    "headings": [],
    "tokens_estimate": 240
  }
}
```

Regole:

```text
- `chunker` identifica l'adapter applicativo;
- `chunking_strategy` identifica la strategia configurata;
- `normalized_text_hash` è calcolato sul testo del chunk dopo normalizzazione newline;
- offset e pagine restano top-level per semplificare evidence lookup e test;
- `metadata` contiene solo dettagli aggiuntivi non necessari alla validazione primaria.
```

### 15.4 Output dei Worker Docling

`normalize_docling` produce:

```text
normalized/<source_id>/<revision_id>/normalized.md
normalized/<source_id>/<revision_id>/normalized.json
normalized/<source_id>/<revision_id>/source_hash.txt
normalized/<source_id>/<revision_id>/docling_report.json
artifacts/runs/<run_id>/process_report.json
```

`chunk_docling` produce:

```text
chunks/<source_id>/<revision_id>/chunks.jsonl
chunks/<source_id>/<revision_id>/chunk_report.json
artifacts/runs/<run_id>/chunk_report.json
```

### 15.5 Version Pinning

L'implementazione deve:

```text
- fissare versioni in `pyproject.toml` o lock file;
- loggare versione Docling in ogni run;
- salvare configurazione risolta;
- fallire chiaramente se un'opzione configurata non è supportata;
- aggiornare golden fixture quando cambia output Docling.
```

Errore configurazione non supportata:

```text
exit_code: 4
error_type: unsupported_docling_option
```

---

## 16. AI Handoff come Scatola Nera

### 16.1 Scopo

Questa sezione definisce solo il contratto tra applicazione e componente AI esterna.

Non descrive:

```text
- quale prodotto AI venga usato;
- come venga invocato;
- come vengano gestiti prompt interni;
- come vengano gestite licenze, limiti, automazioni o connettori;
- come lavori internamente M365 Copilot o alternative future.
```

Questi aspetti sono volutamente fuori dal documento v1 finché le decisioni aziendali non sono finalizzate.

### 16.2 Input alla Scatola Nera

L'applicazione produce package in:

```text
ai/outbox/AIPKG_000042/
  instructions.md
  content.md
  source_manifest.json
  candidate_schema.json
  output_template.jsonl
  package_manifest.json
```

`package_manifest.json`:

```json
{
  "ai_package_id": "AIPKG_000042",
  "run_id": "RUN_000042",
  "source_ids": ["SRC_000017"],
  "source_revision_ids": ["REV_000003"],
  "chunk_ids": ["CHK_000001", "CHK_000002"],
  "created_at": "2026-05-25T10:10:00+02:00",
  "expected_output_file": "AIPKG_000042_candidates.jsonl",
  "candidate_schema_version": "1.0",
  "status": "ready"
}
```

### 16.3 Output dalla Scatola Nera

La scatola nera deposita candidati in:

```text
ai/inbox/AIPKG_000042_candidates.jsonl
```

Ogni riga deve essere JSONL e appartenere a uno dei tipi:

```text
candidate_fact
candidate_relation
candidate_mapping
candidate_conflict
candidate_question
```

### 16.4 Vincoli sul Contratto

Il sistema accetta solo candidati che:

```text
- citano source_revision_id;
- citano chunk_id o fragment_id;
- includono evidence_text o riferimento strutturale verificabile;
- dichiarano assertion_type;
- dichiarano confidence;
- rispettano schema JSON;
- non chiedono modifiche dirette al DSL.
```

### 16.5 Stati Package

```text
ready
exported
waiting
imported
validated
failed
stale
```

Un package è `stale` se una revisione o un chunk incluso viene sostituito prima dell'import dei candidati.

---

## 17. Candidate Schema

### 17.1 Tipi Ammessi

```text
candidate_fact
candidate_relation
candidate_mapping
candidate_conflict
candidate_question
```

### 17.2 Campi Comuni

```text
record_type
candidate_id
source_revision_id
chunk_id
fragment_id
assertion_type
confidence
evidence_text
notes
```

`chunk_id` è obbligatorio per documenti chunked. `fragment_id` può essere usato per DDL, XML, SQL code e log.

### 17.3 `assertion_type`

```text
explicit
inferred
ambiguous
observed
```

### 17.4 `confidence`

```text
high
medium
low
```

### 17.5 Candidate Fact

```json
{
  "record_type": "candidate_fact",
  "candidate_id": "CAND_001",
  "source_revision_id": "REV_000001",
  "chunk_id": "CHK_000001",
  "fact_type": "business_entity",
  "entity_name": "Cliente",
  "property_name": "description",
  "property_value": "Anagrafica dei clienti gestiti dal sistema",
  "assertion_type": "explicit",
  "confidence": "high",
  "evidence_text": "La funzione consente la gestione dell'anagrafica clienti.",
  "notes": ""
}
```

### 17.6 Candidate Relation

```json
{
  "record_type": "candidate_relation",
  "candidate_id": "CAND_002",
  "source_revision_id": "REV_000001",
  "chunk_id": "CHK_000002",
  "source_entity": "Cliente",
  "relation_type": "places",
  "target_entity": "Ordine",
  "assertion_type": "explicit",
  "confidence": "medium",
  "evidence_text": "Il cliente può inserire uno o più ordini.",
  "notes": ""
}
```

### 17.7 Candidate Mapping

```json
{
  "record_type": "candidate_mapping",
  "candidate_id": "CAND_003",
  "source_revision_id": "REV_000010",
  "chunk_id": "CHK_000100",
  "domain_entity": "Cliente",
  "technical_object": "ANCLI",
  "mapping_type": "domain_entity_to_table",
  "assertion_type": "inferred",
  "confidence": "medium",
  "evidence_text": "Tabella ANCLI con colonne CODCLI, RAGSOC, PIVA.",
  "notes": "Il nome e le colonne suggeriscono anagrafica clienti."
}
```

### 17.8 Candidate Conflict

```json
{
  "record_type": "candidate_conflict",
  "candidate_id": "CAND_004",
  "source_revision_id": "REV_000011",
  "chunk_id": "CHK_000105",
  "conflict_type": "different_values_same_property",
  "subject": "Ordine.status_values",
  "left_value": "BOZZA, CONFERMATO, EVASO, ANNULLATO",
  "right_value": "APERTO, CHIUSO",
  "assertion_type": "explicit",
  "confidence": "medium",
  "evidence_text": "Lo stato può assumere i valori APERTO o CHIUSO.",
  "notes": ""
}
```

### 17.9 Candidate Question

```json
{
  "record_type": "candidate_question",
  "candidate_id": "CAND_005",
  "source_revision_id": "REV_000012",
  "chunk_id": "CHK_000111",
  "question_type": "mapping_ambiguity",
  "question_text": "ANCLI rappresenta solo clienti o anche prospect?",
  "subject": "ANCLI",
  "assertion_type": "ambiguous",
  "confidence": "low",
  "evidence_text": "La tabella ANCLI contiene anagrafiche cliente e potenziali clienti.",
  "notes": ""
}
```

---

## 18. Validazione Candidati

### 18.1 Validazioni Obbligatorie

Ogni candidato deve superare:

```text
- JSON valido;
- schema JSON valido;
- record_type ammesso;
- source_revision_id esistente;
- chunk_id o fragment_id esistente;
- chunk/fragment appartenente alla source_revision indicata;
- evidence_text non vuoto, se richiesto dal tipo;
- evidence_text presente nel chunk o nel frammento strutturale;
- assertion_type ammesso;
- confidence ammessa;
- package non stale, salvo --allow-stale;
- nessun riferimento a sorgenti non incluse nel package;
- nessuna istruzione di modifica diretta al DSL.
```

### 18.2 Rejection

I candidati non validi vengono salvati in `rejected_candidates`:

```text
rejected_candidate_id
candidate_batch_id
raw_record_json
rejection_reason
rejection_details
created_at
```

Motivi:

```text
invalid_json
schema_validation_failed
unknown_source_revision
unknown_chunk
unknown_fragment
chunk_source_mismatch
fragment_source_mismatch
evidence_text_not_found
invalid_assertion_type
invalid_confidence
stale_package
```

### 18.3 Span Tolleranti

Se `start_char` e `end_char` sono presenti:

```text
- se corretti, vengono salvati;
- se errati ma evidence_text è trovato una sola volta, possono essere corretti;
- se ambigui, il candidato diventa needs_review;
- se impossibili, il candidato viene rifiutato.
```

---

## 19. Merge Deterministico

### 19.1 Obiettivo

Il merge trasforma candidati validi in:

```text
facts
relations
mappings
conflicts
questions
```

### 19.2 Idempotenza

Applicare due volte lo stesso candidato valido non deve duplicare il fatto.

Chiave fact canonica:

```text
hash(
  fact_type +
  canonical_entity_name +
  property_name +
  normalized_property_value +
  source_revision_id +
  chunk_or_fragment_id +
  evidence_text_hash +
  assertion_type
)
```

### 19.3 Regole Base

```text
stessa entità + stessa proprietà + stesso valore:
  aggiungi evidenza o ignora duplicato

stessa entità + stessa proprietà + valore diverso:
  crea conflict

nuovo technical_object:
  crea structural fact

mapping inferred:
  crea mapping con status pending_review o inferred

mapping explicit:
  crea mapping active, salvo conflitti

fonte cancellata:
  marca unsupported i fatti supportati solo da quella fonte

fonte modificata:
  marca stale i fatti derivati da revisioni superate, salvo riconferma
```

### 19.4 Stati Fact

```text
active
inferred
pending_review
stale
superseded
conflicted
unsupported
historical
rejected
```

### 19.5 Stati Mapping

```text
explicit
inferred
pending_review
confirmed_by_human
conflicted
rejected
stale
```

### 19.6 Conflitti

Un conflitto è un record esplicito, non un errore silenzioso:

```json
{
  "conflict_id": "CONF_000001",
  "conflict_type": "different_values_same_property",
  "entity_name": "Cliente",
  "property_name": "identifier",
  "fact_ids": ["FACT_000001", "FACT_000842"],
  "status": "open",
  "created_at": "2026-05-25T11:00:00+02:00"
}
```

---

## 20. DSL

### 20.1 Formati

La v1 deve produrre:

```text
exports/dsl/<snapshot_id>.full.yaml
exports/dsl/<snapshot_id>.full.json
exports/dsl/<snapshot_id>.full.md
```

Output opzionali:

```text
exports/dsl/<snapshot_id>.domain.yaml
exports/dsl/<snapshot_id>.data.yaml
exports/dsl/<snapshot_id>.ui.yaml
exports/dsl/<snapshot_id>.runtime.yaml
```

### 20.2 Struttura

```yaml
dsl_version: "1.0"
snapshot_id: DSL_SNAPSHOT_000001
generated_at: "2026-05-25T12:00:00+02:00"

domain:
  entities: {}
  business_rules: {}
  workflows: {}
  states: {}
  events: {}

data:
  tables: {}
  columns: {}
  keys: {}
  constraints: {}
  indexes: {}
  triggers: {}
  procedures: {}

ui:
  forms: {}
  fields: {}
  buttons: {}
  validations: {}
  navigation: {}

runtime:
  jobs: {}
  logs: {}
  observed_sequences: {}
  errors: {}
  integrations: {}

traceability:
  sources: {}
  facts: {}
  mappings: {}
  conflicts: {}
  assumptions: {}
  open_questions: {}
```

### 20.3 Markdown

Il Markdown è leggibile da persone, ma non è fonte primaria.

```text
# DSL snapshot DSL_SNAPSHOT_000001

## Domain

### Entity: Cliente

Status: partially_verified

Evidence:
- FACT_000001 - SRC_000001 / REV_000001 / CHK_000001

Mappings:
- ANCLI - inferred - medium

Open questions:
- Q_000004: ANCLI rappresenta Cliente o altra anagrafica?
```

### 20.4 Snapshot

Tabella `dsl_snapshots`:

```text
dsl_snapshot_id
created_at
run_id
source_revision_set_hash
fact_registry_hash
dsl_hash
full_yaml_path
full_json_path
full_md_path
status
```

---

## 21. DSL Diff

### 21.1 Comando

```cmd
dsl-manager dsl diff DSL_SNAPSHOT_000001 DSL_SNAPSHOT_000002
```

Output:

```text
exports/dsl_diff/DSL_SNAPSHOT_000001_vs_DSL_SNAPSHOT_000002.md
exports/dsl_diff/DSL_SNAPSHOT_000001_vs_DSL_SNAPSHOT_000002.json
```

Esempio Markdown:

```markdown
# DSL diff

From: DSL_SNAPSHOT_000001
To: DSL_SNAPSHOT_000002

## Added entities

- Ordine
  - caused by: FACT_000102, FACT_000103
  - sources: SRC_000004 REV_000001

## Modified mappings

### Cliente -> ANCLI

Old status: inferred
New status: confirmed_by_human
Decision: REVIEW_000012
```

### 21.2 Cosa Confrontare

```text
- entità aggiunte/rimosse/modificate;
- proprietà aggiunte/rimosse/modificate;
- mapping aggiunti/rimossi/modificati;
- relazioni aggiunte/rimosse/modificate;
- business rule aggiunte/rimosse/modificate;
- conflitti aperti/chiusi/nuovi;
- fonti che hanno causato il cambiamento;
- fact responsabili del cambiamento.
```

Ogni differenza deve avere almeno un riferimento a:

```text
fact_id
relation_id
mapping_id
conflict_id
review_decision_id
source_event_id
```

Se manca una causa tracciabile, il diff deve segnalarlo come errore.

---

## 22. Export GEXF

### 22.1 Obiettivo

Esportare una vista del DSL come grafo GEXF.

```cmd
dsl-manager graph export --snapshot DSL_SNAPSHOT_000001 --format gexf
```

### 22.2 Grafo

La v1 usa un grafo diretto:

```text
DiGraph
```

Motivo: il formato GEXF in NetworkX richiede una scelta coerente del tipo di grafo; la v1 evita mixed graph.

### 22.3 Tipi Nodo

```text
domain_entity
business_rule
workflow
table
column
form
field
procedure
trigger
job
log_event
source
```

### 22.4 Tipi Arco

```text
maps_to
has_column
reads
writes
calls
validates
edits
mentions
derives_from
conflicts_with
observed_in
```

### 22.5 Attributi

Nodo:

```text
node_id
label
node_type
status
confidence
source_count
fact_count
```

Arco:

```text
edge_type
confidence
assertion_type
fact_ids
source_ids
status
```

Config:

```yaml
graph:
  include_sources: true
  include_columns: true
  include_low_confidence: false
  include_conflicts: true
  directed: true
  node_label_strategy: readable
  strict_orphans: false
```

---

## 23. Logging

### 23.1 Formato

Log JSONL:

```text
logs/app.jsonl
artifacts/runs/RUN_000042/log.jsonl
```

### 23.2 Record

```json
{
  "timestamp": "2026-05-25T12:00:00+02:00",
  "level": "INFO",
  "run_id": "RUN_000042",
  "worker": "parse_ddl",
  "worker_version": "1.0",
  "source_id": "SRC_000017",
  "source_revision_id": "REV_000003",
  "event_type": "worker_started",
  "message": "DDL parsing started",
  "details": {}
}
```

Campi obbligatori:

```text
timestamp
level
event_type
message
```

Campi consigliati:

```text
run_id
worker
worker_version
source_id
source_revision_id
chunk_id
candidate_batch_id
duration_ms
exit_code
details
```

### 23.3 Livelli

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

### 23.4 Privacy Log

I log non devono contenere grandi porzioni di documenti.

Regola:

```text
- loggare ID, hash e percorsi relativi;
- evitare contenuti estesi;
- limitare evidence_text nei log;
- conservare evidence_text nei record candidati/fatti, non nel log generale.
```

---

## 24. Visualizzatore Log

### 24.1 Comandi

```cmd
dsl-manager log table logs\app.jsonl
dsl-manager log table artifacts\runs\RUN_000042\log.jsonl --output exports\logs\RUN_000042_log_table.html
dsl-manager log csv logs\app.jsonl --output exports\logs\app.csv
```

### 24.2 Output HTML

Caratteristiche:

```text
- HTML statico;
- tabella semplice;
- colonne principali;
- righe ordinate per timestamp;
- filtro testuale client-side opzionale;
- colori minimi per level;
- nessuna dipendenza server obbligatoria;
- link ai file artefatto se presenti.
```

Colonne default:

```text
timestamp
level
run_id
worker
event_type
source_id
source_revision_id
message
duration_ms
exit_code
```

### 24.3 Mini-Server Opzionale

```cmd
dsl-manager log serve --path logs\app.jsonl --port 8765
```

Il mini-server è utile ma non obbligatorio.

---

## 25. CLI

### 25.1 Libreria

Typer è consigliato per:

```text
- subcommands;
- type hints;
- help automatico;
- testabilità con CliRunner;
- sviluppo incrementale.
```

### 25.2 Comandi Principali

```cmd
dsl-manager init

dsl-manager corpus scan corpus\active
dsl-manager corpus scan corpus\active --process-new --process-modified
dsl-manager corpus status
dsl-manager corpus report

dsl-manager source add corpus\active\manuale_clienti.md
dsl-manager source refresh SRC_000001
dsl-manager source delete SRC_000001
dsl-manager source restore SRC_000001

dsl-manager run prepare SRC_000001
dsl-manager run status RUN_000001
dsl-manager run resume RUN_000001
dsl-manager run retry RUN_000001
dsl-manager run fail RUN_000001

dsl-manager batch process-dir corpus\active
dsl-manager batch process-dir corpus\active --types legacy_document,ddl,xml_form
dsl-manager batch chunk-dir normalized
dsl-manager batch package-waiting --max-chunks-per-package 10

dsl-manager ai package RUN_000001
dsl-manager ai package-batch --status SOURCE_CHUNKED
dsl-manager ai inbox-scan
dsl-manager ai import ai\inbox\AIPKG_000001_candidates.jsonl
dsl-manager ai import-batch ai\inbox

dsl-manager candidates validate RUN_000001
dsl-manager candidates validate-batch --status CANDIDATES_IMPORTED

dsl-manager facts merge RUN_000001
dsl-manager facts merge-batch --status CANDIDATES_VALIDATED

dsl-manager dsl render
dsl-manager dsl snapshot-list
dsl-manager dsl diff DSL_SNAPSHOT_000001 DSL_SNAPSHOT_000002
dsl-manager dsl export --snapshot DSL_SNAPSHOT_000001 --format yaml

dsl-manager graph export --snapshot DSL_SNAPSHOT_000001 --format gexf

dsl-manager log table logs\app.jsonl
dsl-manager log csv logs\app.jsonl
dsl-manager log show RUN_000001

dsl-manager test corpus
dsl-manager test fixtures
```

### 25.3 Batch Obbligatori

```cmd
dsl-manager batch process-dir corpus\active
dsl-manager batch chunk-dir normalized
dsl-manager ai package-batch
dsl-manager ai import-batch ai\inbox
dsl-manager candidates validate-batch
dsl-manager facts merge-batch
```

Ogni batch:

```text
- crea una run batch;
- crea sub-run per ogni item;
- continua dopo errori salvo --stop-on-error;
- produce report riepilogativo;
- logga successi e fallimenti;
- indica cosa riprocessare.
```

Esempio:

```cmd
dsl-manager batch process-dir corpus\active --stop-on-error false
```

---

## 26. UI

La v1 ha CLI come interfaccia primaria.

Motivi:

```text
- più semplice;
- più testabile;
- più adatta a batch;
- più facile da usare con Codex;
- meno rischio di spostare complessità nella UI.
```

UI locale opzionale:

```cmd
dsl-manager ui serve --port 8765
```

Vista minima:

```text
- stato run;
- log tabellare;
- candidati rifiutati;
- conflitti;
- diff snapshot;
- download export.
```

Regola:

```text
La UI non contiene logica di dominio.
```

Tecnologie possibili per UI nativa futura:

```text
- PySide / Qt;
- Tkinter minimale;
- Tauri con frontend statico.
```

---

## 27. Corpus Finto per Test

### 27.1 Directory

```text
tests/fixtures/corpus_initial/
  manuale_clienti.md
  manuale_ordini.md
  ddl_clienti.sql
  ddl_ordini.sql
  form_cliente.xml
  form_ordine.xml
  trigger_ordini.sql
  procedura_sconti.sql
  log_batch_ordini.log
```

### 27.2 `manuale_clienti.md`

```markdown
# Manuale gestione clienti

La funzione Gestione Clienti consente la gestione dell'anagrafica clienti.

Ogni cliente è identificato da un codice cliente. Per i clienti italiani possono essere valorizzati codice fiscale e partita IVA.

La schermata Cliente permette di inserire ragione sociale, indirizzo, provincia e partita IVA.

La cancellazione di un cliente non è consentita se esistono ordini aperti.
```

### 27.3 `manuale_ordini.md`

```markdown
# Manuale gestione ordini

Il cliente può inserire uno o più ordini.

Ogni ordine contiene una testata e una o più righe.

Lo stato dell'ordine può assumere i valori BOZZA, CONFERMATO, EVASO o ANNULLATO.

Quando un ordine viene confermato, il sistema registra la data di conferma.
```

### 27.4 `ddl_clienti.sql`

```sql
CREATE TABLE ANCLI (
  CODCLI CHAR(10) NOT NULL,
  RAGSOC VARCHAR(80) NOT NULL,
  PIVA CHAR(11),
  PROV CHAR(2),
  PRIMARY KEY (CODCLI)
);
```

### 27.5 `ddl_ordini.sql`

```sql
CREATE TABLE ORDTES (
  IDORD INTEGER NOT NULL,
  CODCLI CHAR(10) NOT NULL,
  STATO CHAR(12) NOT NULL,
  DATCONF DATE,
  PRIMARY KEY (IDORD),
  FOREIGN KEY (CODCLI) REFERENCES ANCLI(CODCLI)
);

CREATE TABLE ORDRIG (
  IDORD INTEGER NOT NULL,
  RIGA INTEGER NOT NULL,
  CODART CHAR(20) NOT NULL,
  QTA DECIMAL(9,2) NOT NULL,
  PRIMARY KEY (IDORD, RIGA),
  FOREIGN KEY (IDORD) REFERENCES ORDTES(IDORD)
);
```

### 27.6 `form_cliente.xml`

```xml
<form name="FRM_CLIENTE" title="Cliente">
  <field name="CODCLI" label="Codice cliente" table="ANCLI" column="CODCLI" required="true"/>
  <field name="RAGSOC" label="Ragione sociale" table="ANCLI" column="RAGSOC" required="true"/>
  <field name="PIVA" label="Partita IVA" table="ANCLI" column="PIVA"/>
  <button name="SAVE" label="Salva"/>
</form>
```

### 27.7 `form_ordine.xml`

```xml
<form name="FRM_ORDINE" title="Ordine cliente">
  <field name="IDORD" label="Numero ordine" table="ORDTES" column="IDORD" required="true"/>
  <field name="CODCLI" label="Cliente" table="ORDTES" column="CODCLI" required="true"/>
  <field name="STATO" label="Stato" table="ORDTES" column="STATO" required="true"/>
  <button name="CONFIRM" label="Conferma ordine"/>
</form>
```

### 27.8 `trigger_ordini.sql`

```sql
CREATE TRIGGER TRG_ORDTES_CONF
AFTER UPDATE OF STATO ON ORDTES
FOR EACH ROW
WHEN NEW.STATO = 'CONFERMATO'
BEGIN
  UPDATE ORDTES
  SET DATCONF = CURRENT_DATE
  WHERE IDORD = NEW.IDORD;
END;
```

### 27.9 `procedura_sconti.sql`

```sql
CREATE PROCEDURE PRC_CALCOLA_SCONTO (IN P_CODCLI CHAR(10), IN P_IDORD INTEGER)
BEGIN
  UPDATE ORDTES
  SET STATO = STATO
  WHERE IDORD = P_IDORD
    AND CODCLI = P_CODCLI;
END;
```

### 27.10 `log_batch_ordini.log`

```text
2026-01-15 22:00:01 INFO BATCH_ORDINI start
2026-01-15 22:00:03 INFO BATCH_ORDINI processed order IDORD=1001 CODCLI=C000000001
2026-01-15 22:00:04 WARN BATCH_ORDINI missing VAT for CODCLI=C000000002
2026-01-15 22:00:06 INFO BATCH_ORDINI end processed=2 warnings=1
```

---

## 28. Candidate Fixture per Test

File:

```text
tests/fixtures/ai_candidates/AIPKG_MANUALI_001_candidates.jsonl
```

Contenuto minimo:

```jsonl
{"record_type":"candidate_fact","candidate_id":"CAND_001","source_revision_id":"REV_MAN_CLIENTI_001","chunk_id":"CHK_MAN_CLIENTI_001","fact_type":"business_entity","entity_name":"Cliente","property_name":"description","property_value":"Anagrafica clienti gestita dal sistema","assertion_type":"explicit","confidence":"high","evidence_text":"La funzione Gestione Clienti consente la gestione dell'anagrafica clienti.","notes":""}
{"record_type":"candidate_fact","candidate_id":"CAND_002","source_revision_id":"REV_MAN_CLIENTI_001","chunk_id":"CHK_MAN_CLIENTI_001","fact_type":"business_rule","entity_name":"Cliente","property_name":"delete_rule","property_value":"La cancellazione di un cliente non è consentita se esistono ordini aperti.","assertion_type":"explicit","confidence":"high","evidence_text":"La cancellazione di un cliente non è consentita se esistono ordini aperti.","notes":""}
{"record_type":"candidate_fact","candidate_id":"CAND_003","source_revision_id":"REV_MAN_ORDINI_001","chunk_id":"CHK_MAN_ORDINI_001","fact_type":"business_entity","entity_name":"Ordine","property_name":"description","property_value":"Ordine inserito da un cliente, composto da testata e righe.","assertion_type":"explicit","confidence":"high","evidence_text":"Ogni ordine contiene una testata e una o più righe.","notes":""}
{"record_type":"candidate_relation","candidate_id":"CAND_004","source_revision_id":"REV_MAN_ORDINI_001","chunk_id":"CHK_MAN_ORDINI_001","source_entity":"Cliente","relation_type":"places","target_entity":"Ordine","assertion_type":"explicit","confidence":"high","evidence_text":"Il cliente può inserire uno o più ordini.","notes":""}
```

---

## 29. Expected Output dei Test

### 29.1 Entità

```text
Cliente
Ordine
RigaOrdine
```

### 29.2 Mapping Tecnici

```text
Cliente -> ANCLI
Ordine -> ORDTES
RigaOrdine -> ORDRIG
FRM_CLIENTE -> Cliente / ANCLI
FRM_ORDINE -> Ordine / ORDTES
```

I mapping derivati solo da nomi tecnici e colonne devono essere `inferred` o `pending_review`, salvo candidati espliciti.

### 29.3 Relazioni

```text
Cliente places Ordine
ORDTES has rows ORDRIG
ORDTES references ANCLI
ORDRIG references ORDTES
FRM_CLIENTE edits ANCLI
FRM_ORDINE edits ORDTES
TRG_ORDTES_CONF writes ORDTES.DATCONF
```

### 29.4 Business Rules

```text
Cliente.delete_rule:
  "La cancellazione di un cliente non è consentita se esistono ordini aperti."

Ordine.status_values:
  BOZZA, CONFERMATO, EVASO, ANNULLATO

Ordine.confirmation_date_rule:
  "Quando un ordine viene confermato, il sistema registra la data di conferma."
```

La regola sulla data conferma deve avere doppia evidenza:

```text
- manuale_ordini.md
- trigger_ordini.sql
```

---

## 30. Strategia di Test

### 30.1 Test Deterministici

Usare pytest e `tmp_path`.

Test principali:

```text
test_init_workspace
test_scan_initial_corpus
test_register_sources
test_docling_normalization_no_images
test_chunking_stable
test_parse_ddl
test_parse_xml_form
test_parse_db_code_trigger
test_parse_log
test_build_ai_package
test_import_candidate_fixture
test_validate_candidates
test_reject_candidate_missing_evidence
test_merge_facts_idempotent
test_render_dsl_snapshot
test_diff_dsl_snapshots
test_export_gexf
test_log_table_render
test_source_modified_cascade
test_source_deleted_cascade
```

### 30.2 Golden Tests

Input:

```text
tests/fixtures/corpus_initial
tests/fixtures/ai_candidates
```

Expected:

```text
tests/expected/expected_dsl.full.yaml
tests/expected/expected_graph_edges.json
tests/expected/expected_conflicts.json
```

### 30.3 Tolleranza

Il core deterministico non ha tolleranza:

```text
stesso input + stessa config + stessa versione dipendenze = stesso output
```

La variabilità AI viene assorbita prima tramite fixture, validazione, merge e review.

### 30.4 Test Batch

Verificare:

```text
- errore su una fonte non blocca tutto il batch;
- report batch indica success/failure per ogni item;
- --stop-on-error interrompe correttamente;
- log contengono run_id e worker corretti.
```

---

## 31. Failure Mode

### 31.1 Docling Fallisce

```text
- worker exit_code = 5 oppure 2;
- run status = FAILED;
- nessuna mutazione database parziale;
- report con errore;
- log con worker=normalize_docling;
- source_revision resta registrata ma non normalizzata.
```

### 31.2 Opzione Docling Non Supportata

```text
- exit_code = 4;
- error_type = unsupported_docling_option;
- indicare chiave config problematica;
- non procedere al chunking.
```

### 31.3 Candidate Fuori Schema

```text
- candidato in rejected_candidates;
- batch può comunque importare candidati validi;
- report con conteggio accepted/rejected.
```

### 31.4 Evidence Text Non Trovato

```text
- reject;
- reason = evidence_text_not_found;
- non entra nel registry.
```

### 31.5 Package Stale

```text
- import consentito solo con --allow-stale;
- default: reject batch;
- log WARNING.
```

### 31.6 Worker Produce Output Parziale

```text
- orchestrator valida output;
- se output incompleto, rollback;
- artifact resta disponibile per debug;
- run status = FAILED.
```

### 31.7 Merge Produce Conflitto

```text
- non è failure;
- crea conflict;
- DSL segnala conflitto aperto.
```

### 31.8 GEXF Trova Nodo Orfano

```text
- se strict: failure;
- se non strict: warning + nodo incluso con status orphaned.
```

---

## 32. Sicurezza e Privacy

### 32.1 Locale-First

```text
- nessun upload automatico;
- nessuna chiamata esterna obbligatoria;
- handoff AI manuale o gestito fuori dal core;
- log e artefatti locali.
```

### 32.2 Dati Sensibili

```text
- minimizzare contenuti nei log;
- usare hash e ID;
- conservare evidence_text solo dove serve;
- permettere pulizia artefatti temporanei;
- evitare path assoluti in export condivisibili.
```

### 32.3 Integrazioni Esterne

Ogni integrazione esterna resta fuori dal core finché non è formalizzata.

Il core espone solo:

```text
- outbox;
- inbox;
- manifest;
- import;
- validate;
- merge;
- audit.
```

---

## 33. Slice Verticali per Sviluppo Assistito da AI

Questa sezione divide l'applicazione in unità realizzabili da AI coding agent o da piccoli team. Ogni slice deve produrre valore end-to-end, avere test propri e ridurre il rischio della slice successiva.

### 33.1 Regole per le Slice

Ogni slice deve avere:

```text
- obiettivo funzionale;
- scope file chiaro;
- comando CLI o API verificabile;
- fixture minime;
- test deterministici;
- criteri di accettazione;
- nessuna dipendenza da output AI reale.
```

Le slice devono evitare refactor laterali. Se una slice richiede una migrazione, la migrazione fa parte della slice.

### 33.2 Slice 0 - Fondazione Repository

Obiettivo:

```text
rendere il progetto installabile, importabile e coerente con `src/dsl_mngr`.
```

Deliverable:

```text
- pyproject coerente;
- entry point CLI vuoto o minimale;
- struttura package;
- test smoke;
- documentazione comandi canonical.
```

Test:

```text
python -m pip install -e ".[dev]"
python -m pytest
python -m dsl_mngr
```

### 33.3 Slice 1 - Workspace, Config e Logging

Obiettivo:

```text
dsl-manager init crea un workspace locale valido.
```

Deliverable:

```text
- loader config;
- template workspace;
- `.env` esempio;
- logging JSONL;
- comando log table base;
```

Test:

```text
test_init_workspace
test_load_config_precedence
test_jsonl_log_record
```

### 33.4 Slice 2 - SQLite e Migrazioni

Obiettivo:

```text
inizializzare schema SQLite minimo e gestire migrazioni.
```

Deliverable:

```text
- database.py;
- migrations.py;
- schema_migrations;
- tabelle sources, source_revisions, source_events, runs, worker_runs;
- PRAGMA foreign_keys;
- WAL configurabile.
```

Test:

```text
test_database_init
test_migrations_idempotent
test_wal_config
```

### 33.5 Slice 3 - Corpus Scan e Source Registry

Obiettivo:

```text
rilevare added/modified/deleted e creare revisioni.
```

Deliverable:

```text
- hashing file;
- source_registry;
- corpus scan CLI;
- eventi source_added/source_modified/source_deleted;
- gestione path relativi.
```

Test:

```text
test_scan_initial_corpus
test_source_modified_cascade_minimal
test_source_deleted_event
```

### 33.6 Slice 4 - Runs e Worker Runner

Obiettivo:

```text
standardizzare run, worker_runs, input/output/report.
```

Deliverable:

```text
- runs.py;
- worker_runner.py;
- creazione artifacts/runs/RUN_x;
- resolved_config.yaml;
- gestione exit code;
- rollback su output invalido.
```

Test:

```text
test_run_lifecycle
test_worker_success_report
test_worker_failure_does_not_mutate_db
```

### 33.7 Slice 5 - Candidate Import e Schema Validation

Obiettivo:

```text
importare JSONL candidati fixture e separare validi/rifiutati.
```

Deliverable:

```text
- schemas candidate;
- candidate_batches;
- candidate_records;
- rejected_candidates;
- comando candidates validate;
```

Test:

```text
test_import_candidate_fixture
test_reject_invalid_json
test_reject_unknown_chunk
test_reject_candidate_missing_evidence
```

### 33.8 Slice 6 - Merge Facts Minimo

Obiettivo:

```text
trasformare candidate_fact e candidate_relation validi in registry.
```

Deliverable:

```text
- facts;
- relations;
- evidence links;
- hash idempotenza;
- conflitto base different_values_same_property.
```

Test:

```text
test_merge_facts_idempotent
test_merge_relation
test_merge_conflict
```

### 33.9 Slice 7 - DSL Renderer e Snapshot

Obiettivo:

```text
generare snapshot DSL da registry.
```

Deliverable:

```text
- dsl_renderer;
- YAML/JSON/Markdown;
- dsl_snapshots;
- dsl_hash;
- traceability section.
```

Test:

```text
test_render_dsl_snapshot
test_snapshot_hash_stable
test_dsl_contains_traceability
```

### 33.10 Slice 8 - DSL Diff

Obiettivo:

```text
confrontare due snapshot con cause tracciabili.
```

Deliverable:

```text
- dsl_diff;
- output JSON;
- output Markdown;
- errore se differenza senza causa.
```

Test:

```text
test_diff_added_entity
test_diff_modified_mapping
test_diff_requires_traceability
```

### 33.11 Slice 9 - Fixture Corpus e Golden Tests

Obiettivo:

```text
stabilizzare il comportamento end-to-end senza AI reale.
```

Deliverable:

```text
- corpus_initial;
- ai_candidates fixture;
- expected_dsl;
- expected_graph_edges;
- expected_conflicts.
```

Test:

```text
test_golden_full_pipeline
```

### 33.12 Slice 10 - Docling Adapter No-Images

Obiettivo:

```text
normalizzare documenti tramite Docling dietro adapter.
```

Deliverable:

```text
- normalize_docling worker;
- profilo no-images;
- normalized.md/json;
- docling_report;
- gestione unsupported option.
```

Test:

```text
test_docling_normalization_no_images
test_docling_unsupported_option
```

### 33.13 Slice 11 - Chunking Stabile

Obiettivo:

```text
produrre chunks.jsonl riproducibile.
```

Deliverable:

```text
- chunk_docling worker;
- chunk schema;
- text_hash;
- offsets;
- fallback heading/paragraph.
```

Test:

```text
test_chunking_stable
test_chunk_evidence_lookup
```

### 33.14 Slice 12 - Parser DDL

Obiettivo:

```text
estrarre struttura database senza AI.
```

Deliverable:

```text
- parse_ddl worker;
- tables/columns/keys/fk;
- fragments strutturali;
- facts strutturali.
```

Test:

```text
test_parse_ddl_tables
test_parse_ddl_foreign_keys
```

### 33.15 Slice 13 - Parser XML Form

Obiettivo:

```text
estrarre form, field, button e mapping tecnici.
```

Deliverable:

```text
- parse_xml_form worker;
- fields required;
- table/column references;
- relation edits.
```

Test:

```text
test_parse_xml_form
test_form_edits_table_relation
```

### 33.16 Slice 14 - Parser SQL Code e Log

Obiettivo:

```text
estrarre read/write/call/eventi osservati.
```

Deliverable:

```text
- parse_db_code worker;
- parse_log worker;
- procedure/trigger facts;
- log_event facts;
- observed_in relations.
```

Test:

```text
test_parse_db_code_trigger
test_parse_log
```

### 33.17 Slice 15 - AI Package Handoff

Obiettivo:

```text
produrre outbox package e importare inbox senza conoscere internals AI.
```

Deliverable:

```text
- build_ai_package worker;
- package_manifest;
- candidate_schema;
- output_template;
- inbox scan;
- stale package detection.
```

Test:

```text
test_build_ai_package
test_ai_package_stale
test_import_batch
```

### 33.18 Slice 16 - Batch Orchestration

Obiettivo:

```text
processare directory e code di lavoro con sub-run.
```

Deliverable:

```text
- batch process-dir;
- batch chunk-dir;
- ai package-batch;
- validate-batch;
- merge-batch;
- report batch;
- --stop-on-error.
```

Test:

```text
test_batch_continues_on_error
test_batch_stop_on_error
test_batch_report
```

### 33.19 Slice 17 - Export GEXF

Obiettivo:

```text
esportare grafo navigabile del DSL.
```

Deliverable:

```text
- graph_export;
- GEXF;
- nodi e archi tipizzati;
- orphan handling.
```

Test:

```text
test_export_gexf
test_gexf_orphan_warning
```

### 33.20 Slice 18 - Log Viewer

Obiettivo:

```text
rendere leggibili i log senza UI complessa.
```

Deliverable:

```text
- HTML statico;
- CSV;
- filtro client-side opzionale;
- link artifact.
```

Test:

```text
test_log_table_render
test_log_csv_render
```

### 33.21 Slice 19 - UI Locale Opzionale

Obiettivo:

```text
offrire una vista read-only dello stato senza spostare logica nella UI.
```

Deliverable:

```text
- mini server;
- run list;
- log viewer;
- rejected candidates;
- conflicts;
- snapshot diff.
```

Test:

```text
test_ui_routes_smoke
```

---

## 34. Roadmap

### 34.1 MVP Tecnico

```text
- Slice 0-9;
- nessun Docling obbligatorio;
- nessun AI reale;
- registry, validation, merge, DSL e diff funzionanti;
- golden test base.
```

### 34.2 v1 Applicativa

```text
- Slice 10-18;
- Docling no-images;
- parser tecnici base;
- handoff AI black-box;
- batch;
- GEXF;
- log viewer.
```

### 34.3 v1.1

```text
- review human-in-the-loop;
- conflict browser;
- candidate browser;
- profili Docling multipli;
- miglior parser SQL;
- mini UI locale.
```

### 34.4 v2 Prodotto

```text
- UI nativa o web locale più ricca;
- ricerca full-text;
- vector search locale;
- versionamento DSL avanzato;
- esportazioni aggiuntive;
- integrazioni enterprise autorizzate.
```

---

## 35. Acceptance Criteria

La v1 è accettabile se:

```text
1. dsl-manager init crea un workspace valido.
2. dsl-manager corpus scan rileva added/modified/deleted.
3. SQLite viene inizializzato con schema e migrazioni.
4. I log JSONL contengono run_id e worker quando applicabile.
5. Docling normalizza documenti senza usare immagini.
6. Il chunking produce chunk stabili a parità di input/config.
7. I worker falliscono isolatamente.
8. Il sistema genera package AI.
9. Il sistema resta in WAITING_FOR_AI_CANDIDATES.
10. Il sistema importa candidati JSONL.
11. Il validatore scarta candidati senza evidenza.
12. Il merge è idempotente.
13. Il DSL viene generato dal registry.
14. Due snapshot DSL sono confrontabili.
15. L'export GEXF viene prodotto.
16. Il log viewer genera HTML e CSV.
17. I comandi batch processano directory.
18. Il corpus finto produce expected output.
19. I test automatici passano senza chiamare AI reale.
20. Ogni differenza DSL ha causa tracciabile.
```

---

## 36. Riferimenti Tecnici

Riferimenti progettuali, non dipendenze obbligatorie:

```text
Docling DocumentConverter:
https://docling-project.github.io/docling/reference/document_converter/

Docling pipeline options:
https://docling-project.github.io/docling/reference/pipeline_options/

Docling chunking:
https://docling-project.github.io/docling/concepts/chunking/

Docling CLI:
https://docling-project.github.io/docling/reference/cli/

Docling v2:
https://docling-project.github.io/docling/v2/

JSON Schema Draft 2020-12:
https://json-schema.org/draft/2020-12

Python logging:
https://docs.python.org/3/library/logging.html

Python logging cookbook:
https://docs.python.org/3/howto/logging-cookbook.html

SQLite WAL:
https://www.sqlite.org/wal.html

NetworkX GEXF:
https://networkx.org/documentation/stable/reference/readwrite/gexf.html

NetworkX write_gexf:
https://networkx.org/documentation/stable/reference/readwrite/generated/networkx.readwrite.gexf.write_gexf.html

pytest tmp_path:
https://docs.pytest.org/en/stable/how-to/tmp_path.html

python-dotenv:
https://pypi.org/project/python-dotenv/

Typer:
https://typer.tiangolo.com/
```

---

## 37. Nota Finale per l'Implementatore

Questa applicazione deve essere costruita come un sistema di controllo intorno all'AI, non come un atto di fiducia nell'AI.

Il valore non sta nel far scrivere testo a un modello, ma nel rendere verificabile ciò che il modello suggerisce.

Ogni componente deve essere piccolo, testabile, riproducibile e tracciabile. La pipeline può essere lenta, sospesa o manuale; non può però essere opaca.

Quando sei in dubbio, scegli la variante che conserva più evidenza e produce meno magia.
