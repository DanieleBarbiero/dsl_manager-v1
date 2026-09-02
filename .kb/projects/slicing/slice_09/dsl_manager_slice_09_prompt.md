Implementa solo la Slice 9 per DSL Manager v1.

Prima di iniziare, leggi e segui:
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

Task:
Implementare la minima slice verticale funzionante per stabilizzare un golden test end-to-end dell'MVP tecnico, senza AI reale e senza introdurre parser, Docling, chunker o graph export.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs` e artifact deterministici.
- Slice 5 ha introdotto import/validation di candidati fixture in `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto `facts`, `fact_evidence`, `relations`, `relation_evidence`, `conflicts` e il comando `facts merge`.
- Slice 7 ha introdotto `dsl_snapshots`, renderer JSON/YAML/Markdown e il comando `dsl render`.
- Slice 8 ha introdotto `dsl diff` tra snapshot persistiti, con cause tracciabili.
- La Slice 9 deve chiudere l'MVP tecnico con fixture e golden tests; non deve trasformarsi nella Slice 10 o successive.

Obiettivo funzionale:
Dimostrare che, a partire da un piccolo corpus finto e da candidati JSONL statici, il sistema puo eseguire in modo deterministico:

```text
workspace init
db init / migrations
corpus scan
test-only chunk seeding
candidates validate
facts merge
dsl render
dsl render stabile
dsl diff tra snapshot equivalenti
golden assertions
```

Scope:
- aggiungere fixture di corpus minimo sotto:

```text
tests/fixtures/corpus_initial/
```

- aggiungere fixture candidati AI statici sotto:

```text
tests/fixtures/ai_candidates/AIPKG_MANUALI_001_candidates.jsonl
```

- aggiungere golden expected statici sotto:

```text
tests/expected/expected_dsl.full.json
tests/expected/expected_dsl.full.yaml
tests/expected/expected_conflicts.json
tests/expected/expected_graph_edges.json
```

- aggiungere un test end-to-end, per esempio:

```text
tests/test_slice_09_golden_pipeline.py
```

- se serve, aggiungere piccoli helper test-only nello stesso file di test o in un modulo sotto `tests/`;
- usare solo comandi/API gia introdotti dalle slice 1-8;
- mantenere compatibilita con `python -m dsl_mngr`;
- mantenere output e fixture con newline `\n`, UTF-8 e ordinamenti stabili.

Corpus fixture minimo:
- usare un dominio piccolo e coerente con il design document;
- includere almeno:

```text
tests/fixtures/corpus_initial/manuale_clienti.md
tests/fixtures/corpus_initial/manuale_ordini.md
```

- il testo deve contenere evidenze esplicite per:
  - `Cliente` come business entity;
  - regola `Cliente.delete_rule`;
  - `Ordine` come business entity;
  - composizione di `Ordine` in testata e righe;
  - `RigaOrdine` come business entity o concetto collegato;
  - valori di stato dell'ordine;
  - relazione `Cliente places Ordine`;
  - relazione `Ordine has_rows RigaOrdine`.

Candidate fixture:
- usare solo record supportati davvero dal merge attuale:
  - `candidate_fact`;
  - `candidate_relation`;
- evitare `candidate_mapping`, `candidate_conflict` e `candidate_question` nel golden happy path, perche il merge attuale li salta;
- ogni candidato deve avere `source_revision_id`, `chunk_id`, `assertion_type`, `confidence` ed `evidence_text` validi;
- ogni `evidence_text` deve comparire esattamente nel chunk referenziato;
- i candidati devono produrre almeno:
  - `facts` per `Cliente`, `Ordine` e `RigaOrdine`;
  - relation `Cliente places Ordine`;
  - relation `Ordine has_rows RigaOrdine`;
  - zero rejected candidates nel golden happy path.

Nota sul chunking:
- non implementare chunking in produzione;
- nel test Slice 9 e ammesso un helper deterministico test-only che inserisce una riga `chunks` per ogni `source_revision` creata da `corpus scan`;
- ordinare le revisioni per `file_path` e creare `CHK_000001`, `CHK_000002`, ...;
- il testo del chunk puo essere l'intero contenuto del file sorgente;
- il test deve documentare implicitamente questo ponte come sostituto temporaneo delle future Slice 10-11, senza aggiungere comandi CLI o moduli di produzione.

Expected behavior:
- il test crea un workspace temporaneo con `tmp_path`;
- copia `tests/fixtures/corpus_initial/` in `workspace/corpus/active/`;
- inizializza workspace e database usando le funzioni o la CLI gia presenti;
- esegue `corpus scan` e verifica almeno che i file fixture siano registrati come `source_added`;
- inserisce i chunk test-only per le revisioni attive;
- copia `AIPKG_MANUALI_001_candidates.jsonl` in `workspace/ai/inbox/`;
- esegue `candidates validate` e verifica:
  - `total_records` coerente con la fixture;
  - `accepted_count == total_records`;
  - `rejected_count == 0`;
  - `candidate_batches.status == "completed"`;
- esegue `facts merge --batch CBATCH_000001` e verifica:
  - `facts` creati;
  - `relations` create;
  - zero skipped nel golden happy path;
  - zero conflicts, salvo diversa scelta esplicita e motivata negli expected;
- esegue `dsl render` e confronta:
  - `exports/dsl/DSL_000001.json` con `tests/expected/expected_dsl.full.json`;
  - `exports/dsl/DSL_000001.yaml` con `tests/expected/expected_dsl.full.yaml`;
  - `content["conflicts"]` con `tests/expected/expected_conflicts.json`;
- deriva dal DSL renderizzato una piccola proiezione test-only di graph edges e la confronta con `tests/expected/expected_graph_edges.json`;
- esegue un secondo `dsl render` sullo stesso registry e verifica che `dsl_hash` e `registry_hash` restino invariati;
- esegue `dsl diff --from DSL_000001 --to DSL_000002` e verifica:
  - `summary.total_changes == 0`;
  - output JSON/Markdown creati sotto `exports/dsl_diff`;
  - run `dsl_diff` completata;
- verifica che gli artifact rilevanti siano scritti sotto `artifacts/runs` con path relativi al workspace e separatori `/`;
- verifica che i log applicativi contengano almeno eventi completati per validation, merge, render e diff.

Golden expected:
- gli expected devono essere file statici versionati, non generati dinamicamente dentro il test;
- se il DSL cambia legittimamente, aggiornare gli expected in modo esplicito;
- `expected_dsl.full.json` deve includere `metadata.dsl_hash` e `metadata.registry_hash` perche il renderer corrente li produce in modo deterministico;
- `expected_dsl.full.yaml` deve essere il YAML prodotto dal renderer corrente per lo stesso snapshot;
- `expected_conflicts.json` puo essere `[]` se il golden corpus non contiene conflitti;
- `expected_graph_edges.json` deve essere una proiezione semplice e deterministica delle `relations` presenti nel DSL, per esempio:

```json
[
  {
    "source": "cliente",
    "type": "places",
    "target": "ordine"
  },
  {
    "source": "ordine",
    "type": "has_rows",
    "target": "rigaordine"
  }
]
```

- non aggiungere `graph_export.py`, output GEXF o comando `graph` nella Slice 9.

Constraints:
- non implementare Docling;
- non implementare parser DDL/XML/SQL/log;
- non implementare chunker di produzione;
- non implementare AI package handoff;
- non implementare batch orchestration;
- non implementare GEXF;
- non implementare UI, web/API/auth o integrazioni esterne;
- non aggiungere ORM;
- non aggiungere nuove dipendenze runtime;
- non aggiungere migration salvo motivazione strettamente necessaria;
- non modificare il contratto pubblico di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`;
- non rendere i golden test dipendenti da tempo corrente, path assoluti, ordine del filesystem o output AI reale;
- non usare import da `src`;
- usare import assoluti da `dsl_mngr`;
- mantenere il codice piccolo, leggibile e coerente con lo stile dei test esistenti;
- i test devono usare `tmp_path`.

Test minimi richiesti:
- `test_golden_full_pipeline`;
- se utile, un secondo test piccolo per verificare che gli expected siano file statici validi e leggibili.

Il test `test_golden_full_pipeline` deve verificare almeno:
- corpus scan registra le fonti fixture;
- i chunk test-only referenziano revisioni attive esistenti;
- validation accetta tutti i candidati fixture;
- merge crea `facts` e `relations` attesi;
- render JSON/YAML coincide con golden files;
- conflicts coincidono con expected;
- graph edges projection coincide con expected;
- secondo render produce hash identici;
- diff tra i due snapshot equivalenti produce zero changes;
- nessuna regressione sulle slice 1-8.

Done when:
- Slice 9 e implementata end-to-end nello scope richiesto;
- le fixture `corpus_initial`, `ai_candidates` e `expected` sono presenti e versionate;
- il golden test dimostra il flusso MVP senza AI reale;
- il comportamento e deterministico;
- tutta la suite passa;
- non e stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l'interprete corretto;
5. mostra diff e risultato dei test, indicando l'interprete usato;
6. esegui una breve autoverifica finale contro scope, constraints e done criteria.

Report finale:

```text
salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_09/dsl_manager_slice_09_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
```
