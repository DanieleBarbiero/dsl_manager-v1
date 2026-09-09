# Contratti dati e manifest di DSL Manager

## 1. Scopo

Questo documento è il riferimento operativo per schema persistente, artefatti e
manifest consegnati fino alla Slice 28. Non sostituisce il
[design v02](../documenti%20di%20design/run%202/design_document_v_02.md). La
[analisi tecnica](analisi_tecnica_dsl_manager.md) spiega l'architettura e il
[manuale](../manuali/manuale_utente_dsl_manager.md) mostra i comandi.

Principio di autorità:

```text
byte osservati -> evidenza -> candidato pending -> decisione -> merge
```

Un manifest registra osservazioni e provenienza; non è, da solo, verità di
dominio. Un candidato strutturalmente valido non è merge-eligible finché la sua
foglia corrente non ha una testa `confirmed`.

## 2. Regole trasversali

- I path condivisibili sono relativi al workspace e usano `/`.
- I contenuti JSON deterministici usano la serializzazione canonica del progetto.
- Gli hash semantici non includono path assoluti, timestamp operativi, run ID o
  note di audit.
- Gli ID runtime sono persistenti ma non sostituiscono gli hash dei contenuti.
- Gli artefatti già registrati non vengono riscritti retroattivamente.
- Le evidenze lunghe o sensibili non devono essere replicate in log e report.
- Gli output dei worker vengono validati prima di essere applicati al registry.

## 3. Schema SQLite e migrazioni

`schema_migrations(version, name, checksum, applied_at)` è la catena di custodia
dello schema. All'apertura, il codice verifica versione, nome e checksum; una
divergenza blocca l'operazione.

| Versione | Nome | Aggiunte principali |
|---:|---|---|
| 1 | `create_minimal_registry_schema` | sources, revisions, runs, worker runs |
| 2 | `create_candidate_validation_schema` | chunks/fragments, batch e record candidati, rifiuti |
| 3 | `create_fact_merge_schema` | facts, relations, evidence e conflicts |
| 4 | `create_dsl_snapshot_schema` | snapshot DSL |
| 5 | `create_ai_package_schema` | package AI e stato inbox |
| 6 | `create_graph_export_schema` | export GEXF registrati |
| 7 | `create_candidate_review_lineage_schema` | review, heads, lineage, correzioni, reconcile, derivation, effective views |
| 8 | `create_workbook_manifest_schema` | manifest, fogli e regioni workbook |
| 9 | `create_temporal_core_schema` | raw evidence, candidati temporali e intervalli |
| 10 | `create_temporal_consolidation_schema` | gruppi, membri e conflitti temporali |

Le migrazioni v7-v10 sono append-only rispetto alla cronologia applicata. La v7
ricostruisce `candidate_batches` per ammettere origini interne senza `input_path`
e applica un backfill selettivo: solo candidati legacy `explicit` o `observed`
che già sostengono oggetti attivi ricevono una decisione sintetica
`system/migration`, `confirmed`, policy `legacy_backfill/1`. Gli altri restano
senza approvazione. Gli snapshot precedenti non cambiano.

## 4. Contratto workspace e registry sorgenti

### 4.1 Workspace

I path canonici includono:

```text
corpus/active/
configs/
ai/outbox/
ai/inbox/
runs/<RUN_ID>/artifacts/
exports/dsl/
exports/graph/
logs/
workspace.sqlite
```

La posizione del database è configurabile, ma viene risolta all'interno del
workspace secondo i controlli del core.

### 4.2 Source e source revision

`sources` identifica la fonte logica; `source_revisions` identifica byte
specifici tramite `content_hash`, `file_size`, `file_path` relativo e numero di
revisione. La scansione mantiene una sola revisione corrente per fonte e conserva
la storia di sostituzione/rimozione.

`sources.first_seen_at` è un dato operativo del registry. Può essere registrato
come evidenza temporale a bassa affidabilità, ma non prova la validità semantica.
I timestamp del filesystem (`mtime`, `ctime`) non fanno parte del contratto di
evidenza.

## 5. Contratti di evidenza

### 5.1 Chunk e frammenti

Un candidato non temporale deve riferire almeno uno tra `chunk_id` e
`fragment_id`. Il riferimento deve esistere, appartenere alla stessa
`source_revision_id` e contenere l'`evidence_text` dichiarato.

I chunk provengono da testo normalizzato. I frammenti provengono da parser DDL,
XML form, codice DB, log o manifest workbook. I locator tecnici possono includere
path/selector, linee, foglio, coordinate, parte OOXML e manifest ID.

### 5.2 Raw temporal evidence

`raw_temporal_evidence` è append-only e contiene almeno:

- target type/id e source revision/fragment;
- `source_key`, `source_format`, `raw_value`;
- metodo/versione di estrazione;
- precisione originale;
- timezone status/value;
- affidabilità iniziale e warning;
- evidence hash canonico.

I target ammessi sono `source_revision`, `source_fragment`, `candidate_record`,
`fact` e `relation`. `explicit`, `resolved`, `unknown` e `incompatible` sono gli
stati timezone persistibili. Raw evidence e metadata restano segnali da
revisionare, non fatti autoritativi.

## 6. Candidati, review e decisioni

### 6.1 Candidate record

Tipi accettati dal validator:

```text
candidate_fact
candidate_relation
candidate_mapping
candidate_conflict
candidate_question
temporal_interval
```

Campi comuni obbligatori: `candidate_id`, `source_revision_id`,
`assertion_type`, `confidence`, `evidence_text`. Gli assertion type sono
`explicit`, `inferred`, `ambiguous`, `observed`; la confidence è `high`,
`medium` o `low`. I campi semantici non possono contenere placeholder irrisolti.

Campi specifici:

| Tipo | Campi principali |
|---|---|
| `candidate_fact` | `fact_type`, `entity_name`, `property_name`, `property_value` |
| `candidate_relation` | `source_entity`, `relation_type`, `target_entity` |
| `candidate_mapping` | `domain_entity`, `technical_object`, `mapping_type` |
| `candidate_conflict` | `conflict_type`, `subject`, `left_value`, `right_value` |
| `candidate_question` | `question_type`, `subject`, `question_text` |
| `temporal_interval` | target, precision, timezone, bounds, policy ed evidence IDs |

L'import registra record validi e rifiuti separati. “Accepted” significa valido
per lo schema del candidato, non confermato e non mergeabile.

### 6.2 Origine dei batch

`candidate_batches.origin_type` ammette:

- `file_import` e `ai_import`, con `input_path`;
- `deterministic_derivation`, senza `input_path` e con `origin_ref`;
- `human_correction`, senza `input_path` e con `origin_ref`.

### 6.3 Review decision

`review_decisions` è append-only. Il contratto comprende soggetto, attore,
outcome, reason, run, decisione precedente/attesa, chiave idempotente, hash e JSON
request/semantic, policy/versione. `review_decision_evidence` conserva i
riferimenti ordinati; `review_subject_heads` seleziona la testa corrente.

Gli outcome ammessi sono:

- `confirmed`: testa positiva;
- `rejected`: testa negativa;
- `superseded`: testa sostituita/corretta.

`pending` non è una decisione persistita: è l'assenza di testa. Il merge richiede
la foglia corrente con testa `confirmed`.

Replay e concorrenza:

- `(actor_type, actor_id, idempotency_key)` è unico;
- replay identico restituisce la decisione esistente;
- stessa chiave con request hash diverso è conflitto;
- `expected_head_decision_id` deve coincidere con la testa corrente;
- un payload semanticamente identico alla testa produce `semantic_noop`.

### 6.4 Correzione e lineage

`candidate_lineage` conserva root e parent; `candidate_corrections` conserva
originale, sostituzione, delta ed evidence refs. Trigger e servizio impediscono
cicli, rami e update/delete della lineage. La correzione crea un nuovo candidato
già confermato in un nuovo batch e rende l'originale `superseded`; non modifica
il payload originario.

## 7. Effective views, merge e reconcile

Le viste effettive sono:

```text
effective_fact_evidence
effective_relation_evidence
effective_facts
effective_relations
```

Una evidence row è effettiva soltanto se il candidato è una foglia e la testa è
`confirmed`. Un oggetto con altri supporti positivi resta effettivo.

`facts merge` materializza `candidate_fact` e `candidate_relation`. Un candidato
temporale viene materializzato dalla review comune quando la foglia è confermata;
il merge ne verifica la presenza e lo include nei propri contatori governati.
Mapping, conflict e question restano record candidati senza materializzazione
dedicata. Il merge è idempotente sui semantic identity hash e conserva la
traceability.

Una modifica della testa dopo materializzazione può aprire
`reconciliation_required`. `facts reconcile` applica la compensazione senza
cancellare cronologia e chiude la richiesta quando il replacement è stato
materializzato o la rimozione è risolta. Con richieste aperte render, diff ed
export sono bloccati per default.

## 8. Contratto di derivazione

Ogni regola ha `rule_id`, `rule_version`, parser/fragment schema, tipo candidato,
assertion type, locator, policy automatica e default `pending`. Le regole
consegnate sono:

```text
ddl_table_fact/1
ddl_column_fact/1
ddl_fk_relation/1
xml_form_structure/1
xml_table_usage/1
db_code_unit/1
db_code_dependency/1
log_event_observation/1
excel_workbook_fact/1
excel_sheet_fact/1
excel_region_fact/1
excel_named_range_fact/1
excel_table_fact/1
excel_explicit_reference/1
```

Tutte producono candidati. `excel_explicit_reference/1` non consente review
automatica; il log richiede una policy esplicita nominata. Una policy automatica
deve comparire in `review.automatic_policies` e coincidere con quella del
contratto di regola.

Il report di derive usa `result_catalog_v1`, pubblica conteggi per regola,
deduplicati/rifiutati/pending, payload hash e semantic report hash.

## 9. Contratto batch consolidato

Il checkpoint ha `schema_version: "2"`, `catalog_version:
"result_catalog_v1"`, opzioni, run/retry ID e cinque fasi ordinate:

```text
parse, derive, review, merge, reconcile
```

Ogni fase registra status, tentativi, transizioni e result. Gli status fase
ammessi includono `pending`, `running`, `completed`, `blocked`, `failed` e
`skipped`. `--resume` riusa soltanto fasi coerentemente completate; le fasi da
rifare tornano pending. La review automatica senza policy consentita non viene
simulata. `--strict-review` rende il merge all-or-nothing per la precondizione di
review.

## 10. Contratti Excel/OOXML

### 10.1 Ingest diretto

`.xlsx` e `.xlsm` sono package OOXML letti direttamente. Per `.xlsm` non esiste
conversione in `.xlsx`: il VBA viene solo inventariato/hashato e non eseguito.
Il parent consegna al preflight e a Docling gli stessi byte della revisione.

Il preflight controlla:

- firme ZIP, entry duplicate e path traversal;
- content types coerenti con estensione;
- DTD/entity e dimensione delle part XML;
- relazioni interne/esterne, senza dereferenziare target esterni;
- budget di file, entry, decompressione, rapporto, fogli, celle, regioni,
  relazioni, output, tempo e memoria.

### 10.2 `workbook_manifest.json`

Il manifest è JSON canonico schema `"1"`, legato a
`source_revision.content_hash`. Contiene:

- workbook metadata tecnici e warning;
- fogli ordinati con visibilità, relationship/part name e bounds;
- celle ordinate con coordinate, tipo, value, formula e cached value distinti;
- merged cells, named ranges e tabelle;
- hyperlink, relazioni e link esterni marcati `not_dereferenced`;
- macro presence e hash, con `macros_executed: false`;
- regioni ordinate con tipo, coordinate, region hash e fragment locator.

`workbook_manifests`, `workbook_sheets` e `workbook_regions` registrano il
manifest senza duplicare l'intero OOXML. Ogni regione ha un frammento
`excel_region`; rerun identici riusano identità stabili e rendono stale soltanto
frammenti non più prodotti.

Docling produce `normalized.json`/`normalized.md` per lettura umana. Il manifest
e i frammenti sono autoritativi solo per la struttura tecnica osservata; il testo
Docling e le formule non sono autorità semantica.

### 10.3 Stati ed exit OOXML

I principali exit code sono `0` successo, `3` rifiuto sicurezza/budget, `4`
byte cambiati, `5` errore/timeout worker e `6` partial accettabile. Su partial gli
artefatti sono marcati tali; su errore operativo gli artefatti incompleti non
vengono pubblicati come completi.

## 11. Contratti temporali

### 11.1 Consolidamento

La v10 aggiunge `temporal_evidence_groups`,
`temporal_evidence_group_members` e `temporal_conflicts`. I membri sono
classificati `independent`, `correlated`, `duplicate` o `low_quality`; gli
assessment sono `concordant`, `single_source`, `ambiguous`, `conflicted` o
`low_quality`.

Contraddizioni aprono un conflitto e producono proposte pending. Due segnali
correlati non contano come due conferme indipendenti. L'eventuale adapter AI
offline può proporre candidati/evidenze, mai modificare lo stato autoritativo.

### 11.2 `temporal_interval`

Il candidato contiene target, start/end normalizzati, precisione originale,
timezone status/value, bounds, policy/versione ed evidence IDs. Solo una
decisione `confirmed` lo materializza in `temporal_intervals`; tabella e raw
evidence sono append-only.

- `year`: envelope `YYYY-01-01` / `YYYY-12-31`;
- `month`: primo/ultimo giorno del mese;
- `day`: data ISO;
- `dateTime`: conserva precisione e richiede offset esplicito o timezone
  risolta;
- bounds: `inclusive` o `coverage_envelope`.

Timezone unknown/incompatible resta pending o viene omessa soltanto in una
modalità incompleta esplicita. Non viene convertita silenziosamente in `date`.
Più intervalli disgiunti restano distinti e ordinati.

## 12. DSL e diff

### 12.1 Schema 1

Schema 1 è il contratto legacy/statico. Legge lo stato fisico per compatibilità,
non accetta `--allow-incomplete` e alimenta solo export GEXF statici. Gli snapshot
storici restano leggibili e immutati.

### 12.2 Schema 2

Schema 2 legge effective views e aggiunge:

- metadata temporal con profilo GEXF;
- `intervals` sempre presenti per facts e relations;
- più intervalli e traceability temporale;
- marker `incomplete`, warning e conteggi quando autorizzato.

`--allow-incomplete` è valido soltanto per schema 2. Non rende mergeabili i
pending: omette oggetti non effettivi mentre una riconciliazione resta aperta.

### 12.3 Diff

Il diff ordinario richiede snapshot dello stesso schema. `--cross-schema` abilita
esplicitamente v1/v2 e separa differenze `structural`, `governance` e `temporal`.
Il diff non altera gli snapshot confrontati.

## 13. GEXF 1.3

Lo statico legacy consuma DSL v1. Il dinamico richiede DSL v2 e produce GEXF 1.3
diretto, con `mode="dynamic"`, `timerepresentation="interval"` e un solo
`timeformat` per file.

`--temporal-output-mode`:

- `strict`: errore su intervalli irrisolti o profilo incompatibile;
- `omit`: omette gli intervalli incompatibili e aggiunge warning;
- `separate`: pubblica file distinti per profilo temporale.

`--allow-incomplete` vale solo per export dinamico. Bounds/spells sono inclusivi;
edge source/target devono esistere e ogni intervallo edge deve essere contenuto
nei bounds degli estremi.

La validazione è offline e composta da:

1. XSD GEXF 1.3, dynamics e viz vendorizzati e verificati per hash;
2. controlli semantici su namespace/versione, IDs, riferimenti, tipi, ordine,
   timeformat e containment.

La sola XSD non soddisfa il contratto. Nessun resolver può accedere alla rete.

Gap: il limite previsto dal design per nodi+archi GEXF non è implementato nel
codice corrente.

## 14. Package AI

Il package AI contiene directory package, `manifest.json`,
`source_manifest.json`, contenuto, istruzioni, `candidate_schema.json` e template
di output. Il package hash deriva dai file dichiarati; source revision, chunk e
fragment sono elencati con identità e hash.

L'inbox riconosce `<AIPKG_ID>_candidates.jsonl`, verifica che package e manifest
siano correnti e blocca gli stale per default. `--allow-stale` registra
esplicitamente l'eccezione. L'import usa il validator comune e produce candidati
pending; nessun output AI viene fuso direttamente.

## 15. Result catalog ed exit code

L'envelope richiesto dal design è `result_catalog_v1` con:

```text
catalog_version, condition, status, outcome, reason, severity,
mutations, retryable, exit_code, run_id, subject_ids,
artifact_paths, counters
```

È implementato in review, derive, merge, reconcile e batch consolidato. Gli
esiti includono `idempotent_replay`, `semantic_noop`,
`review_head_conflict`, `no_merge_eligible_candidates`,
`merge_review_precondition_failed`, `reconciliation_required`,
`replacement_merge_pending`, `ooxml_security_violation`,
`temporal_profile_incompatible`, `gexf_xsd_invalid` e
`gexf_semantic_invalid`.

Gap osservato: OOXML/worker usa ancora `catalog_version: 1`; i risultati
temporali e il graph report non pubblicano tutti i campi dell'envelope comune.
Pertanto `result_catalog_v1` non va descritto come uniforme su ogni produttore
finché il runtime non verrà allineato.

## 16. Compatibilità e rischi

- Schema 1/statico resta fisico e legacy; schema 2/dinamico è governato dalle
  viste effettive.
- La migrazione v7 non conferma genericamente ogni candidato storico.
- Pending non significa approvato e non è mergeabile.
- `.xlsm` non è convertito; macro, formule e link non sono eseguiti.
- Metadata e timestamp package/registry sono evidenza grezza, non verità.
- Formula Docling non sostituisce formula/cached del manifest.
- GEXF dinamico richiede XSD e validazione semantica offline.
- Mapping/question/conflict non hanno materializzazione dedicata.
- Budget GEXF e catalogo uniforme restano gap runtime documentati.

## 17. Riferimenti verificabili

- [Manuale utente](../manuali/manuale_utente_dsl_manager.md)
- [Outline input-output](../manuali/outline%20dsl%20manager%20flow%20from%20input%20to%20output.md)
- [Corpus Aurora](../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/LEGGIMI_PRIMA.md)
- [Checklist Aurora](../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/checklist_risultati_attesi.md)
- [Report Slice 28](../../projects/slicing/slice_28/dsl_manager_slice_28_report.md)
