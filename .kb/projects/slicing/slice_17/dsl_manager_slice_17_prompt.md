Implementa solo la Slice 17 per DSL Manager v1.

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
- `.kb/projects/slicing/slice_15/dsl_manager_slice_15_report.md`
- `.kb/projects/slicing/slice_16/dsl_manager_slice_16_report.md`
- il codice attuale sotto `src/dsl_mngr`
- i test attuali sotto `tests`

Task:
implementare il minimo incremento verticale per "Export GEXF".

Obiettivo:
- esportare una vista navigabile del DSL come grafo GEXF;
- usare uno snapshot DSL persistito come sorgente dell'export, non il registry live;
- produrre nodi e archi tipizzati, deterministici e tracciabili;
- gestire relazioni verso entita' mancanti con orphan handling;
- registrare l'export come run auditabile e, se necessario, in una tabella `graph_exports`;
- non cambiare il significato pubblico delle slice precedenti.

Contesto attuale:
- Slice 1 ha introdotto workspace, config, logging JSONL e `log table`.
- Slice 2 ha introdotto SQLite, migrazioni, `runs` e `worker_runs`.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto run lifecycle, artifact run e worker runner.
- Slice 5 ha introdotto import/validation candidati, `chunks`, `source_fragments`, `candidate_batches`, `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto merge idempotente di `facts`/`relations`/conflicts.
- Slice 7 ha introdotto renderer DSL JSON/YAML/Markdown e `dsl_snapshots`.
- Slice 8 ha introdotto `dsl diff`.
- Slice 9 ha stabilizzato un golden test end-to-end e `tests/expected/expected_graph_edges.json`.
- Slice 10 ha introdotto normalizzazione Docling no-images.
- Slice 11 ha introdotto chunking stabile.
- Slice 12 ha introdotto parser DDL e frammenti strutturali.
- Slice 13 ha introdotto parser XML form.
- Slice 14 ha introdotto parser SQL code e parser log.
- Slice 15 ha introdotto AI package handoff e tabella `ai_packages`.
- Slice 16 ha introdotto batch orchestration, run padre `batch` e sub-run.
- `runs.RUN_TYPES` contiene gia' `gexf_export`; verifica lo stato reale prima di modificare.
- `workspace.py` crea gia' `exports/graph`; verifica se serve aggiungere un profilo `gexf.default.yaml`.
- Al momento non dovrebbe esistere un core `graph_export`, un comando `graph export`, una tabella `graph_exports` o test Slice 17: verifica comunque lo stato reale prima di modificare.
- `pyproject.toml` contiene gia' `docling==2.97.0` come dipendenza runtime; non dare per scontata la presenza di NetworkX.

Decisione di scope:
- La Slice 17 deve esportare un grafo da uno snapshot DSL gia' renderizzato.
- Non deve renderizzare automaticamente un nuovo DSL snapshot.
- Non deve rieseguire candidate validation, merge, diff, parser, AI handoff o batch.
- Non deve implementare log viewer, UI, web/API/auth o integrazioni esterne.
- Non deve chiamare provider AI o rete.
- Preferisci un writer GEXF piccolo basato su standard library `xml.etree.ElementTree`, salvo motivo forte per aggiungere una dipendenza. Se aggiungi una dipendenza runtime, motivala nel report e coprila nei test.
- L'export GEXF e' una vista derivata: non deve diventare memoria primaria.

Scope:
- aggiungi un core piccolo e testabile per l'export grafo, per esempio:

```text
src/dsl_mngr/core/graph_export.py
```

- aggiungi il comando CLI, nello stile `argparse` esistente:

```powershell
dsl-manager graph export <workspace> --snapshot DSL_000001
dsl-manager graph export <workspace> --snapshot DSL_000001 --format gexf
dsl-manager graph export <workspace> --snapshot DSL_000001 --output-dir exports/graph
dsl-manager graph export <workspace> --snapshot DSL_000001 --strict-orphans
```

- mantieni compatibilita' con:

```powershell
python -m dsl_mngr graph export <workspace> --snapshot DSL_000001
```

- aggiungi il wiring in `src/dsl_mngr/cli/app.py`;
- aggiungi un file CLI dedicato, per esempio:

```text
src/dsl_mngr/cli/commands/graph.py
```

- aggiungi test deterministici Slice 17, per esempio:

```text
tests/test_slice_17_graph_export.py
```

- aggiungi una migration append-only per `graph_exports`, salvo motivo forte per rimandarla. Schema minimo consigliato:

```sql
CREATE TABLE IF NOT EXISTS graph_exports (
  graph_export_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  dsl_hash TEXT NOT NULL,
  graph_hash TEXT NOT NULL,
  format TEXT NOT NULL,
  graph_path TEXT NOT NULL,
  report_path TEXT NOT NULL,
  node_count INTEGER NOT NULL,
  edge_count INTEGER NOT NULL,
  orphan_count INTEGER NOT NULL,
  warning_count INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (snapshot_id) REFERENCES dsl_snapshots(snapshot_id)
);
```

Se scegli nomi campo o un ID prefix diversi, mantienili coerenti, documentali nel report e coprili nei test. Non modificare migration gia' applicate.

Profilo/config opzionale:
- se aggiungi un profilo default, usa una forma semplice compatibile con il parser YAML minimale:

```yaml
worker:
  name: export_gexf
  version: 1.0
graph:
  include_sources: true
  include_fact_nodes: true
  include_conflicts: true
  include_low_confidence: true
  directed: true
  node_label_strategy: readable
  strict_orphans: false
```

- non fare un refactor generale della configurazione.

Comportamento atteso per `graph export`:
- richiede workspace inizializzato e database migrato;
- richiede uno snapshot esistente con `status = "completed"`;
- legge `dsl_snapshots.content_json`;
- verifica che `content_json.metadata.dsl_hash` coincida con `dsl_snapshots.dsl_hash`;
- verifica che `metadata.schema_version` sia supportata;
- verifica che le sezioni minime `metadata`, `entities`, `relations`, `conflicts` e `traceability` siano presenti e del tipo atteso;
- crea una run `gexf_export`;
- genera un file GEXF sotto:

```text
exports/graph/DSL_000001.gexf
```

- genera un report JSON sotto:

```text
exports/graph/DSL_000001.graph_report.json
```

- registra l'export in `graph_exports`;
- aggiorna `artifacts/runs/RUN_xxxxxx/input.json`, `output.json` e `process_report.json`;
- logga su `logs/app.jsonl` almeno `gexf_export_completed` o `gexf_export_failed`;
- path salvati in DB, artifact e report devono essere relativi al workspace e usare `/`;
- l'ordine di nodi, archi, attributi e warning deve essere stabile.

Comportamento CLI minimo al successo:

```text
Run: RUN_000001
Graph export: GEXF_000001
Snapshot: DSL_000001
Format: gexf
DSL hash: <sha256>
Graph hash: <sha256>
Nodes: 3
Edges: 2
Orphans: 0
Warnings: 0
GEXF: exports/graph/DSL_000001.gexf
Report: exports/graph/DSL_000001.graph_report.json
```

Se ci sono warning non bloccanti, stampa anche un blocco compatto:

```text
Warnings:
- orphan_node_added: relation REL_000001 references missing target entity ordine
```

Regole grafo:
- la v1 usa un grafo diretto;
- `--format` accetta solo `gexf` per ora;
- crea almeno un nodo `domain_entity` per ogni entita' in `content["entities"]`;
- crea un arco per ogni relation in `content["relations"]`:
  - source = nodo `entity:<canonical_source_entity>`;
  - target = nodo `entity:<canonical_target_entity>`;
  - `edge_type` = `relation_type`;
  - attributi minimi: `relation_id`, `assertion_type`, `confidence`, `status`, `source_entity`, `target_entity`;
- includi attributi utili sui nodi entita':
  - `node_id`;
  - `label`;
  - `node_type`;
  - `canonical_name`;
  - `status`;
  - `source_count`;
  - `fact_count`;
- se `include_fact_nodes` e' attivo, crea nodi fact per `facts` non descrittivi, almeno per `fact_type = "business_rule"`:
  - node id stabile, per esempio `fact:FACT_000001`;
  - `node_type = "business_rule"` per business rules;
  - label leggibile, per esempio `Cliente.delete_rule`;
  - collega entita' -> fact con un arco tipizzato, per esempio `edge_type = "mentions"`;
  - includi `fact_id`, `fact_type`, `property_name`, `status`, `assertion_type`, `confidence`;
- se `include_sources` e' attivo, crea nodi `source` a partire da `traceability.facts` e `traceability.relations`:
  - node id stabile, per esempio `source:SRC_000001`;
  - label = file path o logical source leggibile;
  - collega la fonte agli oggetti derivati con archi `edge_type = "derives_from"` oppure includi gli `source_ids` sugli archi/`facts`. Scegli una politica semplice e documentala nel report;
- se `include_conflicts` e' attivo, rappresenta i conflitti aperti come nodi o archi `conflicts_with`, in modo deterministico. Per la slice e' accettabile una rappresentazione minima, purche' sia testata almeno a livello unitario o documentata come fuori scope se non necessaria alle fixture.

GEXF:
- il file deve essere XML valido e parseable con `xml.etree.ElementTree`;
- usa `defaultedgetype = "directed"`;
- usa ID nodo e ID arco stabili, senza path assoluti;
- definisci attributi GEXF per i campi custom invece di serializzare tutto in label;
- valori lista come `source_ids` o `fact_ids` possono essere stringhe JSON canoniche o stringhe comma-separated: scegli una convenzione e mantienila stabile;
- non inserire timestamp nel GEXF se rendono fragile il confronto deterministico;
- scrivi con encoding UTF-8 e newline LF.

Hash e determinismo:
- calcola `graph_hash` con SHA-256 su una rappresentazione canonica del grafo, oppure sul GEXF stabilizzato;
- due export dello stesso snapshot e stesse opzioni devono produrre lo stesso `graph_hash`;
- un secondo export dello stesso snapshot deve creare un nuovo record/run, senza sovrascrivere audit storico. Se il file path finale verrebbe sovrascritto, usa una policy chiara:
  - consentito sovrascrivere il file derivato se il report/DB conserva il nuovo audit; oppure
  - generare path con suffisso export id.
  Documenta la scelta nel report e coprila nei test se rilevante.

Orphan handling:
- un orphan e' almeno una relation che punta a una canonical entity non presente in `content["entities"]`;
- default `strict_orphans = false`:
  - crea un nodo placeholder con `status = "orphaned"`;
  - incrementa `orphan_count`;
  - aggiungi warning nel report;
  - completa la run con status `completed`;
- con `--strict-orphans`:
  - fallisci con errore leggibile;
  - run `gexf_export` in status `failed`;
  - non inserire record `graph_exports` completato;
  - non lasciare artifact incoerenti.

Report export:
- crea un report JSON canonico, per esempio:

```json
{
  "graph_export_id": "GEXF_000001",
  "run_id": "RUN_000001",
  "snapshot_id": "DSL_000001",
  "format": "gexf",
  "dsl_hash": "<sha256>",
  "registry_hash": "<sha256>",
  "graph_hash": "<sha256>",
  "graph_path": "exports/graph/DSL_000001.gexf",
  "node_count": 3,
  "edge_count": 2,
  "orphan_count": 0,
  "warning_count": 0,
  "options": {
    "include_sources": true,
    "include_fact_nodes": true,
    "include_conflicts": true,
    "strict_orphans": false
  },
  "warnings": []
}
```

- aggiorna `process_report.json` della run con gli stessi campi principali;
- `output.json` deve contenere lo stesso summary o un riferimento chiaro a `graph_path` e `report_path`;
- non salvare contenuti sorgente lunghi nel report.

Failure mode:
- workspace non inizializzato: errore leggibile, exit code `2`, nessuna run parziale se possibile;
- database non inizializzato o migrazioni pendenti: errore leggibile, exit code `2`;
- snapshot inesistente: errore leggibile, run fallita se la run e' gia' stata creata;
- snapshot non completed: errore leggibile;
- `content_json` non valido o schema minimo non rispettato: errore leggibile;
- mismatch fra `metadata.dsl_hash` e `dsl_snapshots.dsl_hash`: errore leggibile;
- output path fuori workspace: errore leggibile;
- formato diverso da `gexf`: errore leggibile;
- orphan con `--strict-orphans`: errore leggibile e run failed;
- failure durante scrittura GEXF/report: run failed e messaggio diagnostico sintetico.

Test minimi richiesti:
- `test_export_gexf`
- `test_gexf_orphan_warning`

I test devono coprire almeno:
- workspace temporaneo con `tmp_path`;
- `dsl-manager init` e `dsl-manager db init`;
- creazione o rendering di almeno uno snapshot DSL valido;
- `dsl-manager graph export <workspace> --snapshot DSL_000001`;
- compatibilita' `python -m dsl_mngr graph export ...`;
- file `exports/graph/DSL_000001.gexf` presente;
- report `exports/graph/DSL_000001.graph_report.json` presente;
- XML GEXF parseable con standard library;
- grafo diretto;
- presenza dei nodi `domain_entity` attesi;
- presenza degli archi relation attesi, coerenti almeno con `tests/expected/expected_graph_edges.json` per le fixture Slice 9 o con fixture equivalenti nel test;
- attributi custom principali su nodi e archi;
- record in `graph_exports` con path relativi e senza `\`;
- run `gexf_export` completata;
- artifact standard della run presenti e coerenti;
- log applicativo `gexf_export_completed`;
- `graph_hash` stabile su due export dello stesso snapshot;
- orphan default:
  - export completato;
  - nodo placeholder `status = "orphaned"`;
  - warning nel report;
  - `orphan_count > 0`;
- orphan strict:
  - comando ritorna `2`;
  - run `gexf_export` fallita;
  - nessun record `graph_exports` completato per quell'export;
- nessun render DSL automatico durante `graph export`;
- nessuna chiamata AI reale o rete.

Fixture e dati test:
- usa fixture gia' esistenti quando possibile:
  - `tests/fixtures/corpus_initial/`
  - `tests/fixtures/ai_candidates/AIPKG_MANUALI_001_candidates.jsonl`
  - `tests/expected/expected_graph_edges.json`
- se usare il golden pipeline completo rende il test lento o fragile, inserisci snapshot sintetici direttamente come fanno i test Slice 8, purche' il contenuto rispetti lo schema prodotto da Slice 7;
- non modificare gli expected della Slice 9 salvo motivo esplicito e documentato.

Constraints:
- non implementare log viewer della Slice 18;
- non implementare UI, web/API/auth o integrazioni esterne;
- non implementare provider AI o chiamate HTTP;
- non generare candidati con euristiche;
- non eseguire merge, render DSL, diff o batch automaticamente;
- non introdurre ORM;
- non aggiungere dipendenze runtime nuove salvo necessita' forte e motivata;
- non salvare path assoluti nel DB, nei report o negli artifact condivisibili;
- non salvare contenuti sorgente lunghi nei log applicativi;
- mantieni import assoluti da `dsl_mngr`;
- mantieni separati CLI, core graph export, persistence e test;
- mantieni implementazione piccola, leggibile e deterministica.

Done when:
- Slice 17 e' implementata nello scope sopra;
- `dsl-manager graph export <workspace> --snapshot DSL_000001` produce GEXF valido;
- il grafo contiene nodi e archi tipizzati;
- orphan handling default e strict sono implementati e testati;
- `graph_exports` registra l'export, se la migration e' stata aggiunta;
- gli artifact run sono coerenti;
- i test Slice 17 esistono e passano;
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
5. esegui test mirati Slice 17 e poi tutta la suite con l'interprete corretto;
6. esegui `git diff --check`;
7. esegui una autoverifica finale su scope, test, diff, GEXF, graph export report, orphan handling, artifact run e failure mode;
8. riassumi cosa e' stato aggiunto e cosa e' rimasto fuori scope.

salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_17/dsl_manager_slice_17_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
