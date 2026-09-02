Implementa solo la Slice 8 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`
- `.kb/projects/slicing/slice_05/dsl_manager_slice_05_report.md`
- `.kb/projects/slicing/slice_06/dsl_manager_slice_06_report.md`
- `.kb/projects/slicing/slice_07/dsl_manager_slice_07_report.md`

Task:
Implementare la minima slice verticale funzionante per confrontare due snapshot DSL gia persistiti in SQLite e produrre un diff tracciabile.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs` e artifact deterministici.
- Slice 5 ha introdotto import/validation di candidati fixture in `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto `facts`, `fact_evidence`, `relations`, `relation_evidence`, `conflicts` e il comando `facts merge`.
- Slice 7 ha introdotto `dsl_snapshots`, renderer JSON/YAML/Markdown e il comando `dsl render`.
- La Slice 8 deve confrontare snapshot esistenti; non deve rigenerare il DSL dal registry e non deve creare nuova conoscenza semantica.

Scope:
- aggiungere un modulo core piccolo e testabile, per esempio `src/dsl_mngr/core/dsl_diff.py`;
- estendere il comando `dsl` con:

```powershell
dsl-manager dsl diff <workspace> --from DSL_000001 --to DSL_000002
```

- mantenere compatibilita con:

```powershell
python -m dsl_mngr dsl diff <workspace> --from DSL_000001 --to DSL_000002
```

- leggere gli snapshot solo da `dsl_snapshots.content_json`;
- produrre output JSON e Markdown;
- scrivere gli export sotto `exports/dsl_diff` per default;
- permettere, se utile e piccolo, `--output-dir <path>` purche il path resti dentro il workspace;
- creare una run di tipo `dsl_diff`;
- scrivere `input.json`, `output.json`, `process_report.json`, `resolved_config.yaml`, `config_hash.txt` e `log.jsonl` secondo le regole della Slice 4;
- aggiungere log JSONL applicativo per diff completato o fallito.

Expected behavior:
- il comando verifica workspace, database migrato e presenza degli snapshot richiesti;
- se uno snapshot non esiste, fallisce con errore leggibile e exit code `2`;
- se `content_json` non e JSON valido, fallisce con errore leggibile;
- se `metadata.dsl_hash` non coincide con `dsl_snapshots.dsl_hash`, fallisce con errore leggibile;
- se `from` e `to` hanno lo stesso `dsl_hash`, produce comunque un diff valido con zero changes;
- il diff confronta il contenuto DSL gia renderizzato dalla Slice 7:
  - `entities`;
  - `facts` contenuti dentro ogni entity;
  - `relations`;
  - `conflicts`;
  - `traceability`;
- il diff non legge direttamente `facts`, `relations`, `conflicts`, `candidate_records`, `candidate_batches` o `rejected_candidates`;
- ogni change semantico deve avere almeno una causa tracciabile;
- se una differenza semantica non ha causa tracciabile, il comando fallisce, marca la run come `failed` e non produce un report di diff completato;
- i path salvati in artifact e output devono essere relativi al workspace e usare `/`.

Change types minimi:
- `added_entity`;
- `removed_entity`;
- `added_fact`;
- `removed_fact`;
- `modified_fact`;
- `added_relation`;
- `removed_relation`;
- `modified_relation`;
- `added_conflict`;
- `removed_conflict`;
- `modified_conflict`.

Regole di confronto:
- usare ordinamenti stabili e output deterministico;
- non trattare `metadata.dsl_hash`, `metadata.registry_hash` e `metadata.counts` come change semantici autonomi: usarli nel summary;
- identificare le entity con `canonical_name`;
- identificare le relation con `canonical_source_entity`, `relation_type`, `canonical_target_entity`;
- identificare i conflict con `conflict_type`, `canonical_entity_name`, `property_name`, `left_fact_id`, `right_fact_id`;
- per i fact, usare una chiave logica basata su `canonical_entity_name`, `fact_type` e `property_name`;
- se su una stessa chiave logica ci sono piu fact nello stesso snapshot e il confronto diventa ambiguo, rappresentare la differenza come `added_fact` / `removed_fact` invece di forzare un `modified_fact`;
- considerare `modified_fact` quando la stessa chiave logica ha un singolo fact in entrambi gli snapshot e cambiano campi come `property_value`, `assertion_type`, `confidence` o `status`;
- considerare `modified_relation` quando la stessa relation logica esiste in entrambi gli snapshot e cambiano campi come `assertion_type`, `confidence` o `status`;
- considerare `modified_conflict` quando lo stesso conflict logico esiste in entrambi gli snapshot e cambiano `left_value`, `right_value` o `status`;
- ordinare i changes per tipo, path logico e id stabile.

Regole di traceability:
- ogni change deve contenere una lista `causes`;
- per `facts`, usare `traceability.facts[<fact_id>]`;
- per `relations`, usare `traceability.relations[<relation_id>]`;
- per entity aggiunte o rimosse, usare la traceability dei `facts` dell'entity;
- per conflicts, usare la traceability dei `facts` indicati da `left_fact_id` e `right_fact_id`, quando presente;
- ogni causa deve includere almeno:
  - `owner_type`;
  - `owner_id`;
  - `candidate_record_id`;
  - `source_revision_id`;
  - `source_id`;
  - `file_path`;
  - `chunk_id`;
  - `fragment_id`;
  - `evidence_text_hash`;
- per `modified_*`, includere cause `before` e `after` quando entrambe sono disponibili;
- se una change non puo produrre almeno una causa, fallire con errore `missing_traceability` o equivalente.

Struttura minima del diff JSON:

```json
{
  "metadata": {
    "schema_version": "1",
    "from_snapshot_id": "DSL_000001",
    "to_snapshot_id": "DSL_000002",
    "from_dsl_hash": "<sha256>",
    "to_dsl_hash": "<sha256>",
    "from_registry_hash": "<sha256>",
    "to_registry_hash": "<sha256>",
    "has_changes": true
  },
  "summary": {
    "total_changes": 1,
    "added": 1,
    "removed": 0,
    "modified": 0,
    "entities": {
      "added": 1,
      "removed": 0,
      "modified": 0
    },
    "facts": {
      "added": 1,
      "removed": 0,
      "modified": 0
    },
    "relations": {
      "added": 0,
      "removed": 0,
      "modified": 0
    },
    "conflicts": {
      "added": 0,
      "removed": 0,
      "modified": 0
    }
  },
  "changes": [
    {
      "change_id": "CHG_000001",
      "change_type": "added_entity",
      "path": "entities[cliente]",
      "before": null,
      "after": {
        "name": "Cliente",
        "canonical_name": "cliente"
      },
      "causes": [
        {
          "side": "after",
          "owner_type": "fact",
          "owner_id": "FACT_000001",
          "candidate_record_id": "CREC_000001",
          "source_revision_id": "REV_000001",
          "source_id": "SRC_000001",
          "file_path": "corpus/active/manuale_clienti.txt",
          "chunk_id": "CHK_000001",
          "fragment_id": null,
          "evidence_text_hash": "<sha256>"
        }
      ]
    }
  ]
}
```

Markdown:
- deve essere una vista leggibile del diff, non un report narrativo lungo;
- deve contenere almeno:
  - metadata dei due snapshot;
  - summary;
  - lista changes raggruppata per tipo;
  - cause tracciabili per ogni change;
- deve essere deterministico.

Output CLI minimo:

```text
Run: RUN_000005
From: DSL_000001
To: DSL_000002
Changes: 1
Added: 1
Removed: 0
Modified: 0
JSON: exports/dsl_diff/DSL_000001__DSL_000002.json
Markdown: exports/dsl_diff/DSL_000001__DSL_000002.md
```

Artifact:
- `input.json`, `output.json` e `process_report.json` devono includere almeno:
  - `from_snapshot_id`;
  - `to_snapshot_id`;
  - `from_dsl_hash`;
  - `to_dsl_hash`;
  - `total_changes`;
  - `added_count`;
  - `removed_count`;
  - `modified_count`;
  - `json_path`;
  - `markdown_path`;
- `process_report.json` deve avere `run_type = "dsl_diff"` e `status = "completed"` quando il diff riesce.

Constraints:
- non aggiungere migration salvo motivazione strettamente necessaria;
- non aggiungere una tabella `dsl_diffs` nella Slice 8;
- non rigenerare snapshot DSL;
- non modificare `dsl_snapshots`;
- non modificare `facts`, `relations`, conflicts, candidate records o registry;
- non implementare mappings: il design cita un test `modified_mapping`, ma il codice attuale non ha ancora `mappings`; usare un test su `modified_relation` o su un caso relation mapping-like senza introdurre nuove tabelle;
- non implementare GEXF;
- non implementare golden full pipeline;
- non implementare Docling, parser, chunker, batch o AI handoff;
- non introdurre ORM;
- non introdurre nuove dipendenze runtime;
- mantenere separati CLI, core diff e persistence/read model;
- usare import assoluti dal package `dsl_mngr`;
- mantenere l'implementazione piccola, leggibile e deterministica;
- i test devono usare `tmp_path`.

Test minimi richiesti:
- `test_diff_added_entity`;
- `test_diff_modified_relation`;
- `test_diff_requires_traceability`;
- `test_diff_same_hash_has_no_changes`.

I test devono verificare almeno:
- due snapshot uguali producono zero changes e output JSON/Markdown;
- uno snapshot successivo con una nuova entity produce `added_entity` e cause derivate dai `facts` della nuova entity;
- una relation modificata produce `modified_relation` con cause tracciabili;
- un fact/relation/entity/conflict senza traceability causa errore leggibile e run fallita;
- gli output vengono creati sotto `exports/dsl_diff`;
- gli artifact della run contengono summary, hash e path relativi;
- il comando funziona anche via `python -m dsl_mngr`;
- nessuna regressione sulle slice 1-7.

Done when:
- Slice 8 e implementata end-to-end;
- il diff JSON e deterministico;
- il Markdown e leggibile e deterministico;
- ogni change ha causa tracciabile o la run fallisce;
- i test nuovi sono significativi;
- tutta la suite passa;
- non e stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l'interprete corretto;
5. mostra diff e risultato dei test, indicando l'interprete usato.
