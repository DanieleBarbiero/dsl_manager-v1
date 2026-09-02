Implementa solo la Slice 5 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`

Task:
Implementare la minima slice verticale funzionante per importare un file JSONL di candidate records fixture, validarli contro schema ed evidence locale, e separare i candidati validi da quelli rifiutati.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs` e artifact deterministici sotto `artifacts/runs/RUN_xxxxxx`.
- La Slice 5 deve costruire sopra queste basi, senza introdurre merge, renderer DSL, Docling, parser o AI reale.

Scope:
- aggiungere una nuova migration versionata, senza modificare la migration esistente;
- aggiungere le tabelle minime necessarie per la validazione candidate:
  - `chunks`, come evidence table minimale per documenti chunked;
  - `source_fragments`, come evidence table minimale per future fonti strutturali;
  - `candidate_batches`;
  - `candidate_records`;
  - `rejected_candidates`;
- aggiungere validazione schema per i record type:
  - `candidate_fact`;
  - `candidate_relation`;
  - `candidate_mapping`;
  - `candidate_conflict`;
  - `candidate_question`;
- aggiungere un modulo core piccolo e testabile per import/validation dei candidati;
- aggiungere il comando CLI:

```powershell
dsl-manager candidates validate <workspace> --input <path-to-candidates.jsonl>
```

- mantenere compatibilita' con:

```powershell
python -m dsl_mngr candidates validate <workspace> --input <path-to-candidates.jsonl>
```

Expected behavior:
- il comando legge un file JSONL dentro il workspace, tipicamente sotto `ai/inbox`;
- ogni riga non vuota viene trattata come un candidato indipendente;
- JSON invalido non blocca l'intero batch: la riga viene salvata in `rejected_candidates` con reason `invalid_json`;
- i candidati validi vengono salvati in `candidate_records`;
- i candidati non validi vengono salvati in `rejected_candidates`;
- viene creato un record in `candidate_batches` con input path relativo al workspace e conteggi:
  - `total_records`;
  - `accepted_count`;
  - `rejected_count`;
- il comando stampa almeno:

```text
Run: RUN_000001
Batch: CBATCH_000001
Total: 1
Accepted: 1
Rejected: 0
```

- il comando crea una run di tipo `candidate_validation` usando il lifecycle della Slice 4;
- la run produce artifact deterministici in `artifacts/runs/RUN_xxxxxx`;
- `output.json` e `process_report.json` includono batch id, total, accepted e rejected;
- rejection per singoli record non rende fallita la run;
- errori fatali del comando, come workspace non inizializzato, database non migrato o input path fuori workspace, falliscono con errore leggibile e exit code `2`;
- i path salvati nel database restano relativi al workspace e usano `/`.

Schema validation minima:
- ogni candidato deve essere un JSON object;
- `record_type` deve essere uno dei tipi ammessi;
- i campi comuni richiesti sono:
  - `candidate_id`;
  - `source_revision_id`;
  - `assertion_type`;
  - `confidence`;
  - `evidence_text`;
- deve essere presente almeno uno tra `chunk_id` e `fragment_id`;
- `assertion_type` deve essere uno tra:
  - `explicit`;
  - `inferred`;
  - `ambiguous`;
  - `observed`;
- `confidence` deve essere uno tra:
  - `high`;
  - `medium`;
  - `low`;
- `evidence_text` deve essere non vuoto.

Campi specifici richiesti:
- `candidate_fact`:
  - `fact_type`;
  - `entity_name`;
  - `property_name`;
  - `property_value`;
- `candidate_relation`:
  - `source_entity`;
  - `relation_type`;
  - `target_entity`;
- `candidate_mapping`:
  - `domain_entity`;
  - `technical_object`;
  - `mapping_type`;
- `candidate_conflict`:
  - `conflict_type`;
  - `subject`;
  - `left_value`;
  - `right_value`;
- `candidate_question`:
  - `question_type`;
  - `subject`;
  - `question_text`.

Evidence validation minima:
- `source_revision_id` deve esistere in `source_revisions`;
- se e' presente `chunk_id`:
  - il chunk deve esistere in `chunks`;
  - il chunk deve appartenere alla `source_revision_id` indicata;
  - `evidence_text` deve comparire nel testo del chunk;
- se e' presente `fragment_id`:
  - il fragment deve esistere in `source_fragments`;
  - il fragment deve appartenere alla `source_revision_id` indicata;
  - `evidence_text` deve comparire nel testo del fragment;
- se sono presenti sia `chunk_id` sia `fragment_id`, basta che entrambi siano coerenti con la stessa `source_revision_id`; l'evidence puo' essere verificata sul chunk o sul fragment.

Rejection reasons minime:
- `invalid_json`;
- `schema_validation_failed`;
- `unknown_source_revision`;
- `unknown_chunk`;
- `unknown_fragment`;
- `chunk_source_mismatch`;
- `fragment_source_mismatch`;
- `evidence_text_not_found`;
- `invalid_assertion_type`;
- `invalid_confidence`.

Constraints:
- non implementare il merge in `facts`, `relations`, `mappings`, `conflicts` o `questions`;
- non creare snapshot DSL;
- non implementare AI package, inbox scan, stale package detection o chiamate ad AI reale;
- non implementare Docling, chunking worker, parser DDL/XML/SQL/log o normalizzazione documentale;
- non introdurre ORM;
- non introdurre dipendenze runtime nuove, incluso `jsonschema`; usa standard library per la validazione minima;
- non salvare path assoluti nel database;
- non salvare contenuti sorgente lunghi nei log;
- mantieni CLI, core validation e persistence separati;
- mantieni l'implementazione piccola e leggibile;
- usa import assoluti dal package `dsl_mngr`;
- i test devono essere deterministici e usare `tmp_path`.

Fixture e test:
- aggiungi fixture JSONL minime sotto `tests/fixtures/candidates/`;
- nei test crea workspace, inizializza database, registra almeno una source/revision e inserisci fixture `chunks` direttamente nel database;
- non implementare un chunker solo per preparare i test.

Test minimi richiesti:
- `test_import_candidate_fixture`;
- `test_reject_invalid_json`;
- `test_reject_unknown_chunk`;
- `test_reject_candidate_missing_evidence`.

I test devono verificare almeno:
- righe valide salvate in `candidate_records`;
- righe rifiutate salvate in `rejected_candidates` con reason corretta;
- batch counts corretti;
- run `candidate_validation` completata quando il batch contiene rejection non fatali;
- artifact `output.json` e `process_report.json` coerenti;
- comando CLI funzionante anche via `python -m dsl_mngr`;
- nessuna regressione sulle slice 1-4.

Done when:
- Slice 5 e' implementata end-to-end;
- le migration sono idempotenti;
- i nuovi test esistono e sono significativi;
- tutti i test passano;
- non e' stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l'interprete corretto;
5. mostra diff e risultato dei test, indicando l'interprete usato.
