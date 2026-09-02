Implementa solo la Slice 6 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`
- `.kb/projects/slicing/slice_05/dsl_manager_slice_05_report.md`

Task:
Implementare la minima slice verticale funzionante per fondere `candidate_fact` e `candidate_relation` già validati nel registry, producendo `facts`, `relations`, evidence links e conflitti minimi.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs` e artifact deterministici.
- Slice 5 ha introdotto `chunks`, `source_fragments`, `candidate_batches`, `candidate_records`, `rejected_candidates` e il comando `candidates validate`.
- La Slice 6 deve leggere solo candidati già accettati in `candidate_records`.

Scope:
- aggiungere una nuova migration versionata, senza modificare le migration esistenti;
- aggiungere le tabelle minime:
  - `facts`;
  - `fact_evidence`;
  - `relations`;
  - `relation_evidence`;
  - `conflicts`;
- aggiungere un modulo core piccolo e testabile per il merge deterministico;
- aggiungere il comando CLI:

```powershell
dsl-manager facts merge <workspace> --batch CBATCH_000001
```

- mantenere compatibilità con:

```powershell
python -m dsl_mngr facts merge <workspace> --batch CBATCH_000001
```

Expected behavior:
- il comando verifica workspace, database migrato e batch esistente;
- crea una run di tipo `merge`;
- legge i record validi da `candidate_records` per il batch indicato;
- processa solo:
  - `candidate_fact`;
  - `candidate_relation`;
- ignora per ora `candidate_mapping`, `candidate_conflict` e `candidate_question`, contando questi record come skipped;
- inserisce `facts` e `relations` in modo idempotente;
- collega ogni fact/relation alla sua evidence tramite tabella dedicata;
- ripetere il merge dello stesso batch non deve duplicare `facts`, `relations`, evidence links o conflicts;
- il merge è transazionale: errori fatali dopo l’avvio della run fanno rollback e marcano la run come `failed`;
- rejection in `rejected_candidates` non partecipano al merge e non sono errori.

Schema minimo consigliato:
- `facts`:
  - `fact_id`;
  - `fact_identity_hash` unique;
  - `fact_type`;
  - `entity_name`;
  - `canonical_entity_name`;
  - `property_name`;
  - `property_value`;
  - `normalized_property_value`;
  - `assertion_type`;
  - `confidence`;
  - `status`;
  - `first_candidate_record_id`;
  - `created_at`;
  - `updated_at`.
- `fact_evidence`:
  - `fact_evidence_id`;
  - `fact_id`;
  - `candidate_record_id`;
  - `source_revision_id`;
  - `chunk_id`;
  - `fragment_id`;
  - `evidence_text`;
  - `evidence_text_hash`;
  - `created_at`.
- `relations`:
  - `relation_id`;
  - `relation_identity_hash` unique;
  - `source_entity`;
  - `canonical_source_entity`;
  - `relation_type`;
  - `target_entity`;
  - `canonical_target_entity`;
  - `assertion_type`;
  - `confidence`;
  - `status`;
  - `first_candidate_record_id`;
  - `created_at`;
  - `updated_at`.
- `relation_evidence`:
  - campi equivalenti a `fact_evidence`, con `relation_id`.
- `conflicts`:
  - `conflict_id`;
  - `conflict_key_hash` unique;
  - `conflict_type`;
  - `entity_name`;
  - `canonical_entity_name`;
  - `property_name`;
  - `left_fact_id`;
  - `right_fact_id`;
  - `left_value`;
  - `right_value`;
  - `status`;
  - `created_at`;
  - `updated_at`.

Regole di merge:
- normalizzare nomi canonici con trim, lowercase e compressione whitespace;
- normalizzare valori per hash con trim e compressione whitespace;
- `assertion_type = explicit` o `observed` produce status `active`;
- `assertion_type = inferred` produce status `inferred`;
- `assertion_type = ambiguous` produce status `pending_review`;
- stessa entity + property + stesso valore: riusa il fact esistente e aggiungi solo l’evidence mancante;
- stessa entity + property + valore diverso: crea o riusa un conflict `different_values_same_property`;
- quando nasce un conflict, marca i `facts` coinvolti come `conflicted`;
- per le `relations`, stessa source entity + relation type + target entity riusa la relation esistente e aggiunge solo evidence mancante.

Output CLI minimo:
```text
Run: RUN_000002
Batch: CBATCH_000001
Candidate records: 2
Facts created: 1
Facts existing: 0
Relations created: 1
Relations existing: 0
Conflicts created: 0
Conflicts existing: 0
Skipped: 0
```

Artifact:
- `input.json`, `output.json` e `process_report.json` devono includere:
  - `batch_id`;
  - `candidate_record_count`;
  - `facts_created`;
  - `facts_existing`;
  - `relations_created`;
  - `relations_existing`;
  - `conflicts_created`;
  - `conflicts_existing`;
  - `skipped_records`;
- i path restano relativi al workspace;
- aggiungi log JSONL applicativo per merge completato o fallito.

Constraints:
- non reimplementare import JSONL o candidate validation;
- non processare `candidate_mapping`, `candidate_conflict` o `candidate_question` oltre al conteggio skipped;
- non creare snapshot DSL;
- non implementare renderer DSL, diff, GEXF, Docling, parser, chunker, AI package o chiamate AI reali;
- non introdurre ORM;
- non introdurre nuove dipendenze runtime;
- mantenere separati CLI, core merge e persistence;
- usare import assoluti dal package `dsl_mngr`;
- mantenere l’implementazione piccola, leggibile e deterministica;
- i test devono usare `tmp_path`.

Test minimi richiesti:
- `test_merge_facts_idempotent`;
- `test_merge_relation`;
- `test_merge_conflict`.

I test devono verificare almeno:
- un `candidate_fact` valido diventa un record in `facts`;
- l’evidence viene salvata in `fact_evidence`;
- rieseguire il merge dello stesso batch non duplica `facts`/evidence;
- un `candidate_relation` valido diventa un record in `relations`;
- l’evidence viene salvata in `relation_evidence`;
- due `facts` sulla stessa entity/property con valori diversi creano un conflict `different_values_same_property`;
- i `facts` confliggenti vengono marcati `conflicted`;
- la run `merge` viene completata e produce artifact coerenti;
- il comando funziona anche via `python -m dsl_mngr`;
- nessuna regressione sulle slice 1-5.

Done when:
- Slice 6 è implementata end-to-end;
- le migration sono idempotenti;
- i test nuovi sono significativi;
- tutta la suite passa;
- non è stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l’interprete corretto per l’ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l’interprete corretto;
5. mostra diff e risultato dei test, indicando l’interprete usato.
