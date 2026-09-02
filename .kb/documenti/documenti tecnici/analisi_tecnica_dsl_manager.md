# Analisi tecnica dell'applicazione DSL Manager

## Scopo del documento

Questo documento analizza DSL Manager come applicazione completa per la costruzione di un DSL di conoscenza applicativa a partire da un corpus di fonti eterogenee. L'analisi è stata ricostruita leggendo codice, configurazioni, documentazione interna, fixture e output attesi della suite di test.

Il focus principale è il flusso dei dati: dal corpus iniziale, attraverso normalizzazione, frammentazione, handoff verso AI generativa, validazione, merge nel registry, fino alla generazione del DSL e dei file derivati.

## Metodo di analisi

La ricostruzione seguente espone passaggi verificabili, non ipotesi astratte. Il percorso adottato è stato:

1. identificare entry point, comandi CLI e struttura del package `dsl_mngr`;
2. ricostruire workspace, configurazioni, migrazioni SQLite e tabelle persistenti;
3. seguire i comandi applicativi fino ai moduli core e ai worker isolati;
4. confrontare il comportamento implementato con i documenti di design interni;
5. verificare i flussi end-to-end tramite fixture e output attesi dei test;
6. isolare i confini applicativi attuali, distinguendo ciò che è implementato da ciò che è previsto solo a livello progettuale.

Non è stato necessario consultare fonti web: il repository contiene i contratti applicativi, le fixture e i documenti sufficienti per questa analisi.

## Sintesi esecutiva

DSL Manager è un workbench locale, registry-first, pensato per trasformare fonti tecniche e documentali di un sistema legacy in una rappresentazione DSL tracciabile. La sua memoria primaria non è il DSL finale, ma un registry SQLite che conserva fonti, revisioni, evidenze, candidati AI, fatti, relazioni, conflitti, snapshot e run di elaborazione.

Il DSL è quindi una vista derivata e riproducibile dello stato del registry. Questo è un punto architetturale fondamentale: l'applicazione non considera l'output testuale DSL come sorgente di verità, ma come prodotto generato da dati normalizzati, validati e storicizzati.

Il contributo dell'AI generativa è confinato a un ruolo preciso: produrre record candidati a partire da pacchetti di evidenze già preparati dall'applicazione. L'AI non scrive direttamente nel registry e non decide da sola lo stato finale della conoscenza. Ogni candidato deve superare una validazione evidence-or-reject: deve riferirsi a una revisione sorgente esistente, a un chunk o frammento esistente, e deve riportare un `evidence_text` realmente contenuto nell'evidenza indicata.

L'applicazione è fortemente orientata ad auditabilità e riproducibilità:

- ogni run produce artefatti su disco;
- ogni worker opera tramite input e output JSON;
- le mutazioni del database sono applicate solo dopo validazione dell'output;
- gli hash collegano fonti, normalizzazioni, chunk, package AI, DSL e registry;
- gli snapshot DSL includono traceability fino a candidate record, fonte, revisione, chunk o frammento.

## Architettura generale

Il package Python è `dsl_mngr`, con layout `src/`. L'entry point principale è il comando console:

```text
dsl-manager
```

L'esecuzione come modulo è supportata da:

```text
python -m dsl_mngr
```

La CLI è costruita con `argparse` e delega ai comandi applicativi sotto `dsl_mngr.cli.commands`. I gruppi principali sono:

- `init`: inizializza workspace, configurazioni e directory;
- `db init`: applica le migrazioni SQLite;
- `corpus`: registra fonti e avvia normalizzazioni, chunking e parser strutturali;
- `batch`: esegue pipeline massive su directory o gruppi di file;
- `ai`: costruisce package per l'AI, scansiona inbox e importa candidati;
- `candidates`: valida e importa record candidati;
- `facts`: fonde candidati validi in fatti, relazioni e conflitti;
- `dsl`: genera snapshot DSL e differenze tra snapshot;
- `graph`: esporta grafi GEXF;
- `run`: crea e interroga run applicativi;
- `log`: mostra log in forma tabellare o CSV.

La separazione tra CLI, core applicativo e worker è netta:

- la CLI interpreta parametri e prepara le chiamate;
- i moduli `core` contengono registry, validazioni, rendering, merge, diff, package AI e batch;
- i worker in `workers` eseguono attività isolate, producendo output dichiarativo che viene poi applicato al database dal runner.

## Workspace locale

L'applicazione lavora dentro una directory workspace. L'inizializzazione crea una struttura simile a questa:

```text
configs/
  project.yaml
  workers/
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
.env
```

`configs/project.yaml` contiene le impostazioni principali: nome progetto, timezone, database SQLite, directory corpus, directory AI, logging, worker profile.

Il file `.env` consente override leggeri. Il parser di configurazione è volutamente semplice: non dipende da un parser YAML completo, ma interpreta la struttura necessaria al progetto. La configurazione risolta viene salvata negli artefatti di run per rendere ogni esecuzione verificabile.

## Persistenza e registry

SQLite è la memoria primaria dell'applicazione. Il database viene aperto con foreign key abilitate e, se configurato, modalità WAL.

Le migrazioni creano le seguenti aree dati:

- corpus registry: `sources`, `source_revisions`, `source_events`;
- esecuzioni: `runs`, `worker_runs`;
- evidenze derivate: `chunks`, `source_fragments`;
- handoff AI: `ai_packages`, `candidate_batches`, `candidate_records`, `rejected_candidates`;
- conoscenza consolidata: `facts`, `fact_evidence`, `relations`, `relation_evidence`, `conflicts`;
- output derivati: `dsl_snapshots`, `graph_exports`.

Il modello dati rispecchia la filosofia registry-first:

- la fonte fisica è rappresentata da `sources`;
- ogni versione osservata della fonte è una `source_revision`;
- chunk e frammenti sono evidenze atomiche collegate a una revisione;
- i candidati AI non diventano conoscenza finché non superano validazione e merge;
- fatti e relazioni mantengono prove tramite tabelle evidence;
- snapshot DSL e grafi sono output derivati, collegati allo stato del registry.

## Run e worker isolati

Ogni operazione importante viene tracciata come run. Una run produce una directory sotto `artifacts/runs`, con artefatti standard:

```text
input.json
output.json
process_report.json
resolved_config.yaml
config_hash.txt
log.jsonl
```

Quando una run usa un worker, il worker non modifica direttamente il database. Riceve un input JSON, produce un output JSON con `run_id` e `worker_name`, e il runner applica le mutazioni in transazione solo se:

- il processo termina correttamente;
- l'output JSON è valido;
- il worker dichiarato corrisponde a quello atteso;
- le mutazioni rispettano il contratto applicativo.

Questo design riduce il rischio di stati parziali. Se un worker fallisce o produce output incompleto, il database non viene aggiornato e il report conserva stdout, stderr ed errori.

## Flusso end-to-end dei dati

Il flusso completo può essere letto come una catena di trasformazioni controllate:

```text
corpus fisico
  -> source registry
  -> normalizzazioni e frammenti
  -> chunk e source_fragments
  -> AI package
  -> candidate JSONL
  -> candidate_records / rejected_candidates
  -> facts / relations / conflicts
  -> DSL snapshot
  -> diff, markdown, YAML, JSON, GEXF
```

La caratteristica decisiva è che ogni passaggio conserva riferimenti agli input precedenti. Il DSL finale non perde la genealogia: un fatto nel DSL può essere ricondotto al candidate record, al chunk o frammento, alla revisione sorgente e al file originale.

## 1. Inizializzazione

`dsl-manager init` prepara il workspace e crea configurazioni di default. Tra i profili worker generati ci sono:

- profilo Docling senza immagini;
- profilo di chunking;
- parser DDL;
- parser XML form;
- parser codice database;
- parser log;
- profilo package AI;
- profilo export GEXF.

`dsl-manager db init` applica le migrazioni SQLite. Dopo questa fase l'applicazione ha un registry vuoto ma pronto a ricevere il corpus.

## 2. Scansione del corpus

Il corpus di default è `corpus/active`, salvo diversa configurazione. La scansione visita ricorsivamente i file, calcola hash SHA-256 dei byte e aggiorna il registry.

Per ogni file:

- se il file è nuovo, viene creato un record in `sources`, una revisione attiva in `source_revisions` e un evento `source_added`;
- se il file era già registrato ma il contenuto è cambiato, la revisione precedente diventa `superseded`, viene creata una nuova revisione attiva e viene registrato `source_modified`;
- se una fonte registrata non esiste più nel corpus, la fonte passa a `deleted_from_corpus`, la revisione corrente a `deleted` e viene registrato `source_deleted`.

I path sono salvati in forma relativa al workspace, con separatori POSIX. Questo rende più stabile la portabilità degli artefatti e riduce la dipendenza da path assoluti locali.

All'inizio una fonte può avere `source_type` e `authority_level` sconosciuti. Alcuni parser successivi possono classificare automaticamente la fonte se riconoscono con successo la natura del contenuto.

## 3. Normalizzazione documentale con Docling

Per documenti legacy o file documentali, il flusso usa Docling tramite un adapter dedicato. La dipendenza è bloccata nel progetto a `docling==2.97.0`.

L'applicazione incapsula Docling per controllare variabilità e opzioni consentite. Il profilo standard disabilita immagini e OCR non richiesto. Le opzioni non supportate o incompatibili con il profilo vengono rifiutate prima dell'esecuzione.

Il worker di normalizzazione produce una cartella per source e revisione, contenente:

```text
normalized.md
normalized.json
source_hash.txt
docling_report.json
```

I dati principali del worker sono:

- Markdown normalizzato;
- JSON esportato da Docling;
- hash della fonte originale;
- hash del Markdown normalizzato;
- versione Docling;
- report tecnico.

Il database viene aggiornato con `normalized_hash` sulla `source_revision`. L'hash consente al chunking di verificare che stia operando sulla normalizzazione attesa.

## 4. Chunking dei documenti normalizzati

Il chunking lavora sul Markdown normalizzato. La strategia implementata è deterministica e basata su heading e paragrafi.

Ogni chunk conserva:

- `source_revision_id`;
- `chunk_id` stabile per revisione e sequenza;
- numero di sequenza;
- testo;
- hash del testo;
- offset iniziale e finale;
- percorso heading;
- metadati sul chunker, strategia e normalizzazione di origine;
- stato `active` o `stale`.

L'output su disco viene scritto sotto `chunks/<SOURCE>/<REV>/`, in particolare:

```text
chunks.jsonl
chunk_report.json
```

Quando il chunking viene rieseguito, il registry riusa gli identificativi per sequenza e marca come `stale` i chunk non più prodotti. Questo consente di distinguere evidenze correnti e obsolete senza cancellare bruscamente la storia.

## 5. Parser strutturali

Accanto ai chunk documentali, DSL Manager estrae frammenti strutturali da fonti tecniche. Questi frammenti sono salvati nella tabella `source_fragments` e rappresentano evidenze più specializzate rispetto ai chunk testuali.

I parser principali sono:

- DDL SQL;
- form XML;
- codice database, cioè procedure e trigger;
- log applicativi o batch.

Tutti producono frammenti con:

- `fragment_id`;
- `source_revision_id`;
- `fragment_type`;
- numero di sequenza;
- testo;
- hash;
- riferimenti di posizione;
- metadati strutturati;
- stato.

Come per i chunk, i frammenti non più prodotti diventano `stale`. Se la fonte era sconosciuta, il successo di un parser può aggiornarne `source_type`, `source_subtype` e `authority_level`.

## 6. Parser DDL

Il parser DDL lavora su SQL generico. Riconosce:

- `CREATE TABLE`;
- colonne;
- primary key;
- foreign key;
- vincoli unique;
- `CREATE INDEX`.

I frammenti prodotti includono:

- `ddl_table`;
- `ddl_column`;
- `ddl_constraint`.

I metadati conservano informazioni come tabella, colonna, tipo dati, nullability, default, vincoli, chiavi primarie, foreign key e statement kind.

Quando una fonte DDL viene riconosciuta, può essere classificata come:

```text
source_type = ddl
source_subtype = mixed_ddl
authority_level = technical_structure
```

Nelle fixture tecniche il parser estrae, ad esempio, tre tabelle (`ANCLI`, `ORDTES`, `ORDRIG`), dodici colonne e due foreign key. Queste informazioni diventano evidenze tecniche potenzialmente utilizzabili dall'AI per proporre mapping o relazioni.

## 7. Parser XML form

Il parser XML usa `xml.etree.ElementTree` e interpreta documenti con root `form`. Estrae:

- form;
- campi;
- bottoni;
- flag di obbligatorietà;
- riferimenti a tabelle e colonne;
- relazioni di editing.

I frammenti principali sono:

- `xml_form`;
- `xml_field`;
- `xml_button`.

I selector XML vengono salvati nei metadati, ad esempio path verso campi o bottoni. Il parser può classificare la fonte come:

```text
source_type = xml_form
source_subtype = form
authority_level = technical_structure
```

Questa categoria è importante perché collega la conoscenza funzionale visibile all'utente, cioè maschere, campi obbligatori e azioni, agli oggetti tecnici sottostanti.

## 8. Parser codice database

Il parser per codice database riconosce procedure e trigger SQL generici. Estrae:

- `CREATE TRIGGER`;
- `CREATE PROCEDURE`;
- parametri;
- statement `UPDATE`;
- oggetti letti, scritti o chiamati.

I frammenti includono:

- `sql_trigger`;
- `sql_procedure`;
- `sql_statement`.

La classificazione automatica può impostare:

```text
source_type = database_code
source_subtype = trigger | procedure | mixed_sql_code
authority_level = runtime_code
```

Queste evidenze sono diverse dal DDL: non descrivono solo struttura statica, ma comportamento di esecuzione, regole tecniche e impatti sui dati.

## 9. Parser log

Il parser log riconosce righe con pattern:

```text
YYYY-MM-DD HH:MM:SS LEVEL COMPONENT message
```

Estrae:

- timestamp;
- livello;
- componente;
- messaggio;
- tipo evento;
- identificativi osservati in forma `key=value`.

I frammenti prodotti sono `log_event`. Gli eventi possono essere classificati come `start`, `processed`, `warning`, `end` o `unknown`.

La fonte può essere classificata come log applicativo o batch:

```text
source_type = log
source_subtype = batch_log | application_log
authority_level = runtime_observation
```

I log aggiungono una prospettiva osservazionale: non dicono solo cosa il sistema dovrebbe fare, ma cosa è stato visto accadere in esecuzione.

## 10. Package per AI generativa

Il comando `ai package` costruisce un pacchetto in `ai/outbox`. Il package contiene evidenze attive prese da chunk e frammenti, più istruzioni e schema di output per un motore AI esterno.

Una directory package contiene:

```text
instructions.md
content.md
source_manifest.json
candidate_schema.json
output_template.jsonl
package_manifest.json
```

`instructions.md` definisce il contratto operativo: l'AI deve trattare l'input come sola lettura, copiare gli identificativi esattamente e produrre solo record JSONL.

`content.md` è il cuore informativo: contiene sezioni di evidenza con source, revisione, path, tipo fonte, authority level, tipo evidenza, identificativo chunk o frammento, hash, stato di troncamento e testo.

`source_manifest.json` elenca revisioni, chunk e frammenti inclusi. Serve a rilevare se il corpus o le evidenze sono cambiati dopo la costruzione del package.

`candidate_schema.json` descrive i record ammessi:

- `candidate_fact`;
- `candidate_relation`;
- `candidate_mapping`;
- `candidate_conflict`;
- `candidate_question`.

`output_template.jsonl` offre esempi di record. `package_manifest.json` registra path, hash dei file, hash complessivo, conteggi e stato.

Lo stato iniziale del package è:

```text
waiting_for_ai_candidates
```

## 11. Handoff AI e inbox

DSL Manager non invoca direttamente un provider AI. Il modello è sospendibile:

1. l'applicazione prepara `ai/outbox/<PACKAGE>`;
2. un operatore o automazione esterna passa il contenuto all'AI;
3. l'AI produce un file JSONL;
4. il file viene collocato in `ai/inbox`;
5. DSL Manager lo importa e lo valida.

Per default il file atteso ha forma:

```text
ai/inbox/<PACKAGE>_candidates.jsonl
```

Prima dell'import viene controllato se il package è stale. Un package è stale se:

- una source revision inclusa non esiste più;
- una revisione non è più corrente o attiva;
- un hash sorgente è cambiato;
- un chunk incluso non esiste, non è attivo o ha hash diverso;
- un frammento incluso non esiste, non è attivo o ha hash diverso;
- manifest o file del package non sono più verificabili.

L'import di un package stale viene bloccato, salvo esplicita opzione di override.

## 12. Validazione dei candidati

Il validatore candidati applica regole comuni e regole specifiche per tipo record.

Campi comuni richiesti:

- `candidate_id`;
- `source_revision_id`;
- `assertion_type`;
- `confidence`;
- `evidence_text`;
- almeno uno tra `chunk_id` e `fragment_id`.

Valori ammessi per `assertion_type`:

- `explicit`;
- `inferred`;
- `ambiguous`;
- `observed`.

Valori ammessi per `confidence`:

- `high`;
- `medium`;
- `low`.

Campi specifici per `candidate_fact`:

- `fact_type`;
- `entity_name`;
- `property_name`;
- `property_value`.

Campi specifici per `candidate_relation`:

- `source_entity`;
- `relation_type`;
- `target_entity`.

Campi specifici per `candidate_mapping`:

- `domain_entity`;
- `technical_object`;
- `mapping_type`.

Campi specifici per `candidate_conflict`:

- `conflict_type`;
- `subject`;
- `left_value`;
- `right_value`.

Campi specifici per `candidate_question`:

- `question_type`;
- `subject`;
- `question_text`.

La regola più importante è l'evidenza: `evidence_text` deve comparire nel testo del chunk o frammento indicato, e quel chunk o frammento deve appartenere alla stessa `source_revision_id`. Se la prova non torna, il record viene rifiutato e inserito in `rejected_candidates`, con motivazione.

I record validi vengono inseriti in `candidate_records`, raggruppati in `candidate_batches`. I record originali sono salvati come payload JSON per preservare l'input AI.

## 13. Merge nel registry semantico

Il comando `facts merge` materializza candidati validi nel registry semantico.

Attualmente il merge consolida:

- `candidate_fact` in `facts`;
- `candidate_relation` in `relations`.

I tipi `candidate_mapping`, `candidate_conflict` e `candidate_question` sono accettati dalla validazione ma non vengono ancora materializzati in tabelle semantiche dedicate dal merge corrente. Sono quindi preservati come candidate record, ma risultano conteggiati tra i record saltati dal merge.

### Merge dei fatti

Per un `candidate_fact`, l'identità logica viene calcolata da:

```text
fact
canonical_entity_name
property_key
normalized_property_value
```

Questo produce un identity hash idempotente. Rieseguire il merge non duplica fatti già esistenti.

Lo stato del fatto dipende da `assertion_type`:

- `explicit` e `observed` diventano `active`;
- `inferred` diventa `inferred`;
- `ambiguous` diventa `pending_review`.

Per ogni fatto viene creata una prova in `fact_evidence`, con candidate record, source revision, chunk o frammento ed hash dell'evidence text.

### Merge delle relazioni

Per una `candidate_relation`, l'identità logica viene calcolata da:

```text
relation
canonical_source_entity
relation_type_key
canonical_target_entity
```

Anche le relazioni sono idempotenti. L'evidenza viene salvata in `relation_evidence`.

### Conflitti

Durante il merge dei fatti, se esiste già un fatto per la stessa entità canonica e proprietà, ma con valore normalizzato diverso, DSL Manager crea un conflitto di tipo:

```text
different_values_same_property
```

I fatti coinvolti vengono marcati `conflicted` e il conflitto viene salvato in `conflicts`.

Questa gestione è importante perché il sistema non sceglie automaticamente una verità quando trova affermazioni incompatibili: registra il problema e lo rende visibile negli output.

## 14. Rendering del DSL

Il comando `dsl render` genera snapshot DSL a partire dallo stato corrente del registry.

Il renderer include:

- fatti con stato `active`, `inferred`, `pending_review` o `conflicted`;
- relazioni;
- conflitti;
- traceability verso evidenze e fonti;
- metadati con conteggi e hash.

Gli output vengono scritti in:

```text
exports/dsl/
```

I formati prodotti sono:

```text
DSL_<id>.json
DSL_<id>.yaml
DSL_<id>.md
```

Lo snapshot viene registrato in `dsl_snapshots`, con path, conteggi, `dsl_hash`, `registry_hash` e stato.

La struttura logica del DSL contiene:

- `metadata`;
- `entities`;
- `relations`;
- `conflicts`;
- `traceability`.

Il DSL JSON e YAML sono i formati più adatti ad automazioni successive. Il Markdown è utile per review umana.

## 15. Struttura del DSL generato

La sezione `metadata` contiene:

- versione schema;
- identificativo snapshot;
- hash DSL;
- hash registry;
- conteggi di entità, fatti, relazioni e conflitti.

La sezione `entities` raggruppa i fatti per entità di dominio. Ogni entità ha:

- nome;
- nome canonico;
- lista di fatti con tipo, proprietà, valore, assertion, confidence e stato.

La sezione `relations` conserva archi semantici tra entità, ad esempio:

```text
Cliente places Ordine
Ordine has_rows RigaOrdine
```

La sezione `conflicts` espone conflitti aperti o storicizzati.

La sezione `traceability` è la parte più rilevante per audit: collega ogni fatto o relazione alla prova originale, includendo candidate record, source revision, source, file path, chunk o frammento ed hash dell'evidence text.

## 16. Differenze tra snapshot DSL

Il comando `dsl diff` confronta due snapshot persistiti.

Prima del confronto il loader valida struttura, metadati, hash, sezioni e traceability. Se i due `dsl_hash` coincidono, la diff è vuota.

Il confronto rileva:

- entità aggiunte o rimosse;
- fatti aggiunti, rimossi o modificati;
- relazioni aggiunte, rimosse o modificate;
- conflitti aggiunti, rimossi o modificati.

Per le modifiche vengono confrontati campi semanticamente rilevanti, come valore proprietà, assertion, confidence e stato.

La diff richiede cause tracciabili: candidate record, source revision, source, file path ed evidence hash. Se la traceability manca, la diff fallisce invece di produrre un risultato ambiguo.

Gli output sono:

```text
exports/dsl_diff/<FROM>__<TO>.json
exports/dsl_diff/<FROM>__<TO>.md
```

## 17. Export GEXF

Il comando `graph export` produce un grafo diretto in formato GEXF, pensato per strumenti di analisi grafica.

I nodi principali sono:

- entità di dominio;
- fatti di tipo business rule, se configurati come nodi;
- fonti, se incluse;
- conflitti, se inclusi.

Gli archi principali sono:

- relazioni semantiche tra entità;
- `mentions` tra entità e nodi fact;
- `derives_from` verso fonti;
- `conflicts_with` per conflitti.

L'export può gestire riferimenti a entità mancanti creando nodi orfani con warning, oppure fallire in modalità strict.

Gli output sono:

```text
exports/graph/<SNAPSHOT>.gexf
exports/graph/<SNAPSHOT>.graph_report.json
```

L'operazione viene registrata in `graph_exports`.

## 18. Batch orchestration

I comandi batch permettono di applicare pipeline a directory o insiemi di file.

`batch process-dir` esegue una pianificazione basata su source type e suffisso:

- documenti legacy e file documentali: normalizzazione e chunking;
- XML: parser XML form;
- log: parser log;
- SQL con segnali DDL: parser DDL;
- SQL con segnali procedure o trigger: parser codice database.

Un file SQL può essere analizzato da più parser se contiene sia struttura sia codice. I file non supportati vengono segnati come skipped, con motivazione.

Il batch continua dopo errori salvo opzione `stop_on_error`. Produce un report `batch_report.json` dentro gli artefatti della run.

Altri batch gestiscono:

- chunking di directory;
- costruzione di package AI per gruppi di evidenze;
- validazione massiva di JSONL candidati;
- merge massivo di batch candidati.

## Flusso per tipologia di input

### Documenti funzionali e manuali

Percorso tipico:

```text
file nel corpus
  -> source_revision
  -> Docling normalized.md / normalized.json
  -> chunks
  -> AI package
  -> candidate_fact / candidate_relation
  -> facts / relations
  -> DSL
```

Questo flusso è adatto a manuali, specifiche e documentazione utente. Il testo viene trasformato in chunk con contesto heading, e l'AI estrae candidate fact e candidate relation con prova testuale.

### DDL SQL

Percorso tipico:

```text
DDL nel corpus
  -> source_revision
  -> source_fragments ddl_table / ddl_column / ddl_constraint
  -> AI package
  -> candidati tecnici o semantici
  -> registry
  -> DSL o export derivati
```

Il DDL fornisce evidenze ad alta autorità sulla struttura dati. Può sostenere mapping tra entità di dominio e oggetti fisici, oppure relazioni derivate da chiavi esterne.

### XML form

Percorso tipico:

```text
XML form
  -> source_revision
  -> source_fragments xml_form / xml_field / xml_button
  -> AI package
  -> regole, mapping, domande o relazioni candidate
```

Le form collegano esperienza utente e struttura tecnica: campi obbligatori, azioni e riferimenti a tabelle o colonne.

### Procedure e trigger

Percorso tipico:

```text
SQL procedurale
  -> source_revision
  -> source_fragments sql_trigger / sql_procedure / sql_statement
  -> AI package
  -> candidate_fact o candidate_relation su comportamento runtime
```

Questo flusso consente di intercettare regole operative nascoste nel database, come aggiornamenti automatici, stati, effetti collaterali e logiche di calcolo.

### Log

Percorso tipico:

```text
log
  -> source_revision
  -> source_fragments log_event
  -> AI package
  -> candidate_fact osservazionali o domande
```

I log sono evidenze di comportamento osservato. Hanno authority diversa da DDL o codice, ma sono preziosi per rilevare sequenze operative, anomalie e identificativi reali.

## Esempio end-to-end dalle fixture

Le fixture principali descrivono un dominio commerciale con clienti, ordini e righe ordine.

La conoscenza documentale attesa produce tre entità:

- `Cliente`;
- `Ordine`;
- `RigaOrdine`.

Produce sei fatti:

- descrizione di `Cliente`;
- regola di cancellazione di `Cliente`;
- descrizione di `Ordine`;
- proprietà di composizione di `Ordine`;
- valori di stato di `Ordine`;
- descrizione di `RigaOrdine`.

Produce due relazioni:

- `Cliente places Ordine`;
- `Ordine has_rows RigaOrdine`.

L'output atteso del DSL contiene:

```text
entities: 3
facts: 6
relations: 2
conflicts: 0
```

Lo snapshot atteso include hash deterministici di DSL e registry. Questo conferma che il rendering non dipende dall'ordine casuale di lettura o da dettagli non stabili.

## Qualità dei dati e determinismo

DSL Manager usa più livelli di controllo:

- hash dei file sorgente;
- hash del Markdown normalizzato;
- hash dei chunk;
- hash dei frammenti;
- hash dei file del package AI;
- hash del registry usato per renderizzare il DSL;
- hash del DSL generato.

Questi hash rendono rilevabili modifiche accidentali o non autorizzate. Inoltre, gli identificativi progressivi e gli identity hash di fatti e relazioni consentono riesecuzioni idempotenti.

Il sistema non assume che l'AI sia deterministica. La parte non deterministica viene confinata nell'output JSONL. Da quel punto in poi, validazione, merge e rendering sono regole applicative deterministiche.

## Auditability

L'audit è sostenuto da quattro elementi:

1. `source_events`, che tracciano ingresso, modifica e cancellazione delle fonti;
2. `runs` e `worker_runs`, che tracciano ogni elaborazione;
3. tabelle evidence, che collegano conoscenza consolidata a prove;
4. traceability DSL, che porta questi riferimenti fino agli output.

In pratica, dato un fatto nel DSL è possibile risalire a:

- fatto persistito;
- candidate record;
- batch di import;
- source revision;
- source file;
- chunk o frammento;
- testo di evidenza;
- run che ha prodotto gli artefatti coinvolti.

Questa catena è cruciale per modernization, assessment e review tecnica, perché rende discutibile e verificabile ogni affermazione.

## Failure mode principali

### Fallimento Docling

Se Docling fallisce, il worker fallisce e il database non riceve mutazioni. Gli errori vengono riportati nel process report e nei log.

### Opzioni Docling non ammesse

Le opzioni non compatibili con il profilo applicativo vengono intercettate prima dell'elaborazione. Questo evita output non confrontabili o dipendenze implicite da immagini e OCR non previsti.

### Candidate fuori schema

Un record JSONL incompleto o con valori non ammessi viene rifiutato e salvato in `rejected_candidates`.

### Evidence text assente

Se `evidence_text` non compare nel chunk o frammento indicato, il candidato viene rifiutato. Questa è la protezione più importante contro allucinazioni o riferimenti deboli.

### Package stale

Se il corpus cambia dopo la creazione del package AI, l'import viene bloccato salvo override esplicito. Questo impedisce di applicare candidati generati su evidenze non più correnti.

### Output parziale del worker

Il runner valida l'output worker prima delle mutazioni. Output incompleti o incoerenti non vengono applicati al database.

### Conflitti semantici

Se due candidati producono fatti incompatibili sulla stessa proprietà, il sistema registra un conflitto invece di scegliere automaticamente.

### Entità orfane nel grafo

L'export GEXF può incontrare relazioni verso entità non presenti. In modalità permissiva crea nodi orfani e warning; in modalità strict fallisce.

## Confini applicativi attuali

L'implementazione corrente è solida sui flussi core, ma ha confini chiari:

- non chiama direttamente un provider AI;
- non conserva ancora mapping e question in tabelle semantiche dedicate;
- accetta `candidate_conflict`, ma i conflitti persistenti sono principalmente prodotti dalle regole di merge sui fatti;
- il log viewer disponibile espone output testuale o CSV;
- l'export grafo è GEXF, non una UI grafica integrata;
- il parser YAML interno è sufficiente per le configurazioni previste, non è un parser YAML generale.

Questi confini non compromettono il flusso principale. Indicano piuttosto che l'applicazione è orientata a una pipeline locale, verificabile e automatizzabile, con l'AI tenuta fuori dal perimetro di scrittura diretta.

## Valutazione tecnica complessiva

DSL Manager ha una struttura coerente con un'applicazione di modernization assistita da AI:

- separa fonti, evidenze, candidati e conoscenza consolidata;
- tratta il DSL come prodotto derivato e non come database primario;
- conserva proof chain robuste;
- rende rieseguibili e ispezionabili le elaborazioni;
- limita il rischio AI tramite schema, evidenza obbligatoria e validazione locale;
- supporta sia documenti naturali sia fonti tecniche strutturate;
- produce output consumabili da umani e strumenti.

La scelta più importante è il registry-first: tutto il valore dell'applicazione nasce dal fatto che la conoscenza non viene semplicemente generata, ma registrata, provata, fusa e poi renderizzata.

## Autoverifica

Prima di salvare questo documento ho verificato:

- struttura del package e comandi CLI;
- migrazioni SQLite e tabelle effettive;
- worker e contratti input/output;
- flusso corpus scan, normalizzazione, chunking e parser strutturali;
- costruzione e validazione dei package AI;
- schema e validazione dei candidate record;
- merge di fatti, relazioni e conflitti;
- rendering DSL, diff snapshot ed export GEXF;
- fixture e output attesi della suite di test;
- documentazione interna della `.kb`, distinguendo design generale e implementazione effettiva.

La conclusione è che il flusso portante è implementato end-to-end: dal corpus iniziale si arriva a DSL JSON/YAML/Markdown e a GEXF, mantenendo traceability completa verso le evidenze sorgenti.
