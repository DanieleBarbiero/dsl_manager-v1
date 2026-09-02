Implementa solo la Slice 7 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`
- `.kb/projects/slicing/slice_05/dsl_manager_slice_05_report.md`
- `.kb/projects/slicing/slice_06/dsl_manager_slice_06_report.md`

Task:
Implementare la minima slice verticale funzionante per generare snapshot DSL dal registry SQLite, partendo da `facts`, `relations`, `conflicts` ed evidence links prodotti dalla Slice 6.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs` e artifact deterministici.
- Slice 5 ha introdotto import/validation di candidati fixture in `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto `facts`, `fact_evidence`, `relations`, `relation_evidence`, `conflicts` e il comando `facts merge`.
- La Slice 7 deve solo renderizzare lo stato gia presente nel registry; non deve creare nuova conoscenza semantica.

Scope:
- aggiungere una nuova migration versionata, senza modificare le migration esistenti;
- aggiungere la tabella minima `dsl_snapshots`;
- aggiungere un modulo core piccolo e testabile, per esempio `src/dsl_mngr/core/dsl_renderer.py`;
- aggiungere il comando CLI:

```powershell
dsl-manager dsl render <workspace>
```

- mantenere compatibilita con:

```powershell
python -m dsl_mngr dsl render <workspace>
```

- renderizzare i formati:
  - JSON;
  - YAML;
  - Markdown;
- scrivere gli export sotto `exports/dsl` per default;
- permettere, se utile e piccolo, `--output-dir <path>` purche il path resti dentro il workspace.

Expected behavior:
- il comando verifica workspace, database migrato e schema Slice 7 disponibile;
- crea una run di tipo `dsl_render`;
- legge solo registry gia consolidato:
  - `facts`;
  - `fact_evidence`;
  - `relations`;
  - `relation_evidence`;
  - `conflicts`;
  - `source_revisions`;
  - `sources`;
- ignora `candidate_records` diretti salvo i riferimenti presenti nelle tabelle evidence;
- non legge ne processa `rejected_candidates`;
- produce un documento DSL deterministico con sezioni:
  - `metadata`;
  - `entities`;
  - `relations`;
  - `conflicts`;
  - `traceability`;
- salva una riga in `dsl_snapshots`;
- scrive i tre file:
  - `exports/dsl/DSL_000001.json`;
  - `exports/dsl/DSL_000001.yaml`;
  - `exports/dsl/DSL_000001.md`;
- completa la run con `output.json` e `process_report.json` coerenti;
- aggiunge log JSONL applicativo per render completato o fallito.

Schema minimo consigliato per `dsl_snapshots`:
- `snapshot_id`;
- `run_id`;
- `dsl_hash`;
- `registry_hash`;
- `content_json`;
- `json_path`;
- `yaml_path`;
- `markdown_path`;
- `fact_count`;
- `relation_count`;
- `conflict_count`;
- `status`;
- `created_at`;

Regole di rendering:
- usare ID sequenziali con prefisso `DSL`, per esempio `DSL_000001`;
- usare ordinamenti stabili:
  - entities per `canonical_entity_name`;
  - `facts` per `property_name`, `normalized_property_value`, `fact_id`;
  - `relations` per `canonical_source_entity`, `relation_type`, `canonical_target_entity`, `relation_id`;
  - conflicts per `conflict_id`;
  - evidence per `candidate_record_id`;
- includere `facts` con status `active`, `inferred`, `pending_review` e `conflicted`;
- includere `relations` con il loro status corrente;
- includere conflicts con il loro status corrente;
- non inserire timestamp, `run_id` o `snapshot_id` nel contenuto DSL usato per calcolare `dsl_hash`;
- calcolare `dsl_hash` come sha256 del JSON canonico del DSL content, escludendo il campo `dsl_hash` stesso;
- calcolare `registry_hash` su una rappresentazione canonica dei record registry consumati, escludendo campi volatili;
- se il registry non cambia, due render successivi devono produrre lo stesso `dsl_hash`;
- due render successivi possono creare due righe snapshot diverse, ma con lo stesso `dsl_hash`;
- i path salvati in database e artifact devono essere relativi al workspace e usare `/`.

Struttura minima del DSL JSON:

```json
{
  "metadata": {
    "schema_version": "1",
    "dsl_hash": "<hash>",
    "registry_hash": "<hash>",
    "counts": {
      "entities": 1,
      "facts": 1,
      "relations": 1,
      "conflicts": 0
    }
  },
  "entities": [
    {
      "name": "Cliente",
      "canonical_name": "cliente",
      "facts": [
        {
          "fact_id": "FACT_000001",
          "fact_type": "business_entity",
          "property_name": "description",
          "property_value": "Anagrafica clienti gestita dal sistema",
          "assertion_type": "explicit",
          "confidence": "high",
          "status": "active"
        }
      ]
    }
  ],
  "relations": [],
  "conflicts": [],
  "traceability": {
    "facts": {
      "FACT_000001": [
        {
          "candidate_record_id": "CREC_000001",
          "source_revision_id": "REV_000001",
          "source_id": "SRC_000001",
          "file_path": "corpus/active/manuale_clienti.txt",
          "chunk_id": "CHK_000001",
          "fragment_id": null,
          "evidence_text_hash": "<hash>"
        }
      ]
    },
    "relations": {}
  }
}
```

YAML e Markdown:
- YAML deve essere deterministico e leggibile;
- non aggiungere dipendenze runtime come PyYAML;
- se serve, implementare un emitter YAML minimale sufficiente per dict/list/scalari del DSL;
- Markdown deve contenere almeno sezioni per entities, `relations`, conflicts e traceability;
- Markdown non deve diventare un report narrativo: deve essere una vista leggibile del DSL.

Output CLI minimo:

```text
Run: RUN_000003
Snapshot: DSL_000001
DSL hash: <sha256>
Facts: 1
Relations: 1
Conflicts: 0
JSON: exports/dsl/DSL_000001.json
YAML: exports/dsl/DSL_000001.yaml
Markdown: exports/dsl/DSL_000001.md
```

Artifact:
- `input.json`, `output.json` e `process_report.json` devono includere almeno:
  - `snapshot_id`;
  - `dsl_hash`;
  - `registry_hash`;
  - `fact_count`;
  - `relation_count`;
  - `conflict_count`;
  - `json_path`;
  - `yaml_path`;
  - `markdown_path`;
- `process_report.json` deve avere `run_type = "dsl_render"` e `status = "completed"` quando il render riesce.

Constraints:
- non reimplementare import JSONL, validation o merge;
- non modificare `facts`, `relations`, conflicts o candidate records;
- non implementare DSL diff;
- non implementare GEXF;
- non implementare mappings, questions, review UI, Docling, parser, chunker, batch o AI handoff;
- non introdurre ORM;
- non introdurre nuove dipendenze runtime;
- mantenere separati CLI, core renderer e persistence;
- usare import assoluti dal package `dsl_mngr`;
- mantenere l'implementazione piccola, leggibile e deterministica;
- i test devono usare `tmp_path`.

Test minimi richiesti:
- `test_render_dsl_snapshot`;
- `test_snapshot_hash_stable`;
- `test_dsl_contains_traceability`.

I test devono verificare almeno:
- un registry con un fact mergeato produce una entity nel DSL JSON;
- una relation mergeata appare nella sezione `relations`;
- un conflict esistente appare nella sezione `conflicts`;
- `dsl_snapshots` contiene una riga coerente con file e hash prodotti;
- JSON, YAML e Markdown vengono creati sotto `exports/dsl`;
- `traceability` contiene `candidate_record_id`, `source_revision_id`, `source_id`, `file_path`, `chunk_id` o `fragment_id`, ed `evidence_text_hash`;
- due render successivi senza modifiche al registry producono lo stesso `dsl_hash`;
- il comando funziona anche via `python -m dsl_mngr`;
- nessuna regressione sulle slice 1-6.

Done when:
- Slice 7 e implementata end-to-end;
- la migration Slice 7 e idempotente;
- i test nuovi sono significativi;
- tutta la suite passa;
- non e stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l'interprete corretto;
5. mostra diff e risultato dei test, indicando l'interprete usato.
