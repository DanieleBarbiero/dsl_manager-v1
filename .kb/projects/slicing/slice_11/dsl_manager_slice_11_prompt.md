Implementa solo la Slice 11 per DSL Manager v1.

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
- `.kb/projects/slicing/slice_09/dsl_manager_slice_09_report.md`
- `.kb/projects/slicing/slice_10/dsl_manager_slice_10_report.md`

Task:
Implementare la minima slice verticale funzionante per produrre chunk stabili a partire dagli output normalizzati della Slice 10.

La Slice 11 deve introdurre il chunking di produzione, persistendo i record in `chunks` e producendo `chunks.jsonl` riproducibile. Deve inoltre dimostrare che i chunk prodotti sono utilizzabili come evidence per `candidates validate`.

Contesto attuale:
- Slice 1 ha introdotto workspace, config e logging JSONL.
- Slice 2 ha introdotto SQLite e migrazioni.
- Slice 3 ha introdotto `corpus scan`, `sources`, `source_revisions` e `source_events`.
- Slice 4 ha introdotto `runs`, `worker_runs`, `run_worker` e artifact deterministici.
- Slice 5 ha introdotto `chunks`, `source_fragments`, `candidate_batches`, `candidate_records` e `rejected_candidates`.
- Slice 6 ha introdotto merge deterministico di `candidate_fact` e `candidate_relation`.
- Slice 7 ha introdotto renderer DSL JSON/YAML/Markdown e `dsl_snapshots`.
- Slice 8 ha introdotto `dsl diff` tracciabile.
- Slice 9 ha stabilizzato il golden pipeline test dell'MVP tecnico usando un helper test-only per seminare `chunks`.
- Slice 10 ha introdotto normalizzazione Docling no-images dietro adapter/worker, comando `corpus normalize`, output `normalized.md`, `normalized.json`, `source_hash.txt`, `docling_report.json` e aggiornamento di `source_revisions.normalized_hash`.
- La Slice 11 deve sostituire il ponte test-only sui chunk con un chunker reale e deterministico, ma non deve ancora implementare parser DDL/XML/SQL/log, AI handoff, batch, GEXF o UI.

Note tecniche Docling verificate il 2026-06-04:
- Il progetto ha gia' `docling==2.97.0` in `pyproject.toml`; PyPI indica la release `2.97.0` pubblicata il 2026-06-03.
- La documentazione ufficiale Docling espone `HybridChunker` via `from docling.chunking import HybridChunker`.
- Il contratto `BaseChunker` prevede `chunk(dl_doc=...)` e `contextualize(chunk=...)`.
- `HybridChunker` applica refinements tokenization-aware sopra il chunking gerarchico e puo' fare merge dei peer con `merge_peers=True` di default.
- Gli esempi ufficiali usano `chunker.contextualize(chunk)` per ottenere testo arricchito di contesto.
- Docling v2 permette di ricaricare un `DoclingDocument` salvato come JSON usando `DoclingDocument.load_from_json(...)` oppure `DoclingDocument.model_validate(...)` su `export_to_dict()`.
- Riferimenti utili:
  - https://pypi.org/project/docling/
  - https://docling-project.github.io/docling/concepts/chunking/
  - https://docling-project.github.io/docling/examples/hybrid_chunking/
  - https://docling-project.github.io/docling/reference/docling_document/
  - https://docling-project.github.io/docling/v2/

Decisione di scope:
- Il valore della slice e' chunking stabile, evidence lookup e persistenza in registry.
- Non e' necessario introdurre tokenizer remoti o download runtime per superare la slice.
- Se usare `HybridChunker` richiede download o comportamento non deterministico nei test, implementa come default un fallback deterministico heading/paragraph su `normalized.md`, mantenendo l'adapter Docling isolato e documentando la scelta nel report.
- Il worker deve chiamarsi comunque `chunk_docling`, perche' lavora sugli output normalizzati Docling della Slice 10.

Scope:
- aggiungere un core piccolo e testabile per chunking, per esempio:

```text
src/dsl_mngr/core/chunking.py
```

- aggiungere un worker reale:

```text
src/dsl_mngr/workers/chunk_docling.py
```

- integrare un comando CLI nello stile `argparse` esistente:

```powershell
dsl-manager corpus chunk <workspace> --revision REV_000001
```

- mantenere compatibilita con:

```powershell
python -m dsl_mngr corpus chunk <workspace> --revision REV_000001
```

- aggiungere un profilo default di chunking nel workspace inizializzato:

```text
configs/workers/docling.chunking.yaml
```

- estendere in modo minimale il loader profili, oppure aggiungere un loader dedicato, senza rompere `docling.no_images.yaml`;
- non introdurre PyYAML;
- non aggiungere nuove dipendenze solo per il chunking;
- usare `worker_runner.run_worker` per invocare il worker e registrare `worker_runs`;
- creare run di tipo `chunk`;
- produrre output sotto:

```text
chunks/<source_id>/<source_revision_id>/chunks.jsonl
chunks/<source_id>/<source_revision_id>/chunk_report.json
```

- persistere i chunk prodotti nella tabella `chunks`;
- salvare offsets e metadati strutturali in `chunks.metadata_json`, dato che lo schema attuale non ha colonne dedicate per gli offsets.

Profilo default minimo consigliato:

```yaml
worker:
  name: chunk_docling
  version: 1.0
chunking:
  strategy: heading_paragraph
  max_chars: 8000
  min_chars: 1
  include_heading_context: true
  preserve_paragraphs: true
  merge_small_paragraphs: true
  strict_options_fail_on_unsupported_option: true
  require_normalized_hash_match: true
  output_chunks_jsonl: true
```

Se il parser YAML minimale non supporta strutture oltre un livello, mantieni questa forma flat a sezioni semplici. Non fare un refactor generale della configurazione.

Expected behavior:
- il comando verifica che workspace e database siano inizializzati e migrati;
- il comando verifica che `source_revision_id` esista;
- la revision deve appartenere a una `source` esistente;
- la revision deve avere `source_revisions.normalized_hash` valorizzato;
- se la revision non e' normalizzata, fallire con errore leggibile che invita a eseguire prima `corpus normalize`;
- il comando risolve e valida questi file dentro il workspace:
  - `normalized/<source_id>/<source_revision_id>/normalized.md`;
  - `normalized/<source_id>/<source_revision_id>/normalized.json`;
  - `normalized/<source_id>/<source_revision_id>/source_hash.txt`;
- il comando rifiuta path assoluti o path traversal;
- il comando crea una run `chunk`;
- il comando invoca `chunk_docling` via `run_worker`;
- il worker legge `normalized.md` e, se utile, `normalized.json`;
- il worker produce chunk in ordine stabile;
- al successo, il sistema scrive:
  - `chunks.jsonl`;
  - `chunk_report.json`;
- al successo, `worker_runs.status == "completed"`;
- al successo, `runs.status == "completed"`;
- al successo, i chunk sono persistiti nella tabella `chunks` con `status = "active"`;
- rieseguire il chunking della stessa revision con stesso input/config non deve creare duplicati attivi;
- rieseguire il chunking della stessa revision deve riusare gli stessi `chunk_id` per le stesse sequence quando possibile;
- i chunk attivi in eccesso per la stessa revision, se presenti, devono essere marcati `stale`;
- i path salvati in output, report e artifact devono essere relativi al workspace e usare `/`;
- i log non devono contenere contenuti lunghi del documento.

Output CLI minimo al successo:

```text
Run: RUN_000001
Revision: REV_000001
Source: SRC_000001
Chunks: 1
Chunks hash: <sha256>
Chunks JSONL: chunks/SRC_000001/REV_000001/chunks.jsonl
Report: chunks/SRC_000001/REV_000001/chunk_report.json
```

Contratto worker:
- il worker deve accettare il contratto gia' usato da `run_worker`:

```powershell
python <worker_path> --input artifacts\runs\RUN_000001\input.json --output artifacts\runs\RUN_000001\output.json
```

- il worker non deve scrivere direttamente nel database principale;
- il worker deve produrre `output.json` coerente con `run_worker`, includendo almeno:
  - `run_id`;
  - `worker_name`;
  - `worker_version`;
  - `status`;
  - `exit_code`;
  - `source_id`;
  - `source_revision_id`;
  - `normalized_hash`;
  - `normalized_markdown_path`;
  - `normalized_json_path`;
  - `chunks_jsonl_path`;
  - `chunk_report_path`;
  - `chunk_count`;
  - `chunks_hash`;
  - `profile`;
  - `strategy`;
  - `chunks`;
- `chunks` puo' contenere chunk candidate senza `chunk_id` tecnico, purche' il core applicativo assegni o riusi gli ID prima di scrivere il `chunks.jsonl` canonico finale;
- non lasciare nel `chunks.jsonl` finale ID provvisori.

Formato `chunks.jsonl` canonico:

Ogni riga deve essere JSON valido e deterministico. Esempio:

```json
{"chunk_id":"CHK_000001","source_revision_id":"REV_000001","sequence":1,"text":"# Manuale clienti\n\nCliente e' una business entity del dominio commerciale.\n\nLa cancellazione di un cliente non e' consentita se esistono ordini aperti.\n","text_hash":"<sha256>","status":"active","metadata":{"chunker":"chunk_docling","chunker_version":"1.0","strategy":"heading_paragraph","normalized_hash":"<sha256>","start_char":0,"end_char":142,"heading_path":["Manuale clienti"],"source_text_kind":"normalized_markdown"}}
```

Regole chunk:
- `sequence` parte da 1 per ogni `source_revision_id`;
- `text` deve essere non vuoto;
- `text` deve usare newline `\n`;
- `text` deve terminare con newline;
- `text_hash` e' SHA-256 del `text` UTF-8;
- `chunks_hash` e' SHA-256 del contenuto canonico di `chunks.jsonl`;
- `metadata_json` nel database deve essere JSON canonico, con chiavi ordinate;
- `metadata_json` deve includere almeno:
  - `chunker`;
  - `chunker_version`;
  - `strategy`;
  - `normalized_hash`;
  - `normalized_markdown_path`;
  - `normalized_json_path`;
  - `start_char`;
  - `end_char`;
  - `heading_path`;
  - `source_text_kind`;
- offsets `start_char` e `end_char` sono offset sul `normalized.md` normalizzato con newline `\n`;
- per fallback heading/paragraph, gli offsets devono essere coerenti con il testo sorgente normalizzato;
- se usi `HybridChunker` e gli offsets non sono ricostruibili in modo affidabile, salva `start_char`/`end_char` come `null` solo per quella strategia e documenta il motivo nel report;
- il default della slice deve comunque coprire offsets deterministici.

Strategia fallback heading/paragraph:
- operare su `normalized.md`;
- separare blocchi su heading Markdown e paragrafi;
- mantenere headings nel chunk quando `include_heading_context = true`;
- fondere paragrafi finche' il chunk resta entro `max_chars`;
- non spezzare parole se non inevitabile;
- se un singolo paragrafo supera `max_chars`, spezzarlo in modo deterministico su newline, frase o spazio;
- produrre almeno un chunk per documento non vuoto;
- per i fixture piccoli `manuale_clienti.md` e `manuale_ordini.md`, il comportamento atteso e' un chunk per documento con `max_chars` default, cosi' i candidati fixture possono continuare a usare `CHK_000001` e `CHK_000002`.

Persistenza DB:
- usare la tabella `chunks` gia' esistente;
- non modificare migrazioni gia' applicate solo per aggiungere colonne agli offsets;
- se serve una modifica schema, aggiungere una nuova migration append-only e motivarla nel report;
- per questa slice dovrebbe bastare lo schema attuale;
- inserire o aggiornare i campi:
  - `chunk_id`;
  - `source_revision_id`;
  - `sequence`;
  - `text`;
  - `text_hash`;
  - `metadata_json`;
  - `status`;
  - `created_at`;
- non cancellare chunk storici;
- per idempotenza:
  - se esiste gia' un chunk per stessa revision e stessa sequence, riusa il suo `chunk_id`;
  - aggiorna testo/metadati se sono cambiati;
  - marca `active` i chunk prodotti dalla run corrente;
  - marca `stale` eventuali chunk attivi della stessa revision con sequence non piu' prodotta;
  - non creare una nuova serie di chunk attivi identica a ogni rerun.

Evidence lookup:
- `candidate_validation.validate_candidate_payload` verifica che `evidence_text` sia contenuto in `chunks.text`;
- i chunk prodotti devono quindi contenere il testo necessario alle fixture candidate;
- aggiungi un test che dimostri che i candidati fixture possono essere validati usando chunk creati dal chunker di produzione, senza helper test-only di seeding chunk;
- se aggiorni il golden pipeline Slice 9 per usare il chunker reale, fallo senza introdurre chiamate Docling pesanti o rete nei test;
- se lasci il test Slice 9 invariato per evitare lentezza/flakiness, aggiungi un nuovo test Slice 11 equivalente che copra init, scan, normalized fixture, chunk, validate.

Gestione errori:
- se `source_revision_id` non esiste, errore leggibile;
- se la revision non ha `normalized_hash`, errore leggibile;
- se `normalized.md` o `normalized.json` mancano, errore leggibile;
- se `source_hash.txt` non coincide con `source_revisions.content_hash`, fallire;
- se `normalized.md` non ha hash coerente con `source_revisions.normalized_hash`, fallire;
- se il profilo contiene un'opzione non supportata e `strict_options_fail_on_unsupported_option` e' true:
  - il worker deve fallire con exit code `4`;
  - `worker_runs.exit_code` deve essere `4`;
  - `worker_runs.status` deve essere `failed`;
  - `runs.status` deve essere `failed`;
  - `process_report.json` o `log.jsonl` devono includere `unsupported_chunking_option` e la chiave problematica;
  - non devono essere creati chunk attivi nel database;
  - non deve partire alcun import candidati, merge o render;
- il comando CLI puo' restituire `2`, seguendo la convenzione locale degli errori leggibili.

Artifact:
- `artifacts/runs/<run_id>/input.json` deve includere almeno:
  - `source_id`;
  - `source_revision_id`;
  - `normalized_hash`;
  - `normalized_markdown_path`;
  - `normalized_json_path`;
  - `source_hash_path`;
  - `output_dir`;
  - `profile`;
  - `chunking_options`;
- `artifacts/runs/<run_id>/output.json` deve includere almeno il payload del worker/core;
- `artifacts/runs/<run_id>/process_report.json` deve avere:
  - `run_type = "chunk"`;
  - `status = "completed"` al successo;
  - una voce worker `chunk_docling`;
  - `artifact_dir` relativo;
  - `config_hash`;
- `resolved_config.yaml`, `config_hash.txt` e `log.jsonl` devono restare coerenti con Slice 4.

Test minimi richiesti:
- `test_chunking_stable`;
- `test_chunk_evidence_lookup`.

I test devono verificare almeno:
- un workspace temporaneo viene inizializzato con `tmp_path`;
- il database viene inizializzato/migrato;
- `configs/workers/docling.chunking.yaml` esiste o il profilo default e' disponibile in modo equivalente;
- vengono registrate almeno le fixture `manuale_clienti.md` e `manuale_ordini.md` tramite `corpus scan`;
- per mantenere i test veloci, puoi preparare `normalized.md`, `normalized.json`, `source_hash.txt` e `source_revisions.normalized_hash` in fixture/helper deterministico, senza chiamare Docling reale in ogni test Slice 11;
- `corpus chunk <workspace> --revision REV_000001` completa con exit code 0;
- `corpus chunk <workspace> --revision REV_000002` completa con exit code 0;
- `chunks/SRC_000001/REV_000001/chunks.jsonl` e `chunk_report.json` vengono creati;
- `chunks/SRC_000002/REV_000002/chunks.jsonl` e `chunk_report.json` vengono creati;
- i chunk hanno `CHK_000001` e `CHK_000002` in ordine stabile quando il database parte vuoto;
- ogni `text_hash` coincide con SHA-256 del `text`;
- `chunks_hash` resta stabile su rerun con stesso input/config;
- rerun della stessa revision non crea duplicati attivi;
- `runs` contiene run `chunk` completate;
- `worker_runs` contiene worker `chunk_docling` completati;
- `process_report.json` contiene path relativi e nessun `\`;
- il comando funziona anche via `python -m dsl_mngr`;
- il test evidence lookup copia `tests/fixtures/ai_candidates/AIPKG_MANUALI_001_candidates.jsonl` in `ai/inbox`;
- `candidates validate` accetta tutti i record perche' `evidence_text` e' trovato nei chunk creati dal chunker reale;
- il caso unsupported option fallisce con worker exit code `4`, se lo implementi come test aggiuntivo;
- nessuna regressione sulle slice 1-10.

Fixture consigliata:
- usare Markdown piccolo e locale;
- non usare rete nei test;
- non usare AI reale;
- non dipendere da OCR;
- non scaricare tokenizer o modelli;
- evitare assert fragili sull'intero JSON Docling;
- verificare invece hash, path, conteggi, contenuto essenziale e evidence lookup.

Constraints:
- non implementare parser DDL;
- non implementare parser XML form;
- non implementare parser SQL code o log;
- non implementare AI package handoff;
- non implementare batch orchestration;
- non implementare export GEXF;
- non implementare UI, web/API/auth o integrazioni esterne;
- non aggiungere ORM;
- non modificare il contratto pubblico di `candidates validate`, `facts merge`, `dsl render` o `dsl diff`;
- non salvare path assoluti negli artifact o nel database;
- non generare immagini;
- non fare chiamate di rete durante chunking o test;
- non usare import da `src`;
- usare import assoluti da `dsl_mngr`;
- mantenere separati CLI, worker, core chunking, persistence e test;
- mantenere l'implementazione piccola, leggibile e deterministica;
- i test devono usare `tmp_path`.

Done when:
- Slice 11 e' implementata end-to-end nello scope richiesto;
- `corpus chunk` produce chunk stabili da output normalizzati;
- `chunks.jsonl` e `chunk_report.json` vengono prodotti;
- la tabella `chunks` viene popolata in modo idempotente;
- evidence lookup funziona con `candidates validate`;
- i test nuovi sono significativi;
- tutta la suite passa;
- non e' stata aggiunta alcuna feature fuori scope.

Prima di codificare:
1. dichiara brevemente quali file prevedi di toccare;
2. installa il progetto in editable mode con l'interprete corretto per l'ambiente, seguendo `AGENTS.md`;
3. implementa la slice;
4. esegui tutta la suite con l'interprete corretto;
5. mostra diff e risultato dei test, indicando l'interprete usato;
6. esegui una breve autoverifica finale contro scope, constraints e done criteria.

Report finale:

```text
salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_11/dsl_manager_slice_11_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.
```
