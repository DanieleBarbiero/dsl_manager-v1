Implementa solo la Slice 15 per DSL Manager v1.

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
- il codice attuale sotto `src/dsl_mngr`
- i test attuali sotto `tests`

Task:
implementare il minimo incremento verticale per "AI Package Handoff".

Obiettivo:
- produrre un package deterministico in `ai/outbox` per un AI tool esterno;
- trattare l'AI come black box: nessuna chiamata da codice, nessun provider integrato;
- includere nel package solo evidenze tracciabili gia' presenti nel registry come `chunks` e `source_fragments`;
- fornire schema e template JSONL coerenti con il validatore esistente;
- rilevare se un package e' diventato stale prima dell'import dei candidati;
- importare da `ai/inbox` i candidati prodotti esternamente, riusando la pipeline esistente di validation e persistence.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs`, `run_worker` e artifact deterministici.
- Slice 5 ha introdotto `chunks`, `source_fragments`, `candidate_batches`, `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto merge deterministico di `candidate_fact` e `candidate_relation`.
- Slice 7 ha introdotto renderer DSL JSON/YAML/Markdown e `dsl_snapshots`.
- Slice 8 ha introdotto `dsl diff` tracciabile.
- Slice 9 ha stabilizzato il golden pipeline test dell'MVP tecnico.
- Slice 10 ha introdotto normalizzazione Docling no-images dietro adapter/worker.
- Slice 11 ha introdotto chunking stabile ed evidence lookup su `chunks`.
- Slice 12 ha introdotto parser DDL e `source_fragments` DDL.
- Slice 13 ha introdotto parser XML form e `source_fragments` XML.
- Slice 14 ha introdotto parser SQL code e log, sempre tramite `source_fragments`.
- `candidate_validation.validate_candidate_payload` richiede gia' `chunk_id` oppure `fragment_id`, e verifica che `evidence_text` sia contenuto nell'evidenza referenziata.
- `runs.RUN_TYPES` potrebbe gia' contenere `ai_package` e `candidate_import`; verifica lo stato reale e aggiungi solo cio' che manca.
- `workspace.py` crea gia' `ai/outbox`, `ai/inbox` e `ai/imported`.

Decisione di scope:
- La Slice 15 non deve generare candidati AI.
- La Slice 15 deve solo preparare l'handoff verso AI esterna e controllare il rientro dei candidati.
- Il package deve essere leggibile da una persona e da un AI tool esterno, ma il core continua a fidarsi solo di `candidates validate`.
- L'import dall'inbox deve creare record in `candidate_batches`, `candidate_records` e `rejected_candidates` usando le regole esistenti.
- Non modificare il significato di `facts merge`: eventuali `facts`/`relations` entrano nel registry solo dopo validazione candidati e merge esplicito.

Scope:
- aggiungi un core piccolo e testabile per la costruzione e verifica dei package AI, per esempio:

```text
src/dsl_mngr/core/ai_package.py
```

- se utile, aggiungi un core separato per import/scansione inbox, per esempio:

```text
src/dsl_mngr/core/ai_inbox.py
```

- aggiungi il worker isolato:

```text
src/dsl_mngr/workers/build_ai_package.py
```

- aggiungi il comando CLI, nello stile `argparse` esistente:

```powershell
dsl-manager ai package <workspace>
dsl-manager ai package <workspace> --revision REV_000001
dsl-manager ai inbox scan <workspace>
dsl-manager ai import <workspace> --package AIPKG_000001
```

- mantieni compatibilita' con:

```powershell
python -m dsl_mngr ai package <workspace>
python -m dsl_mngr ai import <workspace> --package AIPKG_000001
```

- aggiungi un profilo default creato da `dsl-manager init`:

```text
configs/workers/ai_package.default.yaml
```

- aggiungi una migration append-only per tracciare i package AI nel registry, per esempio `ai_packages`;
- collega il nuovo comando in `src/dsl_mngr/cli/app.py`;
- aggiungi test deterministici Slice 15.

Migration minima consigliata:

```sql
CREATE TABLE IF NOT EXISTS ai_packages (
  package_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  package_path TEXT NOT NULL,
  manifest_path TEXT NOT NULL,
  content_path TEXT NOT NULL,
  instructions_path TEXT NOT NULL,
  candidate_schema_path TEXT NOT NULL,
  output_template_path TEXT NOT NULL,
  package_hash TEXT NOT NULL,
  source_revision_count INTEGER NOT NULL,
  chunk_count INTEGER NOT NULL,
  fragment_count INTEGER NOT NULL,
  status TEXT NOT NULL,
  stale_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

Status minimi:
- `waiting_for_ai_candidates` quando il package e' stato generato correttamente;
- `imported` dopo import riuscito dei candidati dall'inbox;
- `stale` quando lo stato corrente del registry non corrisponde piu' al manifest del package.

Se scegli un nome campo o status leggermente diverso, mantienilo coerente, documentalo nel report e coprilo nei test. Non modificare migration gia' applicate.

Profilo default minimo consigliato:

```yaml
worker:
  name: build_ai_package
  version: 1.0
ai_package:
  include_chunks: true
  include_fragments: true
  include_candidate_schema: true
  include_output_template: true
  max_evidence_chars: 20000
  strict_options_fail_on_unsupported_option: true
  package_format: markdown_plus_json
```

Se il parser YAML minimale supporta solo sezioni semplici a un livello, mantieni questa forma. Non fare un refactor generale della configurazione.

Comportamento atteso per `ai package`:
- richiede workspace inizializzato e database migrato;
- seleziona solo revisioni attive;
- se `--revision` e' indicato una o piu' volte, include solo quelle revisioni;
- se `--revision` non e' indicato, include tutte le revisioni attive che hanno almeno un chunk attivo o un fragment attivo;
- include solo `chunks.status = active`;
- include solo `source_fragments.status = active`;
- fallisce con errore leggibile se non ci sono evidenze attive da impacchettare;
- crea una run di tipo `ai_package`;
- invoca `build_ai_package` via `worker_runner.run_worker`;
- il worker non deve accedere al database principale;
- il worker riceve dall'orchestratore tutte le evidenze gia' lette dal database;
- il worker produce i file sotto:

```text
ai/outbox/AIPKG_000001/
```

- il core valida l'output del worker e inserisce/aggiorna `ai_packages` in transazione;
- i path salvati nel DB, negli artifact e nei manifest devono essere relativi al workspace e usare `/`;
- nessun path assoluto nei file condivisibili del package;
- l'ordine di sources, chunks, fragments e file deve essere stabile.

File richiesti nel package:

```text
ai/outbox/AIPKG_000001/instructions.md
ai/outbox/AIPKG_000001/content.md
ai/outbox/AIPKG_000001/source_manifest.json
ai/outbox/AIPKG_000001/candidate_schema.json
ai/outbox/AIPKG_000001/output_template.jsonl
ai/outbox/AIPKG_000001/package_manifest.json
```

`instructions.md` deve dire chiaramente all'AI esterna:
- non aggiornare database, registry, DSL, snapshot o file di progetto;
- produrre solo candidati JSONL;
- usare solo evidence block presenti in `content.md`;
- copiare `source_revision_id`, `chunk_id` o `fragment_id` esattamente come forniti;
- valorizzare `evidence_text` con testo contenuto letteralmente nell'evidenza referenziata;
- usare `candidate_fact`, `candidate_relation`, `candidate_mapping`, `candidate_conflict` o `candidate_question`;
- non inventare evidenza;
- preferire `assertion_type = explicit` per testo dichiarativo, `observed` per log/eventi runtime, `inferred` solo se davvero inferito, `ambiguous` per ambiguita';
- salvare il risultato atteso come:

```text
ai/inbox/AIPKG_000001_candidates.jsonl
```

`content.md` deve contenere evidence block riproducibili. Ogni blocco deve includere almeno:
- `source_id`;
- `source_revision_id`;
- `source_path`;
- `source_type`;
- `authority_level`;
- `chunk_id` oppure `fragment_id`;
- `evidence_kind` con valore `chunk` o `fragment`;
- `sequence`;
- `text_hash`;
- per fragments anche `fragment_type` e `path_or_selector`;
- testo dell'evidenza.

Esempio di blocco in `content.md`:

````markdown
## Evidence CHK_000001

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/manuale_clienti.md
- evidence_kind: chunk
- chunk_id: CHK_000001
- sequence: 1
- text_hash: <sha256>

```text
...testo del chunk...
```
````

`source_manifest.json` deve includere almeno:
- package id;
- package path;
- lista delle source revision incluse con `source_id`, `source_revision_id`, `file_path`, `content_hash`, `revision_status`, `current_revision_id`;
- lista chunks inclusi con `chunk_id`, `source_revision_id`, `sequence`, `text_hash`, `status`;
- lista fragments inclusi con `fragment_id`, `source_revision_id`, `fragment_type`, `sequence`, `text_hash`, `status`;
- conteggi.

`candidate_schema.json` deve essere coerente con il validatore attuale:
- record type ammessi:
  - `candidate_fact`
  - `candidate_relation`
  - `candidate_mapping`
  - `candidate_conflict`
  - `candidate_question`
- campi comuni obbligatori:
  - `record_type`
  - `candidate_id`
  - `source_revision_id`
  - `assertion_type`
  - `confidence`
  - `evidence_text`
- deve richiedere almeno uno tra `chunk_id` e `fragment_id`;
- enum `assertion_type`: `explicit`, `inferred`, `ambiguous`, `observed`;
- enum `confidence`: `high`, `medium`, `low`;
- campi specifici coerenti con `candidate_validation.SPECIFIC_REQUIRED_FIELDS`;
- non introdurre una dipendenza runtime da `jsonschema`.

`output_template.jsonl` deve contenere esempi validi come forma, ma con valori chiaramente sostituibili o basati su evidenze reali incluse. Deve mostrare almeno:
- un `candidate_fact` con `chunk_id`;
- un `candidate_relation` con `fragment_id`, se nel package ci sono fragments;
- un `candidate_question`.

`package_manifest.json` deve includere almeno:
- `package_id`;
- `run_id`;
- `worker_name`;
- `worker_version`;
- `status`;
- `package_hash`;
- `created_at`;
- `files` con path relativi e hash dei file;
- `source_revision_count`;
- `chunk_count`;
- `fragment_count`;
- `stale_check` iniziale con `is_stale = false`;
- riferimento a `source_manifest.json`.

Hash e determinismo:
- usa SHA-256;
- usa JSON canonico dove gia' usato dal progetto;
- `package_hash` deve essere calcolato in modo deterministico sui contenuti rilevanti del package;
- non includere path assoluti nel calcolo;
- se includi timestamp nei manifest, non usarli per asserzioni fragili nei test;
- output testuali con newline LF.

Comportamento CLI minimo al successo di `ai package`:

```text
Run: RUN_000001
Package: AIPKG_000001
Status: waiting_for_ai_candidates
Sources: 2
Chunks: 2
Fragments: 3
Package hash: <sha256>
Outbox: ai/outbox/AIPKG_000001
Manifest: ai/outbox/AIPKG_000001/package_manifest.json
```

Comportamento atteso per `ai inbox scan`:
- legge `ai/inbox`;
- riconosce file nel formato `AIPKG_000001_candidates.jsonl`;
- collega ogni file al package registrato, se esiste;
- calcola per ogni package se e' stale rispetto al registry corrente;
- stampa almeno package id, candidate file, exists/missing, stale/not stale e reason;
- non importa candidati e non muta `candidate_batches`.

Comportamento atteso per `ai import`:
- richiede `--package AIPKG_000001`;
- di default usa:

```text
ai/inbox/AIPKG_000001_candidates.jsonl
```

- opzionalmente accetta `--input <path>` dentro il workspace;
- verifica che il package esista nel DB e che `package_manifest.json` sia presente;
- esegue stale detection prima di importare;
- se il package e' stale, fallisce con exit code CLI `2`, messaggio leggibile, nessun `candidate_batch` creato e status package aggiornato a `stale`;
- se viene passato `--allow-stale`, importa comunque ma logga warning e lo segnala nel report;
- al successo, riusa il core esistente di candidate import/validation invece di duplicare la logica;
- crea una run coerente, preferibilmente `candidate_import` per questo comando;
- inserisce `candidate_batches`, `candidate_records` e `rejected_candidates` come fa `candidates validate`;
- aggiorna `ai_packages.status = imported` solo se l'import completa;
- non esegue automaticamente `facts merge`;
- non sposta o cancella il file inbox, salvo scelta esplicita e testata. Se copi in `ai/imported`, conserva comunque audit e path relativi.

Stale detection minima:
- un package e' stale se una qualunque source revision inclusa:
  - non esiste piu' nel DB;
  - non ha piu' `status = active`;
  - non e' piu' la `current_revision_id` della propria source;
  - ha `content_hash` diverso da quello nel manifest;
- un package e' stale se un chunk incluso:
  - non esiste;
  - non ha `status = active`;
  - ha `text_hash` diverso da quello nel manifest;
- un package e' stale se un fragment incluso:
  - non esiste;
  - non ha `status = active`;
  - ha `text_hash` diverso da quello nel manifest;
- il motivo deve essere riportato in modo diagnostico, per esempio `source_revision_not_current`, `chunk_not_active`, `fragment_hash_changed`.

Failure mode:
- workspace non inizializzato: errore leggibile;
- database non inizializzato o non migrato: errore leggibile;
- profilo mancante o invalido: errore leggibile;
- opzione non supportata nel profilo e `strict_options_fail_on_unsupported_option = true`:
  - il worker fallisce con exit code `4`;
  - `worker_runs.status = failed`;
  - `runs.status = failed`;
  - nessun record `ai_packages` pronto viene creato;
  - `process_report.json` o `stderr` contiene `unsupported_ai_package_option` e la chiave problematica;
- outbox package incompleto o manifest incoerente: run failed e nessuna mutazione parziale nel registry;
- inbox file mancante: errore leggibile;
- package stale: errore leggibile, nessun import default.

Artifact:
- `artifacts/runs/<run_id>/input.json` deve includere almeno:
  - `package_id`;
  - `output_dir`;
  - `profile`;
  - `ai_package_options`;
  - elenco revisioni incluse;
  - elenco chunks/fragments passati al worker;
- `artifacts/runs/<run_id>/output.json` deve includere il payload validato del worker;
- `artifacts/runs/<run_id>/process_report.json` deve avere:
  - `run_type = "ai_package"` per build;
  - `status = "completed"` al successo;
  - una voce worker `build_ai_package`;
  - path relativi;
  - `config_hash`;
- per `ai import`, il report deve includere almeno:
  - `package_id`;
  - `input_path`;
  - `batch_id`;
  - `total_records`;
  - `accepted_count`;
  - `rejected_count`;
  - `stale_allowed`.

Test minimi richiesti:
- `test_build_ai_package`
- `test_ai_package_stale`
- `test_import_batch`

I test devono coprire almeno:
- workspace temporaneo con `tmp_path`;
- `dsl-manager init` e `dsl-manager db init`;
- esistenza del profilo `configs/workers/ai_package.default.yaml`;
- creazione di evidenze attive in `chunks` e, preferibilmente, anche in `source_fragments`;
- `dsl-manager ai package <workspace>` via CLI;
- compatibilita' `python -m dsl_mngr ai package <workspace>`;
- creazione di `ai/outbox/AIPKG_000001/`;
- presenza dei sei file del package;
- path relativi e senza `\`;
- `package_manifest.json` e `source_manifest.json` coerenti con il DB;
- `candidate_schema.json` coerente con il validatore corrente;
- `output_template.jsonl` leggibile come JSONL;
- record in `ai_packages` con status `waiting_for_ai_candidates`;
- run `ai_package` e worker `build_ai_package` completati;
- `process_report.json` coerente;
- rerun con stesso input genera `AIPKG_000002` oppure un nuovo package sequenziale senza sovrascrivere audit storici;
- stale detection dopo modifica di una source e nuovo `corpus scan`;
- `ai import` rifiuta package stale di default senza creare candidate batch;
- `ai import --allow-stale`, se implementato, importa ma segnala chiaramente la scelta;
- import happy path: scrivi un file `ai/inbox/AIPKG_000001_candidates.jsonl` con candidati fixture coerenti con chunk/fragment del package, esegui `ai import`, verifica `candidate_batches`, `candidate_records`, `rejected_candidates`, output CLI e report;
- nessun `facts merge` automatico durante `ai import`;
- failure su opzione non supportata con worker exit code `4` e zero package pronto.

Fixture e dati test:
- usa fixture piccole e locali;
- non chiamare AI reale;
- non usare rete;
- evita Docling nei test Slice 15 se non strettamente necessario;
- puoi creare chunks/fragments con helper test-only, oppure usare parser gia' esistenti se il test resta veloce e deterministico;
- non modificare i golden expected della Slice 9 salvo motivo esplicito.

Constraints:
- non implementare provider AI;
- non fare chiamate HTTP o integrazioni esterne;
- non generare candidati con euristiche nel core;
- non implementare batch orchestration generale della Slice 16;
- non implementare GEXF, log viewer, UI, web/API/auth;
- non introdurre ORM;
- non aggiungere dipendenze runtime per JSON Schema validation;
- non cambiare il contratto pubblico esistente di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`, salvo fix strettamente necessari e coperti da test;
- non fare scrivere al worker nel database principale;
- non salvare path assoluti nel DB, nei manifest o negli artifact condivisibili;
- non salvare contenuti sorgente lunghi nei log applicativi;
- mantieni import assoluti da `dsl_mngr`;
- mantieni separati CLI, worker, core package builder, inbox/import logic e persistence;
- mantieni implementazione piccola, leggibile e deterministica.

Done when:
- Slice 15 e' implementata nello scope sopra;
- `ai package` produce package outbox completo e tracciato;
- `ai inbox scan` rileva file candidati e stale status;
- `ai import` importa candidati dall'inbox tramite validation esistente;
- stale detection blocca import di default;
- i test Slice 15 esistono e passano;
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
5. esegui test mirati Slice 15 e poi tutta la suite con l'interprete corretto;
6. esegui `git diff --check`;
7. esegui una autoverifica finale su scope, test, diff, stale detection e report;
8. riassumi cosa e' stato aggiunto e cosa e' rimasto fuori scope.

salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_15/dsl_manager_slice_15_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
