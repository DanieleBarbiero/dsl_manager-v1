# Contratti e manifest di DSL Manager

## Scopo

Questo documento descrive i contratti dati e i manifest usati da DSL Manager, e spiega come entrano nel flusso principale di lavoro: dal workspace inizializzato, al registry SQLite, agli artefatti di run, al package per AI generativa, fino a candidati, merge, snapshot DSL, diff ed export GEXF.

Per "contratto" si intende una struttura dati che l'applicazione produce, consuma o valida con regole precise. Per "manifest" si intende un contratto che elenca contenuti, hash, path, conteggi o stato di un pacchetto/artefatto.

Non e' stata necessaria una ricerca web: i contratti effettivi sono definiti dal codice in `src/dsl_mngr`, dalle migrazioni SQLite e dai test.

## Mappa sintetica

| Area | Artefatti / tabelle | Produttore | Consumatore | Ruolo nel flusso |
| --- | --- | --- | --- | --- |
| Configurazione workspace | `configs/project.yaml`, `.env`, `configs/workers/*.yaml` | `dsl-manager init` | CLI, core, worker | Definisce directory, database, logging e profili worker. |
| Schema registry | `schema_migrations`, tabelle SQLite | `dsl-manager db init` | tutti i comandi persistenti | E' il contratto persistente centrale dell'applicazione. |
| Run contract | `input.json`, `output.json`, `process_report.json`, `resolved_config.yaml`, `config_hash.txt`, `log.jsonl`; tabelle `runs`, `worker_runs` | `core.runs`, `core.worker_runner` | CLI, batch, audit | Traccia ogni elaborazione e collega input, output, configurazione e log. |
| Evidence contract | `chunks`, `source_fragments`, `chunks.jsonl`, `fragments.jsonl` | chunker e parser | AI package, validatore candidati, merge | Fornisce evidenze atomiche verificabili. |
| AI package manifest | `package_manifest.json`, `source_manifest.json` | worker `build_ai_package` | import AI, stale check, audit | Congela evidenze e file dell'handoff verso AI. |
| AI candidate schema | `candidate_schema.json`, `output_template.jsonl`, JSONL in `ai/inbox` | AI package + AI esterna | validatore candidati | Definisce record candidati ammessi e obbligo di evidence. |
| Candidate registry | `candidate_batches`, `candidate_records`, `rejected_candidates` | `candidates validate`, `ai import` | `facts merge` | Separa input AI accettato da input rifiutato. |
| Semantic registry | `facts`, `fact_evidence`, `relations`, `relation_evidence`, `conflicts` | `facts merge` | renderer DSL, diff, graph | Consolida conoscenza con traceability. |
| DSL snapshot | `DSL_*.json`, `DSL_*.yaml`, `DSL_*.md`, `dsl_snapshots` | `dsl render` | `dsl diff`, `graph export`, revisione umana | Produce il DSL derivato dal registry. |
| DSL diff | `exports/dsl_diff/*.json`, `*.md` | `dsl diff` | revisione tecnica | Confronta snapshot e pretende cause tracciabili. |
| Batch report | `batch_report.json` | comandi batch | operatore, process report | Riassume item, sub-run, errori e output di pipeline massive. |
| Graph export | `*.gexf`, `*.graph_report.json`, `graph_exports` | `graph export` | strumenti grafici, audit | Traduce il DSL in grafo diretto. |

## Flusso principale

Il percorso principale dei contratti e' questo:

```text
configs/project.yaml + worker profiles
  -> schema SQLite migrato
  -> run/input/output/report/log
  -> sources/source_revisions
  -> chunks e source_fragments
  -> ai/outbox/<AIPKG>/manifest + content + schema
  -> ai/inbox/<AIPKG>_candidates.jsonl
  -> candidate_records / rejected_candidates
  -> facts / relations / conflicts
  -> exports/dsl/DSL_*.json|yaml|md
  -> exports/dsl_diff o exports/graph
```

Il DSL finale non e' la sorgente di verita'. La sorgente di verita' e' il registry SQLite, arricchito da evidenze, candidati validati e merge semantico. Il DSL e' una vista derivata, riproducibile e dotata di hash.

## 1. Contratti di configurazione

### `configs/project.yaml`

Creato da `dsl-manager init`, contiene il contratto di configurazione del workspace:

- `project`: nome, lingua predefinita, timezone;
- `database`: path SQLite, WAL, foreign key;
- `logging`: log applicativo, log per run, formato JSONL, livello;
- `corpus`: directory `active`, `incoming`, `deleted`, `ignored`;
- `ai_handoff`: outbox, inbox e formato package.

Il parser e' volutamente semplice (`parse_simple_yaml`): supporta solo il sottoinsieme necessario al progetto. La configurazione effettiva viene salvata in ogni run come `resolved_config.yaml` e hashata in `config_hash.txt`.

### `.env`

Permette override leggeri tramite variabili `MDW_*`, ad esempio:

- `MDW_DB_PATH`;
- `MDW_LOG_LEVEL`;
- `MDW_AI_OUTBOX`;
- `MDW_AI_INBOX`;
- `MDW_ENABLE_WAL`.

Questi valori vengono fusi nella configurazione risolta prima degli override CLI.

### Profili worker `configs/workers/*.yaml`

Sono contratti di esecuzione per worker specializzati. Ogni profilo contiene almeno:

- sezione `worker` con `name` e `version`;
- sezione specifica del dominio, per esempio `docling`, `chunking`, `ddl`, `xml_form`, `db_code`, `log`, `ai_package`, `graph`.

I profili default includono:

- `docling.no_images.yaml`;
- `docling.chunking.yaml`;
- `ddl.default.yaml`;
- `xml_form.default.yaml`;
- `db_code.default.yaml`;
- `log.default.yaml`;
- `ai_package.default.yaml`;
- `gexf.default.yaml`.

I worker applicano una regola comune: se `strict_options_fail_on_unsupported_option` e' attivo, opzioni non supportate causano fallimento prima di mutare il registry.

## 2. Contratto del registry SQLite

Lo schema SQLite e' versionato da `schema_migrations`. Ogni migrazione ha `version`, `name`, `checksum`, `applied_at`; prima delle operazioni persistenti l'applicazione verifica che le migrazioni applicate coincidano con quelle definite dal codice.

Le migrazioni attuali sono:

| Versione | Nome | Contratto introdotto |
| --- | --- | --- |
| 1 | `create_minimal_registry_schema` | `sources`, `source_revisions`, `source_events`, `runs`, `worker_runs`. |
| 2 | `create_candidate_validation_schema` | `chunks`, `source_fragments`, `candidate_batches`, `candidate_records`, `rejected_candidates`. |
| 3 | `create_fact_merge_schema` | `facts`, `fact_evidence`, `relations`, `relation_evidence`, `conflicts`. |
| 4 | `create_dsl_snapshot_schema` | `dsl_snapshots`. |
| 5 | `create_ai_package_schema` | `ai_packages`. |
| 6 | `create_graph_export_schema` | `graph_exports`. |

Questo e' il contratto piu' importante: tutte le strutture file sono o input verso queste tabelle, o output derivati da queste tabelle.

## 3. Contratto di run

Ogni comando rilevante crea una run con `run_id` progressivo (`RUN_000001`, ecc.) e una directory:

```text
artifacts/runs/<RUN_ID>/
  input.json
  output.json
  process_report.json
  resolved_config.yaml
  config_hash.txt
  log.jsonl
```

`input.json` contiene sempre il contesto minimo della run:

- `run_id`;
- `run_type`;
- `artifact_dir`;
- `parent_run_id`, se presente;
- `parameters` oppure un input piu' specializzato scritto dal comando.

`output.json` contiene l'esito strutturato della run. `process_report.json` contiene stato, tempi, errore eventuale, hash configurazione e, se presenti, worker eseguiti. `log.jsonl` contiene eventi della singola run.

La tabella `runs` conserva lo stesso ciclo di vita:

- `running`;
- `completed`;
- `failed`.

I batch usano `parent_run_id` per collegare una run batch alle sub-run operative.

## 4. Contratto worker input/output

I worker isolati sono lanciati tramite `core.worker_runner`. Il runner costruisce un input JSON, lo scrive in `input.json`, avvia il processo e pretende un output JSON in `output.json`.

Il payload verso il worker contiene:

- `run_id`;
- `run_type`;
- `artifact_dir`;
- `worker_name`;
- `worker_version`;
- `input`, cioe' i parametri specifici;
- i parametri specifici anche espansi al livello principale.

L'output worker deve rispettare almeno queste regole:

- deve essere JSON valido;
- deve essere un oggetto;
- `run_id` deve coincidere con la run attesa;
- `worker_name` deve coincidere con il worker atteso.

Solo dopo questa validazione il runner applica le mutazioni al database, in transazione. Se il processo fallisce, se l'output manca, o se `run_id`/`worker_name` non tornano, la run viene marcata `failed` e il registry non riceve mutazioni applicative.

## 5. Contratti delle evidenze

Le evidenze sono il ponte tra corpus fisico, AI e conoscenza consolidata.

### Chunk documentali

Il worker `chunk_docling` produce:

```text
chunks/<SOURCE_ID>/<REVISION_ID>/chunks.jsonl
chunks/<SOURCE_ID>/<REVISION_ID>/chunk_report.json
```

Ogni record chunk contiene:

- `chunk_id`;
- `source_revision_id`;
- `sequence`;
- `text`;
- `text_hash`;
- metadati come heading/context e sorgente normalizzata;
- `status`.

Il worker verifica, se configurato, che l'hash di `normalized.md` coincida con `source_revisions.normalized_hash`. Il registro finale e' la tabella `chunks`.

### Frammenti strutturali

I parser `parse_ddl`, `parse_xml_form`, `parse_db_code` e `parse_log` producono:

```text
fragments/<SOURCE_ID>/<REVISION_ID>/fragments.jsonl
fragments/<SOURCE_ID>/<REVISION_ID>/<parser>_report.json
```

Il nome report varia:

- `ddl_report.json`;
- `xml_form_report.json`;
- `db_code_report.json`;
- `log_report.json`.

Ogni frammento contiene:

- `fragment_id`;
- `source_revision_id`;
- `fragment_type`;
- `sequence`;
- `path_or_selector`;
- coordinate testuali se disponibili;
- `text`;
- `text_hash`;
- `metadata_json`;
- `status`.

Il consumer e' `core.fragment_registry`, che valida `source_revision_id`, conteggi, hash e path, poi aggiorna `source_fragments`. Se la fonte era `unknown`, un parser riuscito puo' classificare `source_type`, `source_subtype` e `authority_level`.

## 6. Manifest del package AI

Il comando `ai package` crea una directory:

```text
ai/outbox/<AIPKG_ID>/
  instructions.md
  content.md
  source_manifest.json
  candidate_schema.json
  output_template.jsonl
  package_manifest.json
```

Questa e' la zona contrattuale piu' densa dell'applicazione.

### `instructions.md`

E' il contratto operativo per l'AI esterna. Stabilisce che il package e' read-only, che l'AI deve produrre solo JSONL, deve usare solo blocchi di evidenza presenti in `content.md`, deve copiare gli identificativi esatti e deve valorizzare `evidence_text` con testo letteralmente presente nell'evidenza.

L'applicazione non esegue semanticamente queste istruzioni; le rende verificabili indirettamente tramite `candidate_schema.json`, validazione dei candidati e controllo di evidence.

### `content.md`

E' il contenuto da dare all'AI. Ogni blocco evidenza include:

- `source_id`;
- `source_revision_id`;
- `source_path`;
- `source_type`;
- `authority_level`;
- `evidence_kind` (`chunk` o `fragment`);
- `chunk_id` o `fragment_id`;
- `fragment_type`, per i frammenti;
- `sequence`;
- `text_hash`;
- `truncated`;
- testo evidenza in blocco fenced.

Questo file permette all'AI di leggere il contesto senza accedere direttamente al database.

### `source_manifest.json`

E' il manifest delle evidenze incluse. Contiene:

- `package_id`;
- `package_path`;
- `counts`;
- elenco `source_revisions`;
- elenco `chunks`;
- elenco `fragments`.

Per le revisioni conserva `source_revision_id`, `source_id`, `file_path`, `content_hash`, `current_revision_id`, `revision_status`. Per chunk e frammenti conserva identificativi, sequenza, stato e `text_hash`.

E' usato per lo stale check: prima di importare candidati AI, l'applicazione controlla che le revisioni siano ancora attive e correnti, e che hash/stato di chunk e frammenti coincidano.

### `candidate_schema.json`

E' un contratto descrittivo allineato al validatore interno. Contiene:

- `$schema` impostato a JSON Schema draft 2020-12;
- `allowed_record_types`;
- `common_required_fields`;
- `record_specific_required_fields`;
- `properties`;
- `anyOf` per richiedere almeno `chunk_id` o `fragment_id`;
- `additionalProperties: true`.

Nota importante: il validatore applicativo non usa una libreria JSON Schema. Il file serve come schema di handoff per l'AI; l'enforcement reale avviene in `candidate_validation.py`.

### `output_template.jsonl`

Contiene esempi di record candidati gia' popolati con identificativi reali del package e piccoli estratti di evidenza. I template coprono almeno:

- `candidate_fact`;
- `candidate_relation`, se sono presenti frammenti;
- `candidate_question`.

I test verificano che i record template generati siano accettati dal validatore.

### `package_manifest.json`

E' il manifest del package completo. Contiene:

- `package_id`;
- `run_id`;
- `worker_name`;
- `worker_version`;
- `status`, inizialmente `waiting_for_ai_candidates`;
- `package_path`;
- `source_manifest_path`;
- conteggi di revisioni, chunk e frammenti;
- `files`, con path e SHA-256 dei file del package;
- `package_hash`;
- `stale_check`.

`package_hash` e' calcolato sugli hash dei file dichiarati nel manifest. Quando il worker termina, `persist_ai_package_output` rilegge manifest e file, valida path relativi al workspace, controlla i conteggi e ricalcola l'hash. Solo dopo registra il package nella tabella `ai_packages`.

## 7. Contratto JSONL dei candidati AI

L'AI o un operatore esterno deve depositare il file candidati in:

```text
ai/inbox/<AIPKG_ID>_candidates.jsonl
```

Ogni riga non vuota deve essere un oggetto JSON. I campi comuni richiesti sono:

- `record_type`;
- `candidate_id`;
- `source_revision_id`;
- `assertion_type`;
- `confidence`;
- `evidence_text`;
- almeno uno tra `chunk_id` e `fragment_id`.

Valori ammessi:

- `record_type`: `candidate_fact`, `candidate_relation`, `candidate_mapping`, `candidate_conflict`, `candidate_question`;
- `assertion_type`: `explicit`, `inferred`, `ambiguous`, `observed`;
- `confidence`: `high`, `medium`, `low`.

Campi specifici:

| Record type | Campi richiesti |
| --- | --- |
| `candidate_fact` | `fact_type`, `entity_name`, `property_name`, `property_value` |
| `candidate_relation` | `source_entity`, `relation_type`, `target_entity` |
| `candidate_mapping` | `domain_entity`, `technical_object`, `mapping_type` |
| `candidate_conflict` | `conflict_type`, `subject`, `left_value`, `right_value` |
| `candidate_question` | `question_type`, `subject`, `question_text` |

La regola sostanziale e' evidence-or-reject: `evidence_text` deve essere contenuto letteralmente nel chunk o frammento indicato, e quell'evidenza deve appartenere alla stessa `source_revision_id`.

I record accettati entrano in `candidate_records`; quelli rifiutati entrano in `rejected_candidates` con `reason`, `message`, `raw_line` e payload se disponibile.

Le principali ragioni di rifiuto sono:

- `invalid_json`;
- `schema_validation_failed`;
- `invalid_assertion_type`;
- `invalid_confidence`;
- `unknown_source_revision`;
- `unknown_chunk`;
- `unknown_fragment`;
- `chunk_source_mismatch`;
- `fragment_source_mismatch`;
- `evidence_text_not_found`.

## 8. Contratto di import AI e stale check

`ai import` collega un package registrato a un file JSONL in inbox. Prima dell'import controlla lo stato del package.

Un package e' stale se:

- `package_manifest.json` manca;
- `source_manifest.json` manca;
- una `source_revision` del manifest non esiste;
- una revisione non e' piu' corrente;
- una revisione non e' attiva;
- un `content_hash` di revisione e' cambiato;
- un chunk o frammento manca;
- un chunk o frammento non e' attivo;
- un `text_hash` di chunk o frammento e' cambiato.

Se il package e' stale, l'import e' bloccato salvo opzione esplicita `--allow-stale`. In entrambi i casi lo stato viene riflesso in `ai_packages.status` e `stale_reason`.

## 9. Contratti di merge semantico

`facts merge` consuma `candidate_records` validi e produce:

- `facts`;
- `fact_evidence`;
- `relations`;
- `relation_evidence`;
- `conflicts`.

Il merge materializza attualmente:

- `candidate_fact` in `facts`;
- `candidate_relation` in `relations`.

Gli altri record type vengono conservati come candidati validi ma non diventano ancora oggetti semantici dedicati.

Per i fatti, l'identita' logica e' basata su:

```text
fact + canonical_entity_name + property_key + normalized_property_value
```

Per le relazioni, l'identita' logica e' basata su:

```text
relation + canonical_source_entity + relation_type_key + canonical_target_entity
```

Le tabelle evidence mantengono il legame verso:

- `candidate_record_id`;
- `source_revision_id`;
- `chunk_id` o `fragment_id`;
- `evidence_text`;
- `evidence_text_hash`.

I conflitti sono generati quando due fatti sulla stessa entita' canonica e proprieta' hanno valori normalizzati diversi. Il sistema registra il conflitto invece di scegliere automaticamente un valore.

## 10. Contratto dello snapshot DSL

`dsl render` produce:

```text
exports/dsl/DSL_<N>.json
exports/dsl/DSL_<N>.yaml
exports/dsl/DSL_<N>.md
```

e registra lo snapshot in `dsl_snapshots`.

Il JSON e' il contratto principale. La struttura e':

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

`entities` raggruppa i facts per entita' canonica. `relations` elenca archi semantici tra entita'. `conflicts` elenca conflitti aperti o registrati. `traceability` collega facts e relations alle evidenze tramite candidate record, revisioni, source, path, chunk/frammento ed evidence hash.

`dsl_hash` viene calcolato sul contenuto DSL senza il campo `dsl_hash`. `registry_hash` viene calcolato sulla vista registry che alimenta il rendering. Questo rende confrontabili snapshot generati in momenti diversi.

## 11. Contratto di diff DSL

`dsl diff` consuma due snapshot da `dsl_snapshots` e produce:

```text
exports/dsl_diff/<FROM>__<TO>.json
exports/dsl_diff/<FROM>__<TO>.md
```

Il payload JSON contiene:

- `metadata` con `schema_version`, snapshot id, hash DSL e registry hash;
- `summary`;
- `changes`.

Ogni change contiene:

- `change_id`;
- `change_type`;
- `path`;
- `before`;
- `after`;
- `causes`.

Il contratto piu' forte e' sulle cause: per ogni cambiamento semantico devono esistere riferimenti di traceability con `candidate_record_id`, `source_revision_id`, `source_id`, `file_path`, `chunk_id` o `fragment_id`, `evidence_text_hash`. Se la traceability manca, la diff fallisce con `missing_traceability`.

## 12. Contratto batch

I batch non introducono un nuovo modello dati di dominio, ma orchestrano run e sub-run. Producono:

```text
artifacts/runs/<RUN_ID>/batch_report.json
```

Il report contiene:

- `run_id`;
- `run_type: batch`;
- `batch_command`;
- `status`;
- `stop_on_error`;
- `summary`;
- `items`.

Ogni item include `item_id`, `kind`, `status`, `run_id` se eseguito, input/source/batch riferiti, output sintetici, errore o reason di skip.

Questo contratto e' importante per il flusso principale quando si usa `batch process-dir`, perche' collega in modo esplicito una pianificazione a sub-run di normalizzazione, chunking o parsing.

## 13. Contratto GEXF

`graph export` consuma uno snapshot DSL e produce:

```text
exports/graph/<SNAPSHOT_ID>.gexf
exports/graph/<SNAPSHOT_ID>.graph_report.json
```

Il GEXF e' un grafo diretto. I nodi principali sono:

- entita' di dominio;
- fact node, in particolare facts di tipo `business_rule`;
- source;
- conflitti, se inclusi.

Gli archi principali sono:

- relazioni semantiche;
- `mentions`;
- `derives_from`;
- `conflicts_with`.

Il report JSON contiene:

- `graph_export_id`;
- `run_id`;
- `snapshot_id`;
- `format`;
- `dsl_hash`;
- `registry_hash`;
- `graph_hash`;
- path GEXF e report;
- conteggi nodi, archi, orfani e warning;
- opzioni effettive;
- warning strutturati.

Lo snapshot DSL deve avere `metadata.schema_version` supportata (`"1"`) e sezioni `entities`, `relations`, `conflicts`, `traceability`. Se una relazione punta a una entita' assente, l'export puo' creare un nodo orfano con warning, oppure fallire in modalita' strict.

## 14. Log JSONL

Il log applicativo e i log per run sono JSONL. Ogni record contiene almeno:

- `timestamp`;
- `level`;
- `event`;
- `message`;
- opzionalmente `run_id`;
- opzionalmente `worker`.

Questi log non sono la sorgente primaria dello stato, ma sono il contratto osservazionale per audit operativo e comandi `log`.

## Ruolo dei contratti nel controllo qualita'

I contratti sono usati come barriere successive:

1. la configurazione limita path e profili ammessi;
2. le migrazioni garantiscono compatibilita' dello schema;
3. il run contract rende ogni elaborazione ispezionabile;
4. il worker contract impedisce mutazioni da output incoerenti;
5. chunk e frammenti rendono verificabili le evidenze;
6. i manifest AI congelano l'handoff verso l'esterno;
7. lo stale check blocca candidati generati su evidenze superate;
8. il candidate contract rifiuta record senza prova testuale;
9. il merge mantiene evidence anche dopo la consolidazione;
10. il DSL snapshot mantiene traceability e hash;
11. diff e graph consumano solo snapshot strutturalmente validi.

La conseguenza architetturale e' che l'AI non ha scrittura diretta sul registry. Produce solo candidati JSONL; l'applicazione decide cosa accettare, cosa rifiutare e cosa materializzare.

## Autoverifica della ricostruzione

Ho verificato il contenuto di questo documento contro:

- `src/dsl_mngr/core/config.py` e `workspace.py` per configurazioni e profili;
- `src/dsl_mngr/core/migrations.py` per schema SQLite e versioni;
- `src/dsl_mngr/core/runs.py` e `worker_runner.py` per run e worker contract;
- `src/dsl_mngr/workers/*` per output di normalizzazione, chunking, parser e AI package;
- `src/dsl_mngr/core/ai_package.py` per manifest, schema candidati, stale check e hash;
- `src/dsl_mngr/core/candidate_validation.py` e `candidate_import.py` per contratto JSONL candidati;
- `src/dsl_mngr/core/merge.py` per materializzazione semantica;
- `src/dsl_mngr/core/dsl_renderer.py` e `dsl_diff.py` per snapshot e diff;
- `src/dsl_mngr/core/graph_export.py` per GEXF e report;
- test slice 4, 9, 15, 16 e 17 per confermare comportamento end-to-end, package AI, batch, run artifacts e graph export.

Controllo di coerenza finale:

- i manifest descritti sono effettivamente generati dal codice;
- i campi obbligatori dei candidati corrispondono al validatore interno;
- i path indicati sono workspace-relative e in formato POSIX, come richiesto dai test;
- il ruolo del DSL e' descritto come output derivato, non come source of truth;
- i limiti implementativi sono dichiarati: `candidate_schema.json` e' descrittivo, mentre la validazione reale e' applicativa; `candidate_mapping`, `candidate_conflict` e `candidate_question` sono accettati come candidati, ma non tutti vengono materializzati dal merge attuale.
