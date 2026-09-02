# Manuale utente di DSL Manager

Versione documento: 1.0
Data: 2026-06-12
Applicazione: `dsl_mngr` / `dsl-manager` v1

## Scopo del manuale

DSL Manager e' un'applicazione a riga di comando per costruire un DSL tracciabile a partire da un corpus di documenti, DDL, form XML, codice database, log e candidati prodotti da AI o da operatori esterni.

L'applicazione non tratta l'AI come fonte diretta di verita'. L'AI produce candidati JSONL; DSL Manager li valida contro evidenze testuali reali, li importa nel registry, li consolida in fatti e relazioni, e infine genera snapshot DSL, diff e grafi.

Questo manuale spiega come usare l'applicazione da operatore:

- come preparare un workspace;
- come caricare e processare fonti;
- come creare evidenze documentali e strutturali;
- come generare package per AI;
- come importare e validare candidati;
- come consolidare fatti e relazioni;
- come esportare DSL, diff e grafo;
- come leggere log e report;
- come diagnosticare gli errori piu' frequenti.

Il documento e' basato sul codice e sui test del repository. Non e' stata necessaria una ricerca web.

## Convenzioni

Nei comandi di esempio:

- `<workspace>` indica la directory del workspace DSL Manager;
- `REV_000001` indica una revisione sorgente;
- `CBATCH_000001` indica un batch di candidati validati;
- `AIPKG_000001` indica un package AI;
- `DSL_000001` indica uno snapshot DSL;
- i path stampati da DSL Manager sono normalmente relativi al workspace e usano `/`.

Se l'applicazione e' installata come script console, usare:

```powershell
dsl-manager <comando>
```

Se si esegue dal repository sorgente, usare l'entry point modulo:

```powershell
python -m dsl_mngr <comando>
```

Nel resto del manuale viene usato `dsl-manager`, che corrisponde alla CLI pubblica dell'applicazione.

## Concetti fondamentali

### Workspace

Il workspace e' la directory di lavoro locale in cui DSL Manager salva configurazione, database, corpus, evidenze, package AI, export, log e artefatti di esecuzione.

Un workspace inizializzato contiene almeno:

```text
<workspace>/
  .env
  configs/
    project.yaml
    workers/
      ai_package.default.yaml
      db_code.default.yaml
      ddl.default.yaml
      docling.chunking.yaml
      docling.no_images.yaml
      gexf.default.yaml
      log.default.yaml
      xml_form.default.yaml
  corpus/
    incoming/
    active/
    deleted/
    ignored/
  ai/
    outbox/
    inbox/
    imported/
  artifacts/
    runs/
  chunks/
  fragments/
  exports/
    dsl/
    dsl_diff/
    graph/
    logs/
  logs/
    app.jsonl
```

La directory `normalized/` non viene creata all'inizializzazione, ma compare quando si normalizzano documenti con Docling.

### Registry SQLite

Il file `workspace.sqlite` e' il registry persistente dell'applicazione. Contiene:

- fonti e revisioni;
- run e worker run;
- chunk e frammenti;
- candidati validati e rifiutati;
- fatti, relazioni, conflitti;
- snapshot DSL;
- package AI;
- export grafo.

Il DSL finale non e' la sorgente primaria di verita'. E' una vista derivata e riproducibile del registry.

### Fonte e revisione

Quando si esegue `corpus scan`, ogni file nel corpus attivo diventa una `source`. Il contenuto fisico del file in un dato momento diventa una `source_revision`.

Esempi di identificativi:

- `SRC_000001`: fonte logica;
- `REV_000001`: revisione della fonte.

Se un file cambia e viene rieseguito lo scan, la revisione corrente cambia. La vecchia revisione viene marcata come `superseded`; la nuova diventa `active`.

Se un file viene rimosso dal corpus e si riesegue lo scan, la fonte viene marcata `deleted_from_corpus` e la revisione corrente `deleted`.

### Run

Molti comandi producono una run riproducibile:

```text
artifacts/runs/RUN_000001/
  input.json
  output.json
  process_report.json
  resolved_config.yaml
  config_hash.txt
  log.jsonl
```

La run permette di capire:

- con quali parametri e configurazione e' stato eseguito il comando;
- quale worker e' stato lanciato;
- quale output e' stato prodotto;
- se l'esecuzione e' completata o fallita;
- dove sono i log di dettaglio.

Gli stati run sono:

- `running`;
- `completed`;
- `failed`.

### Worker

I worker sono processi isolati specializzati. Vengono avviati dalla CLI e scrivono output JSON validato prima di mutare il registry.

Worker principali:

| Worker | Comando utente | Ruolo |
| --- | --- | --- |
| `normalize_docling` | `corpus normalize` | Converte documenti in Markdown e JSON normalizzati. |
| `chunk_docling` | `corpus chunk` | Crea chunk stabili da Markdown normalizzato. |
| `parse_ddl` | `corpus parse-ddl` | Estrae tabelle, colonne e vincoli da DDL SQL. |
| `parse_xml_form` | `corpus parse-xml-form` | Estrae form, campi, bottoni e riferimenti tabellari da XML. |
| `parse_db_code` | `corpus parse-db-code` | Estrae procedure, trigger, statement, read/write/call. |
| `parse_log` | `corpus parse-log` | Estrae eventi osservati da log line-based. |
| `build_ai_package` | `ai package` | Costruisce un pacchetto deterministico per AI esterna. |

Se un worker fallisce, il registry non riceve mutazioni applicative parziali.

### Evidenze

Le evidenze sono i riferimenti verificabili da cui derivano i candidati:

- `chunks`: blocchi testuali generati da documenti normalizzati;
- `source_fragments`: frammenti strutturali generati da DDL, XML, codice DB o log.

Ogni candidato AI deve puntare almeno a un `chunk_id` o un `fragment_id` e deve contenere un `evidence_text` presente letteralmente nell'evidenza indicata.

### Candidati

I candidati sono record JSONL prodotti da un'AI o da un operatore. DSL Manager accetta questi tipi:

- `candidate_fact`;
- `candidate_relation`;
- `candidate_mapping`;
- `candidate_conflict`;
- `candidate_question`.

Solo `candidate_fact` e `candidate_relation` vengono materializzati nel registry semantico dal merge attuale. Gli altri tipi vengono validati e conservati, ma contati come skipped durante il merge.

### Fatti, relazioni e conflitti

Il merge trasforma candidati accettati in:

- `facts`: proprieta' o regole relative a entita';
- `relations`: relazioni tra entita';
- `conflicts`: conflitti tra fatti sulla stessa entita' e proprieta'.

La normalizzazione semantica e' conservativa: trim, compressione whitespace e lowercase per nomi canonici. Non vengono risolte sinonimie avanzate.

Gli stati dei fatti e delle relazioni dipendono da `assertion_type`:

| `assertion_type` | Stato generato |
| --- | --- |
| `explicit` | `active` |
| `observed` | `active` |
| `inferred` | `inferred` |
| `ambiguous` | `pending_review` |

Quando due fatti sulla stessa entita' canonica e sulla stessa proprieta' hanno valori normalizzati diversi, DSL Manager registra un conflitto `different_values_same_property` e marca i fatti come `conflicted`.

## Flusso end-to-end consigliato

Questo e' il flusso operativo piu' comune.

### 1. Inizializzare workspace e database

```powershell
dsl-manager init <workspace>
dsl-manager db init <workspace>
```

Output atteso di `init`:

```text
Initialized workspace: <path assoluto>
```

Output atteso di `db init`:

```text
Database: <workspace>/workspace.sqlite
Migrations applied: 6
Migrations skipped: 0
```

Se il database esiste gia' ed e' aggiornato, `Migrations applied` puo' essere `0` e `Migrations skipped` puo' essere `6`.

### 2. Copiare le fonti nel corpus attivo

Mettere i file da analizzare in:

```text
<workspace>/corpus/active/
```

Esempi:

```text
corpus/active/manuale_clienti.md
corpus/active/schema_ordini.sql
corpus/active/form_cliente.xml
corpus/active/log_batch_ordini.log
```

La cartella `incoming/` puo' essere usata come area di appoggio organizzativa, ma lo scan di default legge `corpus/active`.

### 3. Processare le fonti in batch

Per far decidere all'applicazione cosa fare in base al tipo file:

```powershell
dsl-manager batch process-dir <workspace>
```

Per una cartella diversa sotto workspace:

```powershell
dsl-manager batch process-dir <workspace> --path corpus/active
```

Output tipico:

```text
Run: RUN_000001
Command: process-dir
Items: 4
Completed: 3
Failed: 0
Skipped: 1
Report: artifacts/runs/RUN_000001/batch_report.json
```

`batch process-dir` esegue prima uno scan del corpus, poi pianifica gli item:

| Tipo fonte | Riconoscimento | Azione |
| --- | --- | --- |
| Documenti | `.pdf`, `.docx`, `.pptx`, `.html`, `.md`, `.txt` o `source_type=legacy_document` | `normalize` e poi `chunk` |
| XML form | `.xml` o `source_type=xml_form` | `parse_xml_form` |
| Log | `.log` o `source_type=log` | `parse_log` |
| DDL SQL | `.sql` con pattern DDL o `source_type=ddl` | `parse_ddl` |
| Codice DB | `.sql` con procedure, trigger, update, call o `source_type=database_code` | `parse_db_code` |
| Altro | non riconosciuto | skipped con reason `unsupported_source_type` |

Un file SQL puo' produrre piu' azioni se contiene sia strutture DDL sia codice procedurale riconosciuto.

### 4. Generare package AI

Dopo avere creato chunk o frammenti attivi:

```powershell
dsl-manager ai package <workspace>
```

Output tipico:

```text
Run: RUN_000002
Package: AIPKG_000001
Status: waiting_for_ai_candidates
Sources: 2
Chunks: 1
Fragments: 1
Package hash: <sha256>
Outbox: ai/outbox/AIPKG_000001
Manifest: ai/outbox/AIPKG_000001/package_manifest.json
```

Il package viene scritto in:

```text
ai/outbox/AIPKG_000001/
  instructions.md
  content.md
  source_manifest.json
  candidate_schema.json
  output_template.jsonl
  package_manifest.json
```

Dare all'AI esterna almeno:

- `instructions.md`;
- `content.md`;
- `candidate_schema.json`;
- `output_template.jsonl`.

L'AI deve restituire un file JSONL in:

```text
ai/inbox/AIPKG_000001_candidates.jsonl
```

### 5. Controllare inbox AI

```powershell
dsl-manager ai inbox scan <workspace>
```

Output tipico:

```text
AIPKG_000001 | ai/inbox/AIPKG_000001_candidates.jsonl | exists | not stale | -
```

Se il package e' stale, ad esempio perche' una fonte e' stata modificata dopo la creazione del package:

```text
AIPKG_000001 | ai/inbox/AIPKG_000001_candidates.jsonl | exists | stale | source_revision_not_current
```

La scelta consigliata e' rigenerare il package e chiedere candidati aggiornati.

### 6. Importare candidati AI

```powershell
dsl-manager ai import <workspace> --package AIPKG_000001
```

Output tipico:

```text
Run: RUN_000003
Package: AIPKG_000001
Batch: CBATCH_000001
Total: 3
Accepted: 3
Rejected: 0
Stale allowed: false
```

L'import AI:

- verifica che il package sia registrato;
- verifica lo stale status;
- importa il file candidati;
- valida ogni record;
- registra un `candidate batch`;
- marca il package come `imported`.

Se si vuole forzare l'import di un package stale:

```powershell
dsl-manager ai import <workspace> --package AIPKG_000001 --allow-stale
```

Usare `--allow-stale` solo in modo consapevole: i candidati potrebbero essere stati generati su evidenze non piu' correnti.

### 7. Eseguire il merge semantico

```powershell
dsl-manager facts merge <workspace> --batch CBATCH_000001
```

Output tipico:

```text
Run: RUN_000004
Batch: CBATCH_000001
Candidate records: 8
Facts created: 6
Facts existing: 0
Relations created: 2
Relations existing: 0
Conflicts created: 0
Conflicts existing: 0
Skipped: 0
```

Il merge non cancella l'evidenza: ogni fatto e relazione mantiene riferimenti a candidate record, revisione, fonte, chunk/frammento ed evidence hash.

### 8. Renderizzare il DSL

```powershell
dsl-manager dsl render <workspace>
```

Output tipico:

```text
Run: RUN_000005
Snapshot: DSL_000001
DSL hash: <sha256>
Facts: 6
Relations: 2
Conflicts: 0
JSON: exports/dsl/DSL_000001.json
YAML: exports/dsl/DSL_000001.yaml
Markdown: exports/dsl/DSL_000001.md
```

Il JSON e' il formato principale. YAML e Markdown sono viste di supporto per lettura e revisione.

### 9. Esportare il grafo

```powershell
dsl-manager graph export <workspace> --snapshot DSL_000001
```

Output tipico:

```text
Run: RUN_000006
Graph export: GEXF_000001
Snapshot: DSL_000001
Format: gexf
DSL hash: <sha256>
Graph hash: <sha256>
Nodes: 10
Edges: 12
Orphans: 0
Warnings: 0
GEXF: exports/graph/DSL_000001.gexf
Report: exports/graph/DSL_000001.graph_report.json
```

Il file `.gexf` puo' essere aperto con strumenti di analisi grafo che supportano GEXF.

## Flusso manuale controllato

Il batch e' comodo per elaborazioni massive. Il flusso manuale e' utile quando si vuole controllare ogni step.

### Scan del corpus

```powershell
dsl-manager corpus scan <workspace>
```

Output:

```text
Added: 2
Modified: 0
Deleted: 0
Unchanged: 0
```

Opzioni:

```powershell
dsl-manager corpus scan <workspace> --path corpus/active
dsl-manager corpus scan <workspace> --corpus-dir corpus/active
```

`--path` e `--corpus-dir` sono equivalenti. Il path deve restare dentro il workspace.

Nota importante: nella v1 non esiste un comando CLI dedicato per elencare source e revisioni. Per recuperare `REV_...` si puo' usare un viewer SQLite o una query sul database:

```sql
SELECT
  sr.source_revision_id,
  sr.source_id,
  sr.file_path,
  sr.status,
  sr.normalized_hash
FROM source_revisions sr
ORDER BY sr.file_path, sr.source_revision_id;
```

### Normalizzazione documentale

Per documenti `.pdf`, `.docx`, `.pptx`, `.html`, `.md`, `.txt`:

```powershell
dsl-manager corpus normalize <workspace> --revision REV_000001
```

Profilo default:

```text
docling.no_images
```

Output:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Normalized hash: <sha256>
Markdown: normalized/SRC_000001/REV_000001/normalized.md
JSON: normalized/SRC_000001/REV_000001/normalized.json
Report: normalized/SRC_000001/REV_000001/docling_report.json
```

Il profilo default usa Docling, produce Markdown e JSON normalizzati, non esporta immagini e disabilita OCR. Il report contiene versione Docling, opzioni risolte, output e hash.

Per usare un profilo custom:

```powershell
dsl-manager corpus normalize <workspace> --revision REV_000001 --profile docling.no_images
```

I profili custom devono essere file in:

```text
configs/workers/<profile>.yaml
```

Il nome profilo non puo' contenere path o `..`.

### Chunking documentale

Dopo la normalizzazione:

```powershell
dsl-manager corpus chunk <workspace> --revision REV_000001
```

Profilo default:

```text
docling.chunking
```

Output:

```text
Run: RUN_000002
Revision: REV_000001
Source: SRC_000001
Chunks: 1
Chunks hash: <sha256>
Chunks JSONL: chunks/SRC_000001/REV_000001/chunks.jsonl
Report: chunks/SRC_000001/REV_000001/chunk_report.json
```

Il chunker verifica che:

- `normalized.md` esista;
- `normalized.json` esista;
- `source_hash.txt` corrisponda al `content_hash` della revisione;
- l'hash del Markdown corrisponda a `source_revisions.normalized_hash`.

Se la fonte e' cambiata dopo la normalizzazione, rieseguire `corpus scan`, `corpus normalize` e poi `corpus chunk` sulla revisione corrente.

### Parsing DDL

Per DDL SQL:

```powershell
dsl-manager corpus parse-ddl <workspace> --revision REV_000001
```

Profilo default:

```text
ddl.default
```

Output:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Tables: 3
Columns: 12
Foreign keys: 2
Fragments: 20
Fragments hash: <sha256>
Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl
Report: fragments/SRC_000001/REV_000001/ddl_report.json
```

Il parser produce frammenti come:

- `ddl_table`;
- `ddl_column`;
- `ddl_constraint`.

Un parsing riuscito puo' classificare la fonte come:

- `source_type = ddl`;
- `source_subtype = mixed_ddl`;
- `authority_level = technical_structure`.

### Parsing XML form

Per form XML:

```powershell
dsl-manager corpus parse-xml-form <workspace> --revision REV_000001
```

Profilo default:

```text
xml_form.default
```

Output:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Forms: 1
Fields: 3
Required fields: 2
Buttons: 1
Table references: 1
Edit relations: 1
Fragments: 5
Fragments hash: <sha256>
Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl
Report: fragments/SRC_000001/REV_000001/xml_form_report.json
```

Il parser produce frammenti come:

- `xml_form`;
- `xml_field`;
- `xml_button`.

Rileva riferimenti tabellari e puo' inferire relazioni `edits` tra form e tabelle.

Un parsing riuscito puo' classificare la fonte come:

- `source_type = xml_form`;
- `source_subtype = form`;
- `authority_level = technical_structure`.

### Parsing codice database

Per procedure e trigger SQL:

```powershell
dsl-manager corpus parse-db-code <workspace> --revision REV_000001
```

Profilo default:

```text
db_code.default
```

Output:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Procedures: 1
Triggers: 0
Statements: 1
Reads: 0
Writes: 1
Calls: 0
Fragments: 2
Fragments hash: <sha256>
Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl
Report: fragments/SRC_000001/REV_000001/db_code_report.json
```

Il parser produce frammenti come:

- `sql_procedure`;
- `sql_trigger`;
- `sql_statement`.

Rileva, quando possibile:

- parametri;
- statement;
- letture;
- scritture;
- chiamate.

Un parsing riuscito puo' classificare la fonte come:

- `source_type = database_code`;
- `source_subtype = procedure` o `trigger`;
- `authority_level = runtime_code`.

### Parsing log

Per log line-based:

```powershell
dsl-manager corpus parse-log <workspace> --revision REV_000001
```

Profilo default:

```text
log.default
```

Output:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Events: 4
Warnings: 1
Components: BATCH_ORDINI
Fragments: 4
Fragments hash: <sha256>
Fragments JSONL: fragments/SRC_000001/REV_000001/fragments.jsonl
Report: fragments/SRC_000001/REV_000001/log_report.json
```

Il parser produce frammenti `log_event` con metadati come:

- timestamp;
- livello;
- componente;
- messaggio;
- event kind;
- identificativi osservati.

Un parsing riuscito puo' classificare la fonte come:

- `source_type = log`;
- `source_subtype = batch_log`;
- `authority_level = runtime_observation`.

## Package AI

### Quando generare un package

Generare un package AI quando esistono evidenze attive:

- chunk documentali in `chunks`;
- frammenti strutturali in `source_fragments`.

Un package congela un insieme di evidenze per l'handoff verso AI. Questo e' importante perche' l'import successivo puo' verificare se quelle evidenze sono ancora correnti.

### Creare un package unico

```powershell
dsl-manager ai package <workspace>
```

Con revisioni selezionate:

```powershell
dsl-manager ai package <workspace> --revision REV_000001 --revision REV_000002
```

Con profilo custom:

```powershell
dsl-manager ai package <workspace> --profile ai_package.default
```

Il profilo default include:

- chunk;
- frammenti;
- schema candidati;
- template output;
- massimo evidenze per package;
- formato `markdown_plus_json`.

### Creare package per revisione in batch

```powershell
dsl-manager ai package-batch <workspace>
```

Con revisioni selezionate:

```powershell
dsl-manager ai package-batch <workspace> --revision REV_000001 --revision REV_000002
```

Il batch crea un package per ogni revisione con evidenze attive. Revisioni senza evidenze attive vengono skippate con reason `no_active_evidence`.

### Contenuto del package

Ogni package contiene:

| File | Uso |
| --- | --- |
| `instructions.md` | Istruzioni operative per AI esterna. |
| `content.md` | Evidenze leggibili con metadati e testo. |
| `source_manifest.json` | Manifest di revisioni, chunk e frammenti inclusi. |
| `candidate_schema.json` | Schema descrittivo dei candidati ammessi. |
| `output_template.jsonl` | Esempi compilati con identificativi reali. |
| `package_manifest.json` | Manifest completo con conteggi, file hash e package hash. |

L'AI deve usare solo evidenze presenti in `content.md` e deve copiare esattamente `source_revision_id`, `chunk_id` o `fragment_id`.

### Stale check

Un package diventa stale se, dopo la sua creazione:

- manca `package_manifest.json`;
- manca `source_manifest.json`;
- una revisione non esiste piu';
- una revisione non e' piu' corrente;
- una revisione non e' attiva;
- il `content_hash` di una revisione e' cambiato;
- un chunk o frammento manca;
- un chunk o frammento non e' attivo;
- il `text_hash` di un chunk o frammento e' cambiato.

Quando `ai import` trova un package stale, blocca l'import salvo `--allow-stale`.

## Candidati JSONL

### Posizione dei file candidati

Per import AI standard:

```text
ai/inbox/AIPKG_000001_candidates.jsonl
```

Per validazione manuale senza package AI:

```powershell
dsl-manager candidates validate <workspace> --input ai/inbox/miei_candidati.jsonl
```

Il path di input deve essere dentro il workspace. I file devono essere UTF-8.

### Regole comuni

Ogni riga non vuota deve essere un oggetto JSON completo. I campi comuni sono:

| Campo | Obbligatorio | Note |
| --- | --- | --- |
| `record_type` | si | Uno dei tipi ammessi. |
| `candidate_id` | si | Identificativo del candidato. Non viene usato come chiave unica primaria, ma deve essere stabile e leggibile. |
| `source_revision_id` | si | Deve esistere nel registry. |
| `chunk_id` | almeno uno tra `chunk_id` e `fragment_id` | Deve appartenere alla stessa revisione. |
| `fragment_id` | almeno uno tra `chunk_id` e `fragment_id` | Deve appartenere alla stessa revisione. |
| `assertion_type` | si | `explicit`, `inferred`, `ambiguous`, `observed`. |
| `confidence` | si | `high`, `medium`, `low`. |
| `evidence_text` | si | Deve comparire letteralmente nel chunk o frammento indicato. |

Campi extra sono conservati nel payload JSON, ma non necessariamente usati dal merge.

### Tipi record e campi specifici

| `record_type` | Campi specifici obbligatori |
| --- | --- |
| `candidate_fact` | `fact_type`, `entity_name`, `property_name`, `property_value` |
| `candidate_relation` | `source_entity`, `relation_type`, `target_entity` |
| `candidate_mapping` | `domain_entity`, `technical_object`, `mapping_type` |
| `candidate_conflict` | `conflict_type`, `subject`, `left_value`, `right_value` |
| `candidate_question` | `question_type`, `subject`, `question_text` |

### Esempio: fatto

```json
{"record_type":"candidate_fact","candidate_id":"CAND_001","source_revision_id":"REV_000001","chunk_id":"CHK_000001","fact_type":"business_entity","entity_name":"Cliente","property_name":"description","property_value":"Cliente del dominio commerciale.","assertion_type":"explicit","confidence":"high","evidence_text":"Cliente è una business entity del dominio commerciale."}
```

### Esempio: relazione

```json
{"record_type":"candidate_relation","candidate_id":"CAND_002","source_revision_id":"REV_000002","chunk_id":"CHK_000002","source_entity":"Cliente","relation_type":"places","target_entity":"Ordine","assertion_type":"explicit","confidence":"high","evidence_text":"Il cliente può inserire uno o più ordini."}
```

### Validare candidati manualmente

```powershell
dsl-manager candidates validate <workspace> --input ai/inbox/candidati.jsonl
```

Output:

```text
Run: RUN_000001
Batch: CBATCH_000001
Total: 8
Accepted: 8
Rejected: 0
```

Il comando ritorna successo se il file e' stato processato, anche se alcuni record sono rifiutati. Controllare sempre `Rejected`.

Per validare tutti i JSONL in una directory:

```powershell
dsl-manager candidates validate-batch <workspace>
```

Opzioni:

```powershell
dsl-manager candidates validate-batch <workspace> --input-dir ai/inbox --pattern *.jsonl
dsl-manager candidates validate-batch <workspace> --stop-on-error
```

### Ragioni di rigetto comuni

| Reason | Significato | Azione consigliata |
| --- | --- | --- |
| `invalid_json` | La riga non e' JSON valido. | Correggere sintassi JSON della riga. |
| `schema_validation_failed` | Mancano campi o il record non e' oggetto. | Confrontare con `candidate_schema.json`. |
| `invalid_assertion_type` | `assertion_type` non ammesso. | Usare `explicit`, `inferred`, `ambiguous`, `observed`. |
| `invalid_confidence` | `confidence` non ammessa. | Usare `high`, `medium`, `low`. |
| `unknown_source_revision` | Revisione inesistente. | Verificare `REV_...` o rieseguire scan/process. |
| `unknown_chunk` | Chunk inesistente. | Verificare chunking o package AI. |
| `unknown_fragment` | Frammento inesistente. | Verificare parser strutturale o package AI. |
| `chunk_source_mismatch` | Chunk di una revisione diversa. | Usare chunk della stessa `source_revision_id`. |
| `fragment_source_mismatch` | Frammento di una revisione diversa. | Usare frammento della stessa `source_revision_id`. |
| `evidence_text_not_found` | Testo evidenza non trovato letteralmente. | Copiare una sottostringa esatta dall'evidenza. |

## Merge semantico

### Merge singolo

```powershell
dsl-manager facts merge <workspace> --batch CBATCH_000001
```

Il comando legge i record accettati in `candidate_records` per quel batch.

Produce:

- facts da `candidate_fact`;
- relations da `candidate_relation`;
- conflicts quando trova valori diversi sulla stessa entita' e proprieta';
- skipped count per mapping, conflict e question non ancora materializzati.

### Merge batch

```powershell
dsl-manager facts merge-batch <workspace>
```

Con batch selezionati:

```powershell
dsl-manager facts merge-batch <workspace> --batch CBATCH_000001 --batch CBATCH_000002
```

Con stop al primo errore:

```powershell
dsl-manager facts merge-batch <workspace> --stop-on-error
```

### Idempotenza del merge

Se si importa o si rielabora un candidato equivalente:

- lo stesso fatto non viene duplicato;
- la stessa relazione non viene duplicata;
- viene aggiunta evidenza se il candidate record e' nuovo;
- i contatori `Facts existing` e `Relations existing` indicano elementi gia' presenti.

## Snapshot DSL

### Render

```powershell
dsl-manager dsl render <workspace>
```

Output:

```text
Run: RUN_000001
Snapshot: DSL_000001
DSL hash: <sha256>
Facts: 6
Relations: 2
Conflicts: 0
JSON: exports/dsl/DSL_000001.json
YAML: exports/dsl/DSL_000001.yaml
Markdown: exports/dsl/DSL_000001.md
```

Output in directory custom:

```powershell
dsl-manager dsl render <workspace> --output-dir exports/dsl
```

Il path deve restare dentro il workspace.

### Struttura del DSL JSON

Lo snapshot JSON contiene:

- `metadata`;
- `entities`;
- `relations`;
- `conflicts`;
- `traceability`.

`metadata` contiene:

- `schema_version`, attualmente `"1"`;
- `dsl_hash`;
- `registry_hash`;
- `counts`.

`entities` raggruppa i facts per entita' canonica. `relations` elenca archi semantici. `conflicts` elenca conflitti. `traceability` collega fatti e relazioni alle evidenze originali.

Renderizzare due volte senza cambiare il registry produce due snapshot diversi come ID, ma con lo stesso `dsl_hash` e `registry_hash`.

### Diff tra snapshot

```powershell
dsl-manager dsl diff <workspace> --from DSL_000001 --to DSL_000002
```

Output:

```text
Run: RUN_000002
From: DSL_000001
To: DSL_000002
Changes: 0
Added: 0
Removed: 0
Modified: 0
JSON: exports/dsl_diff/DSL_000001__DSL_000002.json
Markdown: exports/dsl_diff/DSL_000001__DSL_000002.md
```

Output custom:

```powershell
dsl-manager dsl diff <workspace> --from DSL_000001 --to DSL_000002 --output-dir exports/dsl_diff
```

La diff richiede traceability. Se un cambiamento semantico non puo' essere collegato a candidate record, source revision, source e evidence hash, il comando fallisce con errore di traceability.

## Export grafo

### GEXF

```powershell
dsl-manager graph export <workspace> --snapshot DSL_000001
```

Formato supportato in v1:

```text
gexf
```

Comando equivalente esplicito:

```powershell
dsl-manager graph export <workspace> --snapshot DSL_000001 --format gexf
```

Output custom:

```powershell
dsl-manager graph export <workspace> --snapshot DSL_000001 --output-dir exports/graph
```

Fail su entita' orfane:

```powershell
dsl-manager graph export <workspace> --snapshot DSL_000001 --strict-orphans
```

Senza `--strict-orphans`, una relazione verso entita' non presente puo' generare un nodo orfano con warning. Con `--strict-orphans`, l'export fallisce.

### Contenuto del grafo

Il grafo e' diretto. Puo' includere:

- nodi entita' di dominio;
- nodi fact per facts di tipo `business_rule`;
- nodi source;
- nodi conflitto;
- archi semantici tra entita';
- archi `mentions`;
- archi `derives_from`;
- archi `conflicts_with`.

Le opzioni default sono in:

```text
configs/workers/gexf.default.yaml
```

## Batch orchestration

I comandi batch creano una run padre `run_type=batch` e sub-run operative collegate tramite `parent_run_id`.

Ogni batch produce:

```text
artifacts/runs/RUN_000001/batch_report.json
```

Il report contiene:

- comando batch;
- opzioni;
- item pianificati;
- stato finale;
- contatori;
- run id delle sub-run;
- output sintetici;
- errori e reason di skip.

### Processare directory

```powershell
dsl-manager batch process-dir <workspace>
```

Opzioni:

```powershell
dsl-manager batch process-dir <workspace> --path corpus/active
dsl-manager batch process-dir <workspace> --stop-on-error
```

Senza `--stop-on-error`, il batch continua dopo un item fallito e ritorna exit code `2` se almeno un item e' fallito.

Con `--stop-on-error`, gli item successivi vengono marcati `skipped` con reason `stopped_after_error`.

### Chunking batch

```powershell
dsl-manager batch chunk-dir <workspace>
```

Senza `--revision`, processa le revisioni attive con `normalized_hash` valorizzato.

Con revisioni selezionate:

```powershell
dsl-manager batch chunk-dir <workspace> --revision REV_000001 --revision REV_000002
```

### Package AI batch

```powershell
dsl-manager ai package-batch <workspace>
```

Con revisioni selezionate:

```powershell
dsl-manager ai package-batch <workspace> --revision REV_000001 --revision REV_000002
```

### Validazione candidati batch

```powershell
dsl-manager candidates validate-batch <workspace>
```

Opzioni:

```powershell
dsl-manager candidates validate-batch <workspace> --input-dir ai/inbox --pattern *.jsonl
```

### Merge batch

```powershell
dsl-manager facts merge-batch <workspace>
```

Senza `--batch`, elabora i candidate batch disponibili. Con `--batch`, limita la lista.

## Log e diagnostica

### Log applicativo

Il log principale e':

```text
logs/app.jsonl
```

Ogni record contiene:

- `timestamp`;
- `level`;
- `event`;
- `message`;
- opzionalmente `run_id`;
- opzionalmente `worker`.

### Tabella log

```powershell
dsl-manager log table <workspace>
```

Output CSV:

```powershell
dsl-manager log table <workspace> --format csv
```

Scrittura su file:

```powershell
dsl-manager log table <workspace> --format csv --output exports/logs/app.csv
```

Il comando legge `logs/app.jsonl`. I log specifici delle run restano in `artifacts/runs/<RUN_ID>/log.jsonl`.

### Stato run

Per controllare una run:

```powershell
dsl-manager run status <workspace> RUN_000001
```

Oppure, se la directory corrente e' il workspace:

```powershell
dsl-manager run status RUN_000001
```

Output:

```text
Run: RUN_000001
Type: dsl_render
Status: completed
Started: 2026-06-12T10:00:00+02:00
Finished: 2026-06-12T10:00:01+02:00
Artifact directory: artifacts/runs/RUN_000001
```

### Creare una run manuale

```powershell
dsl-manager run start <workspace> --type test
```

Questo comando e' soprattutto diagnostico. Crea una run `running`, ma non esegue worker e non la completa. In uso operativo normale non serve.

## Configurazione

### `configs/project.yaml`

Contiene:

- `project`: nome progetto, lingua, timezone;
- `database`: path SQLite, WAL, foreign keys;
- `logging`: path log, livello, JSONL;
- `corpus`: directory active, incoming, deleted, ignored;
- `ai_handoff`: outbox, inbox, formato package.

Default principali:

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
  level: INFO
```

Il parser YAML dell'applicazione supporta solo un sottoinsieme semplice: sezioni e scalar values. Evitare strutture YAML complesse non previste.

### `.env`

Permette override leggeri:

| Variabile | Effetto |
| --- | --- |
| `MDW_WORKSPACE_DIR` | Imposta workspace dir nella config risolta. |
| `MDW_DB_PATH` | Override del path database. |
| `MDW_LOG_LEVEL` | Override livello log. |
| `MDW_DEFAULT_DOC_PROFILE` | Profilo documentale default. |
| `MDW_AI_OUTBOX` | Directory outbox AI. |
| `MDW_AI_INBOX` | Directory inbox AI. |
| `MDW_ENABLE_WAL` | Abilita o disabilita WAL SQLite. |

I path configurati devono restare dentro il workspace.

### Profili worker

I profili sono in:

```text
configs/workers/*.yaml
```

Ogni profilo ha una sezione `worker` e una sezione specifica.

Profili default:

| Profilo | Sezione specifica |
| --- | --- |
| `docling.no_images` | `docling` |
| `docling.chunking` | `chunking` |
| `ddl.default` | `ddl` |
| `xml_form.default` | `xml_form` |
| `db_code.default` | `db_code` |
| `log.default` | `log` |
| `ai_package.default` | `ai_package` |
| `gexf.default` | `graph` |

Molti profili hanno:

```yaml
strict_options_fail_on_unsupported_option: true
```

Con questa opzione, un'impostazione non supportata fa fallire il worker prima di produrre mutazioni. Nei report di errore l'exit code tipico e' `4`.

## Comandi di riferimento

### Workspace e database

```powershell
dsl-manager init [workspace]
dsl-manager db init [workspace]
```

`workspace` e' opzionale per questi comandi e defaulta a `.`.

### Corpus

```powershell
dsl-manager corpus scan [workspace] [--path PATH]
dsl-manager corpus normalize <workspace> --revision REV_ID [--profile PROFILE]
dsl-manager corpus chunk <workspace> --revision REV_ID [--profile PROFILE]
dsl-manager corpus parse-ddl <workspace> --revision REV_ID [--profile PROFILE]
dsl-manager corpus parse-xml-form <workspace> --revision REV_ID [--profile PROFILE]
dsl-manager corpus parse-db-code <workspace> --revision REV_ID [--profile PROFILE]
dsl-manager corpus parse-log <workspace> --revision REV_ID [--profile PROFILE]
```

### Batch

```powershell
dsl-manager batch process-dir <workspace> [--path PATH] [--stop-on-error]
dsl-manager batch chunk-dir <workspace> [--revision REV_ID]... [--profile PROFILE] [--stop-on-error]
```

### AI

```powershell
dsl-manager ai package <workspace> [--revision REV_ID]... [--profile PROFILE]
dsl-manager ai package-batch <workspace> [--revision REV_ID]... [--profile PROFILE] [--stop-on-error]
dsl-manager ai inbox scan <workspace>
dsl-manager ai import <workspace> --package AIPKG_ID [--input PATH] [--allow-stale]
```

### Candidati

```powershell
dsl-manager candidates validate <workspace> --input PATH
dsl-manager candidates validate-batch <workspace> [--input-dir DIR] [--pattern GLOB] [--stop-on-error]
```

### Facts

```powershell
dsl-manager facts merge <workspace> --batch CBATCH_ID
dsl-manager facts merge-batch <workspace> [--batch CBATCH_ID]... [--stop-on-error]
```

### DSL

```powershell
dsl-manager dsl render <workspace> [--output-dir DIR]
dsl-manager dsl diff <workspace> --from DSL_ID --to DSL_ID [--output-dir DIR]
```

### Graph

```powershell
dsl-manager graph export <workspace> --snapshot DSL_ID [--format gexf] [--output-dir DIR] [--strict-orphans]
```

### Run e log

```powershell
dsl-manager run start [workspace] [--type TYPE] [--parent-run-id RUN_ID]
dsl-manager run status <workspace> <run_id>
dsl-manager run status <run_id>
dsl-manager log table [workspace] [--format table|csv] [--output PATH]
```

## Output e artefatti principali

| Operazione | Output file principali |
| --- | --- |
| `corpus normalize` | `normalized/<SRC>/<REV>/normalized.md`, `normalized.json`, `source_hash.txt`, `docling_report.json` |
| `corpus chunk` | `chunks/<SRC>/<REV>/chunks.jsonl`, `chunk_report.json` |
| `corpus parse-ddl` | `fragments/<SRC>/<REV>/fragments.jsonl`, `ddl_report.json` |
| `corpus parse-xml-form` | `fragments/<SRC>/<REV>/fragments.jsonl`, `xml_form_report.json` |
| `corpus parse-db-code` | `fragments/<SRC>/<REV>/fragments.jsonl`, `db_code_report.json` |
| `corpus parse-log` | `fragments/<SRC>/<REV>/fragments.jsonl`, `log_report.json` |
| `ai package` | `ai/outbox/<AIPKG>/instructions.md`, `content.md`, manifest e schema |
| `ai import` / `candidates validate` | record in `candidate_batches`, `candidate_records`, `rejected_candidates` |
| `facts merge` | record in `facts`, `relations`, `conflicts`, evidence tables |
| `dsl render` | `exports/dsl/DSL_*.json`, `.yaml`, `.md` |
| `dsl diff` | `exports/dsl_diff/<FROM>__<TO>.json`, `.md` |
| `graph export` | `exports/graph/<DSL>.gexf`, `<DSL>.graph_report.json` |
| ogni run | `artifacts/runs/<RUN>/input.json`, `output.json`, `process_report.json`, `log.jsonl` |

## Qualita' dati e buone pratiche

1. Eseguire sempre `corpus scan` dopo avere aggiunto, modificato o rimosso file.
2. Non riusare candidati AI creati su package stale, salvo decisione esplicita.
3. Copiare `evidence_text` letteralmente dall'evidenza; anche differenze minime possono causare rigetto.
4. Conservare `Run`, `Batch`, `Package` e `Snapshot` stampati dai comandi: servono negli step successivi.
5. Preferire `batch process-dir` per prime elaborazioni massive.
6. Usare il flusso manuale quando si vuole controllare o ripetere una singola revisione.
7. Non modificare manualmente file in `exports/dsl`; rigenerarli con `dsl render`.
8. Non modificare manualmente `package_manifest.json` o `source_manifest.json`; gli hash servono per audit e stale check.
9. Controllare sempre `Rejected` dopo validazione o import.
10. Aprire `process_report.json` quando un comando stampa un errore worker.

## Troubleshooting

### `Workspace is not initialized`

Significa che mancano `.env`, `configs/project.yaml` o `logs/app.jsonl`.

Soluzione:

```powershell
dsl-manager init <workspace>
```

### `Database is not initialized`

Il workspace esiste, ma `workspace.sqlite` non e' stato creato o migrato.

Soluzione:

```powershell
dsl-manager db init <workspace>
```

### `Database has pending migrations`

Lo schema database non e' allineato alla versione dell'applicazione.

Soluzione:

```powershell
dsl-manager db init <workspace>
```

Se l'errore persiste per mismatch checksum, verificare di usare la stessa versione applicativa con cui il workspace e' stato creato o creare un nuovo workspace.

### `path escapes the workspace`

DSL Manager blocca path assoluti o relativi che puntano fuori dal workspace per la maggior parte degli input e output operativi.

Soluzione:

- usare path relativi al workspace;
- evitare `..`;
- evitare path assoluti per sorgenti, output e profili.

### `Source revision not found`

Il `REV_...` indicato non esiste o non e' attivo.

Soluzione:

- rieseguire `corpus scan`;
- verificare `source_revisions` nel database;
- usare la revisione corrente.

### Hash sorgente non coerente

Messaggi tipici:

- `Source file hash does not match source_revisions.content_hash`;
- `source_hash.txt does not match source_revisions.content_hash`;
- `normalized.md hash does not match source_revisions.normalized_hash`.

Significa che una fonte o un output intermedio e' cambiato dopo la registrazione.

Soluzione consigliata:

```powershell
dsl-manager corpus scan <workspace>
dsl-manager corpus normalize <workspace> --revision <REV_CORRENTE>
dsl-manager corpus chunk <workspace> --revision <REV_CORRENTE>
```

Per DDL, XML, DB code e log, rieseguire lo scan e poi il parser sulla revisione corrente.

### Worker fallito con exit code `4`

Di solito indica opzione profilo non supportata con strict mode attivo.

Controllare:

```text
artifacts/runs/<RUN_ID>/process_report.json
artifacts/runs/<RUN_ID>/log.jsonl
```

Soluzione:

- correggere il profilo in `configs/workers`;
- rimuovere opzioni non supportate;
- rieseguire il comando.

### `evidence_text_not_found`

Il testo nel candidato non e' presente letteralmente nel chunk o frammento referenziato.

Soluzione:

- aprire `content.md` del package AI o il file `chunks.jsonl` / `fragments.jsonl`;
- copiare una sottostringa esatta;
- mantenere lo stesso `chunk_id` o `fragment_id`.

### Package AI stale

Output tipico:

```text
AI package AIPKG_000001 is stale: source_revision_not_current.
```

Soluzione consigliata:

```powershell
dsl-manager ai package <workspace>
```

Poi chiedere all'AI di produrre nuovi candidati usando il nuovo package.

Soluzione forzata:

```powershell
dsl-manager ai import <workspace> --package AIPKG_000001 --allow-stale
```

Usare solo se si accetta il rischio di evidenze obsolete.

### Diff fallisce per traceability mancante

La diff richiede cause tracciabili per ogni cambiamento semantico.

Cause possibili:

- snapshot alterato manualmente;
- registry modificato fuori dall'applicazione;
- traceability corrotta.

Soluzione:

- rigenerare gli snapshot con `dsl render`;
- evitare modifiche manuali ai file esportati o al database.

### Graph export con orfani

Una relazione punta a un'entita' non presente in `entities`.

Senza `--strict-orphans`, l'app crea nodo orfano e warning.

Con `--strict-orphans`, il comando fallisce.

Soluzione:

- aggiungere o validare un `candidate_fact` per l'entita' target;
- rieseguire merge e render DSL;
- riesportare il grafo.

## Limiti attuali della v1

- Non esiste ancora un comando CLI dedicato per listare source, revisioni, chunk o frammenti.
- `candidate_schema.json` e' uno schema di handoff per AI, ma la validazione reale e' implementata dal codice applicativo.
- `candidate_mapping`, `candidate_conflict` e `candidate_question` sono validati e registrati, ma non materializzati come oggetti semantici dedicati dal merge attuale.
- La normalizzazione di nomi e valori e' conservativa; non fa entity resolution avanzata.
- Il grafo supporta solo formato `gexf`.
- `graph export` supporta solo grafi diretti.
- `run start` crea run diagnostiche ma non esegue worker e non completa automaticamente la run.
- Il parser YAML interno supporta solo un sottoinsieme semplice.

## Checklist operativa rapida

Per un nuovo workspace:

```powershell
dsl-manager init <workspace>
dsl-manager db init <workspace>
```

Per caricare fonti:

```powershell
# copiare file in <workspace>/corpus/active
dsl-manager batch process-dir <workspace>
```

Per AI handoff:

```powershell
dsl-manager ai package <workspace>
# consegnare ai/outbox/AIPKG_000001 all'AI esterna
# salvare il risultato in ai/inbox/AIPKG_000001_candidates.jsonl
dsl-manager ai inbox scan <workspace>
dsl-manager ai import <workspace> --package AIPKG_000001
```

Per consolidare ed esportare:

```powershell
dsl-manager facts merge <workspace> --batch CBATCH_000001
dsl-manager dsl render <workspace>
dsl-manager graph export <workspace> --snapshot DSL_000001
```

Per confrontare due versioni:

```powershell
dsl-manager dsl diff <workspace> --from DSL_000001 --to DSL_000002
```

Per diagnosticare:

```powershell
dsl-manager log table <workspace>
dsl-manager run status <workspace> RUN_000001
```

## Autoverifica del manuale

Questo manuale e' stato verificato contro:

- la superficie CLI definita in `src/dsl_mngr/cli/app.py`;
- i comandi in `src/dsl_mngr/cli/commands`;
- la struttura workspace in `src/dsl_mngr/core/workspace.py`;
- la configurazione in `src/dsl_mngr/core/config.py`;
- le migrazioni SQLite in `src/dsl_mngr/core/migrations.py`;
- i contratti run e worker in `src/dsl_mngr/core/runs.py` e `src/dsl_mngr/core/worker_runner.py`;
- scan corpus, chunk, parser, AI package, inbox, validazione candidati, merge, DSL, diff, graph e batch nei moduli `src/dsl_mngr/core`;
- i test end-to-end e slice in `tests/`.

Controlli di coerenza applicati:

- tutti i comandi documentati esistono nella CLI;
- le opzioni documentate corrispondono agli argomenti parser;
- i path di output documentati corrispondono agli output prodotti dai comandi e dai test;
- i tipi candidati e i campi obbligatori corrispondono al validatore;
- e' dichiarato che solo facts e relations vengono materializzati dal merge attuale;
- e' dichiarato che lo stale check blocca l'import AI salvo `--allow-stale`;
- e' dichiarato che la v1 non dispone di comandi list per source/revision/chunk/frammenti;
- i limiti operativi sono esplicitati per evitare aspettative non supportate.
